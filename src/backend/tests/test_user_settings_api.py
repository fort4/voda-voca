# 2026-11-10 - voda-voca - 학습 개수 설정 API 통합 테스트 (실제 MySQL): 조회, 부분 수정, 검증, 사용자 간 격리 (REQ-147, S2)
# 파일 위치: src/backend/tests/test_user_settings_api.py

from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio

from backend.main import app
from backend.tests.helpers import auth_headers, signup_and_login

URL = "/api/users/me/settings"
DEFAULTS = {"quiz_count": 10, "flashcard_count": 10, "daily_goal": 10, "options": [10, 20, 30]}


@pytest_asyncio.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def token_of(client: httpx.AsyncClient) -> str:
    _, token = await signup_and_login(client)
    return token


@pytest.mark.asyncio
async def test_requires_login(client: httpx.AsyncClient) -> None:
    assert (await client.get(URL)).status_code == 401
    assert (await client.patch(URL, json={"daily_goal": 20})).status_code == 401


@pytest.mark.asyncio
async def test_get_returns_defaults_and_options(client: httpx.AsyncClient) -> None:
    response = await client.get(URL, headers=auth_headers(await token_of(client)))
    assert response.status_code == 200
    assert response.json() == DEFAULTS


@pytest.mark.asyncio
async def test_patch_changes_only_the_given_fields_and_persists(client: httpx.AsyncClient) -> None:
    headers = auth_headers(await token_of(client))
    response = await client.patch(URL, json={"daily_goal": 30}, headers=headers)
    assert response.status_code == 200
    assert response.json() == {**DEFAULTS, "daily_goal": 30}
    response = await client.patch(URL, json={"quiz_count": 20, "flashcard_count": 30}, headers=headers)
    assert response.json() == {"quiz_count": 20, "flashcard_count": 30, "daily_goal": 30, "options": [10, 20, 30]}
    assert (await client.get(URL, headers=headers)).json() == response.json()


@pytest.mark.asyncio
async def test_empty_patch_changes_nothing(client: httpx.AsyncClient) -> None:
    headers = auth_headers(await token_of(client))
    await client.patch(URL, json={"quiz_count": 20}, headers=headers)
    response = await client.patch(URL, json={}, headers=headers)
    assert response.status_code == 200
    assert response.json()["quiz_count"] == 20


@pytest.mark.asyncio
@pytest.mark.parametrize("body", [{"quiz_count": 15}, {"daily_goal": 0}, {"flashcard_count": 31}, {"quiz_count": "20"}, {"quiz_count": True}, {"daily_goal": None}, {"unknown": 10}])
async def test_invalid_values_are_422_and_change_nothing(client: httpx.AsyncClient, body: dict) -> None:
    headers = auth_headers(await token_of(client))
    assert (await client.patch(URL, json=body, headers=headers)).status_code == 422
    assert (await client.get(URL, headers=headers)).json() == DEFAULTS


@pytest.mark.asyncio
async def test_settings_are_per_user(client: httpx.AsyncClient) -> None:
    first, second = auth_headers(await token_of(client)), auth_headers(await token_of(client))
    await client.patch(URL, json={"daily_goal": 30}, headers=first)
    assert (await client.get(URL, headers=second)).json()["daily_goal"] == 10
