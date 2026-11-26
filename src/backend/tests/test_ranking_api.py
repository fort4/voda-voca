# 2026-11-26 - voda-voca - 학습 순위 API 통합 테스트: 지표 3종, 공개한 사용자만, me, 노출 항목 제한, 조회 전용 (REQ-172, VOCA-FR-051~053)
# 파일 위치: src/backend/tests/test_ranking_api.py

from collections.abc import AsyncIterator
from datetime import date, datetime, timedelta

import httpx
import pytest
import pytest_asyncio

from backend.db.session import get_session_factory
from backend.main import app
from backend.models import StudyLog, User
from backend.routers import ranking as ranking_router
from backend.services.ranking import RANKING_LIMIT
from backend.tests.helpers import auth_headers, make_vocab, make_words, signup_and_login, unique_nickname, user_id_for_token

URL = "/api/ranking"
VISIBILITY = "/api/users/me/ranking-visibility"
# 고정 "지금": UTC 2026-11-26 02:00 = 한국 시각 11-26 11:00
FIXED_NOW = datetime(2026, 11, 26, 2, 0, 0)
TODAY = date(2026, 11, 26)
METRIC_KEYS = ("learned_words", "week_words", "week_days")


@pytest_asyncio.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ranking_router, "_now", lambda: FIXED_NOW)


def kst_noon(days_ago: int) -> datetime:
    """오늘에서 days_ago 일 전의 한국 시각 정오(= UTC 03:00)."""
    day = TODAY - timedelta(days=days_ago)
    return datetime(day.year, day.month, day.day, 3, 0, 0)


class Player:
    def __init__(self, nickname: str, token: str, user_id: int) -> None:
        self.nickname, self.user_id = nickname, user_id
        self.headers = auth_headers(token)


async def player(client: httpx.AsyncClient, *, public: bool = True) -> Player:
    nickname, token = await signup_and_login(client)
    me = Player(nickname, token, await user_id_for_token(client, token))
    if public:
        assert (await client.put(VISIBILITY, json={"public": True}, headers=me.headers)).status_code == 200
    return me


async def words(client: httpx.AsyncClient, count: int) -> list[int]:
    vocabulary_id = await make_vocab(client, "")
    return list(await make_words(client, "", vocabulary_id, count))


async def seed_logs(user: Player, rows: list[tuple[int, bool, datetime]]) -> None:
    async with get_session_factory()() as db:
        db.add_all(StudyLog(user_id=user.user_id, word_id=w, is_correct=c, created_at=t) for w, c, t in rows)
        await db.commit()


async def ranking(client: httpx.AsyncClient, user: Player, **params) -> dict:
    response = await client.get(URL, params=params, headers=user.headers)
    assert response.status_code == 200, response.text
    return response.json()


def metrics(entry: dict) -> tuple[int, int, int]:
    return tuple(entry[key] for key in METRIC_KEYS)


@pytest.mark.asyncio
async def test_requires_login(client: httpx.AsyncClient) -> None:
    assert (await client.get(URL)).status_code == 401


@pytest.mark.asyncio
async def test_metrics_count_distinct_words_and_study_days(client: httpx.AsyncClient) -> None:
    me = await player(client)
    a, b, c, d = await words(client, 4)
    await seed_logs(
        me,
        [
            (a, True, kst_noon(0)), (a, True, kst_noon(0)), (a, True, kst_noon(1)),  # 반복해도 단어는 1개
            (b, False, kst_noon(1)),  # 틀리기만 한 단어: 학습한 단어는 아니고 이번 주에 푼 단어다
            (c, False, kst_noon(3)), (c, True, kst_noon(3)),
            (d, True, kst_noon(10)),  # 일주일보다 오래된 기록: 누적에만 센다
        ],
    )

    [entry] = (await ranking(client, me))["items"]

    assert metrics(entry) == (3, 3, 3), "학습 a·c·d, 이번 주 a·b·c, 학습일 오늘·어제·3일 전"


@pytest.mark.asyncio
async def test_week_boundary_follows_the_korean_date(client: httpx.AsyncClient) -> None:
    me = await player(client)
    a, b = await words(client, 2)
    first_day = TODAY - timedelta(days=6)
    # 한국 시각 첫날 00:00 = UTC 전날 15:00
    boundary = datetime(first_day.year, first_day.month, first_day.day) - timedelta(hours=9)
    await seed_logs(me, [(a, True, boundary), (b, True, boundary - timedelta(seconds=1))])

    assert metrics((await ranking(client, me))["me"]) == (2, 1, 1)


@pytest.mark.asyncio
async def test_private_users_are_not_listed(client: httpx.AsyncClient) -> None:
    me, open_user, hidden = await player(client), await player(client), await player(client, public=False)
    [word] = await words(client, 1)
    await seed_logs(hidden, [(word, True, kst_noon(0))])

    body = await ranking(client, me)

    assert {e["nickname"] for e in body["items"]} == {me.nickname, open_user.nickname}
    assert body["total_public"] == 2
    assert hidden.nickname not in str(body)


