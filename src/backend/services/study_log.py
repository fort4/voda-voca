# 2026-11-05 - voda-voca - 답 기록의 단일 진입점: study_logs 에 이력을 더하고 user_word_progress 를 함께 갱신한다 (이슈 #3, #15, #17)
# 파일 위치: src/backend/services/study_log.py

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import StudyLog, UserWordProgress
from backend.models.study_log import STUDY_MODE_QUIZ
from backend.services.progress import ProgressState, apply_result


def progress_state_of(row: UserWordProgress) -> ProgressState:
    return ProgressState(
        correct_count=row.correct_count,
        wrong_count=row.wrong_count,
        consecutive_correct_count=row.consecutive_correct_count,
        is_memorized=row.is_memorized,
        last_result=row.last_result,
        last_studied_at=row.last_studied_at,
    )


async def record_result(
    db: AsyncSession,
    user_id: int,
    word_id: int,
    is_correct: bool,
    now: datetime,
    mode: str = STUDY_MODE_QUIZ,
) -> ProgressState:
    """답 1건을 기록한다: 학습 이력 한 줄과 사용자×단어 진행도(숙련 판정)를 같은 트랜잭션에 반영한다 (커밋은 호출자).

    답을 기록하는 모든 경로(옛 퀴즈 API, 새 세션 API)가 이 함수를 거친다. 호출자는 같은 문항을 두 번 기록하지 않아야
    한다 (세션의 answers 가 멱등을 보장한다). 숙련 규칙은 services/progress.py 의 apply_result 가 가진다.

    진행도 행이 처음이면 먼저 만들어 두고(동시 요청과 겹쳐도 한 행만 남는다) 행을 잠근 채 갱신하므로,
    같은 사용자·단어에 대한 동시 기록도 순서대로 정확히 센다.
    """
    db.add(StudyLog(user_id=user_id, word_id=word_id, is_correct=is_correct, mode=mode))
    await db.execute(
        mysql_insert(UserWordProgress)
        .values(user_id=user_id, word_id=word_id)
        .on_duplicate_key_update(user_id=UserWordProgress.user_id)
    )
    row = (
        await db.execute(
            select(UserWordProgress)
            .where(UserWordProgress.user_id == user_id, UserWordProgress.word_id == word_id)
            .with_for_update()
        )
    ).scalar_one()
    state = apply_result(progress_state_of(row), is_correct, now)
    row.correct_count = state.correct_count
    row.wrong_count = state.wrong_count
    row.consecutive_correct_count = state.consecutive_correct_count
    row.is_memorized = state.is_memorized
    row.last_result = state.last_result
    row.last_studied_at = state.last_studied_at
    return state
