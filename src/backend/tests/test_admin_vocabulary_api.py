# 2026-11-26 - voda-voca - 관리자 단어장 통합 테스트: 생성·수정·삭제, 권한, 표준 단어장 보호, 삭제 시 연쇄 정리 (REQ-160)
# 파일 위치: src/backend/tests/test_admin_vocabulary_api.py

from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import func, select

from backend.db.session import get_session_factory
from backend.main import app
from backend.models import QuizSession, StudyLog, SystemVocabulary, SystemWord, User
from backend.tests.helpers import (
    admin_token,
    auth_headers,
    delete_admin_content,
    signup_and_login,
    user_id_for_token,
)

URL = "/api/admin/vocabularies"


@pytest_asyncio.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture(autouse=True)
async def _clean_admin() -> AsyncIterator[None]:
    await delete_admin_content()
    yield
    await delete_admin_content()


def payload(**overrides) -> dict:
    return {"title": "우리 반 단어", "description": "수업용", "category": "ETC", "level": 2} | overrides


async def create(client: httpx.AsyncClient, token: str, **overrides) -> dict:
    response = await client.post(URL, json=payload(**overrides), headers=auth_headers(token))
    assert response.status_code == 201, response.text
    return response.json()


async def add_word(client: httpx.AsyncClient, token: str, vocabulary_id: int, term: str) -> dict:
    response = await client.post(
        f"{URL}/{vocabulary_id}/words", json={"term": term, "meaning": f"{term}의 뜻"}, headers=auth_headers(token)
    )
    assert response.status_code == 201, response.text
    return response.json()


async def count(model, *conditions) -> int:
    async with get_session_factory()() as db:
        return await db.scalar(select(func.count()).select_from(model).where(*conditions))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "url", "body"),
    [
        ("POST", URL, payload()),
        ("PATCH", f"{URL}/1", {"title": "x"}),
        ("DELETE", f"{URL}/1", None),
    ],
)
async def test_only_the_admin_may_manage_vocabularies(client: httpx.AsyncClient, method: str, url: str, body) -> None:
    _, normal = await signup_and_login(client)
    before = await count(SystemVocabulary)

    anonymous = await client.request(method, url, json=body)
    forbidden = await client.request(method, url, json=body, headers=auth_headers(normal))

    assert (anonymous.status_code, forbidden.status_code) == (401, 403)
    assert await count(SystemVocabulary) == before


@pytest.mark.asyncio
async def test_create_returns_an_empty_admin_vocabulary_visible_to_everyone(client: httpx.AsyncClient) -> None:
    token = await admin_token(client)
    created = await create(client, token, title="  우리 반 단어  ", description="   ")

    assert (created["title"], created["description"], created["category"], created["level"]) == (
        "우리 반 단어", None, "ETC", 2,
    )
    assert (created["source"], created["total_words"]) == ("admin", 0)
    assert created["slug"].startswith("admin-")
    _, normal = await signup_and_login(client)
    listed = (await client.get("/api/vocabularies", headers=auth_headers(normal))).json()
    assert listed[-1]["id"] == created["id"], "표준 단어장 뒤에 보인다"
    chosen = await client.post(
        "/api/users/me/active-vocabulary", json={"vocabulary_id": created["id"]}, headers=auth_headers(normal)
    )
    assert chosen.status_code == 200


@pytest.mark.asyncio
async def test_two_vocabularies_with_the_same_title_get_different_slugs(client: httpx.AsyncClient) -> None:
    token = await admin_token(client)

    first, second = await create(client, token), await create(client, token)

    assert first["slug"] != second["slug"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "overrides",
    [
        {"title": ""}, {"title": "   "}, {"title": "t" * 101}, {"description": "d" * 256},
        {"category": " "}, {"category": "c" * 51}, {"level": 0}, {"level": 6},
    ],
)
async def test_create_rejects_invalid_values(client: httpx.AsyncClient, overrides: dict) -> None:
    token = await admin_token(client)

    response = await client.post(URL, json=payload(**overrides), headers=auth_headers(token))

    assert response.status_code == 422, response.text
    assert await count(SystemVocabulary, SystemVocabulary.source == "admin") == 0


