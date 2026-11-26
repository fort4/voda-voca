# 2026-11-26 - voda-voca - 학습 순위 집계: 공개한 사용자의 학습 단어 수·활동량을 study_logs 에서 계산해 순위를 매긴다 (REQ-172, VOCA-FR-051~053)
# 파일 위치: src/backend/services/ranking.py
"""지표는 모두 서로 다른 값(단어, 날짜)을 세므로 같은 단어를 반복해 풀어도 늘지 않는다. 읽기만 한다."""

from dataclasses import dataclass
from datetime import datetime, time, timedelta

from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import StudyLog, User
from backend.schemas.ranking import RankingEntryOut, RankingMeOut, RankingMetric, RankingOut
from backend.services.srs import KST_OFFSET
from backend.services.stats import WEEK_DAYS, kst_day_of, kst_today

RANKING_LIMIT = 50


@dataclass(frozen=True)
class Standing:
    """사용자 한 명의 지표."""

    user_id: int
    nickname: str
    public: bool
    learned_words: int
    week_words: int
    week_days: int

    def metrics(self) -> dict[str, int]:
        return {"learned_words": self.learned_words, "week_words": self.week_words, "week_days": self.week_days}


def rank_standings(standings: list[Standing], metric: RankingMetric) -> list[tuple[int, Standing]]:
    """지표 내림차순으로 (순위, 사용자)를 만든다. 값이 같으면 같은 순위(1, 1, 3)이고 그 안에서는 닉네임 순이다."""
    ordered = sorted(standings, key=lambda s: (-getattr(s, metric), s.nickname.casefold()))
    result: list[tuple[int, Standing]] = []
    for position, standing in enumerate(ordered, start=1):
        tied = result and getattr(result[-1][1], metric) == getattr(standing, metric)
        result.append((result[-1][0] if tied else position, standing))
    return result


async def _standings(db: AsyncSession, user_id: int, now: datetime) -> list[Standing]:
    """공개한 사용자와 본인의 지표. 비공개인 남의 기록은 읽지 않는다 (VOCA-FR-052).

    learned_words 는 단어장 진행률과 같은 정의(한 번이라도 맞힌 단어)이고, 최근 7일은 오늘을 포함한 한국 날짜다.
    """
    week_start = datetime.combine(kst_today(now) - timedelta(days=WEEK_DAYS - 1), time.min) - KST_OFFSET
    in_week = StudyLog.created_at >= week_start
    rows = await db.execute(
        select(
            User.id,
            User.nickname,
            User.ranking_public,
            func.count(func.distinct(case((StudyLog.is_correct.is_(True), StudyLog.word_id)))),
            func.count(func.distinct(case((in_week, StudyLog.word_id)))),
            func.count(func.distinct(case((in_week, kst_day_of(StudyLog.created_at))))),
        )
        .outerjoin(StudyLog, StudyLog.user_id == User.id)
        .where(or_(User.ranking_public.is_(True), User.id == user_id))
        .group_by(User.id)
    )
    return [Standing(*row) for row in rows.all()]


async def get_ranking(db: AsyncSession, user_id: int, metric: RankingMetric, now: datetime) -> RankingOut:
    """상위 RANKING_LIMIT 명과 본인 지표. 본인은 순위 밖이어도 me 에 담는다."""
    standings = await _standings(db, user_id, now)
    mine = next(s for s in standings if s.user_id == user_id)
    ranked = rank_standings([s for s in standings if s.public], metric)
    return RankingOut(
        metric=metric,
        items=[
            RankingEntryOut(rank=rank, nickname=s.nickname, is_me=s.user_id == user_id, **s.metrics())
            for rank, s in ranked[:RANKING_LIMIT]
        ],
        total_public=len(ranked),
        me=RankingMeOut(
            public=mine.public,
            rank=next((rank for rank, s in ranked if s.user_id == user_id), None),
            **mine.metrics(),
        ),
    )
