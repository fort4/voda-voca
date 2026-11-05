# 2026-11-02 - voda-voca - 인증 API 통합 테스트 (실제 MySQL): 닉네임 가입, 로그인 쿠키, /me, 로그아웃, 회원 탈퇴 연쇄 삭제
# 파일 위치: src/backend/tests/test_auth_api.py

from collections.abc import AsyncIterator
from datetime import timedelta

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import delete, func, select

from backend.core.config import get_settings
from backend.core.deps import SESSION_COOKIE_NAME
from backend.db.session import get_session_factory
from backend.main import app
from backend.models import AuthSession, Bookmark, QuizSession, StudyLog, SystemVocabulary, SystemWord, User
from backend.services import auth as auth_service
from backend.models.base import utcnow
from backend.models.quiz_session import QUIZ_SOURCE_BOOKMARKS
from backend.services.session import new_token, token_digest
from backend.tests.helpers import PASSWORD, auth_headers, signup_and_login, unique_nickname

TTL_SECONDS = 14 * 24 * 60 * 60


@pytest_asyncio.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def cookie_flags(set_cookie: str) -> set[str]:
    """Set-Cookie 헤더에서 속성 이름(소문자)만 뽑는다. 토큰 값과 혼동하지 않도록 '=' 앞부분만 본다."""
    parts = [p.strip() for p in set_cookie.split(";")]
    return {p.split("=")[0].lower() for p in parts[1:]}


async def signup(client: httpx.AsyncClient, nickname: str | None = None) -> str:
    nickname = nickname or unique_nickname()
    response = await client.post("/api/auth/signup", json={"nickname": nickname, "password": PASSWORD})
    assert response.status_code == 201, response.text
    return nickname


async def login(client: httpx.AsyncClient, nickname: str) -> str:
    response = await client.post("/api/auth/login", json={"nickname": nickname, "password": PASSWORD})
    assert response.status_code == 200, response.text
    token = response.cookies[SESSION_COOKIE_NAME]
    # httpx 쿠키 jar 가 응답 쿠키를 자동으로 보내지 않도록 비운다. 테스트마다 쿠키를 명시한다.
    client.cookies.clear()
    return token


async def user_id_of(nickname: str) -> int:
    async with get_session_factory()() as session:
        user = (await session.execute(select(User).where(User.nickname == nickname))).scalar_one()
        return user.id


async def count_rows(model, *where) -> int:
    async with get_session_factory()() as session:
        return (await session.execute(select(func.count()).select_from(model).where(*where))).scalar_one()


# --- 가입 (REQ-001, 회원 체계 단순화) ---


@pytest.mark.asyncio
async def test_signup_takes_only_nickname_and_password(client: httpx.AsyncClient) -> None:
    nickname = unique_nickname()
    response = await client.post(
        "/api/auth/signup", json={"nickname": f"  {nickname}  ", "password": PASSWORD}
    )
    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"id", "nickname", "created_at"}, "이메일 필드가 응답에 없어야 한다"
    assert body["nickname"] == nickname
    assert body["created_at"].endswith("Z")

    async with get_session_factory()() as session:
        user = (await session.execute(select(User).where(User.nickname == nickname))).scalar_one()
    assert user.password_hash.startswith("$2b$")
    assert PASSWORD not in user.password_hash


@pytest.mark.asyncio
async def test_signup_ignores_legacy_email_field(client: httpx.AsyncClient) -> None:
    """이메일은 더 이상 받지 않는다. 보내도 무시되고 계정은 닉네임으로만 식별된다."""
    nickname = unique_nickname()
    response = await client.post(
        "/api/auth/signup",
        json={"nickname": nickname, "password": PASSWORD, "email": "legacy@example.com"},
    )
    assert response.status_code == 201
    assert "email" not in response.json()


