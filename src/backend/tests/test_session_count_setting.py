# 2026-11-10 - voda-voca - 세션 생성 문항 수가 사용자 설정을 따르는지 검사 (실제 MySQL): 생략 시 모드별 설정, 명시값 우선 (REQ-147, S3)
# 파일 위치: src/backend/tests/test_session_count_setting.py

from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio

from backend.main import app
from backend.tests.helpers import auth_headers, signup_and_login

SETTINGS = "/api/users/me/settings"
SESSIONS = "/api/study/sessions"
TERMS = [f"word{i:02d}" for i in range(40)]


@pytest_asyncio.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def ready(client, make_vocabulary) -> dict[str, str]:
    vocab = await make_vocabulary(TERMS)
    _, token = await signup_and_login(client)
    headers = auth_headers(token)
    response = await client.post("/api/users/me/active-vocabulary", json={"vocabulary_id": vocab.id}, headers=headers)
    assert response.status_code == 200, response.text
    return headers


async def item_count(client, headers, **body) -> int:
    response = await client.post(SESSIONS, json=body, headers=headers)
    assert response.status_code == 201, response.text
    return len(response.json()["items"])


@pytest.mark.asyncio
async def test_omitted_count_uses_default_10_for_both_modes(client, make_vocabulary) -> None:
    headers = await ready(client, make_vocabulary)
    assert await item_count(client, headers, mode="quiz") == 10
    assert await item_count(client, headers, mode="flashcard") == 10
    assert await item_count(client, headers) == 10  # mode 도 생략하면 quiz


@pytest.mark.asyncio
async def test_omitted_count_follows_the_setting_of_the_requested_mode(client, make_vocabulary) -> None:
    headers = await ready(client, make_vocabulary)
    await client.patch(SETTINGS, json={"quiz_count": 20, "flashcard_count": 30}, headers=headers)
    assert await item_count(client, headers, mode="quiz") == 20
    assert await item_count(client, headers, mode="flashcard") == 30


@pytest.mark.asyncio
async def test_explicit_count_wins_over_the_setting(client, make_vocabulary) -> None:
    headers = await ready(client, make_vocabulary)
    await client.patch(SETTINGS, json={"quiz_count": 30}, headers=headers)
    assert await item_count(client, headers, mode="quiz", count=5) == 5


@pytest.mark.asyncio
async def test_explicit_count_is_still_validated(client, make_vocabulary) -> None:
    headers = await ready(client, make_vocabulary)
    for bad in (0, 31, "x", None):
        response = await client.post(SESSIONS, json={"count": bad}, headers=headers)
        assert response.status_code == 422, bad


@pytest.mark.asyncio
async def test_review_sessions_follow_the_setting_too(client, make_vocabulary) -> None:
    headers = await ready(client, make_vocabulary)
    words = (await client.post(SESSIONS, json={"mode": "flashcard", "count": 30}, headers=headers)).json()["items"]
    for item in words:
        assert (await client.put(f"/api/bookmarks/{item['word_id']}", headers=headers)).status_code == 204
    await client.patch(SETTINGS, json={"flashcard_count": 20}, headers=headers)
    assert await item_count(client, headers, mode="flashcard", source="bookmarks") == 20
