# 2026-11-26 - voda-voca - 일차 진도: 하루 학습량을 채우고 날짜가 바뀌면 다음 일차. 사용자별·단어장별로 센다 (REQ-165)
# 파일 위치: src/backend/services/study_day.py

from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import StudyLog, SystemWord
from backend.services.srs import KST_OFFSET  # 학습일 경계(한국 시각 자정)는 통계·복습과 같다


def next_study_day(last_day: int | None, last_date: date | None, today: date, last_day_words: int, goal: int) -> int:
    """지금 학습하면 몇 일차인지 정한다.

    - 기록이 없으면 1일차.
    - 마지막 일차의 학습량(서로 다른 단어 goal 개)을 채웠고, 마지막 학습보다 뒤의 날짜면 다음 일차.
    - 그 밖(같은 날이거나 학습량 미달)에는 마지막 일차를 이어 간다. 오래 쉬어도 한 일차만 넘어간다.
    """
    if last_day is None or last_date is None:
        return 1
    if today > last_date and last_day_words >= goal:
        return last_day + 1
    return last_day


async def current_day(
    db: AsyncSession, user_id: int, vocabulary_id: int, goal: int, now: datetime
) -> tuple[int, int]:
    """이 단어장의 (지금 일차, 그 일차에 학습한 서로 다른 단어 수). 일차가 없는 옛 기록은 보지 않는다.

    이력에 적을 때와 화면에 보일 때 같은 함수를 써서 두 값이 어긋나지 않게 한다.
    """
    in_vocabulary = (StudyLog.user_id == user_id, SystemWord.vocabulary_id == vocabulary_id)
    last = (
        await db.execute(
            select(StudyLog.study_day, StudyLog.created_at)
            .join(SystemWord, SystemWord.id == StudyLog.word_id)
            .where(*in_vocabulary, StudyLog.study_day.is_not(None))
            .order_by(StudyLog.study_day.desc(), StudyLog.created_at.desc())
            .limit(1)
        )
    ).first()
    if last is None:
        return 1, 0
    last_day, last_at = last
    words = await db.scalar(
        select(func.count(func.distinct(StudyLog.word_id)))
        .join(SystemWord, SystemWord.id == StudyLog.word_id)
        .where(*in_vocabulary, StudyLog.study_day == last_day)
    )
    day = next_study_day(last_day, (last_at + KST_OFFSET).date(), (now + KST_OFFSET).date(), int(words or 0), goal)
    return day, int(words or 0) if day == last_day else 0
