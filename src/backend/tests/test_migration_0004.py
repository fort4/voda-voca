# 2026-11-26 - voda-voca - 마이그레이션 0004 테스트: 일차 컬럼 추가가 기존 학습 이력을 보존하는지 확인 (REQ-165)
# 파일 위치: src/backend/tests/test_migration_0004.py

import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from backend.core.config import get_settings
from backend.db import session as session_module

pytestmark = pytest.mark.no_db  # 임시 SQLite 파일만 쓴다

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _config() -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    return config


def _clear_caches() -> None:
    for cached in (get_settings, session_module.get_engine, session_module.get_session_factory):
        cached.cache_clear()


def _query(db_file: Path, sql: str) -> list[tuple]:
    connection = sqlite3.connect(db_file)
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        rows = connection.execute(sql).fetchall()
        connection.commit()
        return rows
    finally:
        connection.close()


def _table_sql(db_file: Path) -> str:
    return _query(db_file, "SELECT sql FROM sqlite_master WHERE name = 'study_logs'")[0][0]


@pytest.fixture
def database_with_history(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """0003 상태의 DB 에 단어장·단어·사용자·학습 이력을 넣는다."""
    db_file = tmp_path / "mig.db"
    monkeypatch.setenv("DB_PATH", str(db_file))
    _clear_caches()
    command.upgrade(_config(), "0003")
    for sql in (
        "INSERT INTO system_vocabularies (id, slug, title, category) VALUES (1, 'beginner', '초급', 'ELEMENTARY')",
        "INSERT INTO system_words (id, vocabulary_id, term, meaning) VALUES (1, 1, 'apple', '사과')",
        "INSERT INTO users (id, nickname, password_hash) VALUES (1, 'u1', 'x')",
        "INSERT INTO study_logs (user_id, word_id, is_correct, mode) VALUES (1, 1, 1, 'quiz')",
    ):
        _query(db_file, sql)
    yield db_file
    _clear_caches()


def test_upgrade_keeps_history_and_leaves_the_day_empty(database_with_history: Path) -> None:
    before = _table_sql(database_with_history)

    command.upgrade(_config(), "0004")

    assert _query(database_with_history, "SELECT user_id, word_id, is_correct, mode, study_day FROM study_logs") == [
        (1, 1, 1, "quiz", None)
    ]
    after = _table_sql(database_with_history)
    assert "study_day" in after
    # 테이블을 다시 만들지 않았다: 제약이 그대로다
    for constraint in ("ck_study_logs_mode", "ck_study_logs_direction", "ck_study_logs_format", "fk_study_logs_user"):
        assert constraint in before and constraint in after


def test_downgrade_removes_only_the_column(database_with_history: Path) -> None:
    command.upgrade(_config(), "0004")

    command.downgrade(_config(), "0003")

    assert "study_day" not in _table_sql(database_with_history)
    assert _query(database_with_history, "SELECT count(*) FROM study_logs") == [(1,)]