@pytest.mark.asyncio
async def test_duplicate_nickname_is_409_regardless_of_case(client: httpx.AsyncClient) -> None:
    nickname = await signup(client, unique_nickname())
    response = await client.post(
        "/api/auth/signup", json={"nickname": nickname.upper(), "password": PASSWORD}
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "이미 사용 중인 닉네임입니다."


@pytest.mark.asyncio
async def test_signup_rejects_short_password_with_422(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/auth/signup", json={"nickname": unique_nickname(), "password": "1234567"}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_signup_rejects_one_character_nickname_with_422(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/auth/signup", json={"nickname": "가", "password": PASSWORD})
    assert response.status_code == 422


# --- 로그인과 세션 쿠키 (REQ-002) ---


@pytest.mark.asyncio
async def test_login_sets_httponly_samesite_cookie(client: httpx.AsyncClient) -> None:
    nickname = await signup(client)
    response = await client.post("/api/auth/login", json={"nickname": nickname, "password": PASSWORD})
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
    nickname = await signup(client)
    token = await login(client, nickname)
    async with get_session_factory()() as session:
        rows = (
            await session.execute(select(AuthSession).where(AuthSession.id == token_digest(token)))
        ).scalars().all()
    assert len(rows) == 1
    assert rows[0].user_id == await user_id_of(nickname)
    assert rows[0].expires_at > utcnow()


@pytest.mark.asyncio
async def test_login_nickname_is_case_insensitive(client: httpx.AsyncClient) -> None:
    nickname = await signup(client)
    response = await client.post(
        "/api/auth/login", json={"nickname": f"  {nickname.upper()} ", "password": PASSWORD}
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_each_login_issues_a_new_token(client: httpx.AsyncClient) -> None:
    nickname = await signup(client)
    assert await login(client, nickname) != await login(client, nickname)


@pytest.mark.asyncio
async def test_wrong_password_and_unknown_nickname_return_same_401(client: httpx.AsyncClient) -> None:
    nickname = await signup(client)
    wrong_pw = await client.post("/api/auth/login", json={"nickname": nickname, "password": "wrong-pass-9"})
    unknown = await client.post(
        "/api/auth/login", json={"nickname": unique_nickname(), "password": PASSWORD}
    )
    assert wrong_pw.status_code == unknown.status_code == 401
    assert wrong_pw.json() == unknown.json()
    assert wrong_pw.json()["detail"] == "닉네임 또는 비밀번호가 올바르지 않습니다.", "이메일 문구가 남아 있으면 안 된다"
    assert SESSION_COOKIE_NAME not in wrong_pw.cookies
    assert SESSION_COOKIE_NAME not in unknown.cookies


@pytest.mark.asyncio
async def test_login_with_long_unknown_nickname_is_401_not_422(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/auth/login", json={"nickname": "가" * 150, "password": PASSWORD})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_cookie_secure_flag_follows_cookie_secure_setting(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    nickname = await signup(client)
    monkeypatch.setenv("COOKIE_SECURE", "true")
    get_settings.cache_clear()
    response = await client.post("/api/auth/login", json={"nickname": nickname, "password": PASSWORD})
    assert "secure" in cookie_flags(response.headers["set-cookie"])


# --- 현재 사용자 (/me) 및 인증 (REQ-002, REQ-003) ---


@pytest.mark.asyncio
async def test_me_without_cookie_is_401(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_with_valid_cookie_returns_current_user(client: httpx.AsyncClient) -> None:
    nickname = await signup(client)
    token = await login(client, nickname)
    response = await client.get("/api/auth/me", headers=auth_headers(token))
    assert response.status_code == 200
    assert response.json()["nickname"] == nickname


@pytest.mark.asyncio
async def test_me_with_unknown_token_is_401(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/auth/me", headers=auth_headers(new_token()))
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_each_session_sees_only_its_own_user(client: httpx.AsyncClient) -> None:
    nick_a = await signup(client)
    nick_b = await signup(client)
    token_a = await login(client, nick_a)
    token_b = await login(client, nick_b)
    me_a = await client.get("/api/auth/me", headers=auth_headers(token_a))
    me_b = await client.get("/api/auth/me", headers=auth_headers(token_b))
    assert me_a.json()["nickname"] == nick_a
    assert me_b.json()["nickname"] == nick_b


@pytest.mark.asyncio
async def test_expired_session_is_rejected(client: httpx.AsyncClient) -> None:
    nickname = await signup(client)
    token = new_token()
    async with get_session_factory()() as session:
        session.add(
            AuthSession(
                id=token_digest(token),
                user_id=await user_id_of(nickname),
                expires_at=utcnow() - timedelta(seconds=1),
            )
        )
        await session.commit()

    response = await client.get("/api/auth/me", headers=auth_headers(token))
    assert response.status_code == 401


# --- 로그아웃 (REQ-002) ---


@pytest.mark.asyncio
async def test_logout_invalidates_session_immediately(client: httpx.AsyncClient) -> None:
    nickname = await signup(client)
    token = await login(client, nickname)

    logout = await client.post("/api/auth/logout", headers=auth_headers(token))
    assert logout.status_code == 204
    assert f"{SESSION_COOKIE_NAME}=" in logout.headers["set-cookie"]
    assert "Max-Age=0" in logout.headers["set-cookie"]

    after = await client.get("/api/auth/me", headers=auth_headers(token))
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


# --- 회원 탈퇴 (DELETE /api/auth/me, 회원 체계 단순화) ---


@pytest.mark.asyncio
async def test_delete_me_without_login_is_401_and_deletes_nothing(client: httpx.AsyncClient) -> None:
    nickname = await signup(client)
    before = await count_rows(User, User.nickname == nickname)

    response = await client.delete("/api/auth/me")
    assert response.status_code == 401
    assert await count_rows(User, User.nickname == nickname) == before == 1


@pytest.mark.asyncio
async def test_delete_me_with_invalid_or_expired_cookie_is_401(client: httpx.AsyncClient) -> None:
    nickname = await signup(client)
    assert (await client.delete("/api/auth/me", headers=auth_headers(new_token()))).status_code == 401
    expired = new_token()
    async with get_session_factory()() as session:
        session.add(
            AuthSession(id=token_digest(expired), user_id=await user_id_of(nickname), expires_at=utcnow() - timedelta(seconds=1))
        )
        await session.commit()
    assert (await client.delete("/api/auth/me", headers=auth_headers(expired))).status_code == 401
    assert await count_rows(User, User.nickname == nickname) == 1


@pytest.mark.asyncio
async def test_delete_me_removes_account_and_personal_rows_but_keeps_shared_content(client: httpx.AsyncClient) -> None:
    """탈퇴하면 계정, 세션, 북마크, 학습 이력, 퀴즈 세션이 사라진다 (CASCADE). 표준 단어장·단어는 공용이라 남는다."""
    nickname, token = await signup_and_login(client)
    user_id = await user_id_of(nickname)

    async with get_session_factory()() as session:
        vocabulary = SystemVocabulary(slug="tvoda-delete-me", title="탈퇴 테스트", category="ELEMENTARY", level=1)
        session.add(vocabulary)
        await session.flush()
        word = SystemWord(vocabulary_id=vocabulary.id, term="apple", meaning="사과")
        session.add(word)
        await session.flush()
        word_id = word.id
        session.add(Bookmark(user_id=user_id, word_id=word_id))
        session.add(StudyLog(user_id=user_id, word_id=word_id, is_correct=True))
        session.add(
            QuizSession(
                user_id=user_id,
                vocabulary_id=None,
                source=QUIZ_SOURCE_BOOKMARKS,
                questions=[],
                is_submitted=False,
                expires_at=utcnow() + timedelta(minutes=30),
            )
        )
        await session.commit()
    assert await count_rows(StudyLog, StudyLog.user_id == user_id) == 1

    try:
        response = await client.delete("/api/auth/me", headers=auth_headers(token))
        assert response.status_code == 204
        assert response.content == b""
        set_cookie = response.headers["set-cookie"]
        assert set_cookie.startswith(f"{SESSION_COOKIE_NAME}=")
        assert "Max-Age=0" in set_cookie

        assert await count_rows(User, User.id == user_id) == 0
        assert await count_rows(AuthSession, AuthSession.user_id == user_id) == 0
        assert await count_rows(Bookmark, Bookmark.user_id == user_id) == 0
        assert await count_rows(StudyLog, StudyLog.user_id == user_id) == 0
        assert await count_rows(QuizSession, QuizSession.user_id == user_id) == 0
        assert await count_rows(SystemWord, SystemWord.id == word_id) == 1, "공용 단어는 탈퇴로 지워지지 않는다"
    finally:
        async with get_session_factory()() as session:
            await session.execute(delete(SystemVocabulary).where(SystemVocabulary.slug == "tvoda-delete-me"))
            await session.commit()


# --- 가입 시 활성 단어장 자동 지정 (개인 단어장은 더 이상 만들지 않는다) ---


async def active_vocabulary_slug(user_id: int) -> str | None:
    async with get_session_factory()() as session:
        row = (
            await session.execute(
                select(SystemVocabulary.slug)
                .join(User, User.active_vocabulary_id == SystemVocabulary.id)
                .where(User.id == user_id)
            )
        ).scalar_one_or_none()
        return row


@pytest.mark.asyncio
async def test_signup_activates_the_beginner_vocabulary(client: httpx.AsyncClient) -> None:
    nickname, _ = await signup_and_login(client)
    assert await active_vocabulary_slug(await user_id_of(nickname)) == "beginner-200"
    assert auth_service.DEFAULT_VOCABULARY_SLUG == "beginner-200"


@pytest.mark.asyncio
async def test_signup_still_works_when_the_default_vocabulary_is_missing(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """시드가 아직 없어도 가입은 막지 않는다. 활성 단어장은 비워 두고 나중에 지정한다."""
    monkeypatch.setattr(auth_service, "DEFAULT_VOCABULARY_SLUG", "tvoda-no-such-slug")
    nickname, _ = await signup_and_login(client)
    assert await active_vocabulary_slug(await user_id_of(nickname)) is None


@pytest.mark.asyncio
async def test_duplicate_nickname_signup_changes_nothing(client: httpx.AsyncClient) -> None:
    """닉네임 중복으로 실패한 가입은 계정을 하나만 남기고 기존 계정의 활성 단어장도 바꾸지 않는다."""
    nickname, _ = await signup_and_login(client)
    user_id = await user_id_of(nickname)
    response = await client.post("/api/auth/signup", json={"nickname": nickname, "password": PASSWORD})
    assert response.status_code == 409
    assert await count_rows(User, User.nickname == nickname) == 1
    assert await active_vocabulary_slug(user_id) == "beginner-200"
