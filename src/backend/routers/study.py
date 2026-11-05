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
    WrongWordOut,
    WrongWordPage,
    FLASHCARD_LIMIT_DEFAULT,
    FLASHCARD_LIMIT_MAX,
    STUDY_LOG_LIMIT,
    FlashcardOut,
    FlashcardPage,
    QuizCreate,
    QuizAnswer,
    QuizAnswerOut,
    QuizQuestionOut,
    QuizResultOut,
    QuizSessionDetailOut,
    QuizSessionOut,
    QuizSubmit,
    StudyLogList,
    StudyLogOut,
    StudyStatsOut,
)
from backend.services import stats as stats_service
from backend.services import study as study_service
from backend.services.study import (
    FlashcardOffsetWithShuffleError,
    StudyError,
    QuizAlreadySubmittedError,
    QuizAnswerError,
    QuizAnswerLockedError,
    QuizExpiredError,
    QuizSessionNotFoundError,
    QuizSourceTooSmallError,
    QuizWordMissingError,
)
from backend.services.errors import VocabularyNotFoundError

router = APIRouter(prefix="/api/study", tags=["study"])

VOCABULARY_NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="단어장을 찾을 수 없습니다.",
)
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


def _now() -> datetime:
    """테스트에서 바꿔 끼울 수 있도록 현재 UTC 시각을 한 곳에서 얻는다 (naive, REQ-109)."""
    return utcnow()


@router.get("/flashcards", response_model=FlashcardPage)
async def get_flashcards(
    vocabulary_id: int | None = Query(default=None, description="이 표준 단어장의 카드만"),
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
    if vocabulary_id is None and not bookmarked:
        raise HTTPException(
            status_code=422,
            detail="vocabulary_id 또는 bookmarked=true 중 하나를 지정해야 합니다.",
        )
    try:
        rows, total = await study_service.list_flashcards(
            db, user.id, vocabulary_id, bookmarked, shuffle, limit, offset
        )
    except VocabularyNotFoundError as exc:
        raise VOCABULARY_NOT_FOUND from exc
    except FlashcardOffsetWithShuffleError as exc:
        raise HTTPException(
            status_code=422,
            detail="shuffle=true 에서는 offset 을 쓸 수 없습니다. 순서가 매번 달라 이어 받을 수 없습니다.",
        ) from exc

    items = [
        FlashcardOut(
            word_id=word.id,
            vocabulary_id=word.vocabulary_id,
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
            vocabulary_id=body.vocabulary_id,
            bookmarks=body.bookmarks,
            count=body.count,
            wrong_only=body.wrong_only,
            now=_now(),
        )
    except VocabularyNotFoundError as exc:
        raise VOCABULARY_NOT_FOUND from exc
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


def quiz_http_error(exc: StudyError) -> HTTPException:
    """퀴즈 세션 API(답 기록, 완료, 상세)의 도메인 오류를 HTTP 오류로 바꾼다. 화면은 X-Error-Code 로 분기한다."""
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


@router.post("/quiz/sessions/{session_id}/answers", response_model=QuizAnswerOut)
async def answer_quiz_question(
    session_id: int,
    body: QuizAnswer,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> QuizAnswerOut:
    """문항 하나의 답을 바로 기록한다. 같은 답을 다시 보내도 안전하고, 다른 답으로 바꾸려 하면 409 다."""
    try:
        return await study_service.record_answer(db, user.id, session_id, body, now=_now())
    except QUIZ_ERRORS as exc:
        raise quiz_http_error(exc) from exc


@router.post("/quiz/sessions/{session_id}/submit", response_model=QuizResultOut)
async def submit_quiz_session(
    session_id: int,
    body: QuizSubmit,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> QuizResultOut:
    """퀴즈를 끝낸다. 일부만 풀어도 되고, 아직 기록되지 않은 답을 함께 보내도 된다."""
    try:
        return await study_service.submit_quiz(db, user.id, session_id, body.answers, now=_now())
    except QUIZ_ERRORS as exc:
        raise quiz_http_error(exc) from exc


@router.get("/quiz/sessions/{session_id}", response_model=QuizSessionDetailOut)
async def get_quiz_session(
    session_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> QuizSessionDetailOut:
    """세션의 문항과 내가 고른 답, 요약. 결과 화면을 새로고침이나 다른 탭에서도 다시 볼 수 있다."""
    try:
        return await study_service.get_quiz_session(db, user.id, session_id)
    except QuizSessionNotFoundError as exc:
        raise QUIZ_SESSION_NOT_FOUND from exc


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