@pytest.mark.asyncio
async def test_update_changes_title_and_description_only(client: httpx.AsyncClient) -> None:
    token = await admin_token(client)
    created = await create(client, token)

    response = await client.patch(
        f"{URL}/{created['id']}",
        json={"title": "새 제목", "description": None, "level": 5},
        headers=auth_headers(token),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["title"], body["description"], body["level"]) == ("새 제목", None, 2)


@pytest.mark.asyncio
async def test_standard_vocabularies_cannot_be_changed_or_deleted(client: httpx.AsyncClient, make_vocabulary) -> None:
    standard = await make_vocabulary(["a", "b"], title="표준")
    token = await admin_token(client)

    update = await client.patch(f"{URL}/{standard.id}", json={"title": "바꿈"}, headers=auth_headers(token))
    delete_ = await client.delete(f"{URL}/{standard.id}", headers=auth_headers(token))

    for response in (update, delete_):
        assert response.status_code == 403
        assert response.headers["X-Error-Code"] == "SEED_READ_ONLY"
    assert await count(SystemWord, SystemWord.vocabulary_id == standard.id) == 2


@pytest.mark.asyncio
async def test_unknown_vocabulary_is_404(client: httpx.AsyncClient) -> None:
    token = await admin_token(client)

    assert (await client.patch(f"{URL}/999999999", json={"title": "x"}, headers=auth_headers(token))).status_code == 404
    assert (await client.delete(f"{URL}/999999999", headers=auth_headers(token))).status_code == 404


@pytest.mark.asyncio
async def test_delete_removes_words_history_and_sessions_and_clears_the_active_choice(client: httpx.AsyncClient) -> None:
    token = await admin_token(client)
    created = await create(client, token)
    for term in ("one", "two", "three", "four"):
        await add_word(client, token, created["id"], term)
    _, learner = await signup_and_login(client)
    learner_id = await user_id_for_token(client, learner)
    await client.post(
        "/api/users/me/active-vocabulary", json={"vocabulary_id": created["id"]}, headers=auth_headers(learner)
    )
    session = (await client.post("/api/study/sessions", json={}, headers=auth_headers(learner))).json()
    answered = await client.post(
        f"/api/study/sessions/{session['session_id']}/answer",
        json={"question_id": 0, "choice_index": 0},
        headers=auth_headers(learner),
    )
    assert answered.status_code == 200, answered.text

    response = await client.delete(f"{URL}/{created['id']}", headers=auth_headers(token))

    assert response.status_code == 204, response.text
    assert await count(SystemWord, SystemWord.vocabulary_id == created["id"]) == 0
    assert await count(StudyLog, StudyLog.user_id == learner_id) == 0
    assert await count(QuizSession, QuizSession.user_id == learner_id) == 0
    assert await count(User, User.id == learner_id, User.active_vocabulary_id.is_(None)) == 1
    # 활성 단어장이 없어도 다음 학습은 시작된다 (REQ-142)
    assert (await client.post("/api/study/sessions", json={}, headers=auth_headers(learner))).status_code == 201


@pytest.mark.asyncio
async def test_an_empty_vocabulary_cannot_start_a_session_but_does_not_fail(client: httpx.AsyncClient) -> None:
    token = await admin_token(client)
    created = await create(client, token)
    await client.post(
        "/api/users/me/active-vocabulary", json={"vocabulary_id": created["id"]}, headers=auth_headers(token)
    )

    for mode in ("quiz", "flashcard"):
        response = await client.post("/api/study/sessions", json={"mode": mode}, headers=auth_headers(token))
        assert 400 <= response.status_code < 500, response.text
