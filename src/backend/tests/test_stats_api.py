# 2026-11-03 - voda-voca - 학습 통계 API 통합 테스트 (실제 MySQL): 누적 정답률, 연속 학습일, 7일 활동, 단어장 진행률, 오답 판정 (이슈 #3)
# 파일 위치: src/backend/tests/test_stats_api.py

from collections.abc import AsyncIterator
from datetime import date, datetime, timedelta

import httpx
import pytest
import pytest_asyncio

from backend.db.session import get_session_factory
from backend.main import app
from backend.models import StudyLog, Word
from backend.routers import study as study_router
from backend.tests.helpers import auth_headers, signup_and_login
from backend.tests.test_study_api import _user_id_for_token, create_quiz, make_wordbook, make_words

# 고정 "지금": UTC 2026-11-04 02:00 = 한국 시각 2026-11-04 11:00. 한국 날짜 기준 "오늘"은 11-04 다.
FIXED_NOW = datetime(2026, 11, 4, 2, 0, 0)
TODAY = date(2026, 11, 4)
KOREAN_WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]


@pytest_asyncio.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(study_router, "_now", lambda: FIXED_NOW)


def kst_noon(day: date) -> datetime:
    """한국 날짜의 정오(= UTC 03:00). 날짜 경계와 멀어서 시각 오차에 흔들리지 않는다."""
    return datetime(day.year, day.month, day.day, 3, 0, 0)


async def seed_logs(user_id: int, rows: list[tuple[int, bool, datetime]]) -> None:
    """(단어 ID, 정답 여부, 기록 시각 UTC) 목록을 순서대로 학습 이력에 넣는다. 시각이 같으면 넣은 순서가 최신이다."""
    async with get_session_factory()() as db:
        db.add_all(StudyLog(user_id=user_id, word_id=w, is_correct=c, created_at=t) for w, c, t in rows)
        await db.commit()


async def insert_words(wordbook_id: int, count: int) -> list[int]:
    """API 호출 없이 단어를 한꺼번에 넣는다 (대형 단어장 시나리오용)."""
    async with get_session_factory()() as db:
        words = [Word(wordbook_id=wordbook_id, term=f"bulk{i:04d}", meaning=f"대량-{i}") for i in range(count)]
        db.add_all(words)
        await db.commit()
        return [w.id for w in words]


async def get_stats(client: httpx.AsyncClient, token: str) -> dict:
    response = await client.get("/api/study/stats", headers=auth_headers(token))
    assert response.status_code == 200, response.text
    return response.json()


def progress_of(stats: dict, wordbook_id: int) -> dict:
    return next(p for p in stats["wordbook_progress"] if p["wordbook_id"] == wordbook_id)


# --- 기본 ---


@pytest.mark.asyncio
async def test_stats_requires_login(client: httpx.AsyncClient) -> None:
    assert (await client.get("/api/study/stats")).status_code == 401


@pytest.mark.asyncio
async def test_new_user_has_empty_stats(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)

    stats = await get_stats(client, token)

    assert (stats["answered"], stats["correct"], stats["streak_days"], stats["wrong_word_count"]) == (0, 0, 0, 0)
    assert stats["accuracy"] is None, "푼 문항이 없으면 정답률은 없다 (0% 가 아니다)"
    assert len(stats["weekly"]) == 7 and all(day["count"] == 0 for day in stats["weekly"])
    assert len(stats["wordbook_progress"]) == 3, "가입하면 기본 단어장 3종이 생긴다"
    assert all(p["learned_words"] == 0 and p["percent"] == 0 for p in stats["wordbook_progress"])
    assert stats["total_words"] == sum(p["word_count"] for p in stats["wordbook_progress"]) > 0


# --- 누적 정답률 (최근 100건 제한이 없다) ---


