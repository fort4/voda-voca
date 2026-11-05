# 2026-11-05 - voda-voca - 표준 단어장 API 통합 테스트 (실제 MySQL): 카탈로그, 단어 목록, 활성 단어장 변경
# 파일 위치: src/backend/tests/test_vocabulary_api.py

import uuid
from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import select

from backend.db.session import get_session_factory
from backend.main import app
from backend.models import User, UserWordProgress
from backend.tests.helpers import auth_headers, signup_and_login
from backend.tests.test_study_api import _user_id_for_token


@pytest_asyncio.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def new_category() -> str:
    """다른 데이터와 섞이지 않는 카테고리. 카탈로그 필터로 내가 만든 단어장만 골라 본다."""
    return f"TVODA_{uuid.uuid4().hex[:8]}"


async def catalog(client: httpx.AsyncClient, token: str, **params) -> list[dict]:
    response = await client.get("/api/vocabularies", params=params, headers=auth_headers(token))
    assert response.status_code == 200, response.text
    return response.json()


async def add_progress(user_id: int, word_id: int, *, memorized: bool = False) -> None:
    async with get_session_factory()() as db:
        db.add(
            UserWordProgress(
                user_id=user_id,
                word_id=word_id,
                correct_count=3 if memorized else 1,
                consecutive_correct_count=3 if memorized else 1,
                is_memorized=memorized,
                last_result="CORRECT",
            )
        )
        await db.commit()


# --- 카탈로그 ---


@pytest.mark.asyncio
async def test_catalog_requires_login(client: httpx.AsyncClient) -> None:
    assert (await client.get("/api/vocabularies")).status_code == 401