@pytest.mark.asyncio
async def test_turning_private_removes_the_user_at_once(client: httpx.AsyncClient) -> None:
    me, other = await player(client), await player(client)
    assert other.nickname in str(await ranking(client, me))

    await client.put(VISIBILITY, json={"public": False}, headers=other.headers)

    assert other.nickname not in str(await ranking(client, me))


@pytest.mark.asyncio
async def test_private_viewer_sees_the_ranking_and_own_numbers_without_a_rank(client: httpx.AsyncClient) -> None:
    open_user, me = await player(client), await player(client, public=False)
    [word] = await words(client, 1)
    await seed_logs(me, [(word, True, kst_noon(0))])

    body = await ranking(client, me)

    assert [e["nickname"] for e in body["items"]] == [open_user.nickname]
    assert body["me"] == {"public": False, "rank": None, "learned_words": 1, "week_words": 1, "week_days": 1}


@pytest.mark.asyncio
async def test_metric_parameter_changes_the_order(client: httpx.AsyncClient) -> None:
    steady, collector = await player(client), await player(client)
    ids = await words(client, 5)
    await seed_logs(steady, [(ids[0], True, kst_noon(i)) for i in range(4)])  # 학습 1, 이번 주 1, 4일
    await seed_logs(collector, [(w, True, kst_noon(20)) for w in ids])  # 학습 5, 이번 주 0

    default = await ranking(client, steady)
    by_days = await ranking(client, steady, metric="week_days")

    assert default["metric"] == "learned_words"
    assert [e["nickname"] for e in default["items"]] == [collector.nickname, steady.nickname]
    assert [e["nickname"] for e in by_days["items"]] == [steady.nickname, collector.nickname]
    assert [e["rank"] for e in by_days["items"]] == [1, 2]
    assert by_days["me"]["rank"] == 1
    assert [e["is_me"] for e in by_days["items"]] == [True, False]
    assert (await ranking(client, steady, metric="week_words"))["metric"] == "week_words"


@pytest.mark.asyncio
@pytest.mark.parametrize("metric", ["accuracy", "", "LEARNED_WORDS"])
async def test_unknown_metric_is_422(client: httpx.AsyncClient, metric: str) -> None:
    me = await player(client)
    assert (await client.get(URL, params={"metric": metric}, headers=me.headers)).status_code == 422


@pytest.mark.asyncio
async def test_public_user_without_records_is_listed_with_zero(client: httpx.AsyncClient) -> None:
    me = await player(client)

    body = await ranking(client, me)

    assert metrics(body["items"][0]) == (0, 0, 0)
    assert body["me"]["rank"] == 1


@pytest.mark.asyncio
async def test_only_the_top_entries_are_listed_but_me_keeps_the_rank(client: httpx.AsyncClient) -> None:
    me = await player(client)
    [word] = await words(client, 1)
    async with get_session_factory()() as db:
        others = [User(nickname=unique_nickname(), password_hash="x", ranking_public=True) for _ in range(RANKING_LIMIT)]
        db.add_all(others)
        await db.flush()
        db.add_all(StudyLog(user_id=u.id, word_id=word, is_correct=True, created_at=kst_noon(0)) for u in others)
        await db.commit()

    body = await ranking(client, me)

    assert len(body["items"]) == RANKING_LIMIT
    assert not any(e["is_me"] for e in body["items"])
    assert body["me"]["rank"] == RANKING_LIMIT + 1
    assert body["total_public"] == RANKING_LIMIT + 1


@pytest.mark.asyncio
async def test_response_exposes_only_the_nickname_and_the_metrics(client: httpx.AsyncClient, make_vocabulary) -> None:
    me, other = await player(client), await player(client)
    private_vocab = await make_vocabulary(["secretterm"], title="비밀 단어장", owner_id=other.user_id)
    await seed_logs(other, [(private_vocab.word_ids["secretterm"], True, kst_noon(0))])

    body = await ranking(client, me)

    assert set(body) == {"metric", "items", "total_public", "me"}
    for entry in body["items"]:
        assert set(entry) == {"rank", "nickname", "is_me", *METRIC_KEYS}
    assert set(body["me"]) == {"public", "rank", *METRIC_KEYS}
    assert "secretterm" not in str(body) and "비밀 단어장" not in str(body)
    assert metrics(body["items"][0]) == (1, 1, 1), "개인 단어장 학습도 센다"


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
async def test_ranking_is_read_only(client: httpx.AsyncClient, method: str) -> None:
    me = await player(client)
    response = await getattr(client, method)(URL, headers=me.headers)
    assert response.status_code == 405


def test_no_ranking_route_takes_a_user_identifier() -> None:
    """다른 사용자를 지정하는 자리가 없다 (VOCA-FR-053)."""
    paths = app.openapi()["paths"]
    ranking_paths = {path: spec for path, spec in paths.items() if "ranking" in path}

    assert set(ranking_paths) == {URL, VISIBILITY}
    assert set(ranking_paths[URL]) == {"get"}
    assert set(ranking_paths[VISIBILITY]) == {"get", "put"}
    names = [p["name"] for spec in ranking_paths.values() for op in spec.values() for p in op.get("parameters", [])]
    assert names == ["metric"]
