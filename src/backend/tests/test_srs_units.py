# 2026-11-11 - voda-voca - SRS 간격 반복 순수 함수 테스트: 단계 증감, 부분 감쇠, 다음 복습 시각 (이슈 #25)
# 파일 위치: src/backend/tests/test_srs_units.py

from datetime import datetime, timedelta

import pytest

from backend.services.progress import apply_result, new_progress
from backend.services.srs import INTERVAL_DAYS, MAX_STEP, WRONG_STEP_PENALTY, schedule_next

T0 = datetime(2026, 11, 11, 9, 0, 0)


def test_interval_table_is_forgetting_curve_like() -> None:
    assert INTERVAL_DAYS == (0, 1, 3, 7, 14, 30)
    assert MAX_STEP == 5
    assert WRONG_STEP_PENALTY == 2


@pytest.mark.parametrize(("step", "expected"), [(0, 1), (1, 2), (4, 5), (5, 5)])
def test_correct_raises_step_up_to_max(step: int, expected: int) -> None:
    new_step, _ = schedule_next(step, True, T0)
    assert new_step == expected


@pytest.mark.parametrize(("step", "expected"), [(5, 3), (3, 1), (2, 0), (1, 0), (0, 0)])
def test_wrong_decays_step_partially_and_not_below_zero(step: int, expected: int) -> None:
    new_step, _ = schedule_next(step, False, T0)
    assert new_step == expected


@pytest.mark.parametrize(
    ("step", "is_correct", "days"),
    [(0, True, 1), (1, True, 3), (2, True, 7), (3, True, 14), (4, True, 30), (5, True, 30), (3, False, 1), (1, False, 0)],
)
def test_next_review_at_uses_interval_of_the_new_step(step: int, is_correct: bool, days: int) -> None:
    _, due = schedule_next(step, is_correct, T0)
    assert due == T0 + timedelta(days=days)


def test_rejects_out_of_range_step() -> None:
    with pytest.raises(ValueError):
        schedule_next(-1, True, T0)
    with pytest.raises(ValueError):
        schedule_next(MAX_STEP + 1, True, T0)


def test_new_progress_has_step_zero_and_no_due_date() -> None:
    state = new_progress()
    assert state.interval_step == 0
    assert state.next_review_at is None


def test_apply_result_updates_srs_fields() -> None:
    state = apply_result(new_progress(), True, T0)
    assert state.interval_step == 1
    assert state.next_review_at == T0 + timedelta(days=1)
    later = T0 + timedelta(days=1)
    state = apply_result(state, False, later)
    assert state.interval_step == 0
    assert state.next_review_at == later


def test_apply_result_does_not_mutate_input() -> None:
    before = apply_result(new_progress(), True, T0)
    apply_result(before, True, T0 + timedelta(days=1))
    assert before.interval_step == 1
