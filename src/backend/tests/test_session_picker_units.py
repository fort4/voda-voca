# 2026-11-05 - voda-voca - 세션 출제 순수 함수 테스트: 오답 30% 상한, 복습 10% 선확보, 미학습 충원, 풀 부족 시 전수 반환
# 파일 위치: src/backend/tests/test_session_picker_units.py

import random
from datetime import datetime, timedelta

import pytest

from backend.services.progress import ProgressState, new_progress
from backend.services.session_picker import (
    WordCandidate,
    review_reserve,
    select_session_words,
    split_pools,
    wrong_cap,
)

WRONG = list(range(1000, 1010))  # 우선순위 순서 (앞이 더 최근 오답)
UNSEEN = list(range(2000, 2100))
REVIEW = list(range(3000, 3050))


def _pick(wrong=WRONG, unseen=UNSEEN, review=REVIEW, n=15, seed=7):
    return select_session_words(wrong, unseen, review, n, rng=random.Random(seed))


def _in(ids: list[int], pool: list[int]) -> list[int]:
    return [i for i in ids if i in set(pool)]


# ---------------------------------------------------------------------------
# 슬롯 계산
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("n", "wrong", "reserve"),
    [(1, 0, 0), (3, 0, 0), (4, 1, 0), (9, 2, 0), (10, 3, 1), (15, 4, 1), (20, 6, 2), (30, 9, 3)],
)
def test_slot_caps_use_floor(n: int, wrong: int, reserve: int) -> None:
    assert wrong_cap(n) == wrong
    assert review_reserve(n) == reserve


# ---------------------------------------------------------------------------
# 기본 배분 (N=15)
# ---------------------------------------------------------------------------


def test_plentiful_pools_give_4_wrong_1_review_10_unseen() -> None:
    result = _pick()
    assert len(result.ids) == 15
    assert (result.wrong_count, result.review_count, result.unseen_count) == (4, 1, 10)
    assert len(_in(result.ids, WRONG)) == 4
    assert len(_in(result.ids, REVIEW)) == 1
    assert len(_in(result.ids, UNSEEN)) == 10


def test_wrong_words_are_taken_in_priority_order() -> None:
    assert set(_in(_pick().ids, WRONG)) == set(WRONG[:4])


def test_unseen_words_are_taken_in_order() -> None:
    assert set(_in(_pick().ids, UNSEEN)) == set(UNSEEN[:10])


def test_no_wrong_words_gives_reserved_review_and_more_unseen() -> None:
    result = _pick(wrong=[])
    assert (result.wrong_count, result.review_count, result.unseen_count) == (0, 1, 14)


def test_few_wrong_words_all_included() -> None:
    result = _pick(wrong=WRONG[:2])
    assert (result.wrong_count, result.review_count, result.unseen_count) == (2, 1, 12)
    assert set(WRONG[:2]) <= set(result.ids)


def test_review_is_reserved_even_while_unseen_words_remain() -> None:
    """미학습이 충분해도 복습이 한 문항도 안 나오는 결함(이전 초안)이 없어야 한다."""
    result = _pick()
    assert result.review_count >= 1
    assert result.unseen_count > 0


def test_empty_review_pool_leaves_the_slot_to_unseen() -> None:
    result = _pick(review=[])
    assert (result.wrong_count, result.review_count, result.unseen_count) == (4, 0, 11)


# ---------------------------------------------------------------------------
# 풀 부족 (워터폴)
# ---------------------------------------------------------------------------


def test_short_unseen_pool_is_filled_by_review() -> None:
    result = _pick(unseen=UNSEEN[:3])
    assert len(result.ids) == 15
    assert (result.wrong_count, result.unseen_count, result.review_count) == (4, 3, 8)


def test_no_unseen_words_left_is_filled_by_review() -> None:
    result = _pick(unseen=[])
    assert (result.wrong_count, result.unseen_count, result.review_count) == (4, 0, 11)


