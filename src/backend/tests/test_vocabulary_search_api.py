# 2026-11-26 - voda-voca - 단어 검색 API 통합 테스트: 표제어·뜻 부분 일치, 대소문자 무시, 와일드카드 이스케이프, 페이지 (REQ-163)
# 파일 위치: src/backend/tests/test_vocabulary_search_api.py

from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio

from backend.main import app
from backend.tests.helpers import auth_headers, signup_and_login


@pytest_asyncio.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def search(client: httpx.AsyncClient, token: str, vocabulary_id: int, **params) -> dict:
    response = await client.get(
        f"/api/vocabularies/{vocabulary_id}/words", params=params, headers=auth_headers(token)
    )
    assert response.status_code == 200, response.text
    return response.json()


def terms(body: dict) -> list[str]:
    return [item["term"] for item in body["items"]]


@pytest.mark.asyncio
async def test_search_matches_part_of_a_term_in_list_order(client: httpx.AsyncClient, make_vocabulary) -> None:
    vocab = await make_vocabulary(["pineapple", "banana", "apple", "grape"])
    _, token = await signup_and_login(client)

    body = await search(client, token, vocab.id, q="apple")

    assert terms(body) == ["pineapple", "apple"]
    assert body["total"] == 2


@pytest.mark.asyncio
async def test_search_matches_part_of_a_meaning(client: httpx.AsyncClient, make_vocabulary) -> None:
    # 픽스처의 뜻은 "<term>의 뜻" 이다. 표제어에는 없는 "의 뜻" 으로 찾는다.
    vocab = await make_vocabulary(["apple", "banana"])
    _, token = await signup_and_login(client)

    assert terms(await search(client, token, vocab.id, q="na의 뜻")) == ["banana"]
    assert terms(await search(client, token, vocab.id, q="의 뜻")) == ["apple", "banana"]


@pytest.mark.asyncio
async def test_search_does_not_look_into_examples(client: httpx.AsyncClient, make_vocabulary) -> None:
    vocab = await make_vocabulary(["apple"])  # 예문: "I like apple."
    _, token = await signup_and_login(client)

    body = await search(client, token, vocab.id, q="I like")

    assert (terms(body), body["total"]) == ([], 0)


@pytest.mark.asyncio
@pytest.mark.parametrize("query", ["APP", "aPp"])
async def test_search_ignores_english_case(client: httpx.AsyncClient, make_vocabulary, query: str) -> None:
    vocab = await make_vocabulary(["Apple", "banana"])
    _, token = await signup_and_login(client)

    assert terms(await search(client, token, vocab.id, q=query)) == ["Apple"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("query", "expected"),
    [("%", ["100%"]), ("_", ["snake_case"]), ("\\", ["back\\slash"]), ("/", ["and/or"]), ("0%", ["100%"])],
)
async def test_search_treats_wildcards_as_plain_characters(
    client: httpx.AsyncClient, make_vocabulary, query: str, expected: list[str]
) -> None:
    vocab = await make_vocabulary(["100%", "snake_case", "back\\slash", "and/or", "plain"])
    _, token = await signup_and_login(client)

    assert terms(await search(client, token, vocab.id, q=query)) == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("query", ["", "   "])
async def test_blank_search_returns_the_whole_list(client: httpx.AsyncClient, make_vocabulary, query: str) -> None:
    vocab = await make_vocabulary(["apple", "banana"])
    _, token = await signup_and_login(client)

    body = await search(client, token, vocab.id, q=query)

    assert (terms(body), body["total"]) == (["apple", "banana"], 2)


@pytest.mark.asyncio
async def test_search_trims_surrounding_spaces(client: httpx.AsyncClient, make_vocabulary) -> None:
    vocab = await make_vocabulary(["apple", "banana"])
    _, token = await signup_and_login(client)

    assert terms(await search(client, token, vocab.id, q="  banana  ")) == ["banana"]


@pytest.mark.asyncio
async def test_search_stays_inside_the_vocabulary(client: httpx.AsyncClient, make_vocabulary) -> None:
    mine = await make_vocabulary(["apple"])
    await make_vocabulary(["applepie"])
    _, token = await signup_and_login(client)

    body = await search(client, token, mine.id, q="apple")

    assert (terms(body), body["total"]) == (["apple"], 1)


@pytest.mark.asyncio
async def test_search_results_are_paginated_with_filtered_total(client: httpx.AsyncClient, make_vocabulary) -> None:
    vocab = await make_vocabulary(["cat1", "dog", "cat2", "cat3"])
    _, token = await signup_and_login(client)

    first = await search(client, token, vocab.id, q="cat", page=1, size=2)
    second = await search(client, token, vocab.id, q="cat", page=2, size=2)

    assert (terms(first), first["total"]) == (["cat1", "cat2"], 3)
    assert (terms(second), second["total"]) == (["cat3"], 3)


@pytest.mark.asyncio
async def test_search_keeps_my_bookmark_flag(client: httpx.AsyncClient, make_vocabulary) -> None:
    vocab = await make_vocabulary(["apple", "banana"])
    _, token = await signup_and_login(client)
    await client.put(f"/api/bookmarks/{vocab.word_ids['banana']}", headers=auth_headers(token))

    body = await search(client, token, vocab.id, q="banana")

    assert [item["bookmarked"] for item in body["items"]] == [True]


@pytest.mark.asyncio
async def test_search_rejects_a_query_longer_than_100(client: httpx.AsyncClient, make_vocabulary) -> None:
    vocab = await make_vocabulary(["apple"])
    _, token = await signup_and_login(client)
    url = f"/api/vocabularies/{vocab.id}/words"

    assert (await client.get(url, params={"q": "a" * 100}, headers=auth_headers(token))).status_code == 200
    assert (await client.get(url, params={"q": "a" * 101}, headers=auth_headers(token))).status_code == 422


@pytest.mark.asyncio
async def test_search_requires_login_and_known_vocabulary(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)

    assert (await client.get("/api/vocabularies/1/words", params={"q": "a"})).status_code == 401
    missing = await client.get("/api/vocabularies/999999999/words", params={"q": "a"}, headers=auth_headers(token))
    assert missing.status_code == 404
