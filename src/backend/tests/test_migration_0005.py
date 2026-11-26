# 2026-11-26 - voda-voca - 마이그레이션 0005 테스트: 단어장 소유자 컬럼 추가가 단어·학습 기록을 보존하고 관리자 등록분을 개인 단어장으로 바꾸는지 확인 (#38)
# 파일 위치: src/backend/tests/test_migration_0005.py

import sqlite3
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from backend.core.config import get_settings
from backend.db import session as session_module
from backend.models import Base

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
    tables = ("system_vocabularies", "system_words", "study_logs", "bookmarks", "users")
    return [_query(db_file, f"SELECT count(*) FROM {t}")[0][0] for t in tables]


def _prepare(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *, admin_nickname: str | None) -> Path:
    """0004 상태의 DB: 표준 단어장(관리자가 더한 단어 1개 포함), 관리자 단어장, 두 사용자의 기록."""
    db_file = tmp_path / "mig.db"
    monkeypatch.setenv("DB_PATH", str(db_file))
    _clear_caches()
    command.upgrade(_config(), "0004")
    statements = [
        "INSERT INTO system_vocabularies (id, slug, title, category) VALUES (1, 'beginner', '초급', 'ELEMENTARY')",
        "INSERT INTO system_vocabularies (id, slug, title, category, source) VALUES (2, 'admin-1', '수업', 'ETC', 'admin')",
        "INSERT INTO system_words (id, vocabulary_id, term, meaning) VALUES (1, 1, 'apple', '사과')",
        "INSERT INTO system_words (id, vocabulary_id, term, meaning, source) VALUES (2, 1, 'extra', '추가', 'admin')",
        "INSERT INTO system_words (id, vocabulary_id, term, meaning, source) VALUES (3, 2, 'class', '수업', 'admin')",
        "INSERT INTO users (id, nickname, password_hash) VALUES (1, 'u1', 'x')",
        "INSERT INTO study_logs (user_id, word_id, is_correct, mode) VALUES (1, 1, 1, 'quiz')",
        "INSERT INTO study_logs (user_id, word_id, is_correct, mode) VALUES (1, 3, 0, 'quiz')",
        "INSERT INTO bookmarks (user_id, word_id) VALUES (1, 3)",
        "UPDATE users SET active_vocabulary_id = 2 WHERE id = 1",
    ]
    if admin_nickname:
        statements.append(f"INSERT INTO users (id, nickname, password_hash) VALUES (2, '{admin_nickname}', 'x')")
    for sql in statements:
        _query(db_file, sql)
    return db_file


@pytest.fixture
def database(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    yield _prepare(monkeypatch, tmp_path, admin_nickname="Admin")
    _clear_caches()


def test_upgrade_keeps_every_row(database: Path) -> None:
    before = _counts(database)

    command.upgrade(_config(), "0005")

    assert _counts(database) == before
    assert _query(database, "SELECT active_vocabulary_id FROM users WHERE id = 1") == [(2,)]


def test_admin_vocabularies_become_personal_ones_of_that_account(database: Path) -> None:
    command.upgrade(_config(), "0005")

    assert _query(database, "SELECT id, owner_id, source FROM system_vocabularies ORDER BY id") == [
        (1, None, "seed"),
        (2, 2, "user"),
    ]
    # 표준 단어장에 더했던 단어는 공용으로 남고, 개인 단어장의 단어만 출처가 바뀐다
    assert _query(database, "SELECT id, source FROM system_words ORDER BY id") == [(1, "seed"), (2, "admin"), (3, "user")]


def test_without_the_admin_account_the_vocabulary_stays_shared(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    database = _prepare(monkeypatch, tmp_path, admin_nickname=None)

    command.upgrade(_config(), "0005")

    assert _query(database, "SELECT owner_id, source FROM system_vocabularies WHERE id = 2") == [(None, "admin")]
    _clear_caches()


def test_upgrade_does_not_rebuild_the_table(database: Path) -> None:
    command.upgrade(_config(), "0005")

    sql = _query(database, "SELECT sql FROM sqlite_master WHERE name = 'system_vocabularies'")[0][0]
    for kept in ("uk_sysvoc_slug", "ck_sysvoc_level_range", "ck_sysvoc_title_not_blank", "NOCASE"):
        assert kept in sql, kept
    assert "idx_sysvoc_owner" in {r[0] for r in _query(database, "SELECT name FROM sqlite_master WHERE type = 'index'")}


def test_deleting_the_owner_removes_only_that_users_vocabulary(database: Path) -> None:
    command.upgrade(_config(), "0005")

    _query(database, "DELETE FROM users WHERE id = 2")

    assert _query(database, "SELECT id FROM system_vocabularies") == [(1,)]
    assert _query(database, "SELECT id FROM system_words ORDER BY id") == [(1,), (2,)]
    assert _query(database, "SELECT word_id FROM study_logs") == [(1,)]
    assert _query(database, "SELECT active_vocabulary_id FROM users WHERE id = 1") == [(None,)]


def test_downgrade_removes_only_the_column(database: Path) -> None:
    command.upgrade(_config(), "0005")
    before = _counts(database)

    command.downgrade(_config(), "0004")

    assert _counts(database) == before
    columns = [r[1] for r in _query(database, "PRAGMA table_info(system_vocabularies)")]
    assert "owner_id" not in columns


@pytest.mark.parametrize("built_by", ["migration", "models"])
def test_owner_foreign_key_cascades(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, built_by: str) -> None:
    """alembic check 가 이 외래키를 비교하지 않으므로 마이그레이션과 모델 양쪽을 직접 확인한다."""
    db_file = tmp_path / f"{built_by}.db"
    monkeypatch.setenv("DB_PATH", str(db_file))
    _clear_caches()
    if built_by == "migration":
        command.upgrade(_config(), "head")
    else:
        engine = sa.create_engine(f"sqlite:///{db_file}")
        Base.metadata.create_all(engine)
        engine.dispose()
    keys = _query(db_file, "PRAGMA foreign_key_list(system_vocabularies)")
    assert [(k[2], k[3], k[4], k[6]) for k in keys] == [("users", "owner_id", "id", "CASCADE")]
    _clear_caches()
