# 2026-11-05 - voda-voca - 중앙 제공형 단어장 모델(system_vocabularies, system_words, user_word_progress) 구조·제약 테스트
# 파일 위치: src/backend/tests/test_system_models.py

import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import CheckConstraint, Enum, String, delete, text
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.exc import DBAPIError, IntegrityError

from backend.db.session import get_session_factory
from backend.models import Base, SystemVocabulary, SystemWord, User, UserWordProgress

SLUG_PREFIX = "tvoda-"

# 파일의 async 테스트(DB 제약 검사)는 모두 이벤트 루프에서 실행한다.
_ASYNC = pytest.mark.asyncio


def _table(name: str):
    return Base.metadata.tables[name]


# ---------------------------------------------------------------------------
# 1. 모델 구조 (DB 없이 메타데이터만 검사)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("table", "columns"),
    [
        ("system_vocabularies", ["id"]),
        ("system_words", ["id", "vocabulary_id"]),
        ("user_word_progress", ["id", "user_id", "word_id"]),
        ("users", ["active_vocabulary_id"]),
    ],
)
def test_pk_fk_columns_are_bigint_unsigned(table: str, columns: list[str]) -> None:
    """모든 PK/FK 는 기존 스키마 규격인 BIGINT UNSIGNED 다 (INT 금지)."""
    for name in columns:
        col_type = _table(table).c[name].type
        assert isinstance(col_type, BIGINT), f"{table}.{name}"
        assert col_type.unsigned is True, f"{table}.{name}"


def test_category_is_free_string_with_index() -> None:
    """category 는 VARCHAR(50) 자유 문자열이다. 열거형·CHECK 로 막으면 새 카테고리마다 스키마를 바꿔야 한다."""
    table = _table("system_vocabularies")
    col_type = table.c.category.type
    assert isinstance(col_type, String) and not isinstance(col_type, Enum)
    assert col_type.length == 50
    assert table.c.category.nullable is False
    assert any("category" in [c.name for c in idx.columns] for idx in table.indexes)
    for constraint in table.constraints:
        if isinstance(constraint, CheckConstraint):
            assert "category" not in str(constraint.sqltext)


@pytest.mark.parametrize("column", ["pos", "phonetic", "level"])
def test_word_extension_fields_are_nullable(column: str) -> None:
    """확장 필드는 DDL 에만 두고 NULL 을 허용한다 (1단계에서는 쓰지 않는다)."""
    assert _table("system_words").c[column].nullable is True


def test_word_core_fields_keep_existing_names() -> None:
    columns = _table("system_words").c
    for name in ("term", "meaning", "example", "example_meaning", "order_index"):
        assert name in columns
    assert columns.term.nullable is False
    assert columns.meaning.nullable is False
    assert columns.example.nullable is True
    assert columns.example_meaning.nullable is True


def test_progress_has_consecutive_counter_and_defaults() -> None:
    columns = _table("user_word_progress").c
    for name in (
        "correct_count",
        "wrong_count",
        "consecutive_correct_count",
        "is_memorized",
        "last_result",
        "last_studied_at",
    ):
        assert name in columns
    assert columns.last_result.nullable is True
    assert columns.last_studied_at.nullable is True
    assert columns.is_memorized.nullable is False


def test_users_active_vocabulary_is_nullable_fk_set_null() -> None:
    column = _table("users").c.active_vocabulary_id
    assert column.nullable is True
    (fk,) = column.foreign_keys
    assert fk.column.table.name == "system_vocabularies"
    assert fk.ondelete == "SET NULL"


# ---------------------------------------------------------------------------
# 2. DB 제약 (Alembic 마이그레이션이 적용된 MySQL 에서 실행)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(autouse=True)
async def _cleanup_slugs() -> AsyncIterator[None]:
    await _delete_test_vocabularies()
    yield
    await _delete_test_vocabularies()


async def _delete_test_vocabularies() -> None:
    async with get_session_factory()() as session:
        await session.execute(delete(SystemVocabulary).where(SystemVocabulary.slug.like(f"{SLUG_PREFIX}%")))
        await session.commit()


def _vocabulary(**overrides: object) -> SystemVocabulary:
    values: dict[str, object] = {
        "slug": f"{SLUG_PREFIX}{uuid.uuid4().hex[:8]}",
        "title": "테스트 단어장",
        "category": "ELEMENTARY",
        "level": 1,
    }
    values.update(overrides)
    return SystemVocabulary(**values)


async def _add_vocabulary_with_word(session, term: str = "apple") -> tuple[SystemVocabulary, SystemWord]:
    vocabulary = _vocabulary()
    session.add(vocabulary)
    await session.flush()
    word = SystemWord(vocabulary_id=vocabulary.id, term=term, meaning="사과")
    session.add(word)
    await session.flush()
    return vocabulary, word


async def _add_user(session) -> User:
    user = User(nickname=f"tvoda-{uuid.uuid4().hex[:8]}", password_hash="x")
    session.add(user)
    await session.flush()
    return user


@_ASYNC
async def test_vocabulary_defaults_and_new_category_needs_no_schema_change() -> None:
    async with get_session_factory()() as session:
        vocabulary = _vocabulary(category="BUSINESS")
        session.add(vocabulary)
        await session.commit()
        await session.refresh(vocabulary)
        assert vocabulary.category == "BUSINESS"
        assert vocabulary.total_words == 0
        assert vocabulary.sort_order == 0
        assert vocabulary.created_at is not None


