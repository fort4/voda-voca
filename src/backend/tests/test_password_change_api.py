# 2026-11-26 - voda-voca - 비밀번호 변경 통합 테스트: 현재 비밀번호 확인, 새 비밀번호 규칙, 다른 세션 만료, 시도 제한 (REQ-164)
# 파일 위치: src/backend/tests/test_password_change_api.py

from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio

from backend.core.deps import SESSION_COOKIE_NAME
from backend.main import app
from backend.tests.helpers import PASSWORD, auth_headers, login_payload, signup_and_login

URL = "/api/auth/me/password"
NEW_PASSWORD = "brand-new-pass-2"


@pytest_asyncio.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def body(current: str = PASSWORD, new: str = NEW_PASSWORD, confirm: str | None = None) -> dict[str, str]:
    return {"current_password": current, "new_password": new, "new_password_confirm": new if confirm is None else confirm}


async def change(client: httpx.AsyncClient, token: str, **values) -> httpx.Response:
    return await client.put(URL, json=body(**values), headers=auth_headers(token))


async def login(client: httpx.AsyncClient, nickname: str, password: str) -> httpx.Response:
    response = await client.post("/api/auth/login", json=login_payload(nickname, password))
    client.cookies.clear()
    return response


async def alive(client: httpx.AsyncClient, token: str) -> bool:
    return (await client.get("/api/auth/me", headers=auth_headers(token))).status_code == 200


@pytest.mark.asyncio
async def test_requires_login(client: httpx.AsyncClient) -> None:
    assert (await client.put(URL, json=body())).status_code == 401


@pytest.mark.asyncio
async def test_change_replaces_the_password(client: httpx.AsyncClient) -> None:
    nickname, token = await signup_and_login(client)

    response = await change(client, token)

    assert response.status_code == 204, response.text
    assert (await login(client, nickname, PASSWORD)).status_code == 401
    assert (await login(client, nickname, NEW_PASSWORD)).status_code == 200


@pytest.mark.asyncio
async def test_wrong_current_password_is_400_not_401(client: httpx.AsyncClient) -> None:
    """401 은 화면이 세션 만료로 처리해 로그아웃시키므로 쓰지 않는다."""
    nickname, token = await signup_and_login(client)

    response = await change(client, token, current="not-my-password")

    assert response.status_code == 400
    assert response.headers["X-Error-Code"] == "CURRENT_PASSWORD_MISMATCH"
    assert response.json() == {"detail": "현재 비밀번호가 올바르지 않습니다."}
    assert (await login(client, nickname, PASSWORD)).status_code == 200


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("values", "field"),
    [
        ({"new": "short12"}, "new_password"),
        ({"new": "가" * 25}, "new_password"),  # 75바이트
        ({"confirm": "different-pass-3"}, "new_password_confirm"),
        ({"new": PASSWORD}, "new_password"),  # 지금 비밀번호와 같다
    ],
)
async def test_new_password_rules(client: httpx.AsyncClient, values: dict, field: str) -> None:
    nickname, token = await signup_and_login(client)

    response = await change(client, token, **values)

    assert response.status_code == 422, response.text
    assert [error["loc"][-1] for error in response.json()["detail"]] == [field]
    assert (await login(client, nickname, PASSWORD)).status_code == 200


@pytest.mark.asyncio
async def test_change_expires_only_my_other_sessions(client: httpx.AsyncClient) -> None:
    nickname, current = await signup_and_login(client)
    other = (await login(client, nickname, PASSWORD)).cookies[SESSION_COOKIE_NAME]
    _, someone = await signup_and_login(client)

    assert (await change(client, current)).status_code == 204

    assert await alive(client, current)
    assert not await alive(client, other)
    assert await alive(client, someone)


@pytest.mark.asyncio
async def test_failed_change_keeps_other_sessions(client: httpx.AsyncClient) -> None:
    nickname, current = await signup_and_login(client)
    other = (await login(client, nickname, PASSWORD)).cookies[SESSION_COOKIE_NAME]

    await change(client, current, current="not-my-password")

    assert await alive(client, other)


@pytest.mark.asyncio
async def test_five_wrong_attempts_block_even_the_right_password(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    _, someone = await signup_and_login(client)
    for _ in range(5):
        assert (await change(client, token, current="not-my-password")).status_code == 400

    blocked = await change(client, token)

    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) >= 1
    assert (await change(client, someone)).status_code == 204, "제한은 계정별이다"


@pytest.mark.asyncio
async def test_success_resets_the_failure_count(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    for _ in range(4):
        await change(client, token, current="not-my-password")
    assert (await change(client, token)).status_code == 204

    again = [(await change(client, token, current="not-my-password")).status_code for _ in range(5)]

    assert again == [400] * 5
