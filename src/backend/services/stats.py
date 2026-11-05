# 2026-11-05 - voda-voca - 학습 통계 집계: 누적 정답률, 연속 학습일, 최근 7일 활동, 표준 단어장 진행률, 오답 단어 (이슈 #3)
# 파일 위치: src/backend/services/stats.py
"""모든 학습 지표를 study_logs 에서 읽는 시점에 집계한다. 최근 N건 제한은 없다.

이 모듈의 함수 시그니처가 지표의 계약이다. 라우터와 퀴즈 출제는 SQL 이 아니라 이 함수만 부른다.
나중에 사용자·단어별 요약 테이블로 바꾸더라도 이 파일의 내부 구현만 바꾸면 된다.
"""

from datetime import date, datetime, time, timedelta

from sqlalchemy import Integer, case, func, literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Bookmark, StudyLog, SystemVocabulary, SystemWord
from backend.schemas.study import DayActivityOut, StudyStatsOut, VocabularyProgressOut

KST_OFFSET = timedelta(hours=9)  # 학습일 경계는 한국 시각 자정이다 (DB 에는 UTC 로 저장)
WEEK_DAYS = 7
STREAK_LOOKBACK_DAYS = 3700  # 연속 학습일을 거슬러 볼 최대 일수 (약 10년). 날짜 하나가 한 행이라 가볍다
WEEKDAY_LABELS = ["월", "화", "수", "목", "금", "토", "일"]  # date.weekday() 순서


def kst_today(now: datetime) -> date:
    """UTC 로 주어진 지금 시각의 한국 날짜."""
    return (now + KST_OFFSET).date()


def _kst_day_of(column):
    """UTC 로 저장된 시각 컬럼을 한국 날짜(DATE)로 바꾸는 SQL 식."""
    return func.date(func.date_add(column, literal_column("INTERVAL 9 HOUR")))


async def wrong_word_ids(db: AsyncSession, user_id: int) -> set[int]:
    """오답 복습 대상: 단어별 가장 최근 결과가 오답인 단어 ID. 맞히면 대상에서 빠진다.

    "가장 최근"은 (created_at, id) 내림차순으로 정한다. 같은 시각이면 나중에 기록된 것이 최신이다.
    통계의 오답 단어 수와 퀴즈 출제가 이 함수를 함께 쓰므로 화면에 보이는 개수와 출제 대상이 항상 같다.
    """
    latest = (
        select(
            StudyLog.word_id.label("word_id"),
            StudyLog.is_correct.label("is_correct"),
            func.row_number()
            .over(
                partition_by=StudyLog.word_id,
                order_by=(StudyLog.created_at.desc(), StudyLog.id.desc()),
            )
            .label("rn"),
        )
        .where(StudyLog.user_id == user_id)
        .subquery()
    )
    rows = await db.execute(select(latest.c.word_id).where(latest.c.rn == 1, latest.c.is_correct.is_(False)))
    return set(rows.scalars())


async def _answer_totals(db: AsyncSession, user_id: int) -> tuple[int, int]:
    """(누적 푼 문항 수, 그중 정답 수)."""
    # SUM(is_correct) 는 컬럼 타입(Boolean)을 따라 결과가 True/False 로 바뀌어 버린다. CASE 로 정수 합계를 만든다.
    correct = func.coalesce(func.sum(case((StudyLog.is_correct.is_(True), 1), else_=0), type_=Integer), 0)
    row = (await db.execute(select(func.count(), correct).where(StudyLog.user_id == user_id))).one()
    return int(row[0]), int(row[1])


async def _streak_days(db: AsyncSession, user_id: int, today: date) -> int:
    """오늘부터 거꾸로 학습한 날이 끊기지 않은 일수. 오늘 아직 안 풀었으면 어제부터 센다."""
    day = _kst_day_of(StudyLog.created_at)
    rows = await db.execute(
        select(day)
        .where(StudyLog.user_id == user_id, StudyLog.created_at >= datetime.combine(today - timedelta(days=STREAK_LOOKBACK_DAYS), time.min) - KST_OFFSET)
        .distinct()
        .order_by(day.desc())
    )
    studied = set(rows.scalars())
    cursor = today if today in studied else today - timedelta(days=1)
    streak = 0
    while cursor in studied:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


