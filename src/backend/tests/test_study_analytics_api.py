# 2026-11-25 - voda-voca - 학습 분석 API 통합 테스트: 자주 틀리는 단어 상위 N(VOCA-FR-033), 시험 성적 추이 회차별·날짜별 정답률(VOCA-FR-032)
# 파일 위치: src/backend/tests/test_study_analytics_api.py

from collections.abc import AsyncIterator
from datetime import date, datetime, timedelta

import httpx
import pytest
import pytest_asyncio

from backend.db.session import get_session_factory
from backend.main import app
from backend.models import QuizSession, StudyLog
from backend.routers import study as study_router
from backend.tests.helpers import auth_headers, make_vocab, make_words, signup_and_login, user_id_for_token

# 고정 "지금": UTC 2026-11-25 02:00 = 한국 시각 11-25 11:00
FIXED_NOW = datetime(2026, 11, 25, 2, 0, 0)
TODAY = date(2026, 11, 25)


@pytest_asyncio.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(study_router, "_now", lambda: FIXED_NOW)


def kst_noon(day: date, seconds: int = 0) -> datetime:
    """한국 날짜의 정오(= UTC 03:00)에 seconds 를 더한 시각. 날짜 경계에서 멀다."""
    return datetime(day.year, day.month, day.day, 3, 0, 0) + timedelta(seconds=seconds)


async def seed_logs(user_id: int, rows: list[tuple[int, bool, datetime]], mode: str = "quiz") -> None:
    async with get_session_factory()() as db:
        db.add_all(StudyLog(user_id=user_id, word_id=w, is_correct=c, created_at=t, mode=mode) for w, c, t in rows)
        await db.commit()


async def seed_session(
    user_id: int,
    vocabulary_id: int,
    word_ids: list[int],
    chosen: list[int | None],
    at: datetime,
    mode: str = "quiz",
) -> int:
    """문항마다 정답은 0번 선지. chosen[i] 가 0 이면 정답, 다른 수면 오답, None 이면 아직 답하지 않은 문항이다."""
    questions = [
        {"question_id": i, "word_id": w, "term": f"t{i}", "choices": ["a", "b", "c", "d"], "correct_index": 0}
        for i, w in enumerate(word_ids)
    ]
    answers = {str(i): c for i, c in enumerate(chosen) if c is not None}
    async with get_session_factory()() as db:
        row = QuizSession(
            user_id=user_id,
            vocabulary_id=vocabulary_id,
            source="vocabulary",
            mode=mode,
            questions=questions,
            answers=answers,
            is_submitted=False,
            expires_at=at + timedelta(minutes=30),
            created_at=at,
        )
        db.add(row)
        await db.commit()
        return row.id


async def frequent(client: httpx.AsyncClient, token: str, **params) -> dict:
    response = await client.get("/api/study/frequent-wrong", params=params, headers=auth_headers(token))
    assert response.status_code == 200, response.text
    return response.json()


async def trend(client: httpx.AsyncClient, token: str, **params) -> dict:
    response = await client.get("/api/study/score-trend", params=params, headers=auth_headers(token))
    assert response.status_code == 200, response.text
    return response.json()


# --- 자주 틀리는 단어 상위 N (VOCA-FR-033) ---


@pytest.mark.asyncio
async def test_analytics_endpoints_require_login(client: httpx.AsyncClient) -> None:
    assert (await client.get("/api/study/frequent-wrong")).status_code == 401
    assert (await client.get("/api/study/score-trend")).status_code == 401