@_ASYNC
async def test_duplicate_slug_is_rejected() -> None:
    async with get_session_factory()() as session:
        session.add(_vocabulary(slug=f"{SLUG_PREFIX}dup"))
        session.add(_vocabulary(slug=f"{SLUG_PREFIX}dup"))
        with pytest.raises(IntegrityError):
            await session.commit()


@_ASYNC
@pytest.mark.parametrize("level", [0, 6])
async def test_vocabulary_level_must_be_1_to_5(level: int) -> None:
    async with get_session_factory()() as session:
        session.add(_vocabulary(level=level))
        with pytest.raises((IntegrityError, DBAPIError)):
            await session.commit()


@_ASYNC
async def test_word_term_is_unique_within_vocabulary() -> None:
    async with get_session_factory()() as session:
        vocabulary, _ = await _add_vocabulary_with_word(session, "apple")
        session.add(SystemWord(vocabulary_id=vocabulary.id, term="apple", meaning="다른 뜻"))
        with pytest.raises(IntegrityError):
            await session.flush()


@_ASYNC
async def test_same_term_is_allowed_in_different_vocabularies() -> None:
    async with get_session_factory()() as session:
        await _add_vocabulary_with_word(session, "apple")
        await _add_vocabulary_with_word(session, "apple")
        await session.commit()


@_ASYNC
@pytest.mark.parametrize(("term", "meaning"), [("   ", "뜻"), ("word", "   ")])
async def test_blank_term_or_meaning_is_rejected(term: str, meaning: str) -> None:
    async with get_session_factory()() as session:
        vocabulary = _vocabulary()
        session.add(vocabulary)
        await session.flush()
        session.add(SystemWord(vocabulary_id=vocabulary.id, term=term, meaning=meaning))
        with pytest.raises((IntegrityError, DBAPIError)):
            await session.flush()


@_ASYNC
async def test_word_extension_fields_default_to_null() -> None:
    async with get_session_factory()() as session:
        _, word = await _add_vocabulary_with_word(session)
        await session.refresh(word)
        assert (word.pos, word.phonetic, word.level) == (None, None, None)
        assert (word.example, word.example_meaning) == (None, None)
        assert word.order_index == 0


@_ASYNC
async def test_deleting_vocabulary_cascades_to_words_and_progress() -> None:
    async with get_session_factory()() as session:
        user = await _add_user(session)
        vocabulary, word = await _add_vocabulary_with_word(session)
        session.add(UserWordProgress(user_id=user.id, word_id=word.id))
        await session.commit()
        vocabulary_id, word_id = vocabulary.id, word.id

        await session.delete(vocabulary)
        await session.commit()

        words = await session.execute(text("SELECT COUNT(*) FROM system_words WHERE id = :i"), {"i": word_id})
        rows = await session.execute(text("SELECT COUNT(*) FROM user_word_progress WHERE word_id = :i"), {"i": word_id})
        assert words.scalar_one() == 0
        assert rows.scalar_one() == 0
        assert vocabulary_id is not None


@_ASYNC
async def test_progress_defaults_and_unique_per_user_word() -> None:
    async with get_session_factory()() as session:
        user = await _add_user(session)
        _, word = await _add_vocabulary_with_word(session)
        progress = UserWordProgress(user_id=user.id, word_id=word.id)
        session.add(progress)
        await session.flush()
        await session.refresh(progress)
        assert progress.correct_count == 0
        assert progress.wrong_count == 0
        assert progress.consecutive_correct_count == 0
        assert progress.is_memorized is False
        assert progress.last_result is None
        assert progress.last_studied_at is None

        session.add(UserWordProgress(user_id=user.id, word_id=word.id))
        with pytest.raises(IntegrityError):
            await session.flush()


@_ASYNC
async def test_progress_last_result_accepts_only_correct_or_wrong() -> None:
    async with get_session_factory()() as session:
        user = await _add_user(session)
        _, word = await _add_vocabulary_with_word(session)
        session.add(UserWordProgress(user_id=user.id, word_id=word.id, last_result="CORRECT"))
        await session.flush()
        await session.execute(text("UPDATE user_word_progress SET last_result = 'WRONG' WHERE word_id = :i"), {"i": word.id})
        with pytest.raises((IntegrityError, DBAPIError)):
            await session.execute(
                text("UPDATE user_word_progress SET last_result = 'MAYBE' WHERE word_id = :i"), {"i": word.id}
            )


@_ASYNC
async def test_deleting_user_cascades_progress() -> None:
    async with get_session_factory()() as session:
        user = await _add_user(session)
        _, word = await _add_vocabulary_with_word(session)
        session.add(UserWordProgress(user_id=user.id, word_id=word.id))
        await session.commit()
        await session.delete(user)
        await session.commit()
        rows = await session.execute(text("SELECT COUNT(*) FROM user_word_progress WHERE word_id = :i"), {"i": word.id})
        assert rows.scalar_one() == 0


@_ASYNC
async def test_deleting_active_vocabulary_sets_user_column_to_null() -> None:
    async with get_session_factory()() as session:
        vocabulary = _vocabulary()
        session.add(vocabulary)
        await session.flush()
        user = await _add_user(session)
        user.active_vocabulary_id = vocabulary.id
        await session.commit()

        await session.delete(vocabulary)
        await session.commit()
        await session.refresh(user)
        assert user.active_vocabulary_id is None
