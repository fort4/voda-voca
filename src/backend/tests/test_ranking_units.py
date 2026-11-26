# 2026-11-26 - voda-voca - 순위 매기기 단위 테스트: 지표 내림차순, 동점 같은 순위(1,1,3), 동점 안에서는 닉네임 순 (REQ-172)
# 파일 위치: src/backend/tests/test_ranking_units.py

import pytest

from backend.services.ranking import Standing, rank_standings

pytestmark = pytest.mark.no_db


def standing(nickname: str, learned: int = 0, words: int = 0, days: int = 0) -> Standing:
    return Standing(user_id=len(nickname), nickname=nickname, public=True, learned_words=learned, week_words=words, week_days=days)


def ranked(standings: list[Standing], metric: str) -> list[tuple[int, str]]:
    return [(rank, s.nickname) for rank, s in rank_standings(standings, metric)]


def test_orders_by_the_chosen_metric_only() -> None:
    people = [standing("a", learned=1, words=30, days=2), standing("b", learned=5, words=10, days=7)]

    assert ranked(people, "learned_words") == [(1, "b"), (2, "a")]
    assert ranked(people, "week_words") == [(1, "a"), (2, "b")]
    assert ranked(people, "week_days") == [(1, "b"), (2, "a")]


def test_equal_values_share_a_rank_and_the_next_rank_skips() -> None:
    people = [standing("carol", 3), standing("Bob", 7), standing("alice", 7), standing("dave", 0)]

    assert ranked(people, "learned_words") == [(1, "alice"), (1, "Bob"), (3, "carol"), (4, "dave")]


def test_empty_input() -> None:
    assert rank_standings([], "learned_words") == []
