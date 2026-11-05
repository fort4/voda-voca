# 2026-11-05 - voda-voca - 단어 숙련도 갱신 순수 함수 테스트: 연속 정답 3회 숙련, 오답 시 리셋 (이슈 #15 안 A)
# 파일 위치: src/backend/tests/test_progress_units.py

from datetime import datetime, timedelta

import pytest

from backend.services.progress import MEMORIZE_STREAK, ProgressState, apply_result, new_progress

T0 = datetime(2026, 11, 5, 9, 0, 0)


def _apply_all(results: list[bool], state: ProgressState | None = None) -> ProgressState:
    state = state or new_progress()
    for index, ok in enumerate(results):
        state = apply_result(state, ok, T0 + timedelta(minutes=index))
    return state


def test_threshold_is_three() -> None:
    assert MEMORIZE_STREAK == 3


def test_new_progress_is_all_zero_and_not_memorized() -> None:
    state = new_progress()
    assert (state.correct_count, state.wrong_count, state.consecutive_correct_count) == (0, 0, 0)
    assert state.is_memorized is False
    assert state.last_result is None and state.last_studied_at is None


def test_first_correct_answer() -> None:
    state = apply_result(new_progress(), True, T0)
    assert (state.correct_count, state.wrong_count, state.consecutive_correct_count) == (1, 0, 1)
    assert state.last_result == "CORRECT"
    assert state.last_studied_at == T0
    assert state.is_memorized is False


def test_first_wrong_answer() -> None:
    state = apply_result(new_progress(), False, T0)
    assert (state.correct_count, state.wrong_count, state.consecutive_correct_count) == (0, 1, 0)
    assert state.last_result == "WRONG"
    assert state.is_memorized is False


@pytest.mark.parametrize(("streak", "memorized"), [(1, False), (2, False), (3, True), (4, True), (10, True)])
def test_memorized_exactly_from_the_third_consecutive_correct(streak: int, memorized: bool) -> None:
    state = _apply_all([True] * streak)
    assert state.consecutive_correct_count == streak
    assert state.is_memorized is memorized


def test_wrong_before_the_threshold_resets_the_streak() -> None:
    state = _apply_all([True, True, False])
    assert state.consecutive_correct_count == 0
    assert state.is_memorized is False
    assert (state.correct_count, state.wrong_count) == (2, 1)


def test_two_correct_after_reset_is_not_enough() -> None:
    state = _apply_all([True, True, False, True, True])
    assert state.consecutive_correct_count == 2
    assert state.is_memorized is False


def test_three_correct_after_reset_memorizes_again() -> None:
    state = _apply_all([True, True, False, True, True, True])
    assert state.consecutive_correct_count == 3
    assert state.is_memorized is True
    assert (state.correct_count, state.wrong_count) == (5, 1)


def test_wrong_after_memorized_clears_memorized_and_streak() -> None:
    memorized = _apply_all([True, True, True])
    assert memorized.is_memorized is True
    state = apply_result(memorized, False, T0 + timedelta(hours=1))
    assert state.is_memorized is False
    assert state.consecutive_correct_count == 0
    assert state.last_result == "WRONG"
    assert state.wrong_count == 1 and state.correct_count == 3


def test_correct_answers_after_memorized_keep_it_memorized() -> None:
    state = _apply_all([True, True, True, True])
    assert state.is_memorized is True
    assert state.correct_count == 4


def test_last_studied_at_follows_the_latest_answer() -> None:
    state = _apply_all([True, False, True])
    assert state.last_studied_at == T0 + timedelta(minutes=2)


def test_apply_result_does_not_mutate_the_input() -> None:
    before = new_progress()
    apply_result(before, True, T0)
    assert before == new_progress()


def test_streak_length_is_configurable_for_boundary_checks() -> None:
    state = new_progress()
    for _ in range(4):
        state = apply_result(state, True, T0, memorize_streak=5)
    assert state.is_memorized is False
    state = apply_result(state, True, T0, memorize_streak=5)
    assert state.is_memorized is True


def test_counters_accumulate_over_a_mixed_history() -> None:
    state = _apply_all([True, False, False, True, True, True, False])
    assert (state.correct_count, state.wrong_count) == (4, 3)
    assert state.consecutive_correct_count == 0 and state.is_memorized is False
