# 2026-11-05 - voda-voca - 학습 통계 집계: 누적 정답률, 연속 학습일, 최근 7일 활동, 표준 단어장 진행률, 오답 단어, 일차 진도 (이슈 #3, #33)
# 파일 위치: src/backend/services/stats.py
"""모든 학습 지표를 study_logs 에서 읽는 시점에 집계한다. 최근 N건 제한은 없다.

이 모듈의 함수 시그니처가 지표의 계약이다. 라우터와 퀴즈 출제는 SQL 이 아니라 이 함수만 부른다.
나중에 사용자·단어별 요약 테이블로 바꾸더라도 이 파일의 내부 구현만 바꾸면 된다.
"""

from datetime import date, datetime, time, timedelta

from sqlalchemy import Date, Integer, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Bookmark, QuizSession, StudyLog, SystemVocabulary, SystemWord, User, UserWordProgress, visible_to
from backend.models.study_log import STUDY_MODE_QUIZ
from backend.schemas.study import (
    DailyScoreOut,
    DayActivityOut,
    DayProgressOut,
    FrequentWrongOut,
    ScoreTrendOut,
    SessionScoreOut,
    StudyStatsOut,
    VocabularyProgressOut,
)
from backend.services.srs import KST_OFFSET  # 학습일 경계(한국 시각 자정) 상수는 srs 와 공유한다
from backend.services.study_day import current_day

WEEK_DAYS = 7
STREAK_LOOKBACK_DAYS = 3700  # 연속 학습일을 거슬러 볼 최대 일수 (약 10년). 날짜 하나가 한 행이라 가볍다
WEEKDAY_LABELS = ["월", "화", "수", "목", "금", "토", "일"]  # date.weekday() 순서


def kst_today(now: datetime) -> date:
    """UTC 로 주어진 지금 시각의 한국 날짜."""
    return (now + KST_OFFSET).date()


def kst_day_of(column):
    """UTC 로 저장된 시각 컬럼을 한국 날짜(DATE)로 바꾸는 SQL 식 (SQLite date() 에 +9 시간 보정을 준다)."""
    return func.date(column, "+9 hours", type_=Date)


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


async def due_review_count(db: AsyncSession, user_id: int, now: datetime) -> int:
    """오늘 복습할 단어 수 (SRS, 이슈 #25): 복습 예정 시각이 지금 이전인 단어. 시각이 비어 있으면 세지 않는다."""
    return int(
        await db.scalar(
            select(func.count()).where(
                UserWordProgress.user_id == user_id,
                UserWordProgress.next_review_at.is_not(None),
                UserWordProgress.next_review_at <= now,
            )
        )
        or 0
    )


async def due_word_ids(db: AsyncSession, user_id: int, now: datetime) -> set[int]:
    """오늘 복습할 단어 ID. due_review_count 와 같은 조건이라 화면의 개수와 출제 대상이 항상 같다."""
    rows = await db.execute(
        select(UserWordProgress.word_id).where(
            UserWordProgress.user_id == user_id,
            UserWordProgress.next_review_at.is_not(None),
            UserWordProgress.next_review_at <= now,
        )
    )
    return set(rows.scalars())


async def _answer_totals(db: AsyncSession, user_id: int) -> tuple[int, int]:
    """(누적 푼 문항 수, 그중 정답 수)."""
    # SUM(is_correct) 는 컬럼 타입(Boolean)을 따라 결과가 True/False 로 바뀌어 버린다. CASE 로 정수 합계를 만든다.
    correct = func.coalesce(func.sum(case((StudyLog.is_correct.is_(True), 1), else_=0), type_=Integer), 0)
    row = (await db.execute(select(func.count(), correct).where(StudyLog.user_id == user_id))).one()
    return int(row[0]), int(row[1])


