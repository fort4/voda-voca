# 2026-11-02 - voda-voca - 정적 프론트엔드 마운트 검증: 루트·자산 서빙, API 라우트 비가림 (REQ-116, 같은 출처 배포)
# 파일 위치: src/backend/tests/test_static_mount.py

from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio

from backend.main import app


@pytest_asyncio.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_root_serves_the_app_shell(client: httpx.AsyncClient) -> None:
    response = await client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert 'id="app"' in response.text


@pytest.mark.asyncio
async def test_static_assets_are_served(client: httpx.AsyncClient) -> None:
    css = await client.get("/css/app.css")
    js = await client.get("/js/app.js")
    assert css.status_code == 200
    assert js.status_code == 200
    assert "javascript" in js.headers["content-type"]


@pytest.mark.asyncio
async def test_api_routes_are_not_shadowed_by_the_mount(client: httpx.AsyncClient) -> None:
    me = await client.get("/api/auth/me")
    assert me.status_code == 401
    assert me.headers["content-type"].startswith("application/json")
    health = await client.get("/health")
    assert health.status_code in (200, 503)
    assert health.headers["content-type"].startswith("application/json")


@pytest.mark.asyncio
async def test_unknown_api_path_is_404_not_the_html_shell(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/does-not-exist")
    assert response.status_code == 404
    assert "text/html" not in response.headers.get("content-type", "")