@pytest.mark.asyncio
async def test_catalog_lists_the_seeded_vocabularies_in_order(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    items = await catalog(client, token)
    slugs = [i["slug"] for i in items]
    assert slugs[:3] == ["beginner-200", "intermediate-200", "advanced-200"]
    first = items[0]
    assert set(first) == {"id", "slug", "title", "category", "level", "description", "total_words", "user_progress"}
    assert (first["category"], first["level"], first["total_words"]) == ("ELEMENTARY", 1, 200)
    assert set(first["user_progress"]) == {"studied_words", "memorized_words", "progress_rate", "is_active"}


@pytest.mark.asyncio
async def test_catalog_filters_by_category_and_level(client: httpx.AsyncClient, make_vocabulary) -> None:
    category = new_category()
    easy = await make_vocabulary(["a1", "a2", "a3", "a4"], title="쉬움", category=category, level=1)
    hard = await make_vocabulary(["b1", "b2", "b3", "b4"], title="어려움", category=category, level=4)
    await make_vocabulary(["c1", "c2", "c3", "c4"], title="다른 분류", category=new_category(), level=1)
    _, token = await signup_and_login(client)

    assert {i["id"] for i in await catalog(client, token, category=category)} == {easy.id, hard.id}
    assert [i["id"] for i in await catalog(client, token, category=category, level=4)] == [hard.id]
    assert await catalog(client, token, category="NO_SUCH_CATEGORY") == []


@pytest.mark.asyncio
@pytest.mark.parametrize("level", [0, 6, "x"])
async def test_catalog_rejects_invalid_level(client: httpx.AsyncClient, level) -> None:
    _, token = await signup_and_login(client)
    response = await client.get("/api/vocabularies", params={"level": level}, headers=auth_headers(token))
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_catalog_user_progress_counts_studied_and_memorized(client: httpx.AsyncClient, make_vocabulary) -> None:
    category = new_category()
    vocab = await make_vocabulary(["a1", "a2", "a3", "a4"], category=category)
    _, token = await signup_and_login(client)
    user_id = await _user_id_for_token(client, token)

    empty = (await catalog(client, token, category=category))[0]["user_progress"]
    assert empty == {"studied_words": 0, "memorized_words": 0, "progress_rate": 0.0, "is_active": False}

    await add_progress(user_id, vocab.word_ids["a1"])
    await add_progress(user_id, vocab.word_ids["a2"], memorized=True)
    progress = (await catalog(client, token, category=category))[0]["user_progress"]
    assert progress["studied_words"] == 2
    assert progress["memorized_words"] == 1
    assert progress["progress_rate"] == 50.0


@pytest.mark.asyncio
async def test_catalog_progress_rate_is_rounded_to_one_decimal(client: httpx.AsyncClient, make_vocabulary) -> None:
    category = new_category()
    vocab = await make_vocabulary(["a1", "a2", "a3"], category=category)
    _, token = await signup_and_login(client)
    await add_progress(await _user_id_for_token(client, token), vocab.word_ids["a1"])
    assert (await catalog(client, token, category=category))[0]["user_progress"]["progress_rate"] == 33.3


@pytest.mark.asyncio
async def test_catalog_progress_is_per_user(client: httpx.AsyncClient, make_vocabulary) -> None:
    category = new_category()
    vocab = await make_vocabulary(["a1", "a2"], category=category)
    _, mine = await signup_and_login(client)
    _, theirs = await signup_and_login(client)
    await add_progress(await _user_id_for_token(client, theirs), vocab.word_ids["a1"])

    assert (await catalog(client, mine, category=category))[0]["user_progress"]["studied_words"] == 0
    assert (await catalog(client, theirs, category=category))[0]["user_progress"]["studied_words"] == 1


@pytest.mark.asyncio
async def test_catalog_marks_only_the_active_vocabulary(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    items = await catalog(client, token)
    active = [i["slug"] for i in items if i["user_progress"]["is_active"]]
    assert active == ["beginner-200"], "가입하면 초급 200제가 활성 단어장이다"


# --- 단어 목록 ---


@pytest.mark.asyncio
async def test_words_are_listed_in_order_with_bookmark_flag(client: httpx.AsyncClient, make_vocabulary) -> None:
    vocab = await make_vocabulary(["apple", "banana", "cherry"])
    _, token = await signup_and_login(client)
    await client.put(f"/api/bookmarks/{vocab.word_ids['banana']}", headers=auth_headers(token))

    response = await client.get(f"/api/vocabularies/{vocab.id}/words", headers=auth_headers(token))

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["vocabulary_id"], body["total"], body["page"]) == (vocab.id, 3, 1)
    assert [i["term"] for i in body["items"]] == ["apple", "banana", "cherry"]
    assert {i["term"]: i["bookmarked"] for i in body["items"]} == {"apple": False, "banana": True, "cherry": False}
    item = body["items"][0]
    assert set(item) == {"word_id", "term", "meaning", "example", "example_meaning", "bookmarked"}
    assert item["word_id"] == vocab.word_ids["apple"] and item["meaning"] == "apple의 뜻"


@pytest.mark.asyncio
async def test_word_bookmark_flag_is_per_user(client: httpx.AsyncClient, make_vocabulary) -> None:
    vocab = await make_vocabulary(["apple", "banana"])
    _, a = await signup_and_login(client)
    _, b = await signup_and_login(client)
    await client.put(f"/api/bookmarks/{vocab.word_ids['apple']}", headers=auth_headers(a))

    as_b = (await client.get(f"/api/vocabularies/{vocab.id}/words", headers=auth_headers(b))).json()
    assert all(i["bookmarked"] is False for i in as_b["items"])


@pytest.mark.asyncio
async def test_words_are_paginated(client: httpx.AsyncClient, make_vocabulary) -> None:
    vocab = await make_vocabulary([f"w{i:02d}" for i in range(5)])
    _, token = await signup_and_login(client)

    page1 = (await client.get(f"/api/vocabularies/{vocab.id}/words", params={"page": 1, "size": 2}, headers=auth_headers(token))).json()
    page3 = (await client.get(f"/api/vocabularies/{vocab.id}/words", params={"page": 3, "size": 2}, headers=auth_headers(token))).json()
    assert [i["term"] for i in page1["items"]] == ["w00", "w01"]
    assert [i["term"] for i in page3["items"]] == ["w04"]
    assert page1["total"] == page3["total"] == 5


@pytest.mark.asyncio
async def test_words_of_a_real_seed_vocabulary(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    first = (await catalog(client, token))[0]
    body = (await client.get(f"/api/vocabularies/{first['id']}/words", params={"size": 200}, headers=auth_headers(token))).json()
    assert body["total"] == 200 and len(body["items"]) == 200
    assert all(i["example"] and i["example_meaning"] for i in body["items"])


@pytest.mark.asyncio
@pytest.mark.parametrize("params", [{"size": 0}, {"size": 201}, {"page": 0}])
async def test_words_reject_out_of_range_paging(client: httpx.AsyncClient, make_vocabulary, params: dict) -> None:
    vocab = await make_vocabulary(["a"])
    _, token = await signup_and_login(client)
    response = await client.get(f"/api/vocabularies/{vocab.id}/words", params=params, headers=auth_headers(token))
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_words_of_unknown_vocabulary_is_404_and_login_required(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    response = await client.get("/api/vocabularies/999999999/words", headers=auth_headers(token))
    assert response.status_code == 404
    assert response.json() == {"detail": "단어장을 찾을 수 없습니다."}
    assert (await client.get("/api/vocabularies/1/words")).status_code == 401


# --- 활성 단어장 변경 ---


async def set_active(client: httpx.AsyncClient, token: str, vocabulary_id) -> httpx.Response:
    return await client.post(
        "/api/users/me/active-vocabulary", json={"vocabulary_id": vocabulary_id}, headers=auth_headers(token)
    )


async def active_id_of(user_id: int) -> int | None:
    async with get_session_factory()() as db:
        return (await db.execute(select(User.active_vocabulary_id).where(User.id == user_id))).scalar_one()


@pytest.mark.asyncio
async def test_set_active_vocabulary_changes_it_and_returns_the_entry(client: httpx.AsyncClient, make_vocabulary) -> None:
    category = new_category()
    vocab = await make_vocabulary(["a1", "a2", "a3", "a4"], title="새 단어장", category=category, level=2)
    _, token = await signup_and_login(client)
    user_id = await _user_id_for_token(client, token)
    await add_progress(user_id, vocab.word_ids["a1"])

    response = await set_active(client, token, vocab.id)

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["id"], body["title"], body["category"], body["level"]) == (vocab.id, "새 단어장", category, 2)
    assert body["user_progress"] == {"studied_words": 1, "memorized_words": 0, "progress_rate": 25.0, "is_active": True}
    assert await active_id_of(user_id) == vocab.id
    actives = [i["id"] for i in await catalog(client, token) if i["user_progress"]["is_active"]]
    assert actives == [vocab.id]


@pytest.mark.asyncio
async def test_set_active_is_idempotent_and_can_switch_back(client: httpx.AsyncClient, make_vocabulary) -> None:
    vocab = await make_vocabulary(["a1", "a2", "a3", "a4"])
    _, token = await signup_and_login(client)
    user_id = await _user_id_for_token(client, token)
    original = await active_id_of(user_id)

    assert (await set_active(client, token, vocab.id)).status_code == 200
    assert (await set_active(client, token, vocab.id)).status_code == 200
    assert await active_id_of(user_id) == vocab.id
    assert (await set_active(client, token, original)).status_code == 200
    assert await active_id_of(user_id) == original


@pytest.mark.asyncio
async def test_set_active_only_affects_the_caller(client: httpx.AsyncClient, make_vocabulary) -> None:
    vocab = await make_vocabulary(["a1"])
    _, mine = await signup_and_login(client)
    _, theirs = await signup_and_login(client)
    their_id = await _user_id_for_token(client, theirs)
    before = await active_id_of(their_id)

    await set_active(client, mine, vocab.id)
    assert await active_id_of(their_id) == before


@pytest.mark.asyncio
async def test_set_active_unknown_vocabulary_is_404_and_keeps_the_current_one(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    user_id = await _user_id_for_token(client, token)
    before = await active_id_of(user_id)

    response = await set_active(client, token, 999999999)

    assert response.status_code == 404
    assert await active_id_of(user_id) == before


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [{}, {"vocabulary_id": "abc"}, {"vocabulary_id": 0}, {"vocabulary_id": None}])
async def test_set_active_rejects_invalid_body(client: httpx.AsyncClient, payload: dict) -> None:
    _, token = await signup_and_login(client)
    response = await client.post("/api/users/me/active-vocabulary", json=payload, headers=auth_headers(token))
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_set_active_requires_login(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/users/me/active-vocabulary", json={"vocabulary_id": 1})
    assert response.status_code == 401
