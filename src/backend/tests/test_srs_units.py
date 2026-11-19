# 2026-11-19 - voda-voca - SRS 간격 반복 순수 함수 테스트: 단계 증감, 부분 감쇠, 한국 날짜 0시 복습 시각, 기한 전 정답 유지 (이슈 #25, REQ-150)
# 파일 위치: src/backend/tests/test_srs_units.py

from datetime import datetime, timedelta

import pytest

from backend.services.progress import apply_result, new_progress
from backend.services.srs import INTERVAL_DAYS, MAX_STEP, WRONG_STEP_PENALTY, kst_day_start, schedule_next

T0 = datetime(2026, 11, 11, 9, 0, 0)  # UTC. 한국 시각으로는 11-11 18:00
KST_DAY0 = datetime(2026, 11, 10, 15, 0, 0)  # T0 가 속한 한국 날짜(11-11)의 0시 (UTC 로 11-10 15:00)


pytestmark = pytest.mark.no_db  # MySQL 없이 통과해야 한다 (test_no_db_guard.py)


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
def test_next_review_at_is_kst_midnight_of_the_interval_day(step: int, is_correct: bool, days: int) -> None:
    """다음 복습은 답한 시각이 아니라 '며칠 뒤 한국 날짜의 0시'다 (그 날 하루 종일 오늘 복습에 뜬다)."""
    _, due = schedule_next(step, is_correct, T0)
    assert due == KST_DAY0 + timedelta(days=days)


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (datetime(2026, 11, 11, 14, 59, 59), datetime(2026, 11, 10, 15, 0)),  # 한국 23:59:59 → 같은 날 0시
        (datetime(2026, 11, 11, 15, 0, 0), datetime(2026, 11, 11, 15, 0)),  # 한국 00:00:00 → 새 날의 0시
        (datetime(2026, 11, 11, 0, 0, 0), datetime(2026, 11, 10, 15, 0)),  # 한국 09:00
    ],
)
def test_kst_day_start_boundaries(now: datetime, expected: datetime) -> None:
    assert kst_day_start(now) == expected


def test_late_night_answer_is_due_all_day_tomorrow() -> None:
    """한국 23:00 에 맞혀도 다음 복습은 내일 0시라, 내일 오전 9시에 열면 오늘 복습에 뜬다."""
    answered = datetime(2026, 11, 11, 14, 0, 0)  # 한국 11-11 23:00
    _, due = schedule_next(0, True, answered)
    morning = datetime(2026, 11, 12, 0, 0, 0)  # 한국 11-12 09:00
    assert due <= morning


def test_correct_before_due_keeps_step_and_due_date() -> None:
    """기한이 되기 전에 맞힌 정답은 단계와 다음 복습 시각을 바꾸지 않는다 (같은 날 반복 학습으로 단계가 부풀지 않게)."""
    due = KST_DAY0 + timedelta(days=3)
    assert schedule_next(2, True, T0, due) == (2, due)


@pytest.mark.parametrize("offset", [timedelta(0), timedelta(seconds=1), timedelta(days=2)])
def test_correct_at_or_after_due_advances(offset: timedelta) -> None:
    due = T0 - timedelta(hours=1)
    now = due + offset
    new_step, new_due = schedule_next(2, True, now, due)
    assert new_step == 3
    assert new_due == kst_day_start(now) + timedelta(days=INTERVAL_DAYS[3])


def test_wrong_before_due_still_decays() -> None:
    """오답은 기한과 상관없이 단계를 내린다."""
    due = KST_DAY0 + timedelta(days=3)
    new_step, new_due = schedule_next(4, False, T0, due)
    assert new_step == 2
    assert new_due == KST_DAY0 + timedelta(days=INTERVAL_DAYS[2])


def test_correct_without_due_date_advances() -> None:
    """복습 시각이 없는 단어(처음 푸는 단어, 옛 데이터)는 기한 전이 아니므로 올라간다."""
    assert schedule_next(0, True, T0, None)[0] == 1


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
    assert state.next_review_at == KST_DAY0 + timedelta(days=1)
    later = T0 + timedelta(days=1)
    state = apply_result(state, False, later)
    assert state.interval_step == 0
    assert state.next_review_at == kst_day_start(later)


def test_apply_result_early_correct_keeps_srs_but_counts_the_answer() -> None:
    """기한 전 정답: 단계·복습 시각은 그대로, 정답 수와 연속 정답(숙련)은 평소대로 쌓인다."""
    first = apply_result(new_progress(), True, T0)
    again = apply_result(first, True, T0 + timedelta(minutes=10))
    assert (again.interval_step, again.next_review_at) == (first.interval_step, first.next_review_at)
    assert (again.correct_count, again.consecutive_correct_count) == (2, 2)
    third = apply_result(again, True, T0 + timedelta(minutes=20))
    assert third.interval_step == 1 and third.is_memorized


def test_apply_result_does_not_mutate_input() -> None:
    before = apply_result(new_progress(), True, T0)
    apply_result(before, True, T0 + timedelta(days=1))
    assert before.interval_step == 1
