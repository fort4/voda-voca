# 2026-11-26 - voda-voca - 개인 단어장 통합 테스트: 생성·수정·삭제, 소유자 확인, 표준 단어장 보호, 삭제 시 연쇄 정리 (#39, REQ-170)
# 파일 위치: src/backend/tests/test_user_vocabulary_api.py

from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import func, select

from backend.db.session import get_session_factory
from backend.main import app
from backend.models import QuizSession, StudyLog, SystemVocabulary, SystemWord, User
from backend.tests.helpers import auth_headers, signup_and_login, user_id_for_token

URL = "/api/vocabularies"


@pytest_asyncio.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@dataclass
class Owner:
    token: str
    user_id: int


@pytest_asyncio.fixture
async def owner(client: httpx.AsyncClient) -> Owner:
    _, token = await signup_and_login(client)
    return Owner(token, await user_id_for_token(client, token))


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
    ("method", "suffix", "body"),
    [("POST", "", payload()), ("PATCH", "/{id}", {"title": "x"}), ("DELETE", "/{id}", None)],
)
async def test_changing_vocabularies_requires_login(
    client: httpx.AsyncClient, owner: Owner, method: str, suffix: str, body
) -> None:
    created = await create(client, owner.token)
    before = await count(SystemVocabulary)

    response = await client.request(method, URL + suffix.format(id=created["id"]), json=body)

    assert response.status_code == 401
    assert await count(SystemVocabulary) == before


@pytest.mark.asyncio
@pytest.mark.parametrize(("method", "body"), [("PATCH", {"title": "x"}), ("DELETE", None)])
async def test_someone_elses_vocabulary_looks_missing(
    client: httpx.AsyncClient, owner: Owner, method: str, body
) -> None:
    created = await create(client, owner.token)
    _, other = await signup_and_login(client)

    hidden = await client.request(method, f"{URL}/{created['id']}", json=body, headers=auth_headers(other))
    missing = await client.request(method, f"{URL}/999999999", json=body, headers=auth_headers(other))

    assert (hidden.status_code, hidden.json()) == (404, missing.json())
    assert await count(SystemVocabulary, SystemVocabulary.id == created["id"], SystemVocabulary.title == "우리 반 단어") == 1


@pytest.mark.asyncio
async def test_create_returns_an_empty_vocabulary_that_only_the_owner_sees(
    client: httpx.AsyncClient, owner: Owner
) -> None:
    created = await create(client, owner.token, title="  우리 반 단어  ", description="   ")

    assert (created["title"], created["description"], created["category"], created["level"]) == (
        "우리 반 단어", None, "ETC", 2,
    )
    assert (created["source"], created["total_words"], created["is_mine"]) == ("user", 0, True)
    assert created["slug"].startswith("user-")
    listed = (await client.get(URL, headers=auth_headers(owner.token))).json()
    assert listed[-1]["id"] == created["id"], "표준 단어장 뒤에 보인다"
    _, other = await signup_and_login(client)
    theirs = (await client.get(URL, headers=auth_headers(other))).json()
    assert created["id"] not in [v["id"] for v in theirs]


@pytest.mark.asyncio
async def test_only_the_title_is_required(client: httpx.AsyncClient, owner: Owner) -> None:
    response = await client.post(URL, json={"title": "내 단어"}, headers=auth_headers(owner.token))

    assert response.status_code == 201, response.text
    body = response.json()
    assert (body["category"], body["level"], body["description"]) == ("PERSONAL", 1, None)


@pytest.mark.asyncio
async def test_two_vocabularies_with_the_same_title_get_different_slugs(client: httpx.AsyncClient, owner: Owner) -> None:
    first, second = await create(client, owner.token), await create(client, owner.token)

    assert first["slug"] != second["slug"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "overrides",
    [
        {"title": ""}, {"title": "   "}, {"title": "t" * 101}, {"description": "d" * 256},
        {"category": " "}, {"category": "c" * 51}, {"level": 0}, {"level": 6},
    ],
)
async def test_create_rejects_invalid_values(client: httpx.AsyncClient, owner: Owner, overrides: dict) -> None:
    token = owner.token

    response = await client.post(URL, json=payload(**overrides), headers=auth_headers(token))

    assert response.status_code == 422, response.text
    assert await count(SystemVocabulary, SystemVocabulary.owner_id == owner.user_id) == 0


@pytest.mark.asyncio
async def test_update_changes_title_and_description_only(client: httpx.AsyncClient, owner: Owner) -> None:
    token = owner.token
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
async def test_standard_vocabularies_cannot_be_changed_or_deleted(
    client: httpx.AsyncClient, owner: Owner, make_vocabulary
) -> None:
    standard = await make_vocabulary(["a", "b"], title="표준")
    token = owner.token

    update = await client.patch(f"{URL}/{standard.id}", json={"title": "바꿈"}, headers=auth_headers(token))
    delete_ = await client.delete(f"{URL}/{standard.id}", headers=auth_headers(token))

    for response in (update, delete_):
        assert response.status_code == 403
        assert response.headers["X-Error-Code"] == "SEED_READ_ONLY"
    assert await count(SystemWord, SystemWord.vocabulary_id == standard.id) == 2


@pytest.mark.asyncio
async def test_unknown_vocabulary_is_404(client: httpx.AsyncClient, owner: Owner) -> None:
    token = owner.token

    assert (await client.patch(f"{URL}/999999999", json={"title": "x"}, headers=auth_headers(token))).status_code == 404
    assert (await client.delete(f"{URL}/999999999", headers=auth_headers(token))).status_code == 404


@pytest.mark.asyncio
async def test_delete_removes_words_history_and_sessions_and_clears_the_active_choice(client: httpx.AsyncClient, owner: Owner) -> None:
    token = owner.token
    created = await create(client, token)
    for term in ("one", "two", "three", "four"):
        await add_word(client, token, created["id"], term)
    learner, learner_id = token, owner.user_id
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
async def test_an_empty_vocabulary_cannot_start_a_session_but_does_not_fail(client: httpx.AsyncClient, owner: Owner) -> None:
    token = owner.token
    created = await create(client, token)
    await client.post(
        "/api/users/me/active-vocabulary", json={"vocabulary_id": created["id"]}, headers=auth_headers(token)
    )

    for mode in ("quiz", "flashcard"):
        response = await client.post("/api/study/sessions", json={"mode": mode}, headers=auth_headers(token))
        assert 400 <= response.status_code < 500, response.text