async def _streak_days(db: AsyncSession, user_id: int, today: date) -> int:
    """오늘부터 거꾸로 학습한 날이 끊기지 않은 일수. 오늘 아직 안 풀었으면 어제부터 센다."""
    day = kst_day_of(StudyLog.created_at)
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
    day = kst_day_of(StudyLog.created_at)
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
    """단어장별 진행률: 한 번이라도 맞힌 단어 수 / 단어 수. 맞힌 뒤 틀려도 학습한 단어로 센다.

    표준 단어장과 내 개인 단어장(sort_order, id 순)을 보여 주고, 맞힌 수는 사용자별로 센다.
    """
    sizes = (
        await db.execute(
            select(SystemVocabulary.id, func.count(SystemWord.id))
            .outerjoin(SystemWord, SystemWord.vocabulary_id == SystemVocabulary.id)
            .where(visible_to(user_id))
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


async def _day_progress(db: AsyncSession, user_id: int, now: datetime) -> DayProgressOut | None:
    """학습 중인 단어장의 지금 일차와 그 일차에 학습한 단어 수 (REQ-165, VOCA-FR-031)."""
    user = await db.get(User, user_id)
    if user is None or user.active_vocabulary_id is None:
        return None
    visible = await db.scalar(
        select(SystemVocabulary.id).where(SystemVocabulary.id == user.active_vocabulary_id, visible_to(user_id))
    )
    if visible is None:
        return None
    day, words = await current_day(db, user_id, user.active_vocabulary_id, user.daily_goal, now)
    return DayProgressOut(vocabulary_id=user.active_vocabulary_id, day=day, words=words)


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
        due_review_count=await due_review_count(db, user_id, now),
        day_progress=await _day_progress(db, user_id, now),
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


def _percent(correct: int, total: int) -> float:
    """정답률(0~100, 소수 첫째 자리). total 이 0 이면 0.0 이다."""
    return round(correct / total * 100, 1) if total else 0.0


async def list_frequent_wrong(db: AsyncSession, user_id: int, limit: int) -> list[FrequentWrongOut]:
    """자주 틀리는 단어 상위 limit 개 (VOCA-FR-033, 034). study_logs 의 오답 행 수로 센다.

    오답 복습 목록(wrong_word_ids)은 "마지막 결과가 오답"이라 맞히면 빠지지만, 이 목록은 누적 횟수라 맞혀도 줄지 않는다.
    횟수가 같으면 최근에 틀린 단어가 먼저, 그래도 같으면 단어 ID 순이다. 틀린 적 없는 단어는 넣지 않는다.
    """
    wrong = func.sum(case((StudyLog.is_correct.is_(False), 1), else_=0), type_=Integer)
    last_wrong = func.max(case((StudyLog.is_correct.is_(False), StudyLog.created_at), else_=None))
    rows = await db.execute(
        select(SystemWord, SystemVocabulary.title, wrong, func.count(), last_wrong)
        .join(StudyLog, StudyLog.word_id == SystemWord.id)
        .join(SystemVocabulary, SystemVocabulary.id == SystemWord.vocabulary_id)
        .where(StudyLog.user_id == user_id)
        .group_by(SystemWord.id, SystemVocabulary.title)
        .having(wrong > 0)
        .order_by(wrong.desc(), last_wrong.desc(), SystemWord.id)
        .limit(limit)
    )
    return [
        FrequentWrongOut(
            word_id=word.id,
            vocabulary_id=word.vocabulary_id,
            vocabulary_title=title,
            term=word.term,
            meaning=word.meaning,
            wrong_count=int(wrong_count),
            answered_count=int(answered),
            last_wrong_at=last,
        )
        for word, title, wrong_count, answered, last in rows.all()
    ]


def _session_score(session: QuizSession) -> tuple[int, int] | None:
    """(문항 수, 정답 수). 아직 끝까지 풀지 않은 세션이면 None.

    끝났는지는 학습 세션 화면과 같은 기준(답한 문항 수 >= 문항 수)으로 정한다. 채점은 저장된 정답 번호와 고른 번호를 비교한다.
    """
    total = len(session.questions)
    answers = session.answers or {}
    if total == 0 or len(answers) < total:
        return None
    correct = sum(1 for q in session.questions if answers.get(str(q["question_id"])) == q["correct_index"])
    return total, correct


async def get_score_trend(db: AsyncSession, user_id: int, now: datetime, sessions: int, days: int) -> ScoreTrendOut:
    """시험 성적 추이 (VOCA-FR-032, 034): 회차별(끝까지 푼 퀴즈)과 날짜별(퀴즈 문항 이력) 정답률.

    회차 번호는 전체 이력의 오래된 순서이며, sessions 는 그중 최근 몇 회를 보여 줄지만 정한다.
    날짜별은 오늘을 포함한 최근 days 일 중 기록이 있는 날만 오래된 날부터 돌려준다.
    """
    session_rows = await db.execute(
        select(QuizSession)
        .where(QuizSession.user_id == user_id, QuizSession.mode == STUDY_MODE_QUIZ)
        .order_by(QuizSession.created_at, QuizSession.id)
    )
    finished = [(row, score) for row in session_rows.scalars() if (score := _session_score(row)) is not None]
    rounds = [
        SessionScoreOut(
            round=number,
            session_id=row.id,
            taken_at=row.created_at,
            total=total,
            correct=correct,
            accuracy=_percent(correct, total),
        )
        for number, (row, (total, correct)) in enumerate(finished, start=1)
    ]

    first = kst_today(now) - timedelta(days=days - 1)
    day = kst_day_of(StudyLog.created_at)
    right = func.sum(case((StudyLog.is_correct.is_(True), 1), else_=0), type_=Integer)
    daily_rows = await db.execute(
        select(day, func.count(), right)
        .where(
            StudyLog.user_id == user_id,
            StudyLog.mode == STUDY_MODE_QUIZ,
            StudyLog.created_at >= datetime.combine(first, time.min) - KST_OFFSET,
        )
        .group_by(day)
        .order_by(day)
    )
    daily = [
        DailyScoreOut(date=d, answered=int(n), correct=int(c), accuracy=_percent(int(c), int(n)))
        for d, n, c in daily_rows.all()
    ]
    return ScoreTrendOut(sessions=rounds[-sessions:], daily=daily)