def test_leftover_wrong_words_fill_slots_when_other_pools_run_dry() -> None:
    """오답 상한(30%)은 우선 배분 한도일 뿐, 풀이 N개 이상이면 N개를 채워야 한다."""
    wrong = list(range(1000, 1020))
    result = select_session_words(wrong, [], [], 15, rng=random.Random(1))
    assert len(result.ids) == 15
    assert result.wrong_count == 15
    assert result.ids and set(result.ids) <= set(wrong)


def test_review_is_used_before_leftover_wrong_words() -> None:
    wrong = list(range(1000, 1020))
    review = list(range(3000, 3005))
    result = select_session_words(wrong, [], review, 15, rng=random.Random(1))
    assert result.review_count == 5
    assert result.wrong_count == 10


def test_fewer_words_than_n_returns_all_of_them() -> None:
    result = select_session_words([1, 2], [3, 4, 5], [6], 15, rng=random.Random(1))
    assert sorted(result.ids) == [1, 2, 3, 4, 5, 6]
    assert (result.wrong_count, result.unseen_count, result.review_count) == (2, 3, 1)


def test_exactly_n_words_returns_all() -> None:
    result = select_session_words([1, 2], [3, 4, 5, 6, 7, 8, 9, 10], [11, 12, 13, 14, 15], 15, rng=random.Random(1))
    assert sorted(result.ids) == list(range(1, 16))


def test_all_pools_empty_returns_nothing() -> None:
    result = select_session_words([], [], [], 15, rng=random.Random(1))
    assert result.ids == []
    assert (result.wrong_count, result.unseen_count, result.review_count) == (0, 0, 0)


# ---------------------------------------------------------------------------
# 경계값 N
# ---------------------------------------------------------------------------


def test_n_equals_1_prefers_unseen() -> None:
    result = _pick(n=1)
    assert len(result.ids) == 1 and result.unseen_count == 1


def test_n_equals_1_without_unseen_uses_review_then_wrong() -> None:
    assert _pick(n=1, unseen=[]).review_count == 1
    only_wrong = select_session_words([1, 2], [], [], 1, rng=random.Random(1))
    assert only_wrong.ids == [1] and only_wrong.wrong_count == 1


def test_n_equals_9_has_two_wrong_slots_and_no_reserved_review() -> None:
    result = _pick(n=9)
    assert (result.wrong_count, result.review_count, result.unseen_count) == (2, 0, 7)


def test_n_equals_30() -> None:
    result = _pick(n=30)
    assert len(result.ids) == 30
    assert (result.wrong_count, result.review_count, result.unseen_count) == (9, 3, 18)


@pytest.mark.parametrize("n", [0, -1])
def test_non_positive_n_is_rejected(n: int) -> None:
    with pytest.raises(ValueError):
        select_session_words([1], [2], [3], n)


# ---------------------------------------------------------------------------
# 안전성
# ---------------------------------------------------------------------------


def test_result_has_no_duplicate_ids() -> None:
    result = _pick()
    assert len(set(result.ids)) == len(result.ids)


def test_ids_listed_in_several_pools_are_counted_once_with_wrong_first() -> None:
    result = select_session_words([1, 2], [2, 3, 4], [1, 3, 5], 15, rng=random.Random(1))
    assert sorted(result.ids) == [1, 2, 3, 4, 5]
    assert result.wrong_count == 2 and result.unseen_count == 2 and result.review_count == 1


def test_duplicate_ids_inside_a_pool_are_ignored() -> None:
    result = select_session_words([1, 1], [2, 2, 3], [], 15, rng=random.Random(1))
    assert sorted(result.ids) == [1, 2, 3]


def test_inputs_are_not_mutated() -> None:
    wrong, unseen, review = list(WRONG), list(UNSEEN), list(REVIEW)
    select_session_words(wrong, unseen, review, 15, rng=random.Random(1))
    assert (wrong, unseen, review) == (WRONG, UNSEEN, REVIEW)


