# 2026-11-02 - voda-voca - 학습 라우터: 플래시카드, 퀴즈 출제·제출, 학습 이력 (REQ-012~016, REQ-019)
# 파일 위치: src/backend/routers/study.py

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.deps import get_current_user
from backend.db.session import get_db_session
from backend.models import User
from backend.models.base import utcnow
from backend.schemas.study import (
    FLASHCARD_LIMIT_DEFAULT,
    FLASHCARD_LIMIT_MAX,
    STUDY_LOG_LIMIT,
    FlashcardOut,
    FlashcardPage,
    QuizCreate,
    QuizQuestionOut,
    QuizResultOut,
    QuizSessionOut,
    QuizSubmit,
    StudyLogList,
    StudyLogOut,
)
from backend.services import study as study_service
from backend.services.study import (
    FlashcardOffsetWithShuffleError,
    QuizAlreadySubmittedError,
    QuizAnswerError,
    QuizExpiredError,
    QuizSessionNotFoundError,
    QuizSourceTooSmallError,
    QuizWordMissingError,
)
from backend.services.wordbook import WordbookNotFoundError

router = APIRouter(prefix="/api/study", tags=["study"])

WORDBOOK_NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="단어장을 찾을 수 없습니다.",
)
QUIZ_SESSION_NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="퀴즈 세션을 찾을 수 없습니다.",
)


def _now() -> datetime:
    """테스트에서 바꿔 끼울 수 있도록 현재 UTC 시각을 한 곳에서 얻는다 (naive, REQ-109)."""
    return utcnow()


@router.get("/flashcards", response_model=FlashcardPage)
async def get_flashcards(
    wordbook_id: int | None = Query(default=None, description="이 단어장의 카드만"),
    bookmarked: bool = Query(default=False, description="true 면 본인 북마크 카드만"),
    shuffle: bool = Query(default=False, description="true 면 무작위 순서"),
    limit: int = Query(default=FLASHCARD_LIMIT_DEFAULT, ge=1, le=FLASHCARD_LIMIT_MAX),
    offset: int = Query(
        default=0,
        ge=0,
        description="표제어 순서에서 건너뛸 카드 수. limit 을 넘는 세트를 이어 받을 때 쓴다 (shuffle=true 와 함께 쓸 수 없다)",
    ),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> FlashcardPage:
    if wordbook_id is None and not bookmarked:
        raise HTTPException(
            status_code=422,
            detail="wordbook_id 또는 bookmarked=true 중 하나를 지정해야 합니다.",
        )
    try:
        rows, total = await study_service.list_flashcards(
            db, user.id, wordbook_id, bookmarked, shuffle, limit, offset
        )
    except WordbookNotFoundError as exc:
        raise WORDBOOK_NOT_FOUND from exc
    except FlashcardOffsetWithShuffleError as exc:
        raise HTTPException(
            status_code=422,
            detail="shuffle=true 에서는 offset 을 쓸 수 없습니다. 순서가 매번 달라 이어 받을 수 없습니다.",
        ) from exc

    items = [
        FlashcardOut(
            word_id=word.id,
            wordbook_id=word.wordbook_id,
            term=word.term,
            meaning=word.meaning,
            example=word.example,
            example_meaning=word.example_meaning,
            bookmarked=flag,
        )
        for word, flag in rows
    ]
    return FlashcardPage(items=items, total=total)


@router.post(
    "/quiz/sessions",
    status_code=status.HTTP_201_CREATED,
    response_model=QuizSessionOut,
)
async def create_quiz_session(
    body: QuizCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> QuizSessionOut:
    try:
        session = await study_service.create_quiz(
            db,
            user.id,
            wordbook_id=body.wordbook_id,
            bookmarks=body.bookmarks,
            count=body.count,
            wrong_only=body.wrong_only,
            now=_now(),
        )
    except WordbookNotFoundError as exc:
        raise WORDBOOK_NOT_FOUND from exc
    except QuizSourceTooSmallError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return QuizSessionOut(
        session_id=session.id,
        expires_at=session.expires_at,
        questions=[
            QuizQuestionOut(
                question_id=question["question_id"],
                term=question["term"],
                choices=question["choices"],
                correct_index=question["correct_index"],
                example=question.get("example"),
                example_meaning=question.get("example_meaning"),
            )
            for question in session.questions
        ],
    )


@router.post("/quiz/sessions/{session_id}/submit", response_model=QuizResultOut)
async def submit_quiz_session(
    session_id: int,
    body: QuizSubmit,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> QuizResultOut:
    try:
        return await study_service.submit_quiz(
            db, user.id, session_id, body.answers, now=_now()
        )
    except QuizSessionNotFoundError as exc:
        raise QUIZ_SESSION_NOT_FOUND from exc
    except QuizAlreadySubmittedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 제출된 퀴즈입니다.",
        ) from exc
    except QuizExpiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="퀴즈 제한 시간(30분)이 지났습니다.",
        ) from exc
    except QuizAnswerError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except QuizWordMissingError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="퀴즈에 포함된 단어가 삭제되어 제출할 수 없습니다. 퀴즈를 다시 시작해 주세요.",
        ) from exc


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
                wordbook_id=wordbook_id,
                term=term,
                is_correct=is_correct,
                created_at=created_at,
            )
            for word_id, wordbook_id, term, is_correct, created_at in rows
        ]
    )
