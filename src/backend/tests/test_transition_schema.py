# 2026-11-05 - voda-voca - 중앙 제공형 전환(B-4a) 스키마 테스트: study_logs/bookmarks/quiz_sessions 의 참조·mode·source 제약
# 파일 위치: src/backend/tests/test_transition_schema.py

import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import delete, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from backend.db.session import get_session_factory
from backend.models import (
    Base,
    Bookmark,
    QuizSession,
    StudyLog,
    SystemVocabulary,
    SystemWord,
    User,
)
from backend.models.quiz_session import QUIZ_SOURCE_BOOKMARKS, QUIZ_SOURCE_VOCABULARY, QUIZ_SOURCE_WRONG
from backend.models.study_log import STUDY_MODE_FLASHCARD, STUDY_MODE_QUIZ

PREFIX = "tvoda-"
_ASYNC = pytest.mark.asyncio
NO_SUCH_ID = 4_000_000_000  # 어느 테이블에도 없는 id (구 words.id 가 새 FK 를 통과하지 못함을 보인다)


# ---------------------------------------------------------------------------
# 1. 모델 정의 (DB 없이)
# ---------------------------------------------------------------------------


def _fk_targets(table: str, column: str) -> set[str]:
    return {fk.column.table.name for fk in Base.metadata.tables[table].c[column].foreign_keys}


def test_references_point_to_the_system_tables() -> None:
    assert _fk_targets("study_logs", "word_id") == {"system_words"}
    assert _fk_targets("bookmarks", "word_id") == {"system_words"}
    assert _fk_targets("quiz_sessions", "vocabulary_id") == {"system_vocabularies"}


def test_quiz_sessions_has_no_wordbook_column_any_more() -> None:
    assert "wordbook_id" not in Base.metadata.tables["quiz_sessions"].c


@pytest.mark.parametrize("table", ["study_logs", "quiz_sessions"])
def test_mode_column_is_not_null_varchar20_default_quiz(table: str) -> None:
    column = Base.metadata.tables[table].c.mode
    assert column.nullable is False
    assert column.type.length == 20
    assert str(column.server_default.arg) == "quiz"


def test_constants() -> None:
    assert (STUDY_MODE_QUIZ, STUDY_MODE_FLASHCARD) == ("quiz", "flashcard")
    assert (QUIZ_SOURCE_VOCABULARY, QUIZ_SOURCE_BOOKMARKS, QUIZ_SOURCE_WRONG) == ("vocabulary", "bookmarks", "wrong")


def test_bookmark_unique_key_is_kept() -> None:
    table = Base.metadata.tables["bookmarks"]
    unique = [
        sorted(c.name for c in constraint.columns)
        for constraint in table.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    ]
    assert ["user_id", "word_id"] in unique


# ---------------------------------------------------------------------------
# 2. 실제 DB 스키마 (마이그레이션 적용 후)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(autouse=True)
async def _cleanup() -> AsyncIterator[None]:
    await _delete_vocabularies()
    yield
    await _delete_vocabularies()


async def _delete_vocabularies() -> None:
    async with get_session_factory()() as session:
        await session.execute(delete(SystemVocabulary).where(SystemVocabulary.slug.like(f"{PREFIX}%")))
        await session.commit()


async def _scalar_rows(sql: str, **params):
    async with get_session_factory()() as session:
        return (await session.execute(text(sql), params)).all()


@_ASYNC
@pytest.mark.parametrize(
    ("table", "column", "target", "delete_rule"),
    [
        ("study_logs", "word_id", "system_words", "CASCADE"),
        ("bookmarks", "word_id", "system_words", "CASCADE"),
        ("quiz_sessions", "vocabulary_id", "system_vocabularies", "CASCADE"),
    ],
)
async def test_database_foreign_keys(table: str, column: str, target: str, delete_rule: str) -> None:
    rows = await _scalar_rows(
        """
        SELECT k.REFERENCED_TABLE_NAME, r.DELETE_RULE
        FROM information_schema.KEY_COLUMN_USAGE k
        JOIN information_schema.REFERENTIAL_CONSTRAINTS r
          ON r.CONSTRAINT_SCHEMA = k.CONSTRAINT_SCHEMA AND r.CONSTRAINT_NAME = k.CONSTRAINT_NAME
        WHERE k.TABLE_SCHEMA = DATABASE() AND k.TABLE_NAME = :t AND k.COLUMN_NAME = :c
          AND k.REFERENCED_TABLE_NAME IS NOT NULL
        """,
        t=table,
        c=column,
    )
    assert [tuple(r) for r in rows] == [(target, delete_rule)]


