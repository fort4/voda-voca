# 2026-11-02 - voda-voca - 로그인 무차별 대입 방어 통합 테스트: 429·Retry-After, IP/계정 키, 성공 시 리셋 (REQ-121)
# 파일 위치: src/backend/tests/test_login_rate_limit_api.py

from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio

from backend.core.rate_limit import login_rate_limiter
from backend.main import app
from backend.tests.helpers import PASSWORD, signup_and_login, unique_email

WRONG_PASSWORD = "wrong-pass-9"


def _client_for_ip(ip: str) -> httpx.AsyncClient:
    """고정 IP 로 요청하는 클라이언트. ASGITransport 의 client 값이 request.client.host 가 된다."""
    transport = httpx.ASGITransport(app=app, client=(ip, 5000))
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest_asyncio.fixture
async def client_a() -> AsyncIterator[httpx.AsyncClient]:
    async with _client_for_ip("10.0.0.1") as c:
        yield c


@pytest_asyncio.fixture
async def client_b() -> AsyncIterator[httpx.AsyncClient]:
    async with _client_for_ip("10.0.0.2") as c:
        yield c


@pytest_asyncio.fixture
async def client_c() -> AsyncIterator[httpx.AsyncClient]:
    async with _client_for_ip("10.0.0.3") as c:
        yield c


async def login(client: httpx.AsyncClient, email: str, password: str) -> httpx.Response:
    return await client.post("/api/auth/login", json={"email": email, "password": password})


async def fail_n(client: httpx.AsyncClient, email: str, n: int) -> list[int]:
    statuses = []
    for _ in range(n):
        statuses.append((await login(client, email, WRONG_PASSWORD)).status_code)
    return statuses


@pytest.mark.asyncio
async def test_sixth_attempt_is_429_even_with_correct_password(client_a: httpx.AsyncClient) -> None:
    email, _ = await signup_and_login(client_a)
    assert await fail_n(client_a, email, 5) == [401] * 5

    blocked = await login(client_a, email, PASSWORD)
    assert blocked.status_code == 429
    assert "잠시 후" in blocked.json()["detail"]


@pytest.mark.asyncio
async def test_429_carries_positive_integer_retry_after(client_a: httpx.AsyncClient) -> None:
    email, _ = await signup_and_login(client_a)
    await fail_n(client_a, email, 5)

    blocked = await login(client_a, email, WRONG_PASSWORD)
    assert blocked.status_code == 429
    retry_after = blocked.headers["Retry-After"]
    assert retry_after.isdigit()
    assert 1 <= int(retry_after) <= 60


@pytest.mark.asyncio
async def test_account_limit_applies_across_ip_addresses(
    client_a: httpx.AsyncClient, client_b: httpx.AsyncClient
) -> None:
    """같은 계정에 IP를 바꿔 가며 공격해도 계정 키로 막힌다."""
    email, _ = await signup_and_login(client_a)
    await fail_n(client_a, email, 5)

    from_other_ip = await login(client_b, email, PASSWORD)
    assert from_other_ip.status_code == 429


@pytest.mark.asyncio
async def test_ip_limit_applies_across_accounts(
    client_a: httpx.AsyncClient, client_b: httpx.AsyncClient
) -> None:
    """한 IP가 여러 계정을 찔러 실패가 5회 쌓이면, 그 IP는 다른 계정으로도 막힌다. 다른 IP는 영향이 없다."""
    for _ in range(5):
        await login(client_a, unique_email(), WRONG_PASSWORD)  # 계정마다 실패 1회씩

    victim_email, _ = await signup_and_login(client_b)
    assert (await login(client_a, victim_email, PASSWORD)).status_code == 429
    assert (await login(client_b, victim_email, PASSWORD)).status_code == 200


@pytest.mark.asyncio
async def test_successful_login_resets_the_account_counter(
    client_a: httpx.AsyncClient, client_b: httpx.AsyncClient, client_c: httpx.AsyncClient
) -> None:
    """성공한 로그인은 계정 실패 기록을 지운다. 각 IP는 4회씩이므로 IP 한도에도 걸리지 않는다."""
    email, _ = await signup_and_login(client_b)  # 성공 로그인 1회 (기록 없음)
    assert await fail_n(client_a, email, 4) == [401] * 4

    assert (await login(client_b, email, PASSWORD)).status_code == 200  # 계정 카운터 리셋

    assert await fail_n(client_c, email, 4) == [401] * 4  # 리셋 덕분에 아직 차단되지 않는다


@pytest.mark.asyncio
async def test_blocked_attempts_are_not_counted_and_block_lifts_after_window(
    client_a: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """차단된 요청은 실패로 세지 않는다. 마지막 실패로부터 60초가 지나면 올바른 비밀번호로 로그인된다."""
    clock = {"now": 10_000.0}
    monkeypatch.setattr(login_rate_limiter, "_clock", lambda: clock["now"])

    email, _ = await signup_and_login(client_a)
    await fail_n(client_a, email, 5)  # t=10000 에 차단

    clock["now"] += 30
    for _ in range(3):
        assert (await login(client_a, email, WRONG_PASSWORD)).status_code == 429

    clock["now"] += 30  # t=10060: 실패 5건이 모두 윈도우 밖으로 나갔다
    assert (await login(client_a, email, PASSWORD)).status_code == 200


@pytest.mark.asyncio
async def test_malformed_email_is_still_rate_limited_by_ip(client_a: httpx.AsyncClient) -> None:
    """형식이 틀린 이메일도 IP 키로 집계된다 (실패 응답은 401 로 유지)."""
    for _ in range(5):
        response = await client_a.post(
            "/api/auth/login", json={"email": "not-an-email", "password": PASSWORD}
        )
        assert response.status_code == 401
    blocked = await client_a.post(
        "/api/auth/login", json={"email": "not-an-email", "password": PASSWORD}
    )
    assert blocked.status_code == 429


@pytest.mark.asyncio
async def test_other_endpoints_are_not_rate_limited(client_a: httpx.AsyncClient) -> None:
    """REQ-121 은 로그인에만 적용된다. 로그인이 차단돼도 가입·내 정보 조회는 그대로다."""
    email, token = await signup_and_login(client_a)
    await fail_n(client_a, email, 5)
    assert (await login(client_a, email, PASSWORD)).status_code == 429

    other = await client_a.post(
        "/api/auth/signup",
        json={"email": unique_email(), "password": PASSWORD, "nickname": "다른사람"},
    )
    assert other.status_code == 201
    me = await client_a.get("/api/auth/me", headers={"Cookie": f"voda_session={token}"})
    assert me.status_code == 200

