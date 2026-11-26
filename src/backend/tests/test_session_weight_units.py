# 2026-11-26 - voda-voca - 퀴즈 가중 무작위 출제 순수 함수 테스트: 많이 틀리고 오래 안 본 단어일수록 자주, 배분은 유지 (REQ-168, #34)
# 파일 위치: src/backend/tests/test_session_weight_units.py

import random
from collections import Counter
from datetime import datetime, timedelta

import pytest

from backend.services.progress import ProgressState
from backend.services.session_picker import (
    WordCandidate,
    candidate_weights,
    select_session_words,
    study_weight,
    weighted_order,
)

pytestmark = pytest.mark.no_db  # DB 없이 통과해야 한다 (test_no_db_guard.py)

NOW = datetime(2026, 11, 26, 9, 0, 0)

WRONG = list(range(1000, 1010))
UNSEEN = list(range(2000, 2100))
REVIEW = list(range(3000, 3050))


def _state(wrong: int = 0, days: float | None = 0) -> ProgressState:
    studied = None if days is None else NOW - timedelta(days=days)
    return ProgressState(wrong_count=wrong, last_studied_at=studied, last_result="CORRECT")


def _pick(seed: int, n: int = 10, weights: dict[int, int] | None = None, **pools):
    return select_session_words(
        pools.get("wrong", WRONG),
        pools.get("unseen", UNSEEN),
        pools.get("review", REVIEW),
        n,
        rng=random.Random(seed),
        due_review_ids=pools.get("due", ()),
        weights={} if weights is None else weights,
    )


# ---------------------------------------------------------------------------
# 가중치
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("wrong", "days", "expected"),
    [
        (0, 0, 10),
        (1, 0, 20),
        (0, 5, 15),
        (2, 10, 60),
        (5, 30, 240),
        (50, 365, 240),  # 둘 다 상한이 있다
        (0, 0.9, 10),  # 하루가 안 되면 0일
        (0, -3, 10),  # 미래 시각(시계 차이)은 0일
        (0, None, 40),  # 학습 시각이 없는 옛 기록은 가장 오래된 것으로 본다
    ],
)
def test_study_weight(wrong: int, days: float | None, expected: int) -> None:
    assert study_weight(_state(wrong, days), NOW) == expected


def test_unseen_words_share_the_same_weight() -> None:
    assert study_weight(None, NOW) == 1


def test_candidate_weights_maps_every_word() -> None:
    candidates = [WordCandidate(1, 0, None), WordCandidate(2, 1, _state(2, 10))]
    assert candidate_weights(candidates, NOW) == {1: 1, 2: 60}


# ---------------------------------------------------------------------------
# 가중 비복원 추출
# ---------------------------------------------------------------------------


def test_weighted_order_is_a_permutation_and_reproducible() -> None:
    ids = list(range(20))
    first = weighted_order(ids, {i: i + 1 for i in ids}, random.Random(3))
    assert sorted(first) == ids
    assert first == weighted_order(ids, {i: i + 1 for i in ids}, random.Random(3))
    assert ids == list(range(20)), "입력은 바꾸지 않는다"


def test_weighted_order_puts_a_word_first_in_proportion_to_its_weight() -> None:
    rng = random.Random(11)
    firsts = Counter(weighted_order([1, 2], {1: 30, 2: 10}, rng)[0] for _ in range(4000))
    assert 0.72 < firsts[1] / 4000 < 0.78  # 기대값 30/40


def test_weighted_order_treats_missing_weight_as_one() -> None:
    rng = random.Random(5)
    firsts = Counter(weighted_order([1, 2, 3, 4], {}, rng)[0] for _ in range(4000))
    assert all(850 < firsts[i] < 1150 for i in (1, 2, 3, 4))


# ---------------------------------------------------------------------------
# 출제: 배분은 그대로, 묶음 안은 가중 무작위
# ---------------------------------------------------------------------------


def test_weights_keep_the_quota_composition() -> None:
    for seed in range(20):
        result = _pick(seed)
        assert (result.wrong_count, result.review_count, result.unseen_count) == (3, 1, 6)
        assert len(set(result.ids)) == 10


def test_every_wrong_and_unseen_word_can_be_picked() -> None:
    seen: set[int] = set()
    for seed in range(300):
        seen |= set(_pick(seed).ids)
    assert set(WRONG) <= seen, "최근 오답 3개만 반복해서 나오지 않는다"
    assert set(UNSEEN) <= seen, "미학습 단어가 등록 순서에 묶이지 않는다"


def test_heavier_wrong_words_are_picked_more_often() -> None:
    weights = {i: 10 for i in WRONG}
    weights[WRONG[-1]] = 240
    counts = Counter()
    for seed in range(400):
        counts.update(i for i in _pick(seed, weights=weights).ids if i in set(WRONG))
    assert counts[WRONG[-1]] > 2 * max(counts[i] for i in WRONG[:-1])


def test_due_review_words_still_come_before_the_others() -> None:
    due = REVIEW[:5]
    weights = {i: 240 for i in REVIEW[5:]}  # 기한 전 단어의 가중치가 훨씬 커도
    for seed in range(50):
        result = _pick(seed, weights=weights, wrong=[], due=due)
        picked = [i for i in result.ids if i in set(REVIEW)]
        assert len(picked) == 1 and picked[0] in due


def test_due_words_are_chosen_by_weight_not_strictly_oldest_first() -> None:
    due = REVIEW[:5]
    counts = Counter()
    for seed in range(400):
        weights = {**{i: 10 for i in due}, due[4]: 40}
        counts.update(i for i in _pick(seed, weights=weights, wrong=[], due=due).ids if i in set(REVIEW))
    assert counts[due[4]] > counts[due[0]]
    assert all(counts[i] > 0 for i in due)


def test_leftover_wrong_words_still_fill_the_session_without_duplicates() -> None:
    result = _pick(1, n=8, wrong=WRONG, unseen=[], review=[])
    assert result.wrong_count == 8 and len(set(result.ids)) == 8


def test_same_seed_gives_the_same_weighted_session() -> None:
    assert _pick(7).ids == _pick(7).ids


def test_without_weights_the_priority_order_is_unchanged() -> None:
    result = select_session_words(WRONG, UNSEEN, REVIEW, 10, rng=random.Random(1))
    assert {i for i in result.ids if i < 2000} == set(WRONG[:3])
    assert {i for i in result.ids if 2000 <= i < 3000} == set(UNSEEN[:6])
