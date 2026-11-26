# 2026-11-26 - voda-voca - 순위 공개 설정 API 통합 테스트: 기본 비공개, 변경, 검증, 본인 것만 바뀜 (REQ-173, VOCA-FR-052·053)
# 파일 위치: src/backend/tests/test_ranking_visibility_api.py

from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio

from backend.main import app
from backend.tests.helpers import auth_headers, signup_and_login, user_id_for_token

URL = "/api/users/me/ranking-visibility"


@pytest_asyncio.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def headers_of(client: httpx.AsyncClient) -> dict[str, str]:
    _, token = await signup_and_login(client)
    return auth_headers(token)


@pytest.mark.asyncio
async def test_requires_login(client: httpx.AsyncClient) -> None:
    assert (await client.get(URL)).status_code == 401
    assert (await client.put(URL, json={"public": True})).status_code == 401


@pytest.mark.asyncio
async def test_new_account_is_private(client: httpx.AsyncClient) -> None:
    response = await client.get(URL, headers=await headers_of(client))
    assert response.status_code == 200
    assert response.json() == {"public": False}


@pytest.mark.asyncio
async def test_put_turns_it_on_and_off_and_persists(client: httpx.AsyncClient) -> None:
    headers = await headers_of(client)
    for value in (True, False):
        response = await client.put(URL, json={"public": value}, headers=headers)
        assert response.status_code == 200
        assert response.json() == {"public": value}
        assert (await client.get(URL, headers=headers)).json() == {"public": value}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body", [{}, {"public": None}, {"public": 1}, {"public": "true"}, {"public": True, "user_id": 1}, {"ranking_public": True}]
)
async def test_invalid_bodies_are_422_and_change_nothing(client: httpx.AsyncClient, body: dict) -> None:
    headers = await headers_of(client)
    assert (await client.put(URL, json=body, headers=headers)).status_code == 422
    assert (await client.get(URL, headers=headers)).json() == {"public": False}


@pytest.mark.asyncio
async def test_only_my_own_setting_changes(client: httpx.AsyncClient) -> None:
    _, other_token = await signup_and_login(client)
    other_id = await user_id_for_token(client, other_token)
    mine = await headers_of(client)

    # 사용자 식별자를 받는 자리가 없다: 쿼리에 남의 id 를 붙여도 내 설정만 바뀐다 (VOCA-FR-053)
    await client.put(URL, params={"user_id": other_id}, json={"public": True}, headers=mine)

    assert (await client.get(URL, headers=auth_headers(other_token))).json() == {"public": False}
    assert (await client.get(URL, headers=mine)).json() == {"public": True}
