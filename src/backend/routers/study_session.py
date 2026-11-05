# 2026-11-05 - voda-voca - 학습 세션 라우터: 세션 생성(활성 단어장 워터폴 출제), 문항별 답 기록
# 파일 위치: src/backend/routers/study_session.py

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.deps import get_current_user
from backend.db.session import get_db_session
from backend.models import User
from backend.models.base import utcnow
from backend.schemas.learning_session import SessionAnswerIn, SessionAnswerOut, SessionCreate, SessionOut
from backend.services import learning_session as session_service
from backend.services.study import (
    QuizAlreadySubmittedError,
    QuizAnswerError,
    QuizAnswerLockedError,
    QuizExpiredError,
    QuizSessionNotFoundError,
    QuizSourceTooSmallError,
    QuizWordMissingError,
    StudyError,
)

router = APIRouter(prefix="/api/study/sessions", tags=["study-sessions"])

# 제출 오류를 문구와 무관하게 구분하도록 응답 헤더에 싣는 오류 코드. 화면은 detail 문구가 아니라 이 값으로 분기한다.
ERROR_CODE_HEADER = "X-Error-Code"
CODE_QUIZ_EXPIRED = "QUIZ_EXPIRED"
CODE_QUIZ_ALREADY_SUBMITTED = "QUIZ_ALREADY_SUBMITTED"
CODE_QUIZ_ANSWER_INVALID = "QUIZ_ANSWER_INVALID"
CODE_QUIZ_ANSWER_LOCKED = "QUIZ_ANSWER_LOCKED"
CODE_QUIZ_WORD_MISSING = "QUIZ_WORD_MISSING"

QUIZ_SESSION_NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="퀴즈 세션을 찾을 수 없습니다.",
)

CODE_NO_WORDS_TO_STUDY = "NO_WORDS_TO_STUDY"
CODE_NO_VOCABULARY = "NO_VOCABULARY"


def quiz_http_error(exc: StudyError) -> HTTPException:
    """세션 러너 API(출제, 답 기록)의 도메인 오류를 HTTP 오류로 바꾼다. 화면은 X-Error-Code 로 분기한다."""
    if isinstance(exc, QuizSessionNotFoundError):
        return QUIZ_SESSION_NOT_FOUND
    if isinstance(exc, QuizAlreadySubmittedError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 끝난 퀴즈입니다.",
            headers={ERROR_CODE_HEADER: CODE_QUIZ_ALREADY_SUBMITTED},
        )
    if isinstance(exc, QuizExpiredError):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="마지막 응답 후 30분이 지나 답을 기록할 수 없습니다. 푼 문항은 이미 저장되어 있습니다.",
            headers={ERROR_CODE_HEADER: CODE_QUIZ_EXPIRED},
        )
    if isinstance(exc, QuizAnswerLockedError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 답한 문항은 바꿀 수 없습니다.",
            headers={ERROR_CODE_HEADER: CODE_QUIZ_ANSWER_LOCKED},
        )
    if isinstance(exc, QuizAnswerError):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
            headers={ERROR_CODE_HEADER: CODE_QUIZ_ANSWER_INVALID},
        )
    if isinstance(exc, QuizWordMissingError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="퀴즈에 포함된 단어가 삭제되어 답을 기록할 수 없습니다. 퀴즈를 다시 시작해 주세요.",
            headers={ERROR_CODE_HEADER: CODE_QUIZ_WORD_MISSING},
        )
    raise exc


QUIZ_ERRORS = (
    QuizSessionNotFoundError,
    QuizAlreadySubmittedError,
    QuizExpiredError,
    QuizAnswerLockedError,
    QuizAnswerError,
    QuizWordMissingError,
)


def _now() -> datetime:
    """테스트에서 바꿔 끼울 수 있도록 현재 UTC 시각을 한 곳에서 얻는다 (naive, REQ-109)."""
    return utcnow()


@router.post("", status_code=status.HTTP_201_CREATED, response_model=SessionOut)
async def create_session(
    body: SessionCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> SessionOut:
    """한 라운드(기본 15문항)를 출제한다. source 로 활성 단어장(all)·북마크·오답 풀을 고른다. 퀴즈 문항에는 정답을 싣지 않는다."""
    try:
        return await session_service.create_session(
            db, user, body.mode, body.count, body.include_memorized, now=_now(), source=body.source
        )
    except session_service.NoWordsToStudyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="학습할 단어가 없습니다. 숙련한 단어를 포함해 볼까요?" if body.source == "all" else "복습할 단어가 없습니다.",
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
