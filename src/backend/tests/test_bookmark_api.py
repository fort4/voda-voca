# 2026-11-05 - voda-voca - 북마크 API 통합 테스트 (실제 MySQL): 표준 단어 대상 멱등 등록/해제, 사용자 격리, CASCADE
# 파일 위치: src/backend/tests/test_bookmark_api.py

import asyncio
from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import delete, func, select

from backend.db.session import get_session_factory
from backend.main import app
from backend.models import Bookmark, SystemVocabulary, SystemWord
from backend.tests.helpers import auth_headers, signup_and_login

TERMS = ["apple", "banana", "cherry"]


@pytest_asyncio.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def put(client: httpx.AsyncClient, token: str, word_id: int) -> httpx.Response:
    return await client.put(f"/api/bookmarks/{word_id}", headers=auth_headers(token))


async def delete_bookmark(client: httpx.AsyncClient, token: str, word_id: int) -> httpx.Response:
    return await client.delete(f"/api/bookmarks/{word_id}", headers=auth_headers(token))


async def bookmark_list(client: httpx.AsyncClient, token: str, **params) -> dict:
    response = await client.get("/api/bookmarks", params=params, headers=auth_headers(token))
    assert response.status_code == 200, response.text
    return response.json()


async def bookmark_rows_for(word_id: int) -> int:
    async with get_session_factory()() as session:
        return await session.scalar(select(func.count()).select_from(Bookmark).where(Bookmark.word_id == word_id))


# --- 등록과 해제: 멱등성 (REQ-017) ---


@pytest.mark.asyncio
async def test_put_registers_bookmark_and_list_shows_it(client: httpx.AsyncClient, make_vocabulary) -> None:
    vocab = await make_vocabulary(TERMS, title="토익 기초")
    _, token = await signup_and_login(client)
    word = vocab.word_ids["apple"]

    assert (await put(client, token, word)).status_code == 204
    body = await bookmark_list(client, token)
    assert body["total"] == 1
    item = body["items"][0]
    assert item["word_id"] == word
    assert item["vocabulary_id"] == vocab.id
    assert item["vocabulary_title"] == "토익 기초"
    assert item["term"] == "apple"
    assert item["meaning"] == "apple의 뜻"
    assert item["example"] == "I like apple."
    assert item["example_meaning"] == "나는 apple을(를) 좋아한다."
    assert item["bookmarked_at"].endswith("Z")
    assert "wordbook_id" not in item and "wordbook_name" not in item


@pytest.mark.asyncio
async def test_put_is_idempotent(client: httpx.AsyncClient, make_vocabulary) -> None:
    vocab = await make_vocabulary(TERMS)
    _, token = await signup_and_login(client)
    word = vocab.word_ids["apple"]

    for _ in range(3):
        assert (await put(client, token, word)).status_code == 204
    assert await bookmark_rows_for(word) == 1
    assert (await bookmark_list(client, token))["total"] == 1


@pytest.mark.asyncio
async def test_concurrent_puts_create_exactly_one_row(client: httpx.AsyncClient, make_vocabulary) -> None:
    """동시에 같은 단어를 등록해도 모두 204 이고 행은 하나다 (uk_bookmarks_user_word)."""
    vocab = await make_vocabulary(TERMS)
    _, token = await signup_and_login(client)
    word = vocab.word_ids["apple"]

    responses = await asyncio.gather(*(put(client, token, word) for _ in range(5)))
    assert [r.status_code for r in responses] == [204] * 5
    assert await bookmark_rows_for(word) == 1


@pytest.mark.asyncio
async def test_delete_removes_bookmark_and_is_idempotent(client: httpx.AsyncClient, make_vocabulary) -> None:
    vocab = await make_vocabulary(TERMS)
    _, token = await signup_and_login(client)
    word = vocab.word_ids["apple"]
    await put(client, token, word)

    assert (await delete_bookmark(client, token, word)).status_code == 204
    assert (await delete_bookmark(client, token, word)).status_code == 204  # 두 번째 해제도 성공
    assert await bookmark_rows_for(word) == 0


@pytest.mark.asyncio
async def test_delete_without_bookmark_is_204(client: httpx.AsyncClient, make_vocabulary) -> None:
    vocab = await make_vocabulary(TERMS)
    _, token = await signup_and_login(client)
    assert (await delete_bookmark(client, token, vocab.word_ids["apple"])).status_code == 204


# --- 공용 단어와 사용자 격리 ---


