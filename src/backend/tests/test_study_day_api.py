# 2026-11-26 - voda-voca - 일차 진도 통합 테스트: 이력의 일차 기록, 단어장별 계산, 한국 날짜 경계, 통계 응답 (REQ-165)
# 파일 위치: src/backend/tests/test_study_day_api.py

from collections.abc import AsyncIterator
from datetime import datetime, timedelta

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import select, update

from backend.db.session import get_session_factory
from backend.main import app
from backend.models import StudyLog, User
from backend.routers import study as study_router
from backend.services.study_log import record_result
from backend.tests.helpers import auth_headers, make_vocab, make_words, signup_and_login, user_id_for_token

# 한국 시각 2026-11-24 12:00
DAY1 = datetime(2026, 11, 24, 3, 0, 0)
DAY2 = DAY1 + timedelta(days=1)
DAY3 = DAY1 + timedelta(days=2)


@pytest_asyncio.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def setup(client: httpx.AsyncClient, words: int = 25) -> tuple[str, int, int, list[int]]:
    """학습량 10 인 사용자와 단어장 하나. 그 단어장을 활성으로 고른다."""
    _, token = await signup_and_login(client)
    user_id = await user_id_for_token(client, token)
    vocabulary = await make_vocab(client, token)
    ids = list(await make_words(client, token, vocabulary, words, prefix=f"v{vocabulary}"))
    await set_user(user_id, active_vocabulary_id=vocabulary, daily_goal=10)
    return token, user_id, vocabulary, ids


async def set_user(user_id: int, **values) -> None:
    async with get_session_factory()() as db:
        await db.execute(update(User).where(User.id == user_id).values(**values))
        await db.commit()


async def study(user_id: int, word_ids: list[int], now: datetime, correct: bool = True, mode: str = "quiz") -> list[int]:
    """단어를 차례로 학습하고, 방금 남긴 이력들의 일차를 돌려준다."""
    async with get_session_factory()() as db:
        for offset, word_id in enumerate(word_ids):
            await record_result(db, user_id, word_id, correct, now + timedelta(seconds=offset), mode)
        await db.commit()
        rows = await db.scalars(
            select(StudyLog.study_day).where(StudyLog.user_id == user_id).order_by(StudyLog.id.desc()).limit(len(word_ids))
        )
        return list(rows)[::-1]


async def day_progress(client, monkeypatch: pytest.MonkeyPatch, token: str, now: datetime) -> dict | None:
    monkeypatch.setattr(study_router, "_now", lambda: now)
    response = await client.get("/api/study/stats", headers=auth_headers(token))
    assert response.status_code == 200, response.text
    return response.json()["day_progress"]


@pytest.mark.asyncio
async def test_the_example_in_the_requirement(client: httpx.AsyncClient) -> None:
    """학습량 10: 첫날 6개 → 1일차, 다음 날 4개 → 1일차(채움), 그다음 날 → 2일차."""
    _, user_id, _, ids = await setup(client)

    assert await study(user_id, ids[:6], DAY1) == [1] * 6
    assert await study(user_id, ids[6:10], DAY2) == [1] * 4
    assert await study(user_id, ids[10:12], DAY3) == [2, 2]


@pytest.mark.asyncio
async def test_filling_the_amount_does_not_advance_within_the_same_day(client: httpx.AsyncClient) -> None:
    _, user_id, _, ids = await setup(client)

    assert await study(user_id, ids[:15], DAY1) == [1] * 15
    assert await study(user_id, ids[15:16], DAY2) == [2]


@pytest.mark.asyncio
async def test_repeating_a_word_counts_once(client: httpx.AsyncClient) -> None:
    _, user_id, _, ids = await setup(client)
    await study(user_id, ids[:5] * 3, DAY1)

    assert await study(user_id, ids[:1], DAY2) == [1]


@pytest.mark.asyncio
async def test_wrong_answers_and_flashcards_count(client: httpx.AsyncClient) -> None:
    _, user_id, _, ids = await setup(client)
    await study(user_id, ids[:5], DAY1, correct=False)
    await study(user_id, ids[5:10], DAY1, mode="flashcard")

    assert await study(user_id, ids[10:11], DAY2) == [2]


