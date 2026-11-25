# 2026-11-25 - voda-voca - SQLite 엔진 연결 설정 테스트: 외래키 강제, WAL, busy_timeout, 풀 사전 점검 제거
# 파일 위치: src/backend/tests/test_sqlite_engine.py

from pathlib import Path

import pytest
from sqlalchemy import text

from backend.core.config import get_settings
from backend.db import session as session_module

pytestmark = pytest.mark.no_db


@pytest.fixture
def sqlite_engine_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    db_file = tmp_path / "voca.db"
    monkeypatch.setenv("DB_PATH", str(db_file))
    for cached in (get_settings, session_module.get_engine, session_module.get_session_factory):
        cached.cache_clear()
    yield db_file
    for cached in (get_settings, session_module.get_engine, session_module.get_session_factory):
        cached.cache_clear()


async def _pragma(name: str) -> object:
    async with session_module.get_engine().connect() as conn:
        return (await conn.execute(text(f"PRAGMA {name}"))).scalar_one()


@pytest.mark.asyncio
async def test_foreign_keys_are_enforced(sqlite_engine_env: Path) -> None:
    # SQLite 는 기본이 꺼져 있어 ON DELETE CASCADE 가 동작하지 않는다. 연결마다 켜야 한다.
    assert await _pragma("foreign_keys") == 1
    await session_module.dispose_engine()


@pytest.mark.asyncio
async def test_journal_mode_is_wal(sqlite_engine_env: Path) -> None:
    assert str(await _pragma("journal_mode")).lower() == "wal"
    await session_module.dispose_engine()


@pytest.mark.asyncio
async def test_busy_timeout_is_set(sqlite_engine_env: Path) -> None:
    # 쓰기 충돌 시 즉시 실패하지 않고 잠시 기다린다 (SQLite 는 쓰기를 한 번에 하나만 허용한다).
    assert int(await _pragma("busy_timeout")) >= 5000
    await session_module.dispose_engine()


@pytest.mark.asyncio
async def test_missing_parent_directory_is_created(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # 처음 실행 시 빈 DB 로 시작할 수 있어야 한다 (VOCA-NFR-003).
    db_file = tmp_path / "nested" / "voca.db"
    monkeypatch.setenv("DB_PATH", str(db_file))
    for cached in (get_settings, session_module.get_engine, session_module.get_session_factory):
        cached.cache_clear()
    try:
        async with session_module.get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
        assert db_file.exists()
    finally:
        await session_module.dispose_engine()
        get_settings.cache_clear()
