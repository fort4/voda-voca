# 2026-11-26 - voda-voca - 마이그레이션 0006 테스트: 순위 공개 컬럼 추가가 기존 계정을 비공개로 두고 데이터와 NOCASE 를 보존하는지 확인 (#42, REQ-173)
# 파일 위치: src/backend/tests/test_migration_0006.py

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


def _counts(db_file: Path) -> list[int]:
    tables = ("users", "system_vocabularies", "system_words", "study_logs")
    return [_query(db_file, f"SELECT count(*) FROM {t}")[0][0] for t in tables]


@pytest.fixture
def database(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """0005 상태의 DB: 사용자 한 명과 그의 학습 기록."""
    db_file = tmp_path / "mig.db"
    monkeypatch.setenv("DB_PATH", str(db_file))
    _clear_caches()
    command.upgrade(_config(), "0005")
    for sql in (
        "INSERT INTO users (id, nickname, password_hash) VALUES (1, 'Minji', 'x')",
        "INSERT INTO system_vocabularies (id, slug, title, category, owner_id, source) VALUES (1, 'u-1', '내 단어장', 'PERSONAL', 1, 'user')",
        "INSERT INTO system_words (id, vocabulary_id, term, meaning) VALUES (1, 1, 'apple', '사과')",
        "INSERT INTO study_logs (user_id, word_id, is_correct, mode) VALUES (1, 1, 1, 'quiz')",
    ):
        _query(db_file, sql)
    yield db_file
    _clear_caches()


def test_existing_accounts_become_private_and_keep_every_row(database: Path) -> None:
    before = _counts(database)

    command.upgrade(_config(), "0006")

    assert _counts(database) == before
    assert _query(database, "SELECT ranking_public FROM users") == [(0,)]


def test_new_rows_default_to_private(database: Path) -> None:
    command.upgrade(_config(), "0006")

    _query(database, "INSERT INTO users (id, nickname, password_hash) VALUES (2, 'new', 'x')")

    assert _query(database, "SELECT ranking_public FROM users WHERE id = 2") == [(0,)]


def test_upgrade_does_not_rebuild_the_users_table(database: Path) -> None:
    command.upgrade(_config(), "0006")

    sql = _query(database, "SELECT sql FROM sqlite_master WHERE name = 'users'")[0][0]
    for kept in ("NOCASE", "uk_users_nickname", "ck_users_nickname_not_blank", "fk_users_active_vocabulary"):
        assert kept in sql, kept
    assert _query(database, "SELECT id FROM users WHERE nickname = 'minji'") == [(1,)]


def test_downgrade_removes_only_the_column(database: Path) -> None:
    command.upgrade(_config(), "0006")
    before = _counts(database)

    command.downgrade(_config(), "0005")

    assert _counts(database) == before
    assert "ranking_public" not in [r[1] for r in _query(database, "PRAGMA table_info(users)")]