@pytest.mark.asyncio
async def test_the_date_changes_at_korean_midnight(client: httpx.AsyncClient) -> None:
    _, user_id, _, ids = await setup(client)
    last_minute = datetime(2026, 11, 24, 14, 59, 0)  # 한국 11-24 23:59
    await study(user_id, ids[:10], last_minute)

    assert await study(user_id, ids[10:11], last_minute + timedelta(seconds=30)) == [1]
    assert await study(user_id, ids[11:12], last_minute + timedelta(minutes=2)) == [2]  # 한국 11-25 00:01


@pytest.mark.asyncio
async def test_each_vocabulary_and_user_counts_its_own_days(client: httpx.AsyncClient) -> None:
    token, user_id, _, ids = await setup(client)
    other_vocabulary = await make_vocab(client, token, "다른 단어장")
    other_ids = list(await make_words(client, token, other_vocabulary, 3, prefix="other"))
    _, second_user, _, _ = await setup(client)
    await study(user_id, ids[:10], DAY1)

    assert await study(user_id, other_ids[:1], DAY2) == [1]
    assert await study(second_user, ids[:1], DAY2) == [1]
    assert await study(user_id, ids[10:11], DAY2) == [2]


@pytest.mark.asyncio
async def test_old_logs_without_a_day_are_ignored(client: httpx.AsyncClient) -> None:
    _, user_id, _, ids = await setup(client)
    async with get_session_factory()() as db:
        db.add_all(StudyLog(user_id=user_id, word_id=w, is_correct=True, created_at=DAY1) for w in ids[:20])
        await db.commit()

    assert await study(user_id, ids[:1], DAY2) == [1]


@pytest.mark.asyncio
async def test_a_session_answer_stores_the_day(client: httpx.AsyncClient) -> None:
    token, user_id, _, _ = await setup(client)
    created = await client.post("/api/study/sessions", json={"mode": "flashcard", "count": 1}, headers=auth_headers(token))
    assert created.status_code == 201, created.text
    session = created.json()

    answered = await client.post(
        f"/api/study/sessions/{session['session_id']}/answer",
        json={"question_id": session["items"][0]["question_id"], "known": True},
        headers=auth_headers(token),
    )

    assert answered.status_code == 200, answered.text
    async with get_session_factory()() as db:
        assert list(await db.scalars(select(StudyLog.study_day).where(StudyLog.user_id == user_id))) == [1]


@pytest.mark.asyncio
async def test_stats_show_the_current_day_of_the_active_vocabulary(client: httpx.AsyncClient, monkeypatch) -> None:
    token, user_id, vocabulary, ids = await setup(client)

    def expect(day: int, words: int) -> dict:
        return {"vocabulary_id": vocabulary, "day": day, "words": words}

    assert await day_progress(client, monkeypatch, token, DAY1) == expect(1, 0)
    await study(user_id, ids[:6] + ids[:1], DAY1)
    assert await day_progress(client, monkeypatch, token, DAY1) == expect(1, 6)
    assert await day_progress(client, monkeypatch, token, DAY2) == expect(1, 6)
    await study(user_id, ids[6:10], DAY2)
    assert await day_progress(client, monkeypatch, token, DAY2) == expect(1, 10)
    assert await day_progress(client, monkeypatch, token, DAY3) == expect(2, 0)  # 아직 풀기 전에도 새 일차를 보인다
    await set_user(user_id, daily_goal=20)
    assert await day_progress(client, monkeypatch, token, DAY3) == expect(1, 10)


@pytest.mark.asyncio
async def test_stats_have_no_day_without_an_active_vocabulary(client: httpx.AsyncClient, monkeypatch) -> None:
    token, user_id, _, _ = await setup(client)
    await set_user(user_id, active_vocabulary_id=None)

    assert await day_progress(client, monkeypatch, token, DAY1) is None
