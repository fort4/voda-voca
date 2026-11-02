# 2026-11-02 - voda-voca - 인증 API 통합 테스트 (실제 MySQL): 가입, 로그인 쿠키, /me, 만료 세션, 로그아웃
# 파일 위치: src/backend/tests/test_auth_api.py

import uuid
from collections.abc import AsyncIterator
from datetime import timedelta

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import select

from backend.core.config import get_settings
from backend.core.deps import SESSION_COOKIE_NAME
from backend.db.session import get_session_factory
from backend.main import app
from backend.models import AuthSession, User
from backend.models.base import utcnow
from backend.services.session import new_token, token_digest

PASSWORD = "correct-horse-1"
TTL_SECONDS = 14 * 24 * 60 * 60


@pytest_asyncio.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def unique_email() -> str:
    return f"tvoda-{uuid.uuid4().hex[:12]}@example.com"


def cookie_flags(set_cookie: str) -> set[str]:
    """Set-Cookie 헤더에서 속성 이름(소문자)만 뽑는다. 토큰 값과 혼동하지 않도록 '=' 앞부분만 본다."""
    parts = [p.strip() for p in set_cookie.split(";")]
    return {p.split("=")[0].lower() for p in parts[1:]}


async def signup(client: httpx.AsyncClient, email: str | None = None) -> str:
    email = email or unique_email()
    response = await client.post(
        "/api/auth/signup",
        json={"email": email, "password": PASSWORD, "nickname": "학습자"},
    )
    assert response.status_code == 201, response.text
    return email


async def login(client: httpx.AsyncClient, email: str) -> str:
    response = await client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    token = response.cookies[SESSION_COOKIE_NAME]
    # httpx 쿠키 jar 가 응답 쿠키를 자동으로 보내지 않도록 비운다. 테스트마다 쿠키를 명시한다.
    client.cookies.clear()
    return token


async def user_id_of(email: str) -> int:
    async with get_session_factory()() as session:
        user = (await session.execute(select(User).where(User.email == email))).scalar_one()
        return user.id


# --- 가입 (REQ-001) ---


@pytest.mark.asyncio
async def test_signup_creates_user_without_exposing_password_hash(client: httpx.AsyncClient) -> None:
    email = unique_email()
    response = await client.post(
        "/api/auth/signup",
        json={"email": email, "password": PASSWORD, "nickname": "  학습자  "},
    )
    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"id", "email", "nickname", "created_at"}
    assert body["email"] == email
    assert body["nickname"] == "학습자"
    assert body["created_at"].endswith("Z")

    async with get_session_factory()() as session:
        user = (await session.execute(select(User).where(User.email == email))).scalar_one()
    assert user.password_hash.startswith("$2b$")
    assert PASSWORD not in user.password_hash


