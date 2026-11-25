# 2026-11-26 - voda-voca - 관리자 계정 통합 테스트: 시작 때 계정 준비, 닉네임 예약, 탈퇴 차단, 관리 권한 검사 (REQ-159)
# 파일 위치: src/backend/tests/test_admin_account_api.py

import asyncio
from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio
from fastapi import Depends, FastAPI
from sqlalchemy import delete, func, select

from backend.core.admin import ADMIN_INITIAL_PASSWORD, ADMIN_NICKNAME
from backend.core.deps import SESSION_COOKIE_NAME, get_admin_user
from backend.db.session import get_session_factory
from backend.main import app
from backend.models import SystemVocabulary, User
from backend.services.admin import ensure_admin_account
from backend.tests.helpers import auth_headers, login_payload, signup_and_login, signup_payload


@pytest_asyncio.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _delete_admin() -> None:
    async with get_session_factory()() as db:
        await db.execute(delete(User).where(User.nickname == ADMIN_NICKNAME))
        await db.commit()


@pytest_asyncio.fixture(autouse=True)
async def _no_admin_account() -> AsyncIterator[None]:
    """공통 정리는 tvoda-% 계정만 지우므로 admin 계정은 여기서 지운다."""
    await _delete_admin()
    yield
    await _delete_admin()


async def ensure() -> None:
    async with get_session_factory()() as db:
        await ensure_admin_account(db)


async def admin_count() -> int:
    async with get_session_factory()() as db:
        return await db.scalar(select(func.count()).select_from(User).where(User.nickname == ADMIN_NICKNAME))


async def login(client: httpx.AsyncClient, nickname: str, password: str) -> httpx.Response:
    response = await client.post("/api/auth/login", json=login_payload(nickname, password))
    client.cookies.clear()
    return response


async def admin_token(client: httpx.AsyncClient) -> str:
    await ensure()
    response = await login(client, ADMIN_NICKNAME, ADMIN_INITIAL_PASSWORD)
    assert response.status_code == 200, response.text
    return response.cookies[SESSION_COOKIE_NAME]


def test_admin_id_and_initial_password_are_fixed() -> None:
    assert (ADMIN_NICKNAME, ADMIN_INITIAL_PASSWORD) == ("admin", "admin1234")


@pytest.mark.asyncio
async def test_ensure_creates_the_admin_who_can_log_in(client: httpx.AsyncClient) -> None:
    await ensure()

    response = await login(client, "admin", "admin1234")

    assert response.status_code == 200, response.text
    assert response.json()["is_admin"] is True
    async with get_session_factory()() as db:
        slug = await db.scalar(
            select(SystemVocabulary.slug)
            .join(User, User.active_vocabulary_id == SystemVocabulary.id)
            .where(User.nickname == ADMIN_NICKNAME)
        )
    assert slug == "beginner-200"


@pytest.mark.asyncio
async def test_ensure_never_resets_an_existing_admin() -> None:
    await ensure()
    async with get_session_factory()() as db:
        user = (await db.execute(select(User).where(User.nickname == ADMIN_NICKNAME))).scalar_one()
        user.password_hash = "changed-by-owner"
        await db.commit()

    await ensure()

    async with get_session_factory()() as db:
        hashes = list((await db.execute(select(User.password_hash).where(User.nickname == ADMIN_NICKNAME))).scalars())
    assert hashes == ["changed-by-owner"]


@pytest.mark.asyncio
async def test_concurrent_ensure_creates_one_account() -> None:
    await asyncio.gather(ensure(), ensure(), ensure())

    assert await admin_count() == 1


@pytest.mark.asyncio
async def test_app_startup_prepares_the_admin(client: httpx.AsyncClient) -> None:
    async with app.router.lifespan_context(app):
        assert await admin_count() == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("nickname", ["admin", "ADMIN", "  Admin  "])
async def test_admin_nickname_is_reserved_even_without_the_account(client: httpx.AsyncClient, nickname: str) -> None:
    signup = await client.post("/api/auth/signup", json=signup_payload(nickname))
    check = await client.get("/api/auth/check-nickname", params={"nickname": nickname})

    assert signup.status_code == 409, signup.text
    assert signup.headers["X-Error-Code"] == "NICKNAME_TAKEN"
    assert check.json() == {"available": False}
    assert await admin_count() == 0


@pytest.mark.asyncio
async def test_a_normal_user_is_not_admin(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)

    me = await client.get("/api/auth/me", headers=auth_headers(token))

    assert me.json()["is_admin"] is False


@pytest.mark.asyncio
async def test_admin_cannot_delete_the_account(client: httpx.AsyncClient) -> None:
    token = await admin_token(client)

    response = await client.delete("/api/auth/me", headers=auth_headers(token))

    assert response.status_code == 403
    assert response.json() == {"detail": "관리자 계정은 탈퇴할 수 없습니다."}
    assert await admin_count() == 1
    assert (await client.get("/api/auth/me", headers=auth_headers(token))).status_code == 200


@pytest.mark.asyncio
async def test_admin_dependency_allows_only_the_admin(client: httpx.AsyncClient) -> None:
    probe = FastAPI()

    @probe.get("/probe")
    async def _probe(user: User = Depends(get_admin_user)) -> dict[str, str]:
        return {"nickname": user.nickname}

    token = await admin_token(client)
    _, normal = await signup_and_login(client)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=probe), base_url="http://test") as c:
        anonymous = await c.get("/probe")
        forbidden = await c.get("/probe", headers=auth_headers(normal))
        allowed = await c.get("/probe", headers=auth_headers(token))

    assert anonymous.status_code == 401
    assert (forbidden.status_code, forbidden.json()) == (403, {"detail": "관리자만 사용할 수 있습니다."})
    assert allowed.json() == {"nickname": "admin"}
