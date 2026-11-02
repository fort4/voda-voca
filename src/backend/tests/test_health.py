# 2026-11-02 - voda-voca - /health 엔드포인트 테스트: DB 연결 성공 및 실패(503) 경로
# 파일 위치: src/backend/tests/test_health.py

from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio

from backend.core.config import get_settings
from backend.db.session import get_engine, get_session_factory
from backend.main import app


@pytest_asyncio.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_health_reports_db_connected(client: httpx.AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": "connected"}


@pytest.mark.asyncio
async def test_health_returns_503_when_db_unreachable(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 아무 프로세스도 듣지 않는 포트로 바꿔 연결을 실패시킨다.
    monkeypatch.setenv("MYSQL_PORT", "1")
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    try:
        response = await client.get("/health")
        assert response.status_code == 503
        assert response.json() == {"status": "error", "db": "disconnected"}
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()
        get_engine.cache_clear()
        get_session_factory.cache_clear()
