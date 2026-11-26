# 2026-11-26 - voda-voca - 학습 순위 라우터: 순위 조회(읽기 전용)와 내 공개 설정 (REQ-172, REQ-173)
# 파일 위치: src/backend/routers/ranking.py
"""다른 사용자를 지정하는 입력은 없다. 쓰기는 로그인한 본인의 공개 설정뿐이다 (VOCA-FR-053)."""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.deps import get_current_user
from backend.db.session import get_db_session
from backend.models import User
from backend.models.base import utcnow
from backend.schemas.ranking import RankingMetric, RankingOut, RankingVisibility
from backend.services import ranking as ranking_service

router = APIRouter(prefix="/api", tags=["ranking"])


def _now() -> datetime:
    """테스트에서 바꿔 끼울 수 있도록 현재 UTC 시각을 한 곳에서 얻는다 (naive, REQ-109)."""
    return utcnow()


@router.get("/ranking", response_model=RankingOut)
async def get_ranking(
    metric: RankingMetric = Query(default="learned_words"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> RankingOut:
    """공개한 사용자의 학습 순위와 내 지표 (VOCA-FR-051)."""
    return await ranking_service.get_ranking(db, user.id, metric, _now())


@router.get("/users/me/ranking-visibility", response_model=RankingVisibility)
async def get_visibility(user: User = Depends(get_current_user)) -> RankingVisibility:
    return RankingVisibility(public=user.ranking_public)


@router.put("/users/me/ranking-visibility", response_model=RankingVisibility)
async def set_visibility(
    body: RankingVisibility,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> RankingVisibility:
    """내 순위 공개 여부를 정한다 (VOCA-FR-052)."""
    user.ranking_public = body.public
    await db.commit()
    return body