@pytest.mark.asyncio
async def test_frequent_wrong_is_ordered_by_wrong_count_and_excludes_never_wrong(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    vocab = await make_vocab(client, token, "분석용")
    a, b, c, d = list(await make_words(client, token, vocab, 4))
    user_id = await user_id_for_token(client, token)
    rows = (
        [(a, False, kst_noon(TODAY, i)) for i in range(3)]  # a: 오답 3
        + [(b, False, kst_noon(TODAY, 10 + i)) for i in range(5)]  # b: 오답 5
        + [(c, False, kst_noon(TODAY, 20))]  # c: 오답 1 + 정답 2
        + [(c, True, kst_noon(TODAY, 21)), (c, True, kst_noon(TODAY, 22))]
        + [(d, True, kst_noon(TODAY, 30))]  # d: 틀린 적 없음
    )
    await seed_logs(user_id, rows)

    result = await frequent(client, token)

    assert [item["word_id"] for item in result["items"]] == [b, a, c], "오답 횟수 내림차순이며 틀린 적 없는 d 는 없다"
    assert [item["wrong_count"] for item in result["items"]] == [5, 3, 1]
    top = result["items"][0]
    assert top["answered_count"] == 5 and top["vocabulary_title"] == "분석용"
    assert {"term", "meaning", "last_wrong_at"} <= set(top)
    assert result["items"][2]["answered_count"] == 3, "c 는 3번 풀어 1번 틀렸다"


@pytest.mark.asyncio
async def test_frequent_wrong_breaks_ties_by_most_recent_wrong_and_applies_limit(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    vocab = await make_vocab(client, token)
    a, b, c = list(await make_words(client, token, vocab, 3))
    user_id = await user_id_for_token(client, token)
    await seed_logs(
        user_id,
        [(a, False, kst_noon(TODAY, 1)), (b, False, kst_noon(TODAY, 50)), (c, False, kst_noon(TODAY, 20))],
    )

    result = await frequent(client, token, limit=2)

    assert [item["word_id"] for item in result["items"]] == [b, c], "횟수가 같으면 최근에 틀린 단어가 먼저, limit 만큼만"


@pytest.mark.asyncio
async def test_frequent_wrong_counts_only_the_users_own_logs(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    _, other = await signup_and_login(client)
    vocab = await make_vocab(client, token)
    (word,) = list(await make_words(client, token, vocab, 1))
    await seed_logs(await user_id_for_token(client, other), [(word, False, kst_noon(TODAY, i)) for i in range(4)])

    assert (await frequent(client, token))["items"] == []


@pytest.mark.asyncio
@pytest.mark.parametrize("limit", [0, 51, -1])
async def test_frequent_wrong_rejects_out_of_range_limit(client: httpx.AsyncClient, limit: int) -> None:
    _, token = await signup_and_login(client)
    response = await client.get("/api/study/frequent-wrong", params={"limit": limit}, headers=auth_headers(token))
    assert response.status_code == 422


# --- 시험 성적 추이 (VOCA-FR-032) ---


@pytest.mark.asyncio
async def test_new_user_has_empty_trend(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    assert await trend(client, token) == {"sessions": [], "daily": []}


@pytest.mark.asyncio
async def test_trend_sessions_are_numbered_oldest_first_with_score(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    vocab = await make_vocab(client, token)
    words = list(await make_words(client, token, vocab, 4))
    user_id = await user_id_for_token(client, token)
    first = await seed_session(user_id, vocab, words, [0, 0, 1, 2], kst_noon(TODAY - timedelta(days=2)))  # 2/4
    second = await seed_session(user_id, vocab, words, [0, 0, 0, 1], kst_noon(TODAY - timedelta(days=1)))  # 3/4
    third = await seed_session(user_id, vocab, words, [0, 0, 0, 0], kst_noon(TODAY))  # 4/4

    sessions = (await trend(client, token))["sessions"]

    assert [s["round"] for s in sessions] == [1, 2, 3]
    assert [s["session_id"] for s in sessions] == [first, second, third]
    assert [(s["correct"], s["total"], s["accuracy"]) for s in sessions] == [(2, 4, 50.0), (3, 4, 75.0), (4, 4, 100.0)]
    assert sessions[0]["taken_at"].endswith("Z"), "시각은 UTC ISO 로 내려간다"


@pytest.mark.asyncio
async def test_trend_excludes_unfinished_flashcard_and_other_users_sessions(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    _, other = await signup_and_login(client)
    vocab = await make_vocab(client, token)
    words = list(await make_words(client, token, vocab, 4))
    user_id = await user_id_for_token(client, token)
    done = await seed_session(user_id, vocab, words, [0, 1, 0, 0], kst_noon(TODAY))
    await seed_session(user_id, vocab, words, [0, 0, None, None], kst_noon(TODAY, 100))  # 중간에 그만둔 시험
    await seed_session(user_id, vocab, words, [1, 1, 1, 1], kst_noon(TODAY, 200), mode="flashcard")  # 플래시카드는 시험이 아니다
    await seed_session(await user_id_for_token(client, other), vocab, words, [0, 0, 0, 0], kst_noon(TODAY, 300))

    sessions = (await trend(client, token))["sessions"]

    assert [s["session_id"] for s in sessions] == [done]
    assert sessions[0]["round"] == 1


@pytest.mark.asyncio
async def test_trend_sessions_limit_keeps_the_latest_but_keeps_round_numbers(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    vocab = await make_vocab(client, token)
    words = list(await make_words(client, token, vocab, 4))
    user_id = await user_id_for_token(client, token)
    for i in range(5):
        await seed_session(user_id, vocab, words, [0, 0, 0, 0], kst_noon(TODAY - timedelta(days=5 - i)))

    sessions = (await trend(client, token, sessions=2))["sessions"]

    assert [s["round"] for s in sessions] == [4, 5], "최근 2회만, 회차 번호는 전체 기준을 유지한다"


@pytest.mark.asyncio
async def test_trend_daily_groups_quiz_logs_by_korean_date(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    vocab = await make_vocab(client, token)
    a, b = list(await make_words(client, token, vocab, 2))
    user_id = await user_id_for_token(client, token)
    yesterday = TODAY - timedelta(days=1)
    await seed_logs(user_id, [(a, True, kst_noon(yesterday)), (b, False, kst_noon(yesterday, 1)), (a, True, kst_noon(TODAY))])
    await seed_logs(user_id, [(a, False, kst_noon(TODAY, 5))], mode="flashcard")  # 플래시카드는 시험 성적에서 뺀다
    # 한국 시각 00:30 은 UTC 로는 전날 15:30 이다. 한국 날짜 기준으로 TODAY 에 묶여야 한다.
    await seed_logs(user_id, [(b, True, datetime(2026, 11, 24, 15, 30, 0))])

    daily = (await trend(client, token))["daily"]

    assert [d["date"] for d in daily] == ["2026-11-24", "2026-11-25"], "오래된 날부터, 기록 있는 날만"
    assert [(d["answered"], d["correct"], d["accuracy"]) for d in daily] == [(2, 1, 50.0), (2, 2, 100.0)]


@pytest.mark.asyncio
async def test_trend_daily_respects_days_window(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    vocab = await make_vocab(client, token)
    (word,) = list(await make_words(client, token, vocab, 1))
    user_id = await user_id_for_token(client, token)
    await seed_logs(
        user_id,
        [(word, True, kst_noon(TODAY - timedelta(days=10))), (word, True, kst_noon(TODAY - timedelta(days=1)))],
    )

    daily = (await trend(client, token, days=3))["daily"]

    assert [d["date"] for d in daily] == ["2026-11-24"]


@pytest.mark.asyncio
@pytest.mark.parametrize("params", [{"sessions": 0}, {"sessions": 101}, {"days": 0}, {"days": 91}])
async def test_trend_rejects_out_of_range_params(client: httpx.AsyncClient, params: dict) -> None:
    _, token = await signup_and_login(client)
    response = await client.get("/api/study/score-trend", params=params, headers=auth_headers(token))
    assert response.status_code == 422