@pytest.mark.asyncio
async def test_unknown_word_is_404(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    response = await put(client, token, 999999999)
    assert response.status_code == 404
    assert response.json() == {"detail": "단어를 찾을 수 없습니다."}


@pytest.mark.asyncio
async def test_any_user_can_bookmark_the_same_shared_word(client: httpx.AsyncClient, make_vocabulary) -> None:
    """표준 단어는 모든 사용자가 공유한다. 북마크는 사용자별로 따로 생긴다."""
    vocab = await make_vocabulary(TERMS)
    _, a = await signup_and_login(client)
    _, b = await signup_and_login(client)
    word = vocab.word_ids["apple"]

    assert (await put(client, a, word)).status_code == 204
    assert (await put(client, b, word)).status_code == 204
    assert await bookmark_rows_for(word) == 2


@pytest.mark.asyncio
async def test_other_users_delete_does_not_touch_my_bookmark(client: httpx.AsyncClient, make_vocabulary) -> None:
    vocab = await make_vocabulary(TERMS)
    _, owner = await signup_and_login(client)
    _, other = await signup_and_login(client)
    word = vocab.word_ids["apple"]
    await put(client, owner, word)

    assert (await delete_bookmark(client, other, word)).status_code == 204
    assert await bookmark_rows_for(word) == 1
    assert (await bookmark_list(client, owner))["total"] == 1


@pytest.mark.asyncio
async def test_list_shows_only_own_bookmarks(client: httpx.AsyncClient, make_vocabulary) -> None:
    vocab = await make_vocabulary(TERMS)
    _, a = await signup_and_login(client)
    _, b = await signup_and_login(client)
    await put(client, a, vocab.word_ids["apple"])

    assert (await bookmark_list(client, b))["items"] == []


# --- 목록 페이징과 정렬 (REQ-018) ---


@pytest.mark.asyncio
async def test_list_is_newest_first_and_paginated(client: httpx.AsyncClient, make_vocabulary) -> None:
    vocab = await make_vocabulary(["first", "second", "third"])
    _, token = await signup_and_login(client)
    for term in ["first", "second", "third"]:
        await put(client, token, vocab.word_ids[term])
        await asyncio.sleep(0.01)  # created_at 이 구분되도록 간격을 둔다

    body = await bookmark_list(client, token)
    assert [i["term"] for i in body["items"]] == ["third", "second", "first"]

    page1 = await bookmark_list(client, token, page=1, size=2)
    page2 = await bookmark_list(client, token, page=2, size=2)
    assert [i["term"] for i in page1["items"]] == ["third", "second"]
    assert [i["term"] for i in page2["items"]] == ["first"]
    assert page1["total"] == page2["total"] == 3


@pytest.mark.asyncio
@pytest.mark.parametrize("params", [{"size": 0}, {"size": 101}, {"page": 0}])
async def test_list_rejects_out_of_range_paging(client: httpx.AsyncClient, params: dict) -> None:
    _, token = await signup_and_login(client)
    response = await client.get("/api/bookmarks", params=params, headers=auth_headers(token))
    assert response.status_code == 422


# --- CASCADE ---


@pytest.mark.asyncio
async def test_deleting_a_word_removes_its_bookmarks(client: httpx.AsyncClient, make_vocabulary) -> None:
    vocab = await make_vocabulary(TERMS)
    _, token = await signup_and_login(client)
    word = vocab.word_ids["apple"]
    await put(client, token, word)

    async with get_session_factory()() as session:
        await session.execute(delete(SystemWord).where(SystemWord.id == word))
        await session.commit()
    assert (await bookmark_list(client, token))["total"] == 0


@pytest.mark.asyncio
async def test_deleting_a_vocabulary_removes_bookmarks_of_its_words_only(client: httpx.AsyncClient, make_vocabulary) -> None:
    doomed = await make_vocabulary(["a1", "a2"])
    kept = await make_vocabulary(["k1"])
    _, token = await signup_and_login(client)
    for term in ["a1", "a2"]:
        await put(client, token, doomed.word_ids[term])
    await put(client, token, kept.word_ids["k1"])

    async with get_session_factory()() as session:
        await session.execute(delete(SystemVocabulary).where(SystemVocabulary.id == doomed.id))
        await session.commit()

    body = await bookmark_list(client, token)
    assert [i["term"] for i in body["items"]] == ["k1"]


@pytest.mark.asyncio
async def test_bookmark_requires_login(client: httpx.AsyncClient) -> None:
    assert (await client.put("/api/bookmarks/1")).status_code == 401
    assert (await client.delete("/api/bookmarks/1")).status_code == 401
    assert (await client.get("/api/bookmarks")).status_code == 401
