# 2026-11-26 - voda-voca - 닉네임 중복 확인 API 통합 테스트: 중복 여부, 대소문자, 규칙 오류, 호출 제한 (REQ-158, 이슈 #27)
# 파일 위치: src/backend/tests/test_availability_api.py

from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio

from backend.core.rate_limit import availability_rate_limiter
from backend.main import app
from backend.tests.helpers import login_payload, signup_and_login, unique_nickname


def _client_for_ip(ip: str) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app, client=(ip, 5000))
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest_asyncio.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    async with _client_for_ip("10.0.1.1") as c:
        yield c


@pytest_asyncio.fixture
async def other_ip_client() -> AsyncIterator[httpx.AsyncClient]:
    async with _client_for_ip("10.0.1.2") as c:
        yield c


async def check_nickname(client: httpx.AsyncClient, nickname: str) -> httpx.Response:
    return await client.get("/api/auth/check-nickname", params={"nickname": nickname})


# --- 이메일 확인 API 는 없다 ---


@pytest.mark.asyncio
async def test_there_is_no_email_check_endpoint(client: httpx.AsyncClient) -> None:
    assert (await client.get("/api/auth/check-email", params={"email": "a@b.co"})).status_code == 404


# --- 닉네임 ---


@pytest.mark.asyncio
async def test_unused_nickname_is_available(client: httpx.AsyncClient) -> None:
    response = await check_nickname(client, unique_nickname())
    assert response.status_code == 200
    assert response.json() == {"available": True}


@pytest.mark.asyncio
async def test_registered_nickname_is_not_available_ignoring_case_and_spaces(client: httpx.AsyncClient) -> None:
    nickname, _ = await signup_and_login(client)
    assert (await check_nickname(client, nickname)).json() == {"available": False}
    assert (await check_nickname(client, f"  {nickname.upper()}  ")).json() == {"available": False}


@pytest.mark.asyncio
@pytest.mark.parametrize("nickname", ["", "   ", "가", " a ", "가" * 31])
async def test_invalid_nickname_is_422(client: httpx.AsyncClient, nickname: str) -> None:
    assert (await check_nickname(client, nickname)).status_code == 422


# --- 호출 제한 (계정 존재 여부 열거 완화) ---


@pytest.mark.asyncio
async def test_availability_checks_are_limited_per_ip(
    client: httpx.AsyncClient, other_ip_client: httpx.AsyncClient
) -> None:
    """닉네임 확인은 IP 당 1분 30회. 31번째는 429 와 Retry-After, 다른 IP 는 영향이 없다."""
    for _ in range(30):
        assert (await check_nickname(client, unique_nickname())).status_code == 200

    blocked = await check_nickname(client, unique_nickname())
    assert blocked.status_code == 429
    assert 1 <= int(blocked.headers["Retry-After"]) <= 60
    assert (await check_nickname(other_ip_client, unique_nickname())).status_code == 200


@pytest.mark.asyncio
async def test_availability_limit_lifts_after_the_window(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = {"now": 5_000.0}
    monkeypatch.setattr(availability_rate_limiter, "_clock", lambda: clock["now"])
    for _ in range(30):
        await check_nickname(client, unique_nickname())
    assert (await check_nickname(client, unique_nickname())).status_code == 429
    clock["now"] += 60
    assert (await check_nickname(client, unique_nickname())).status_code == 200


@pytest.mark.asyncio
async def test_availability_calls_do_not_consume_the_login_limit(client: httpx.AsyncClient) -> None:
    """두 제한기는 따로 집계한다. 확인 버튼을 많이 눌러도 로그인이 막히지 않는다."""
    nickname, _ = await signup_and_login(client)
    for _ in range(10):
        await check_nickname(client, unique_nickname())
    response = await client.post("/api/auth/login", json=login_payload(nickname))
    assert response.status_code == 200