@pytest.mark.asyncio
async def test_signup_duplicate_email_is_case_insensitive_409(client: httpx.AsyncClient) -> None:
    email = await signup(client, unique_email())
    response = await client.post(
        "/api/auth/signup",
        json={"email": email.upper(), "password": PASSWORD, "nickname": "다른사람"},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "이미 사용 중인 이메일입니다."


@pytest.mark.asyncio
async def test_signup_rejects_short_password_with_422(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/auth/signup",
        json={"email": unique_email(), "password": "1234567", "nickname": "학습자"},
    )
    assert response.status_code == 422


# --- 로그인과 세션 쿠키 (REQ-002) ---


@pytest.mark.asyncio
async def test_login_sets_httponly_samesite_cookie(client: httpx.AsyncClient) -> None:
    email = await signup(client)
    response = await client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200
    set_cookie = response.headers["set-cookie"]
    assert set_cookie.startswith(f"{SESSION_COOKIE_NAME}=")
    flags = cookie_flags(set_cookie)
    assert {"httponly", "samesite", "path", "max-age"} <= flags
    assert "secure" not in flags  # 기본값 COOKIE_SECURE=false
    assert f"Max-Age={TTL_SECONDS}" in set_cookie
    assert "SameSite=lax" in set_cookie
    assert "Path=/" in set_cookie


@pytest.mark.asyncio
async def test_login_stores_only_token_digest(client: httpx.AsyncClient) -> None:
    email = await signup(client)
    token = await login(client, email)
    async with get_session_factory()() as session:
        rows = (
            await session.execute(select(AuthSession).where(AuthSession.id == token_digest(token)))
        ).scalars().all()
    assert len(rows) == 1
    assert rows[0].user_id == await user_id_of(email)
    assert rows[0].expires_at > utcnow()


@pytest.mark.asyncio
async def test_each_login_issues_a_new_token(client: httpx.AsyncClient) -> None:
    email = await signup(client)
    assert await login(client, email) != await login(client, email)


@pytest.mark.asyncio
async def test_wrong_password_and_unknown_email_return_same_401(client: httpx.AsyncClient) -> None:
    email = await signup(client)
    wrong_pw = await client.post("/api/auth/login", json={"email": email, "password": "wrong-pass-9"})
    unknown = await client.post(
        "/api/auth/login", json={"email": unique_email(), "password": PASSWORD}
    )
    assert wrong_pw.status_code == unknown.status_code == 401
    assert wrong_pw.json() == unknown.json()
    assert SESSION_COOKIE_NAME not in wrong_pw.cookies
    assert SESSION_COOKIE_NAME not in unknown.cookies


@pytest.mark.asyncio
async def test_login_with_malformed_email_is_401_not_422(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/auth/login", json={"email": "not-an-email", "password": PASSWORD})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_cookie_secure_flag_follows_cookie_secure_setting(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    email = await signup(client)
    monkeypatch.setenv("COOKIE_SECURE", "true")
    get_settings.cache_clear()
    response = await client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert "secure" in cookie_flags(response.headers["set-cookie"])


# --- 현재 사용자 (/me) 및 인증 (REQ-002, REQ-003) ---


@pytest.mark.asyncio
async def test_me_without_cookie_is_401(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_with_valid_cookie_returns_current_user(client: httpx.AsyncClient) -> None:
    email = await signup(client)
    token = await login(client, email)
    response = await client.get("/api/auth/me", headers={"Cookie": f"{SESSION_COOKIE_NAME}={token}"})
    assert response.status_code == 200
    assert response.json()["email"] == email


@pytest.mark.asyncio
async def test_me_with_unknown_token_is_401(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/auth/me", headers={"Cookie": f"{SESSION_COOKIE_NAME}={new_token()}"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_each_session_sees_only_its_own_user(client: httpx.AsyncClient) -> None:
    email_a = await signup(client)
    email_b = await signup(client)
    token_a = await login(client, email_a)
    token_b = await login(client, email_b)
    me_a = await client.get("/api/auth/me", headers={"Cookie": f"{SESSION_COOKIE_NAME}={token_a}"})
    me_b = await client.get("/api/auth/me", headers={"Cookie": f"{SESSION_COOKIE_NAME}={token_b}"})
    assert me_a.json()["email"] == email_a
    assert me_b.json()["email"] == email_b


@pytest.mark.asyncio
async def test_expired_session_is_rejected(client: httpx.AsyncClient) -> None:
    email = await signup(client)
    token = new_token()
    async with get_session_factory()() as session:
        session.add(
            AuthSession(
                id=token_digest(token),
                user_id=await user_id_of(email),
                expires_at=utcnow() - timedelta(seconds=1),
            )
        )
        await session.commit()

    response = await client.get("/api/auth/me", headers={"Cookie": f"{SESSION_COOKIE_NAME}={token}"})
    assert response.status_code == 401


# --- 로그아웃 (REQ-002) ---


@pytest.mark.asyncio
async def test_logout_invalidates_session_immediately(client: httpx.AsyncClient) -> None:
    email = await signup(client)
    token = await login(client, email)

    logout = await client.post("/api/auth/logout", headers={"Cookie": f"{SESSION_COOKIE_NAME}={token}"})
    assert logout.status_code == 204
    assert f"{SESSION_COOKIE_NAME}=" in logout.headers["set-cookie"]
    assert "Max-Age=0" in logout.headers["set-cookie"]

    after = await client.get("/api/auth/me", headers={"Cookie": f"{SESSION_COOKIE_NAME}={token}"})
    assert after.status_code == 401

    async with get_session_factory()() as session:
        rows = (
            await session.execute(select(AuthSession).where(AuthSession.id == token_digest(token)))
        ).scalars().all()
    assert rows == []


@pytest.mark.asyncio
async def test_logout_without_cookie_is_204(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/auth/logout")
    assert response.status_code == 204