@_ASYNC
async def test_database_columns_and_old_tables() -> None:
    columns = {
        (r[0], r[1])
        for r in await _scalar_rows(
            "SELECT TABLE_NAME, COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE()"
        )
    }
    assert ("quiz_sessions", "vocabulary_id") in columns
    assert ("quiz_sessions", "wordbook_id") not in columns
    assert ("quiz_sessions", "mode") in columns
    assert ("study_logs", "mode") in columns
    tables = {r[0] for r in await _scalar_rows("SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE()")}
    assert {"words", "wordbooks"} <= tables  # B-7 까지 보존 (롤백 안전성)


@_ASYNC
async def test_bookmark_unique_key_exists_in_database() -> None:
    rows = await _scalar_rows(
        """
        SELECT INDEX_NAME, GROUP_CONCAT(COLUMN_NAME ORDER BY SEQ_IN_INDEX)
        FROM information_schema.STATISTICS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'bookmarks' AND NON_UNIQUE = 0 AND INDEX_NAME <> 'PRIMARY'
        GROUP BY INDEX_NAME
        """
    )
    assert [tuple(r) for r in rows] == [("uk_bookmarks_user_word", "user_id,word_id")]


# ---------------------------------------------------------------------------
# 3. 동작
# ---------------------------------------------------------------------------


async def _fixture_rows(session) -> tuple[User, SystemVocabulary, SystemWord]:
    user = User(nickname=f"tvoda-{uuid.uuid4().hex[:8]}", password_hash="x")
    vocabulary = SystemVocabulary(
        slug=f"{PREFIX}{uuid.uuid4().hex[:8]}", title="테스트", category="ELEMENTARY", level=1
    )
    session.add_all([user, vocabulary])
    await session.flush()
    word = SystemWord(vocabulary_id=vocabulary.id, term="apple", meaning="사과")
    session.add(word)
    await session.flush()
    return user, vocabulary, word


def _quiz_session(user: User, vocabulary_id: int | None, **overrides: object) -> QuizSession:
    values: dict[str, object] = {
        "user_id": user.id,
        "vocabulary_id": vocabulary_id,
        "source": QUIZ_SOURCE_VOCABULARY,
        "questions": [],
        "is_submitted": False,
        "expires_at": datetime(2030, 1, 1) + timedelta(minutes=30),
    }
    values.update(overrides)
    return QuizSession(**values)


@_ASYNC
async def test_study_log_mode_defaults_to_quiz_and_accepts_flashcard() -> None:
    async with get_session_factory()() as session:
        user, _, word = await _fixture_rows(session)
        default_log = StudyLog(user_id=user.id, word_id=word.id, is_correct=True)
        flash_log = StudyLog(user_id=user.id, word_id=word.id, is_correct=False, mode=STUDY_MODE_FLASHCARD)
        session.add_all([default_log, flash_log])
        await session.flush()
        await session.refresh(default_log)
        assert default_log.mode == "quiz"
        assert flash_log.mode == "flashcard"


@_ASYNC
async def test_study_log_rejects_unknown_mode() -> None:
    async with get_session_factory()() as session:
        user, _, word = await _fixture_rows(session)
        session.add(StudyLog(user_id=user.id, word_id=word.id, is_correct=True, mode="spelling"))
        with pytest.raises((IntegrityError, DBAPIError)):
            await session.flush()