@pytest.mark.asyncio
async def test_accuracy_is_cumulative_not_limited_to_the_last_100_logs(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    wb = await make_wordbook(client, token)
    word = next(iter(await make_words(client, token, wb, 4)))
    user_id = await _user_id_for_token(client, token)
    # 150건: 처음 120건 정답, 마지막 30건 오답. 최근 100건만 보면 정답률이 훨씬 낮게 나온다.
    rows = [(word, True, kst_noon(TODAY) + timedelta(seconds=i)) for i in range(120)]
    rows += [(word, False, kst_noon(TODAY) + timedelta(seconds=120 + i)) for i in range(30)]
    await seed_logs(user_id, rows)

    stats = await get_stats(client, token)

    assert (stats["answered"], stats["correct"], stats["accuracy"]) == (150, 120, 80.0)


# --- 연속 학습일 (한국 날짜, 100건 제한이 없다) ---


@pytest.mark.asyncio
async def test_streak_counts_consecutive_days_even_with_over_100_logs_per_week(client: httpx.AsyncClient) -> None:
    """하루 30건씩 5일이면 150건이다. 최근 100건만 보면 연속 학습일이 3~4일로 줄어든다."""
    _, token = await signup_and_login(client)
    wb = await make_wordbook(client, token)
    word = next(iter(await make_words(client, token, wb, 4)))
    user_id = await _user_id_for_token(client, token)
    rows = [
        (word, True, kst_noon(TODAY - timedelta(days=offset)) + timedelta(seconds=n))
        for offset in range(5)
        for n in range(30)
    ]
    await seed_logs(user_id, rows)

    assert (await get_stats(client, token))["streak_days"] == 5


@pytest.mark.asyncio
async def test_streak_continues_from_yesterday_when_today_is_not_studied_yet(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    wb = await make_wordbook(client, token)
    word = next(iter(await make_words(client, token, wb, 4)))
    user_id = await _user_id_for_token(client, token)
    await seed_logs(user_id, [(word, True, kst_noon(TODAY - timedelta(days=d))) for d in (1, 2, 3)])

    assert (await get_stats(client, token))["streak_days"] == 3


@pytest.mark.asyncio
async def test_streak_breaks_on_a_missing_day_and_is_zero_after_two_idle_days(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    wb = await make_wordbook(client, token)
    word = next(iter(await make_words(client, token, wb, 4)))
    user_id = await _user_id_for_token(client, token)
    # 오늘과 3일 전만 학습: 어제와 그제가 비어 있어 연속은 1일.
    await seed_logs(user_id, [(word, True, kst_noon(TODAY)), (word, True, kst_noon(TODAY - timedelta(days=3)))])
    assert (await get_stats(client, token))["streak_days"] == 1

    _, other = await signup_and_login(client)
    other_wb = await make_wordbook(client, other)
    other_word = next(iter(await make_words(client, other, other_wb, 4)))
    other_id = await _user_id_for_token(client, other)
    await seed_logs(other_id, [(other_word, True, kst_noon(TODAY - timedelta(days=2)))])  # 그제만
    assert (await get_stats(client, other))["streak_days"] == 0


# --- 최근 7일 활동 ---


@pytest.mark.asyncio
async def test_weekly_is_seven_days_oldest_first_with_distinct_words_per_day(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    wb = await make_wordbook(client, token)
    words = list(await make_words(client, token, wb, 4))
    user_id = await _user_id_for_token(client, token)
    await seed_logs(
        user_id,
        [
            (words[0], True, kst_noon(TODAY)),
            (words[0], False, kst_noon(TODAY) + timedelta(minutes=1)),  # 같은 단어를 같은 날 두 번 풀어도 1
            (words[1], True, kst_noon(TODAY)),
            (words[2], True, kst_noon(TODAY - timedelta(days=6))),  # 7일 창의 첫날
            (words[3], True, kst_noon(TODAY - timedelta(days=7))),  # 창 밖
        ],
    )

    weekly = (await get_stats(client, token))["weekly"]

    assert [day["date"] for day in weekly] == [str(TODAY - timedelta(days=6 - i)) for i in range(7)]
    assert [day["count"] for day in weekly] == [1, 0, 0, 0, 0, 0, 2]
    assert [day["label"] for day in weekly] == [KOREAN_WEEKDAYS[(TODAY - timedelta(days=6 - i)).weekday()] for i in range(7)]
    assert [day["is_today"] for day in weekly] == [False] * 6 + [True]


@pytest.mark.asyncio
async def test_day_boundary_is_korean_midnight(client: httpx.AsyncClient) -> None:
    """UTC 11-03 15:00 = 한국 11-04 00:00. 그 1초 전은 한국 11-03 이다."""
    _, token = await signup_and_login(client)
    wb = await make_wordbook(client, token)
    words = list(await make_words(client, token, wb, 4))
    user_id = await _user_id_for_token(client, token)
    await seed_logs(
        user_id,
        [
            (words[0], True, datetime(2026, 11, 3, 14, 59, 59)),  # 한국 11-03 23:59:59
            (words[1], True, datetime(2026, 11, 3, 15, 0, 0)),  # 한국 11-04 00:00:00
        ],
    )

    by_date = {day["date"]: day["count"] for day in (await get_stats(client, token))["weekly"]}

    assert by_date["2026-11-03"] == 1
    assert by_date["2026-11-04"] == 1


# --- 단어장 진행률 (최근 100건 제한이 없다) ---


@pytest.mark.asyncio
async def test_progress_counts_words_ever_answered_correctly_beyond_100_logs(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    wb = await make_wordbook(client, token)
    user_id = await _user_id_for_token(client, token)
    ids = await insert_words(wb, 150)
    rows: list[tuple[int, bool, datetime]] = []
    base = kst_noon(TODAY)
    rows += [(w, True, base + timedelta(seconds=i)) for i, w in enumerate(ids[:120])]  # 120개를 맞힘 (로그 120건)
    rows += [(ids[0], False, base + timedelta(minutes=1))]  # 맞힌 뒤 틀려도 "한 번이라도 맞힌 단어"다
    rows += [(w, False, base + timedelta(minutes=2, seconds=i)) for i, w in enumerate(ids[120:130])]  # 틀리기만 한 10개
    await seed_logs(user_id, rows)

    progress = progress_of(await get_stats(client, token), wb)

    assert progress["word_count"] == 150
    assert progress["learned_words"] == 120
    assert progress["percent"] == 80, "100건 창이면 최대 66% 로 막혔을 값이다"


@pytest.mark.asyncio
async def test_progress_is_100_percent_when_every_word_was_answered_correctly(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    wb = await make_wordbook(client, token)
    words = list(await make_words(client, token, wb, 4))
    user_id = await _user_id_for_token(client, token)
    await seed_logs(user_id, [(w, True, kst_noon(TODAY)) for w in words])

    assert progress_of(await get_stats(client, token), wb)["percent"] == 100


# --- 오답 판정 (단어별 마지막 결과) ---


@pytest.mark.asyncio
async def test_wrong_word_is_one_whose_latest_result_is_wrong(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    wb = await make_wordbook(client, token)
    w1, w2, w3, w4 = list(await make_words(client, token, wb, 4))
    user_id = await _user_id_for_token(client, token)
    t = kst_noon(TODAY)
    await seed_logs(
        user_id,
        [
            (w1, False, t),  # 틀리기만 함 → 오답
            (w2, False, t + timedelta(seconds=1)),  # 틀렸다가
            (w2, True, t + timedelta(seconds=2)),  # 맞힘 → 오답 아님
            (w3, True, t + timedelta(seconds=3)),  # 맞혔다가
            (w3, False, t + timedelta(seconds=4)),  # 다시 틀림 → 오답
            (w4, True, t + timedelta(seconds=5)),  # 맞히기만 함 → 오답 아님
        ],
    )

    assert (await get_stats(client, token))["wrong_word_count"] == 2


@pytest.mark.asyncio
async def test_old_wrong_words_still_count_without_any_log_window(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    wb = await make_wordbook(client, token)
    words = list(await make_words(client, token, wb, 5))
    user_id = await _user_id_for_token(client, token)
    t = kst_noon(TODAY)
    rows = [(w, False, t + timedelta(seconds=i)) for i, w in enumerate(words[:4])]  # 오래된 오답 4개
    rows += [(words[4], True, t + timedelta(minutes=1, seconds=i)) for i in range(150)]  # 그 뒤 다른 단어 150건
    await seed_logs(user_id, rows)

    assert (await get_stats(client, token))["wrong_word_count"] == 4


@pytest.mark.asyncio
async def test_wrong_review_quiz_uses_the_same_rule_and_shrinks_as_words_are_corrected(client: httpx.AsyncClient) -> None:
    """오답 복습에서 맞히면 대상에서 빠지고, 4개 미만이 되면 더는 시작할 수 없다."""
    _, token = await signup_and_login(client)
    wb = await make_wordbook(client, token)
    words = list(await make_words(client, token, wb, 6))
    user_id = await _user_id_for_token(client, token)
    t = kst_noon(TODAY)
    await seed_logs(user_id, [(w, False, t + timedelta(seconds=i)) for i, w in enumerate(words[:5])])
    assert (await get_stats(client, token))["wrong_word_count"] == 5

    await seed_logs(user_id, [(words[0], True, t + timedelta(minutes=1))])  # 하나 맞힘 → 4개
    assert (await get_stats(client, token))["wrong_word_count"] == 4
    ok = await create_quiz(client, token, {"wrong_only": True, "count": 10})
    assert ok.status_code == 201, ok.text
    assert len(ok.json()["questions"]) == 4

    await seed_logs(user_id, [(words[1], True, t + timedelta(minutes=2))])  # 하나 더 → 3개
    assert (await get_stats(client, token))["wrong_word_count"] == 3
    blocked = await create_quiz(client, token, {"wrong_only": True})
    assert blocked.status_code == 400
    assert "현재 3개" in blocked.json()["detail"]


# --- 분리·합계 ---


@pytest.mark.asyncio
async def test_stats_are_isolated_per_user(client: httpx.AsyncClient) -> None:
    _, mine = await signup_and_login(client)
    _, theirs = await signup_and_login(client)
    wb = await make_wordbook(client, theirs)
    words = list(await make_words(client, theirs, wb, 4))
    their_id = await _user_id_for_token(client, theirs)
    await seed_logs(their_id, [(w, False, kst_noon(TODAY)) for w in words])

    stats = await get_stats(client, mine)

    assert (stats["answered"], stats["streak_days"], stats["wrong_word_count"]) == (0, 0, 0)
    assert all(day["count"] == 0 for day in stats["weekly"])
    assert wb not in [p["wordbook_id"] for p in stats["wordbook_progress"]], "남의 단어장은 보이지 않는다"
