# 2026-11-05 - voda-voca - 단어 숙련도 갱신 순수 함수: 연속 정답 3회 숙련, 오답 시 리셋 (이슈 #15 안 A)
# 파일 위치: src/backend/services/progress.py
"""DB 와 무관한 순수 로직이다. user_word_progress 한 행의 값을 ProgressState 로 받아 새 값을 돌려준다.

라우터/서비스는 행을 ProgressState 로 바꿔 apply_result 를 부르고, 결과를 행에 되쓰기만 한다.
숙련 규칙: 연속 정답이 MEMORIZE_STREAK 회에 닿으면 is_memorized = True.
오답 1회면 연속 정답 0, is_memorized = False (숙련 이후의 오답도 같다).
"""

from dataclasses import dataclass, replace
from datetime import datetime

from backend.services.srs import schedule_next

MEMORIZE_STREAK = 3

CORRECT = "CORRECT"
WRONG = "WRONG"


@dataclass(frozen=True)
class ProgressState:
    correct_count: int = 0
    wrong_count: int = 0
    consecutive_correct_count: int = 0
    is_memorized: bool = False
    last_result: str | None = None  # 'CORRECT' | 'WRONG' | None
    last_studied_at: datetime | None = None
    interval_step: int = 0  # SRS 복습 단계 0~5 (이슈 #25)
    next_review_at: datetime | None = None


def new_progress() -> ProgressState:
    """한 번도 학습하지 않은 단어의 초기 상태."""
    return ProgressState()


def apply_result(
    state: ProgressState,
    is_correct: bool,
    now: datetime,
    memorize_streak: int = MEMORIZE_STREAK,
) -> ProgressState:
    """답 하나를 반영한 새 상태를 돌려준다. 입력 상태는 바꾸지 않는다."""
    step, due = schedule_next(state.interval_step, is_correct, now)
    if is_correct:
        streak = state.consecutive_correct_count + 1
        return replace(
            state,
            correct_count=state.correct_count + 1,
            consecutive_correct_count=streak,
            is_memorized=streak >= memorize_streak,
            last_result=CORRECT,
            last_studied_at=now,
            interval_step=step,
            next_review_at=due,
        )
    return replace(
        state,
        wrong_count=state.wrong_count + 1,
        consecutive_correct_count=0,
        is_memorized=False,
        last_result=WRONG,
        last_studied_at=now,
        interval_step=step,
        next_review_at=due,
    )
