# 2026-11-26 - voda-voca - 관리자 단어 통합 테스트: 등록·수정·삭제, 중복 표제어, 표준 단어 보호, 단어 수와 이력 (REQ-161)
# 파일 위치: src/backend/tests/test_admin_word_api.py

import asyncio
from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import func, select

from backend.db.session import get_session_factory
from backend.main import app
from backend.models import Bookmark, StudyLog, SystemVocabulary, SystemWord, UserWordProgress
from backend.tests.helpers import (
    admin_token,
    auth_headers,
    delete_admin_content,
    signup_and_login,
)


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


def word(**overrides) -> dict:
    return {"term": "ladle", "meaning": "국자", "example": "Use a ladle.", "example_meaning": "국자를 써."} | overrides


async def post_word(client: httpx.AsyncClient, token: str, vocabulary_id: int, **overrides) -> httpx.Response:
    return await client.post(
        f"/api/admin/vocabularies/{vocabulary_id}/words", json=word(**overrides), headers=auth_headers(token)
    )


async def add(client: httpx.AsyncClient, token: str, vocabulary_id: int, **overrides) -> dict:
    response = await post_word(client, token, vocabulary_id, **overrides)
    assert response.status_code == 201, response.text
    return response.json()


async def listing(client: httpx.AsyncClient, token: str, vocabulary_id: int) -> dict:
    response = await client.get(f"/api/vocabularies/{vocabulary_id}/words", headers=auth_headers(token))
    assert response.status_code == 200, response.text
    return response.json()


async def total_words(vocabulary_id: int) -> int:
    async with get_session_factory()() as db:
        return await db.scalar(select(SystemVocabulary.total_words).where(SystemVocabulary.id == vocabulary_id))


async def count(model, *conditions) -> int:
    async with get_session_factory()() as db:
        return await db.scalar(select(func.count()).select_from(model).where(*conditions))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "url"),
    [("POST", "/api/admin/vocabularies/1/words"), ("PUT", "/api/admin/words/1"), ("DELETE", "/api/admin/words/1")],
)
async def test_only_the_admin_may_manage_words(client: httpx.AsyncClient, method: str, url: str) -> None:
    _, normal = await signup_and_login(client)
    before = await count(SystemWord)

    anonymous = await client.request(method, url, json=word())
    forbidden = await client.request(method, url, json=word(), headers=auth_headers(normal))

    assert (anonymous.status_code, forbidden.status_code) == (401, 403)
    assert await count(SystemWord) == before


@pytest.mark.asyncio
async def test_add_to_a_standard_vocabulary_appends_at_the_end_and_updates_the_count(
    client: httpx.AsyncClient, make_vocabulary
) -> None:
    vocab = await make_vocabulary(["apple", "banana"])
    token = await admin_token(client)

    created = await add(client, token, vocab.id, term="  ladle ", meaning=" 국자 ")

    assert (created["term"], created["meaning"], created["source"]) == ("ladle", "국자", "admin")
    assert (created["phonetic"], created["pos"], created["bookmarked"]) == (None, None, False)
    body = await listing(client, token, vocab.id)
    assert [i["term"] for i in body["items"]] == ["apple", "banana", "ladle"]
    assert [i["source"] for i in body["items"]] == ["seed", "seed", "admin"]
    assert body["total"] == await total_words(vocab.id) == 3


@pytest.mark.asyncio
@pytest.mark.parametrize("blank", [None, "", "   "])
async def test_without_an_example_the_translation_is_not_stored(
    client: httpx.AsyncClient, make_vocabulary, blank
) -> None:
    vocab = await make_vocabulary(["apple"])
    token = await admin_token(client)

    created = await add(client, token, vocab.id, example=blank, example_meaning="남으면 안 되는 뜻")

    assert (created["example"], created["example_meaning"]) == (None, None)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "overrides",
    [
        {"term": ""}, {"term": "   "}, {"term": "t" * 101}, {"meaning": ""}, {"meaning": "m" * 201},
        {"example": "e" * 501}, {"example_meaning": "e" * 501},
    ],
)
async def test_invalid_values_are_rejected(client: httpx.AsyncClient, make_vocabulary, overrides: dict) -> None:
    vocab = await make_vocabulary(["apple"])
    token = await admin_token(client)

    response = await post_word(client, token, vocab.id, **overrides)

    assert response.status_code == 422, response.text
    assert await total_words(vocab.id) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("duplicate", ["Café", "CAFE", " cafe "])
async def test_duplicate_term_ignores_case_and_accents(
    client: httpx.AsyncClient, make_vocabulary, duplicate: str
) -> None:
    vocab = await make_vocabulary(["cafe"])
    token = await admin_token(client)

    response = await post_word(client, token, vocab.id, term=duplicate)

    assert response.status_code == 409, response.text
    assert response.headers["X-Error-Code"] == "TERM_TAKEN"
    assert await total_words(vocab.id) == 1


@pytest.mark.asyncio
async def test_the_same_term_is_allowed_in_another_vocabulary(client: httpx.AsyncClient, make_vocabulary) -> None:
    first = await make_vocabulary(["apple"])
    second = await make_vocabulary(["banana"])
    token = await admin_token(client)

    await add(client, token, second.id, term="apple")

    assert (await total_words(first.id), await total_words(second.id)) == (1, 2)


