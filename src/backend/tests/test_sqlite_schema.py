# 2026-11-25 - voda-voca - SQLite 스키마 테스트: 방언 제거, 기본값, 제약, 닉네임 대소문자, CASCADE, 마이그레이션-모델 일치 (ADR-010)
# 파일 위치: src/backend/tests/test_sqlite_schema.py

import re
from pathlib import Path

import pytest
import pytest_asyncio
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from backend.core.config import get_settings
from backend.db import session as session_module
from backend.models import AuthSession, Base, User

pytestmark = pytest.mark.no_db  # 임시 SQLite 파일만 쓴다. DB 서버가 필요 없다.

BACKEND_DIR = Path(__file__).resolve().parents[1]


@pytest_asyncio.fixture
async def empty_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """빈 SQLite 파일에 모델 정의로 테이블을 만든다."""
    monkeypatch.setenv("DB_PATH", str(tmp_path / "voca.db"))
    for cached in (get_settings, session_module.get_engine, session_module.get_session_factory):
        cached.cache_clear()
    async with session_module.get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield session_module.get_session_factory()
    await session_module.dispose_engine()
    get_settings.cache_clear()


# ---------- 1. 방언 잔재 제거 (회귀 방지) ----------


def test_models_use_no_mysql_dialect_or_table_options() -> None:
    for table in Base.metadata.tables.values():
        assert not [k for k in table.kwargs if k.startswith("mysql_")], table.name
        for column in table.columns:
            assert "mysql" not in type(column.type).__module__, f"{table.name}.{column.name}"


@pytest.mark.parametrize("path", sorted((BACKEND_DIR).glob("[!t]*/**/*.py")) + [BACKEND_DIR / "main.py"])
def test_source_has_no_mysql_only_sql(path: Path) -> None:
    if "alembic/versions" in path.as_posix() or "__pycache__" in path.as_posix():
        pytest.skip("마이그레이션은 test_migration_* 가 검사한다")
    text_ = path.read_text(encoding="utf-8")
    code = "\n".join(line for line in text_.splitlines() if not line.lstrip().startswith("#"))
    forbidden = r"dialects\.mysql|UTC_TIMESTAMP|JSON_OBJECT|CHAR_LENGTH|on_duplicate_key|INTERVAL \d+ HOUR|date_add"
    assert not re.search(forbidden, code), f"{path.name}: MySQL 전용 구문이 남아 있다"


# ---------- 2. 기본값과 시각 ----------


@pytest.mark.asyncio
async def test_created_at_default_is_utc_with_millisecond_precision(empty_db) -> None:
    async with empty_db() as db:
        db.add(User(nickname="alice", password_hash="x"))
        await db.commit()
        user = (await db.execute(select(User))).scalar_one()
        assert user.created_at.year >= 2026
        # 밀리초가 마이크로초로 잘못 읽히면(123 → 0.000123초) 값이 과거로 어긋난다. 현재 시각과 1분 안이어야 한다.
        from backend.models.base import utcnow

        assert abs((utcnow() - user.created_at).total_seconds()) < 60
        assert user.quiz_count == user.flashcard_count == user.daily_goal == 10


# ---------- 3. 제약 ----------


@pytest.mark.asyncio
async def test_nickname_is_unique_ignoring_case(empty_db) -> None:
    async with empty_db() as db:
        db.add(User(nickname="Alice", password_hash="x"))
        await db.commit()
        db.add(User(nickname="aLiCe", password_hash="x"))
        with pytest.raises(IntegrityError):
            await db.commit()


@pytest.mark.asyncio
async def test_nickname_lookup_ignores_case(empty_db) -> None:
    async with empty_db() as db:
        db.add(User(nickname="Alice", password_hash="x"))
        await db.commit()
        found = (await db.execute(select(User).where(User.nickname == "ALICE"))).scalar_one_or_none()
        assert found is not None


@pytest.mark.asyncio
async def test_blank_nickname_is_rejected(empty_db) -> None:
    async with empty_db() as db:
        db.add(User(nickname="   ", password_hash="x"))
        with pytest.raises(IntegrityError):
            await db.commit()


@pytest.mark.asyncio
async def test_non_positive_quiz_count_is_rejected(empty_db) -> None:
    async with empty_db() as db:
        db.add(User(nickname="bob", password_hash="x", quiz_count=0))
        with pytest.raises(IntegrityError):
            await db.commit()


# ---------- 4. 외래키 CASCADE ----------


@pytest.mark.asyncio
async def test_deleting_user_cascades_to_sessions(empty_db) -> None:
    from datetime import datetime, timedelta

    async with empty_db() as db:
        user = User(nickname="carol", password_hash="x")
        db.add(user)
        await db.flush()
        db.add(AuthSession(id=b"\x01" * 32, user_id=user.id, expires_at=datetime.now() + timedelta(days=1)))
        await db.commit()
        await db.delete(user)
        await db.commit()
        assert (await db.execute(text("SELECT count(*) FROM sessions"))).scalar_one() == 0


@pytest.mark.asyncio
async def test_binary_primary_key_round_trips(empty_db) -> None:
    from datetime import datetime, timedelta

    token_hash = bytes(range(32))
    async with empty_db() as db:
        user = User(nickname="dave", password_hash="x")
        db.add(user)
        await db.flush()
        db.add(AuthSession(id=token_hash, user_id=user.id, expires_at=datetime.now() + timedelta(days=1)))
        await db.commit()
        got = (await db.execute(select(AuthSession).where(AuthSession.id == token_hash))).scalar_one()
        assert got.id == token_hash


# ---------- 5. 마이그레이션 ----------


def _alembic_config(db_path: Path) -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    return cfg


def test_migration_history_is_single_sqlite_initial_revision() -> None:
    versions = [p for p in (BACKEND_DIR / "alembic" / "versions").glob("*.py")]
    assert len(versions) == 1, [p.name for p in versions]
    source = versions[0].read_text(encoding="utf-8")
    assert not re.search(r"dialects import mysql|mysql_|UTC_TIMESTAMP|JSON_OBJECT", source)


def test_migration_upgrade_on_empty_db_matches_models(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import sqlalchemy as sa

    db_file = tmp_path / "mig.db"
    monkeypatch.setenv("DB_PATH", str(db_file))
    for cached in (get_settings, session_module.get_engine, session_module.get_session_factory):
        cached.cache_clear()
    command.upgrade(_alembic_config(db_file), "head")

    engine = sa.create_engine(f"sqlite:///{db_file}")
    with engine.connect() as conn:
        diff = compare_metadata(
            MigrationContext.configure(conn, opts={"compare_type": True}), Base.metadata
        )
    engine.dispose()
    get_settings.cache_clear()
    assert diff == [], diff
