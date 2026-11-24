# 2026-11-02 - voda-voca - 정적 프론트엔드 마운트 검증: 루트·자산 서빙, API 라우트 비가림 (REQ-116, 같은 출처 배포)
# 파일 위치: src/backend/tests/test_static_mount.py

from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio

from backend.main import app


pytestmark = pytest.mark.no_db  # MySQL 없이 통과해야 한다 (test_no_db_guard.py)


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


@pytest.mark.asyncio
async def test_vendor_font_is_served_with_font_mime_type(client: httpx.AsyncClient) -> None:
    """woff2 는 font/woff2 로 나가야 한다. 시스템 mime.types 가 없는 slim 컨테이너에서는 파이썬이 이 확장자를
    몰라 application/octet-stream 이 되므로, 앱이 직접 등록해 환경과 무관하게 같은 값을 보장한다."""
    response = await client.get("/vendor/fonts/Paperlogy-7Bold.woff2")
    assert response.status_code == 200
    assert response.headers["content-type"] == "font/woff2"


VENDOR_CACHE = "public, max-age=31536000, immutable"


@pytest.mark.asyncio
async def test_vendor_files_are_cached_for_a_year_because_versions_are_in_the_path(client: httpx.AsyncClient) -> None:
    """vendor/ 는 파일명·폴더에 버전이 들어 있어(tailwindcss-3.4.17.js) 바뀌면 경로가 바뀐다. 오래 캐시해도 안전하다."""
    for path in ["/vendor/tailwindcss-3.4.17.js", "/vendor/fonts/Paperlogy-7Bold.woff2"]:
        response = await client.get(path)
        assert response.status_code == 200
        assert response.headers["cache-control"] == VENDOR_CACHE, path


@pytest.mark.asyncio
async def test_app_own_files_are_not_given_a_long_cache(client: httpx.AsyncClient) -> None:
    """app.js/app.css 는 파일명에 버전이 없고 자주 고친다. 긴 캐시를 주면 사용자가 옛 화면을 계속 본다."""
    for path in ["/", "/js/app.js", "/css/app.css"]:
        response = await client.get(path)
        assert "max-age" not in response.headers.get("cache-control", ""), path


@pytest.mark.asyncio
async def test_vendor_conditional_request_still_returns_304_with_cache_header(client: httpx.AsyncClient) -> None:
    first = await client.get("/vendor/tailwindcss-3.4.17.js")
    second = await client.get("/vendor/tailwindcss-3.4.17.js", headers={"If-None-Match": first.headers["etag"]})
    assert second.status_code == 304
    assert second.headers["cache-control"] == VENDOR_CACHE
