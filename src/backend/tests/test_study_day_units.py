# 2026-11-26 - voda-voca - 일차 계산 규칙 단위 테스트: 학습량을 채우고 날짜가 바뀌면 다음 일차 (REQ-165)
# 파일 위치: src/backend/tests/test_study_day_units.py

from datetime import date

import pytest

from backend.services.study_day import next_study_day

pytestmark = pytest.mark.no_db

YESTERDAY, TODAY = date(2026, 11, 25), date(2026, 11, 26)


def test_the_first_study_is_day_one() -> None:
    assert next_study_day(None, None, TODAY, 0, 10) == 1


@pytest.mark.parametrize(
    ("last_date", "words", "expected"),
    [
        (TODAY, 3, 2),  # 같은 날, 학습량 미달
        (TODAY, 10, 2),  # 같은 날에는 학습량을 채워도 넘어가지 않는다 (하루에 한 일차)
        (TODAY, 25, 2),
        (YESTERDAY, 9, 2),  # 날짜가 바뀌어도 못 채웠으면 이어 간다
        (YESTERDAY, 10, 3),
        (YESTERDAY, 11, 3),
        (date(2026, 11, 1), 10, 3),  # 오래 쉬어도 한 일차만 넘어간다
        (date(2026, 11, 27), 10, 2),  # 시계가 거꾸로 간 기록은 넘기지 않는다
    ],
)
def test_the_day_advances_only_when_the_amount_is_met_and_the_date_changed(
    last_date: date, words: int, expected: int
) -> None:
    assert next_study_day(2, last_date, TODAY, words, 10) == expected


@pytest.mark.parametrize(("goal", "expected"), [(10, 2), (20, 1), (30, 1)])
def test_the_amount_follows_the_daily_goal(goal: int, expected: int) -> None:
    assert next_study_day(1, YESTERDAY, TODAY, 10, goal) == expected
