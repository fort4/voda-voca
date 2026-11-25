# 2026-11-25 - voda-voca - SQLite 서비스 동작 테스트: upsert, 동시 기록(쓰기 직렬화), 시드 멱등·소요 시간, KST 일자 집계 (ADR-010)
# 파일 위치: src/backend/tests/test_sqlite_services.py

import asyncio
import time
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import func, select

from backend.core.config import get_settings
from backend.db import session as session_module
from backend.models import Base, StudyLog, SystemVocabulary, SystemWord, User, UserWordProgress
from backend.services.stats import _weekly
from backend.services.study_log import record_result
from backend.services.system_seed import seed_system_vocabularies

pytestmark = pytest.mark.no_db  # 임시 SQLite 파일만 쓴다


@pytest_asyncio.fixture
async def db_factory(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "voca.db"))
    for cached in (get_settings, session_module.get_engine, session_module.get_session_factory):
        cached.cache_clear()
    async with session_module.get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield session_module.get_session_factory()
    await session_module.dispose_engine()
    get_settings.cache_clear()


async def _user_and_word(factory) -> tuple[int, int]:
    async with factory() as db:
        user = User(nickname="alice", password_hash="x")
        vocab = SystemVocabulary(slug="t", title="t", category="t")
        db.add_all([user, vocab])
        await db.flush()
        word = SystemWord(vocabulary_id=vocab.id, term="apple", meaning="사과")
        db.add(word)
        await db.commit()
        return user.id, word.id


NOW = datetime(2026, 11, 25, 3, 0, 0)


# ---------- 답 기록 upsert ----------


@pytest.mark.asyncio
async def test_record_result_creates_progress_row_once(db_factory) -> None:
    user_id, word_id = await _user_and_word(db_factory)
    for is_correct in (True, False, True):
        async with db_factory() as db:
            await record_result(db, user_id, word_id, is_correct, NOW)
            await db.commit()
    async with db_factory() as db:
        rows = (await db.execute(select(UserWordProgress))).scalars().all()
        assert len(rows) == 1
        assert (rows[0].correct_count, rows[0].wrong_count) == (2, 1)
        assert await db.scalar(select(func.count()).select_from(StudyLog)) == 3


@pytest.mark.asyncio
async def test_concurrent_records_are_counted_exactly(db_factory) -> None:
    """MySQL 의 행 잠금(FOR UPDATE)이 없어도 같은 사용자·단어의 동시 기록이 하나도 유실되지 않아야 한다."""
    user_id, word_id = await _user_and_word(db_factory)

    async def one() -> None:
        async with db_factory() as db:
            await record_result(db, user_id, word_id, True, NOW)
            await db.commit()

    await asyncio.gather(*(one() for _ in range(20)))
    async with db_factory() as db:
        row = (await db.execute(select(UserWordProgress))).scalar_one()
        assert row.correct_count == 20
        assert await db.scalar(select(func.count()).select_from(StudyLog)) == 20


@pytest.mark.asyncio
async def test_write_after_read_in_same_transaction_does_not_fail_busy(db_factory) -> None:
    """읽기로 시작한 트랜잭션이 나중에 쓰기를 해도, 그 사이 다른 연결이 커밋해도 SQLITE_BUSY 로 실패하지 않는다."""
    user_id, word_id = await _user_and_word(db_factory)

    async def reader_then_writer() -> None:
        async with db_factory() as db:
            await db.scalar(select(func.count()).select_from(User))  # 인증 의존성처럼 먼저 읽는다
            await asyncio.sleep(0.05)
            await record_result(db, user_id, word_id, True, NOW)
            await db.commit()

    await asyncio.gather(*(reader_then_writer() for _ in range(8)))
    async with db_factory() as db:
        assert (await db.execute(select(UserWordProgress))).scalar_one().correct_count == 8


# ---------- 시드 ----------


@pytest.mark.asyncio
async def test_seed_is_idempotent_and_fast_on_empty_db(db_factory) -> None:
    started = time.perf_counter()
    async with db_factory() as db:
        first = await seed_system_vocabularies(db)
    elapsed = time.perf_counter() - started
    assert first.created > 0 and first.words_inserted > 0
    # 점검 워크플로는 기동 후 30초 안에 첫 화면 응답을 요구한다. 시드 적재가 그 안에 끝나야 안전하다.
    assert elapsed < 10, f"시드 적재 {elapsed:.1f}초"

    async with db_factory() as db:
        second = await seed_system_vocabularies(db)
        assert second.created == 0 and second.words_inserted == 0
        assert second.unchanged == first.created
        total = await db.scalar(select(func.count()).select_from(SystemWord))
        assert total == first.words_inserted


# ---------- KST 일자 집계 ----------


@pytest.mark.asyncio
async def test_weekly_groups_by_kst_date(db_factory) -> None:
    user_id, word_id = await _user_and_word(db_factory)
    async with db_factory() as db:
        # UTC 11-24 16:00 = KST 11-25 01:00, UTC 11-24 14:59 = KST 11-24 23:59
        db.add(StudyLog(user_id=user_id, word_id=word_id, is_correct=True, created_at=datetime(2026, 11, 24, 16, 0)))
        db.add(StudyLog(user_id=user_id, word_id=word_id, is_correct=True, created_at=datetime(2026, 11, 24, 14, 59)))
        await db.commit()
        days = await _weekly(db, user_id, date(2026, 11, 25))
    by_date = {d.date: d.count for d in days}
    assert by_date[date(2026, 11, 25)] == 1
    assert by_date[date(2026, 11, 24)] == 1
    assert days[-1].is_today and days[-1].date == date(2026, 11, 25)
