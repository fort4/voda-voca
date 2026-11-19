# 2026-11-11 - voda-voca - SRS 출제 풀 테스트: 복습 기한이 지난 단어 우선, 숙련 단어도 기한이 되면 복귀 (이슈 #25)
# 파일 위치: src/backend/tests/test_srs_picker_units.py

import random
from datetime import datetime, timedelta

from backend.services.progress import ProgressState
from backend.services.session_picker import WordCandidate, select_session_words, split_pools

NOW = datetime(2026, 11, 11, 9, 0, 0)


def _learned(due: datetime | None, memorized: bool = False, result: str = "CORRECT") -> ProgressState:
    return ProgressState(
        correct_count=3, consecutive_correct_count=3 if memorized else 1, is_memorized=memorized,
        last_result=result, last_studied_at=NOW - timedelta(days=2), interval_step=2, next_review_at=due,
    )


def _cands() -> list[WordCandidate]:
    return [
        WordCandidate(1, 0, _learned(NOW + timedelta(days=3))),  # 아직 기한 전
        WordCandidate(2, 1, _learned(NOW - timedelta(days=1))),  # 기한 지남(1일)
        WordCandidate(3, 2, _learned(NOW - timedelta(days=5))),  # 기한 지남(5일, 가장 오래)
        WordCandidate(4, 3, _learned(NOW + timedelta(days=10), memorized=True)),  # 숙련, 기한 전
        WordCandidate(5, 4, _learned(NOW - timedelta(hours=1), memorized=True)),  # 숙련, 기한 지남
    ]


def test_without_now_behaviour_is_unchanged() -> None:
    pools = split_pools(_cands())
    assert sorted(pools.review) == [1, 2, 3] and pools.due == []


def test_due_words_come_first_most_overdue_first() -> None:
    pools = split_pools(_cands(), now=NOW)
    assert pools.due == [3, 2, 5]
    assert pools.review[:3] == [3, 2, 5]


def test_memorized_word_returns_only_when_due() -> None:
    pools = split_pools(_cands(), now=NOW)
    assert 5 in pools.review and 4 not in pools.review


def test_not_due_words_stay_as_fallback_after_due_ones() -> None:
    pools = split_pools(_cands(), now=NOW)
    assert pools.review[3:] == [1]


def test_include_memorized_still_adds_memorized_not_due() -> None:
    pools = split_pools(_cands(), include_memorized=True, now=NOW)
    assert 4 in pools.review and pools.due == [3, 2, 5]


def test_missing_next_review_at_counts_as_due() -> None:
    pools = split_pools([WordCandidate(9, 0, _learned(None))], now=NOW)
    assert pools.due == [9]


def test_due_review_words_are_picked_before_random_ones() -> None:
    review = list(range(100, 120))
    due = [118, 119]
    for seed in range(10):
        result = select_session_words([], [], review, 5, rng=random.Random(seed), due_review_ids=due)
        assert set(due) <= set(result.ids) and len(result.ids) == 5


def test_due_ids_not_in_review_pool_are_ignored() -> None:
    result = select_session_words([], [], [1, 2, 3], 3, rng=random.Random(1), due_review_ids=[99])
    assert sorted(result.ids) == [1, 2, 3]


def test_memorized_word_without_due_date_is_not_revived() -> None:
    pools = split_pools([WordCandidate(9, 0, _learned(None, memorized=True))], now=NOW)
    assert pools.review == [] and pools.due == []
