# 2026-11-05 - voda-voca - 학습 지표 라우터: 통계, 오답 단어 목록, 학습 이력 (REQ-016). 출제·채점은 study_session.py 가 맡는다
# 파일 위치: src/backend/routers/study.py

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.deps import get_current_user
from backend.db.session import get_db_session
from backend.models import User
from backend.models.base import utcnow
from backend.schemas.study import (
    STUDY_LOG_LIMIT,
    StudyLogList,
    StudyLogOut,
    StudyStatsOut,
    WrongWordOut,
    WrongWordPage,
)
from backend.services import stats as stats_service
from backend.services import study as study_service

router = APIRouter(prefix="/api/study", tags=["study"])


def _now() -> datetime:
    """테스트에서 바꿔 끼울 수 있도록 현재 UTC 시각을 한 곳에서 얻는다 (naive, REQ-109)."""
    return utcnow()


@router.get("/stats", response_model=StudyStatsOut)
async def get_study_stats(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> StudyStatsOut:
    """학습 지표 전체 (누적 정답률, 연속 학습일, 최근 7일, 단어장 진행률, 오답 단어 수). 최근 N건 제한이 없다."""
    return await stats_service.get_study_stats(db, user.id, now=_now())


@router.get("/wrong-words", response_model=WrongWordPage)
async def list_wrong_words(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> WrongWordPage:
    """오답 복습 대상 단어 목록 (단어별 마지막 결과가 오답). 최근에 틀린 순서이며 통계의 오답 단어 수와 같은 규칙이다."""
    rows, total = await stats_service.list_wrong_words(db, user.id, page, size)
    items = [
        WrongWordOut(
            word_id=word.id,
            vocabulary_id=vocabulary.id,
            vocabulary_title=vocabulary.title,
            term=word.term,
            meaning=word.meaning,
            example=word.example,
            example_meaning=word.example_meaning,
            pos=word.pos,
            phonetic=word.phonetic,
            bookmarked=bool(bookmarked),
            wrong_at=wrong_at,
        )
        for word, vocabulary, bookmarked, wrong_at in rows
    ]
    return WrongWordPage(items=items, total=total, page=page, size=size)


@router.get("/logs", response_model=StudyLogList)
async def list_study_logs(
    limit: int = Query(default=STUDY_LOG_LIMIT, ge=1, le=STUDY_LOG_LIMIT),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> StudyLogList:
    rows = await study_service.list_study_logs(db, user.id, limit)
    return StudyLogList(
        items=[
            StudyLogOut(
                word_id=word_id,
                vocabulary_id=vocabulary_id,
                term=term,
                is_correct=is_correct,
                created_at=created_at,
            )
            for word_id, vocabulary_id, term, is_correct, created_at in rows
        ]
    )
