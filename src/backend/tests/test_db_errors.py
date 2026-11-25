# 2026-11-25 - voda-voca - SQLite 무결성 오류 판별 헬퍼 단위 테스트 (제약 이름이 아닌 테이블.컬럼 기준, ADR-010)
# 파일 위치: src/backend/tests/test_db_errors.py

import pytest
from sqlalchemy.exc import IntegrityError

from backend.db.errors import is_foreign_key_violation, is_unique_violation

pytestmark = pytest.mark.no_db


def _error(message: str) -> IntegrityError:
    return IntegrityError("INSERT ...", {}, Exception(message))


def test_unique_violation_matches_table_and_columns() -> None:
    exc = _error("UNIQUE constraint failed: bookmarks.user_id, bookmarks.word_id")
    assert is_unique_violation(exc, "bookmarks", "user_id", "word_id")


def test_unique_violation_ignores_column_order() -> None:
    exc = _error("UNIQUE constraint failed: bookmarks.word_id, bookmarks.user_id")
    assert is_unique_violation(exc, "bookmarks", "user_id", "word_id")


def test_unique_violation_rejects_other_table_or_columns() -> None:
    exc = _error("UNIQUE constraint failed: users.nickname")
    assert not is_unique_violation(exc, "bookmarks", "user_id", "word_id")
    assert not is_unique_violation(exc, "users", "email")
    # 일부 컬럼만 겹치는 다른 제약은 같은 것으로 보지 않는다.
    partial = _error("UNIQUE constraint failed: bookmarks.user_id")
    assert not is_unique_violation(partial, "bookmarks", "user_id", "word_id")


def test_unique_violation_is_false_for_other_error_kinds() -> None:
    assert not is_unique_violation(_error("FOREIGN KEY constraint failed"), "users", "nickname")
    assert not is_unique_violation(_error("NOT NULL constraint failed: users.nickname"), "users", "nickname")


def test_foreign_key_violation() -> None:
    assert is_foreign_key_violation(_error("FOREIGN KEY constraint failed"))
    assert not is_foreign_key_violation(_error("UNIQUE constraint failed: users.nickname"))