async def _weekly(db: AsyncSession, user_id: int, today: date) -> list[DayActivityOut]:
    """오늘을 포함한 최근 7일의 날짜별 학습 단어 수(같은 단어를 여러 번 풀어도 1). 오래된 날부터."""
    first = today - timedelta(days=WEEK_DAYS - 1)
    day = _kst_day_of(StudyLog.created_at)
    rows = await db.execute(
        select(day, func.count(func.distinct(StudyLog.word_id)))
        .where(StudyLog.user_id == user_id, StudyLog.created_at >= datetime.combine(first, time.min) - KST_OFFSET)
        .group_by(day)
    )
    counts = {d: int(n) for d, n in rows.all()}
    days = [first + timedelta(days=i) for i in range(WEEK_DAYS)]
    return [
        DayActivityOut(date=d, label=WEEKDAY_LABELS[d.weekday()], count=counts.get(d, 0), is_today=d == today)
        for d in days
    ]


async def _vocabulary_progress(db: AsyncSession, user_id: int) -> list[VocabularyProgressOut]:
    """표준 단어장별 진행률: 한 번이라도 맞힌 단어 수 / 단어 수. 맞힌 뒤 틀려도 학습한 단어로 센다.

    표준 단어장은 모든 사용자가 공유하므로 전체 목록(sort_order, id 순)을 보여 주고, 맞힌 수만 사용자별로 센다.
    """
    sizes = (
        await db.execute(
            select(SystemVocabulary.id, func.count(SystemWord.id))
            .outerjoin(SystemWord, SystemWord.vocabulary_id == SystemVocabulary.id)
            .group_by(SystemVocabulary.id, SystemVocabulary.sort_order)
            .order_by(SystemVocabulary.sort_order, SystemVocabulary.id)
        )
    ).all()
    learned = dict(
        (
            await db.execute(
                select(SystemWord.vocabulary_id, func.count(func.distinct(SystemWord.id)))
                .join(StudyLog, StudyLog.word_id == SystemWord.id)
                .where(StudyLog.user_id == user_id, StudyLog.is_correct.is_(True))
                .group_by(SystemWord.vocabulary_id)
            )
        ).all()
    )
    result = []
    for vocabulary_id, word_count in sizes:
        learned_words = int(learned.get(vocabulary_id, 0))
        percent = min(100, int(learned_words * 100 / word_count + 0.5)) if word_count else 0
        result.append(
            VocabularyProgressOut(
                vocabulary_id=vocabulary_id, word_count=int(word_count), learned_words=learned_words, percent=percent
            )
        )
    return result


async def get_study_stats(db: AsyncSession, user_id: int, now: datetime) -> StudyStatsOut:
    """대시보드·이력·퀴즈 설정 화면이 쓰는 학습 지표 전체."""
    today = kst_today(now)
    answered, correct = await _answer_totals(db, user_id)
    progress = await _vocabulary_progress(db, user_id)
    return StudyStatsOut(
        answered=answered,
        correct=correct,
        accuracy=round(correct / answered * 100, 1) if answered else None,
        streak_days=await _streak_days(db, user_id, today),
        weekly=await _weekly(db, user_id, today),
        total_words=sum(p.word_count for p in progress),
        vocabulary_progress=progress,
        wrong_word_count=len(await wrong_word_ids(db, user_id)),
    )


async def list_wrong_words(db: AsyncSession, user_id: int, page: int, size: int) -> tuple[list[tuple], int]:
    """오답 복습 대상 단어 목록. wrong_word_ids 와 같은 규칙(단어별 가장 최근 결과가 오답)이며, 최근에 틀린 순서다.

    각 행은 (SystemWord, SystemVocabulary, 북마크 여부, 틀린 시각). 두 번째 값은 전체 개수(페이지와 무관).
    """
    latest = (
        select(
            StudyLog.word_id.label("word_id"),
            StudyLog.is_correct.label("is_correct"),
            StudyLog.created_at.label("created_at"),
            StudyLog.id.label("log_id"),
            func.row_number()
            .over(partition_by=StudyLog.word_id, order_by=(StudyLog.created_at.desc(), StudyLog.id.desc()))
            .label("rn"),
        )
        .where(StudyLog.user_id == user_id)
        .subquery()
    )
    wrong = select(latest.c.word_id, latest.c.created_at, latest.c.log_id).where(latest.c.rn == 1, latest.c.is_correct.is_(False)).subquery()
    total = int(await db.scalar(select(func.count()).select_from(wrong)) or 0)
    rows = await db.execute(
        select(SystemWord, SystemVocabulary, Bookmark.id.is_not(None), wrong.c.created_at)
        .join(wrong, wrong.c.word_id == SystemWord.id)
        .join(SystemVocabulary, SystemVocabulary.id == SystemWord.vocabulary_id)
        .outerjoin(Bookmark, (Bookmark.word_id == SystemWord.id) & (Bookmark.user_id == user_id))
        .order_by(wrong.c.created_at.desc(), wrong.c.log_id.desc())
        .limit(size)
        .offset((page - 1) * size)
    )
    return [tuple(row) for row in rows.all()], total