@_ASYNC
async def test_study_log_and_bookmark_reject_ids_missing_from_system_words() -> None:
    async with get_session_factory()() as session:
        user, _, _ = await _fixture_rows(session)
        session.add(StudyLog(user_id=user.id, word_id=NO_SUCH_ID, is_correct=True))
        with pytest.raises(IntegrityError):
            await session.flush()
        await session.rollback()
    async with get_session_factory()() as session:
        user, _, _ = await _fixture_rows(session)
        session.add(Bookmark(user_id=user.id, word_id=NO_SUCH_ID))
        with pytest.raises(IntegrityError):
            await session.flush()


@_ASYNC
async def test_bookmark_is_unique_per_user_and_word() -> None:
    async with get_session_factory()() as session:
        user, _, word = await _fixture_rows(session)
        session.add(Bookmark(user_id=user.id, word_id=word.id))
        await session.flush()
        session.add(Bookmark(user_id=user.id, word_id=word.id))
        with pytest.raises(IntegrityError):
            await session.flush()


@_ASYNC
async def test_deleting_a_system_word_cascades_to_logs_and_bookmarks() -> None:
    async with get_session_factory()() as session:
        user, _, word = await _fixture_rows(session)
        session.add_all([StudyLog(user_id=user.id, word_id=word.id, is_correct=True), Bookmark(user_id=user.id, word_id=word.id)])
        await session.commit()
        word_id = word.id
        await session.delete(word)
        await session.commit()
        logs = await session.scalar(text("SELECT COUNT(*) FROM study_logs WHERE word_id = :i"), {"i": word_id})
        marks = await session.scalar(text("SELECT COUNT(*) FROM bookmarks WHERE word_id = :i"), {"i": word_id})
        assert (logs, marks) == (0, 0)


@_ASYNC
@pytest.mark.parametrize("source", [QUIZ_SOURCE_VOCABULARY, QUIZ_SOURCE_BOOKMARKS, QUIZ_SOURCE_WRONG])
async def test_quiz_session_accepts_new_sources_and_defaults_mode(source: str) -> None:
    async with get_session_factory()() as session:
        user, vocabulary, _ = await _fixture_rows(session)
        vocabulary_id = vocabulary.id if source == QUIZ_SOURCE_VOCABULARY else None
        quiz = _quiz_session(user, vocabulary_id, source=source)
        session.add(quiz)
        await session.flush()
        await session.refresh(quiz)
        assert quiz.mode == "quiz"
        assert quiz.answers == {}  # 기존 answers 구조 유지


@_ASYNC
async def test_quiz_session_rejects_old_wordbook_source_and_unknown_mode() -> None:
    async with get_session_factory()() as session:
        user, vocabulary, _ = await _fixture_rows(session)
        session.add(_quiz_session(user, vocabulary.id, source="wordbook"))
        with pytest.raises((IntegrityError, DBAPIError)):
            await session.flush()
        await session.rollback()
    async with get_session_factory()() as session:
        user, vocabulary, _ = await _fixture_rows(session)
        session.add(_quiz_session(user, vocabulary.id, mode="spelling"))
        with pytest.raises((IntegrityError, DBAPIError)):
            await session.flush()


@_ASYNC
async def test_quiz_session_accepts_flashcard_mode_and_rejects_missing_vocabulary() -> None:
    async with get_session_factory()() as session:
        user, vocabulary, _ = await _fixture_rows(session)
        session.add(_quiz_session(user, vocabulary.id, mode=STUDY_MODE_FLASHCARD))
        await session.flush()
        session.add(_quiz_session(user, NO_SUCH_ID))
        with pytest.raises(IntegrityError):
            await session.flush()


@_ASYNC
async def test_deleting_a_vocabulary_cascades_to_its_quiz_sessions() -> None:
    async with get_session_factory()() as session:
        user, vocabulary, _ = await _fixture_rows(session)
        session.add(_quiz_session(user, vocabulary.id))
        await session.commit()
        vocabulary_id = vocabulary.id
        await session.delete(vocabulary)
        await session.commit()
        count = await session.scalar(select(text("COUNT(*)")).select_from(text("quiz_sessions")).where(text("vocabulary_id = :i")), {"i": vocabulary_id})
        assert count == 0
