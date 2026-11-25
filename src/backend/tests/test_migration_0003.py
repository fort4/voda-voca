# 2026-11-26 - voda-voca - 마이그레이션 0003 테스트: 출처 컬럼 추가가 기존 데이터, 학습 이력, NOCASE 를 보존하는지 확인 (REQ-160, REQ-161)
# 파일 위치: src/backend/tests/test_migration_0003.py

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


@pytest.fixture
def database_with_history(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """0002 상태의 DB 에 단어장·단어·사용자·학습 이력·북마크를 넣는다."""
    db_file = tmp_path / "mig.db"
    monkeypatch.setenv("DB_PATH", str(db_file))
    _clear_caches()
    command.upgrade(_config(), "0002")
    for sql in (
        "INSERT INTO system_vocabularies (id, slug, title, category) VALUES (1, 'Beginner', '초급', 'ELEMENTARY')",
        "INSERT INTO system_words (id, vocabulary_id, term, meaning) VALUES (1, 1, 'Apple', '사과')",
        "INSERT INTO users (id, nickname, password_hash, active_vocabulary_id) VALUES (1, 'u1', 'x', 1)",
        "INSERT INTO study_logs (user_id, word_id, is_correct, mode) VALUES (1, 1, 1, 'quiz')",
        "INSERT INTO bookmarks (user_id, word_id) VALUES (1, 1)",
    ):
        _query(db_file, sql)
    yield db_file
    _clear_caches()


def _assert_preserved(db_file: Path) -> None:
    assert _query(db_file, "SELECT term, meaning FROM system_words") == [("Apple", "사과")]
    assert _query(db_file, "SELECT count(*) FROM study_logs") == [(1,)]
    assert _query(db_file, "SELECT count(*) FROM bookmarks") == [(1,)]
    assert _query(db_file, "SELECT active_vocabulary_id FROM users") == [(1,)]
    # NOCASE 가 남아 있어야 표제어·slug 가 대소문자와 무관하게 유일하다
    assert _query(db_file, "SELECT count(*) FROM system_words WHERE term = 'APPLE'") == [(1,)]
    assert _query(db_file, "SELECT count(*) FROM system_vocabularies WHERE slug = 'beginner'") == [(1,)]
    with pytest.raises(sqlite3.IntegrityError):
        _query(db_file, "INSERT INTO system_words (vocabulary_id, term, meaning) VALUES (1, 'aPPle', '중복')")


def test_upgrade_marks_existing_rows_as_seed_and_preserves_data(database_with_history: Path) -> None:
    command.upgrade(_config(), "0003")

    assert _query(database_with_history, "SELECT source FROM system_words") == [("seed",)]
    assert _query(database_with_history, "SELECT source FROM system_vocabularies") == [("seed",)]
    _assert_preserved(database_with_history)


def test_downgrade_removes_the_columns_and_preserves_data(database_with_history: Path) -> None:
    command.upgrade(_config(), "0003")
    command.downgrade(_config(), "0002")

    for table in ("system_words", "system_vocabularies"):
        columns = [row[1] for row in _query(database_with_history, f"PRAGMA table_info({table})")]
        assert "source" not in columns, table
    _assert_preserved(database_with_history)
