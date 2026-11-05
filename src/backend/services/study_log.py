# 2026-11-05 - voda-voca - 학습 이력 기록의 단일 진입점: 답 1건을 study_logs 에 더한다 (이슈 #3)
# 파일 위치: src/backend/services/study_log.py

from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import StudyLog
from backend.models.study_log import STUDY_MODE_QUIZ


def add_study_log(
    db: AsyncSession, user_id: int, word_id: int, is_correct: bool, mode: str = STUDY_MODE_QUIZ
) -> None:
    """학습 이력 1건을 세션에 더한다 (커밋은 호출자가 한다).

    답을 기록하는 모든 경로가 이 함수를 거친다. 나중에 단어별 요약 테이블(user_word_stats)을 함께 갱신해야 할 때
    이 한 곳만 고치면 된다.
    """
    db.add(StudyLog(user_id=user_id, word_id=word_id, is_correct=is_correct, mode=mode))