@pytest.mark.asyncio
async def test_concurrent_duplicate_adds_create_one_word(client: httpx.AsyncClient, make_vocabulary) -> None:
    vocab = await make_vocabulary(["apple"])
    token = await admin_token(client)

    responses = await asyncio.gather(*(post_word(client, token, vocab.id, term=t) for t in ("Café", "cafe", "CAFE")))

    assert sorted(r.status_code for r in responses) == [201, 409, 409]
    assert await total_words(vocab.id) == 2


@pytest.mark.asyncio
async def test_unknown_vocabulary_or_word_is_404(client: httpx.AsyncClient) -> None:
    token = await admin_token(client)

    assert (await post_word(client, token, 999999999)).status_code == 404
    put = await client.put("/api/admin/words/999999999", json=word(), headers=auth_headers(token))
    delete_ = await client.delete("/api/admin/words/999999999", headers=auth_headers(token))
    assert (put.status_code, delete_.status_code) == (404, 404)


@pytest.mark.asyncio
async def test_update_replaces_an_admin_word_and_keeps_its_id(client: httpx.AsyncClient, make_vocabulary) -> None:
    vocab = await make_vocabulary(["apple"])
    token = await admin_token(client)
    created = await add(client, token, vocab.id)

    response = await client.put(
        f"/api/admin/words/{created['word_id']}",
        json={"term": "Ladle", "meaning": "큰 국자", "example": None},
        headers=auth_headers(token),
    )

    assert response.status_code == 200, "대소문자만 바꾸는 것은 자기 자신과의 중복이 아니다: " + response.text
    body = response.json()
    assert body["word_id"] == created["word_id"]
    assert (body["term"], body["meaning"], body["example"], body["example_meaning"]) == ("Ladle", "큰 국자", None, None)


@pytest.mark.asyncio
async def test_update_to_another_words_term_is_409(client: httpx.AsyncClient, make_vocabulary) -> None:
    vocab = await make_vocabulary(["apple"])
    token = await admin_token(client)
    created = await add(client, token, vocab.id)

    response = await client.put(
        f"/api/admin/words/{created['word_id']}", json=word(term="APPLE"), headers=auth_headers(token)
    )

    assert response.status_code == 409
    assert response.headers["X-Error-Code"] == "TERM_TAKEN"


@pytest.mark.asyncio
async def test_standard_words_cannot_be_changed_or_deleted(client: httpx.AsyncClient, make_vocabulary) -> None:
    vocab = await make_vocabulary(["apple"])
    token = await admin_token(client)
    word_id = vocab.word_ids["apple"]

    update = await client.put(f"/api/admin/words/{word_id}", json=word(), headers=auth_headers(token))
    delete_ = await client.delete(f"/api/admin/words/{word_id}", headers=auth_headers(token))

    for response in (update, delete_):
        assert response.status_code == 403
        assert response.headers["X-Error-Code"] == "SEED_READ_ONLY"
    assert [i["meaning"] for i in (await listing(client, token, vocab.id))["items"]] == ["apple의 뜻"]


@pytest.mark.asyncio
async def test_delete_removes_the_word_with_everyones_records(client: httpx.AsyncClient, make_vocabulary) -> None:
    vocab = await make_vocabulary(["a1", "a2", "a3"])
    token = await admin_token(client)
    created = await add(client, token, vocab.id)
    word_id = created["word_id"]
    _, learner = await signup_and_login(client)
    await client.post(
        "/api/users/me/active-vocabulary", json={"vocabulary_id": vocab.id}, headers=auth_headers(learner)
    )
    await client.put(f"/api/bookmarks/{word_id}", headers=auth_headers(learner))
    session = (
        await client.post(
            "/api/study/sessions", json={"mode": "flashcard", "count": 10}, headers=auth_headers(learner)
        )
    ).json()
    question = next(i for i in session["items"] if i["word_id"] == word_id)
    answer_url = f"/api/study/sessions/{session['session_id']}/answer"
    first = await client.post(
        answer_url, json={"question_id": question["question_id"], "known": True}, headers=auth_headers(learner)
    )
    assert first.status_code == 200, first.text
    assert await count(StudyLog, StudyLog.word_id == word_id) == 1

    response = await client.delete(f"/api/admin/words/{word_id}", headers=auth_headers(token))

    assert response.status_code == 204, response.text
    for model in (StudyLog, Bookmark, UserWordProgress):
        assert await count(model, model.word_id == word_id) == 0, model.__name__
    assert await total_words(vocab.id) == 3


@pytest.mark.asyncio
async def test_answering_a_deleted_word_in_a_running_session_is_409(client: httpx.AsyncClient, make_vocabulary) -> None:
    vocab = await make_vocabulary(["a1"])
    token = await admin_token(client)
    created = await add(client, token, vocab.id)
    _, learner = await signup_and_login(client)
    await client.post(
        "/api/users/me/active-vocabulary", json={"vocabulary_id": vocab.id}, headers=auth_headers(learner)
    )
    session = (
        await client.post("/api/study/sessions", json={"mode": "flashcard"}, headers=auth_headers(learner))
    ).json()
    question = next(i for i in session["items"] if i["word_id"] == created["word_id"])
    await client.delete(f"/api/admin/words/{created['word_id']}", headers=auth_headers(token))

    response = await client.post(
        f"/api/study/sessions/{session['session_id']}/answer",
        json={"question_id": question["question_id"], "known": True},
        headers=auth_headers(learner),
    )

    assert response.status_code == 409, response.text