def test_same_seed_gives_same_result_and_order_is_shuffled() -> None:
    assert _pick(seed=3).ids == _pick(seed=3).ids
    orders = {tuple(_pick(seed=s).ids) for s in range(8)}
    assert len(orders) > 1
    fixed = set(WRONG[:4]) | set(UNSEEN[:10])  # 오답·미학습은 시드와 무관하게 정해진다 (복습만 무작위)
    assert all(fixed <= set(o) and len(o) == 15 for o in orders)


# ---------------------------------------------------------------------------
# 풀 나누기 (숙련 단어 제외 포함)
# ---------------------------------------------------------------------------

T0 = datetime(2026, 11, 5, 9, 0, 0)


def _state(**kw) -> ProgressState:
    base = new_progress()
    values = {**base.__dict__, **kw}
    return ProgressState(**values)


def _candidates() -> list[WordCandidate]:
    return [
        WordCandidate(1, 1, None),  # 미학습
        WordCandidate(2, 0, None),  # 미학습, order_index 가 더 앞
        WordCandidate(3, 2, _state(last_result="WRONG", last_studied_at=T0)),
        WordCandidate(4, 3, _state(last_result="WRONG", last_studied_at=T0 + timedelta(hours=1))),
        WordCandidate(5, 4, _state(last_result="CORRECT", correct_count=1, consecutive_correct_count=1)),
        WordCandidate(
            6, 5, _state(last_result="CORRECT", correct_count=3, consecutive_correct_count=3, is_memorized=True)
        ),
    ]


def test_split_pools_classifies_and_orders() -> None:
    pools = split_pools(_candidates())
    assert pools.unseen == [2, 1]  # order_index 순
    assert pools.wrong == [4, 3]  # 최근 오답이 먼저
    assert pools.review == [5]  # 숙련 단어(6)는 기본 제외


def test_split_pools_can_include_memorized_words() -> None:
    pools = split_pools(_candidates(), include_memorized=True)
    assert sorted(pools.review) == [5, 6]


def test_wrong_with_missing_timestamp_sorts_last() -> None:
    candidates = [
        WordCandidate(1, 0, _state(last_result="WRONG", last_studied_at=None)),
        WordCandidate(2, 1, _state(last_result="WRONG", last_studied_at=T0)),
    ]
    assert split_pools(candidates).wrong == [2, 1]


def test_all_words_memorized_gives_empty_pools_and_empty_session() -> None:
    memorized = _state(last_result="CORRECT", correct_count=3, consecutive_correct_count=3, is_memorized=True)
    candidates = [WordCandidate(i, i, memorized) for i in range(1, 21)]

    pools = split_pools(candidates)
    assert (pools.wrong, pools.unseen, pools.review) == ([], [], [])
    assert select_session_words(pools.wrong, pools.unseen, pools.review, 15).ids == []

    included = split_pools(candidates, include_memorized=True)
    assert len(select_session_words(included.wrong, included.unseen, included.review, 15).ids) == 15


def test_progress_row_without_last_result_counts_as_review() -> None:
    pools = split_pools([WordCandidate(1, 0, new_progress())])
    assert pools.review == [1] and pools.unseen == []


def test_split_then_pick_end_to_end() -> None:
    candidates = [WordCandidate(i, i, None) for i in range(1, 101)]
    candidates += [
        WordCandidate(200 + i, 200 + i, _state(last_result="WRONG", last_studied_at=T0 + timedelta(minutes=i)))
        for i in range(10)
    ]
    candidates += [
        WordCandidate(300 + i, 300 + i, _state(last_result="CORRECT", correct_count=1, consecutive_correct_count=1))
        for i in range(10)
    ]
    pools = split_pools(candidates)
    result = select_session_words(pools.wrong, pools.unseen, pools.review, 15, rng=random.Random(5))
    assert (result.wrong_count, result.review_count, result.unseen_count) == (4, 1, 10)
