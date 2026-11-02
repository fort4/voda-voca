# 2026-11-02 - voda-voca - 북마크 API 통합 테스트 (실제 MySQL): 멱등 등록/해제, 소유권 404, CASCADE, bookmarked 플래그
# 파일 위치: src/backend/tests/test_bookmark_api.py

import asyncio
from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import func, select

from backend.db.session import get_session_factory
from backend.main import app
from backend.models import Bookmark
from backend.tests.helpers import auth_headers, signup_and_login


@pytest_asyncio.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def make_wordbook(client: httpx.AsyncClient, token: str, name: str = "단어장") -> int:
    response = await client.post("/api/wordbooks", json={"name": name}, headers=auth_headers(token))
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def make_word(client: httpx.AsyncClient, token: str, wordbook_id: int, term: str) -> int:
    response = await client.post(
        f"/api/wordbooks/{wordbook_id}/words",
        json={"term": term, "meaning": "뜻"},
        headers=auth_headers(token),
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def put(client: httpx.AsyncClient, token: str, word_id: int) -> httpx.Response:
    return await client.put(f"/api/bookmarks/{word_id}", headers=auth_headers(token))


async def delete(client: httpx.AsyncClient, token: str, word_id: int) -> httpx.Response:
    return await client.delete(f"/api/bookmarks/{word_id}", headers=auth_headers(token))


async def bookmark_list(client: httpx.AsyncClient, token: str, **params) -> dict:
    response = await client.get("/api/bookmarks", params=params, headers=auth_headers(token))
    assert response.status_code == 200, response.text
    return response.json()


async def bookmark_rows_for(word_id: int) -> int:
    async with get_session_factory()() as session:
        return await session.scalar(
            select(func.count()).select_from(Bookmark).where(Bookmark.word_id == word_id)
        )


# --- 등록과 해제: 멱등성 (REQ-017) ---


@pytest.mark.asyncio
async def test_put_registers_bookmark_and_list_shows_it(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    wb = await make_wordbook(client, token, "토익")
    word = await make_word(client, token, wb, "apple")

    assert (await put(client, token, word)).status_code == 204
    body = await bookmark_list(client, token)
    assert body["total"] == 1
    item = body["items"][0]
    assert item["word_id"] == word
    assert item["wordbook_id"] == wb
    assert item["wordbook_name"] == "토익"
    assert item["term"] == "apple"
    assert item["bookmarked_at"].endswith("Z")


@pytest.mark.asyncio
async def test_put_is_idempotent(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    wb = await make_wordbook(client, token)
    word = await make_word(client, token, wb, "apple")

    assert (await put(client, token, word)).status_code == 204
    assert (await put(client, token, word)).status_code == 204
    assert (await put(client, token, word)).status_code == 204
    assert await bookmark_rows_for(word) == 1
    assert (await bookmark_list(client, token))["total"] == 1


@pytest.mark.asyncio
async def test_concurrent_puts_create_exactly_one_row(client: httpx.AsyncClient) -> None:
    """동시에 같은 단어를 등록해도 모두 204 이고 행은 하나다 (uk_bookmarks_user_word)."""
    _, token = await signup_and_login(client)
    wb = await make_wordbook(client, token)
    word = await make_word(client, token, wb, "apple")

    responses = await asyncio.gather(*(put(client, token, word) for _ in range(5)))
    assert [r.status_code for r in responses] == [204] * 5
    assert await bookmark_rows_for(word) == 1


@pytest.mark.asyncio
async def test_delete_removes_bookmark_and_is_idempotent(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    wb = await make_wordbook(client, token)
    word = await make_word(client, token, wb, "apple")
    await put(client, token, word)

    assert (await delete(client, token, word)).status_code == 204
    assert (await delete(client, token, word)).status_code == 204  # 두 번째 해제도 성공
    assert await bookmark_rows_for(word) == 0


@pytest.mark.asyncio
async def test_delete_without_bookmark_is_204(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    wb = await make_wordbook(client, token)
    word = await make_word(client, token, wb, "apple")
    assert (await delete(client, token, word)).status_code == 204


# --- 소유권 격리 (REQ-003, 404 일원화) ---


@pytest.mark.asyncio
async def test_put_on_other_users_word_is_404_same_as_missing(client: httpx.AsyncClient) -> None:
    _, owner = await signup_and_login(client)
    _, intruder = await signup_and_login(client)
    wb = await make_wordbook(client, owner)
    word = await make_word(client, owner, wb, "secret")

    foreign = await put(client, intruder, word)
    missing = await put(client, intruder, 999999999)

    assert foreign.status_code == missing.status_code == 404
    assert foreign.json() == missing.json()
    assert await bookmark_rows_for(word) == 0


@pytest.mark.asyncio
async def test_intruder_delete_does_not_touch_owners_bookmark(client: httpx.AsyncClient) -> None:
    _, owner = await signup_and_login(client)
    _, intruder = await signup_and_login(client)
    wb = await make_wordbook(client, owner)
    word = await make_word(client, owner, wb, "secret")
    await put(client, owner, word)

    response = await delete(client, intruder, word)
    assert response.status_code == 204  # 존재 여부를 드러내지 않도록 항상 204
    assert await bookmark_rows_for(word) == 1
    assert (await bookmark_list(client, owner))["total"] == 1


@pytest.mark.asyncio
async def test_list_shows_only_own_bookmarks(client: httpx.AsyncClient) -> None:
    _, a = await signup_and_login(client)
    _, b = await signup_and_login(client)
    wb_a = await make_wordbook(client, a)
    word_a = await make_word(client, a, wb_a, "alpha")
    await put(client, a, word_a)

    assert (await bookmark_list(client, b))["items"] == []


# --- 목록 페이징과 정렬 (REQ-018) ---


@pytest.mark.asyncio
async def test_list_is_newest_first_and_paginated(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    wb = await make_wordbook(client, token)
    words = []
    for term in ["first", "second", "third"]:
        word = await make_word(client, token, wb, term)
        words.append(word)
        await put(client, token, word)
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


# --- CASCADE (REQ-007, REQ-011) ---


@pytest.mark.asyncio
async def test_deleting_word_removes_its_bookmark(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    wb = await make_wordbook(client, token)
    word = await make_word(client, token, wb, "apple")
    await put(client, token, word)

    response = await client.delete(f"/api/wordbooks/{wb}/words/{word}", headers=auth_headers(token))
    assert response.status_code == 204
    assert (await bookmark_list(client, token))["total"] == 0


@pytest.mark.asyncio
async def test_deleting_wordbook_removes_bookmarks_of_its_words(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    wb = await make_wordbook(client, token)
    keep_wb = await make_wordbook(client, token, "남길 단어장")
    for term in ["a1", "a2"]:
        await put(client, token, await make_word(client, token, wb, term))
    kept = await make_word(client, token, keep_wb, "k1")
    await put(client, token, kept)

    response = await client.delete(f"/api/wordbooks/{wb}", headers=auth_headers(token))
    assert response.status_code == 204

    body = await bookmark_list(client, token)
    assert [i["term"] for i in body["items"]] == ["k1"]
    assert body["items"][0]["word_id"] == kept


# --- 단어 목록의 bookmarked 플래그 정합성 ---


@pytest.mark.asyncio
async def test_word_list_bookmarked_flag_matches_bookmarks(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    wb = await make_wordbook(client, token)
    ids = {term: await make_word(client, token, wb, term) for term in ["apple", "banana", "cherry"]}
    await put(client, token, ids["apple"])
    await put(client, token, ids["cherry"])

    flags = {
        item["term"]: item["bookmarked"]
        for item in (await client.get(f"/api/wordbooks/{wb}/words", headers=auth_headers(token))).json()["items"]
    }
    assert flags == {"apple": True, "banana": False, "cherry": True}

    await delete(client, token, ids["apple"])
    flags = {
        item["term"]: item["bookmarked"]
        for item in (await client.get(f"/api/wordbooks/{wb}/words", headers=auth_headers(token))).json()["items"]
    }
    assert flags == {"apple": False, "banana": False, "cherry": True}


@pytest.mark.asyncio
async def test_bookmarked_flag_is_consistent_with_prefix_search(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    wb = await make_wordbook(client, token)
    apple = await make_word(client, token, wb, "apple")
    await make_word(client, token, wb, "apricot")
    await put(client, token, apple)

    items = (await client.get(f"/api/wordbooks/{wb}/words", params={"q": "ap"}, headers=auth_headers(token))).json()["items"]
    assert {i["term"]: i["bookmarked"] for i in items} == {"apple": True, "apricot": False}


@pytest.mark.asyncio
async def test_bookmarked_flag_on_get_patch_and_create(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    wb = await make_wordbook(client, token)
    word = await make_word(client, token, wb, "apple")
    url = f"/api/wordbooks/{wb}/words/{word}"

    assert (await client.get(url, headers=auth_headers(token))).json()["bookmarked"] is False
    await put(client, token, word)
    assert (await client.get(url, headers=auth_headers(token))).json()["bookmarked"] is True
    patched = await client.patch(url, json={"meaning": "사과"}, headers=auth_headers(token))
    assert patched.json()["bookmarked"] is True


@pytest.mark.asyncio
async def test_bookmark_requires_login(client: httpx.AsyncClient) -> None:
    assert (await client.put("/api/bookmarks/1")).status_code == 401
    assert (await client.delete("/api/bookmarks/1")).status_code == 401
    assert (await client.get("/api/bookmarks")).status_code == 401
