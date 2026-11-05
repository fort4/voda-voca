# 2026-11-05 - voda-voca - 학습 세션 라우터: 세션 생성(활성 단어장 워터폴 출제), 문항별 답 기록
# 파일 위치: src/backend/routers/study_session.py

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.deps import get_current_user
from backend.db.session import get_db_session
from backend.models import User
from backend.models.base import utcnow
from backend.routers.study import ERROR_CODE_HEADER, QUIZ_ERRORS, quiz_http_error
from backend.schemas.learning_session import SessionAnswerIn, SessionAnswerOut, SessionCreate, SessionOut
from backend.services import learning_session as session_service
from backend.services.study import QuizSourceTooSmallError

router = APIRouter(prefix="/api/study/sessions", tags=["study-sessions"])

CODE_NO_WORDS_TO_STUDY = "NO_WORDS_TO_STUDY"
CODE_NO_VOCABULARY = "NO_VOCABULARY"


def _now() -> datetime:
    """테스트에서 바꿔 끼울 수 있도록 현재 UTC 시각을 한 곳에서 얻는다 (naive, REQ-109)."""
    return utcnow()


@router.post("", status_code=status.HTTP_201_CREATED, response_model=SessionOut)
async def create_session(
    body: SessionCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> SessionOut:
    """활성 단어장에서 한 라운드(기본 15문항)를 출제한다. 퀴즈 문항에는 정답을 싣지 않는다."""
    try:
        return await session_service.create_session(
            db, user, body.mode, body.count, body.include_memorized, now=_now()
        )
    except session_service.NoWordsToStudyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="학습할 단어가 없습니다. 숙련한 단어를 포함해 볼까요?",
            headers={ERROR_CODE_HEADER: CODE_NO_WORDS_TO_STUDY},
        ) from exc
    except session_service.NoVocabularyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="학습할 단어장이 없습니다.",
            headers={ERROR_CODE_HEADER: CODE_NO_VOCABULARY},
        ) from exc
    except QuizSourceTooSmallError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/{session_id}/answer", response_model=SessionAnswerOut)
async def answer_question(
    session_id: int,
    body: SessionAnswerIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> SessionAnswerOut:
    """문항 하나를 채점하고 학습 이력과 단어 진행도(숙련 판정)에 반영한다. 같은 답을 다시 보내도 안전하다."""
    try:
        return await session_service.record_session_answer(db, user.id, session_id, body, now=_now())
    except QUIZ_ERRORS as exc:
        raise quiz_http_error(exc) from exc
