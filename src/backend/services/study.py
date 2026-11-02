# 2026-11-02 - voda-voca - 학습 서비스: 플래시카드 조회, 퀴즈 출제(4지선다), 답안 채점·학습 이력 일괄 기록, 이력 조회 (REQ-012~016, REQ-019, REQ-106)
# 파일 위치: src/backend/services/study.py

import random
from datetime import datetime, timedelta

from sqlalchemy import and_, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Bookmark, QuizSession, StudyLog, Word, Wordbook
from backend.models.quiz_session import QUIZ_SOURCE_BOOKMARKS, QUIZ_SOURCE_WORDBOOK, QUIZ_SOURCE_WRONG
from backend.schemas.study import QUIZ_CHOICE_COUNT, QuizAnswer, QuizResultOut, WrongItem
from backend.services.wordbook import get_owned_wordbook

QUIZ_TTL = timedelta(minutes=30)
QUIZ_MIN_SOURCE_WORDS = 4  # 출제 원천 최소 단어 수 (REQ-014, REQ-019)
WRONG_REVIEW_WINDOW = 100  # 오답 복습은 최근 학습 기록 100건에서 고른다 (이력 API 의 최대 건수와 같다)
DISTRACTOR_COUNT = QUIZ_CHOICE_COUNT - 1  # 오답 3개 + 정답 1개 = 4지선다

FK_STUDY_LOG_WORD = "fk_study_logs_word"


class StudyError(Exception):
    """학습 도메인 오류의 공통 부모. 라우터가 HTTP 상태 코드로 바꾼다."""


class QuizSourceTooSmallError(StudyError):
    """출제 원천 단어가 4개 미만이거나, 오답 보기를 만들 수 없다 (400)."""


class QuizSessionNotFoundError(StudyError):
    """세션이 없거나 다른 사용자의 것이다. 두 경우를 구분하지 않는다 (404 일원화)."""


class QuizExpiredError(StudyError):
    """출제 후 30분이 지나 제출할 수 없다 (400)."""


class QuizAlreadySubmittedError(StudyError):
    """이미 제출된 세션을 다시 제출했다 (409)."""


class QuizAnswerError(StudyError):
    """답안이 문항과 맞지 않는다. 누락, 중복, 알 수 없는 문항 (400)."""


class QuizWordMissingError(StudyError):
    """출제 후 문항의 단어가 삭제되었다. 채점하면 이력 행이 깨지므로 제출을 막는다 (409)."""


# --- 플래시카드 (REQ-012, 013, 019) ---


async def list_flashcards(
    db: AsyncSession,
    user_id: int,
    wordbook_id: int | None,
    bookmarked: bool,
    shuffle: bool,
    limit: int,
) -> tuple[list[tuple[Word, bool]], int]:
    """플래시카드 세트를 반환한다. 단어장 범위, 북마크 범위, 또는 둘의 교집합.

    - wordbook_id 가 있으면 소유권을 먼저 확인한다 (타인이면 WordbookNotFoundError).
    - shuffle=True 이면 무작위 순서, 아니면 표제어 순서다.
    - 반환값은 (단어, 북마크 여부) 목록과 조건에 맞는 전체 개수다.
    """
    if wordbook_id is not None:
        await get_owned_wordbook(db, user_id, wordbook_id)

    flag = Bookmark.id.is_not(None).label("bookmarked")
    base = select(Word, flag).outerjoin(
        Bookmark, and_(Bookmark.word_id == Word.id, Bookmark.user_id == user_id)
    )
    conditions = []
    if wordbook_id is not None:
        conditions.append(Word.wordbook_id == wordbook_id)
    if bookmarked:
        conditions.append(Bookmark.id.is_not(None))
    base = base.where(*conditions)

    total = (
        await db.execute(select(func.count()).select_from(base.subquery()))
    ).scalar_one()

    ordering = (func.rand(),) if shuffle else (Word.term.asc(), Word.id.asc())
    result = await db.execute(base.order_by(*ordering).limit(limit))
    return [(word, bool(flag_value)) for word, flag_value in result.all()], total


# --- 퀴즈 출제 (REQ-014, REQ-019) ---


async def _all_user_words(db: AsyncSession, user_id: int) -> list[Word]:
    """요청 사용자의 모든 단어. 오답 보기의 보충 풀로 쓴다."""
    result = await db.execute(
        select(Word)
        .join(Wordbook, Wordbook.id == Word.wordbook_id)
        .where(Wordbook.user_id == user_id)
    )
    return list(result.scalars().all())


def _pick_distractors(
    word: Word,
    primary: list[Word],
    fallback: list[Word],
    rng: random.Random,
) -> list[str] | None:
    """정답 단어와 다른 뜻 3개를 고른다.

    1순위는 primary(원본 단어장), 부족하면 fallback(사용자 전체 단어)에서 보충한다.
    뜻이 같은 단어는 건너뛰어 선지가 중복되지 않게 한다. 3개를 못 채우면 None.
    """
    used_meanings = {word.meaning}
    picked: list[str] = []
    for pool in (primary, fallback):
        for other in rng.sample(pool, len(pool)):
            if other.id == word.id or other.meaning in used_meanings:
                continue
            used_meanings.add(other.meaning)
            picked.append(other.meaning)
            if len(picked) == DISTRACTOR_COUNT:
                return picked
    return None


def _build_question(
    word: Word,
    by_wordbook: dict[int, list[Word]],
    user_words: list[Word],
    rng: random.Random,
) -> dict | None:
    """단어 하나에 대한 4지선다 문항을 만든다. 오답 보기를 못 채우면 None."""
    distractors = _pick_distractors(
        word,
        primary=by_wordbook.get(word.wordbook_id, []),
        fallback=user_words,
        rng=rng,
    )
    if distractors is None:
        return None
    choices = distractors + [word.meaning]
    rng.shuffle(choices)
    return {
        "word_id": word.id,
        "term": word.term,
        "choices": choices,
        "correct_index": choices.index(word.meaning),
        "example": word.example,
    }


async def _recent_wrong_word_ids(db: AsyncSession, user_id: int) -> set[int]:
    """최근 학습 기록 WRONG_REVIEW_WINDOW 건 중 틀린 답이 있었던 단어 ID 의 집합 (고유)."""
    rows = await db.execute(
        select(StudyLog.word_id, StudyLog.is_correct)
        .where(StudyLog.user_id == user_id)
        .order_by(StudyLog.created_at.desc(), StudyLog.id.desc())
        .limit(WRONG_REVIEW_WINDOW)
    )
    return {word_id for word_id, is_correct in rows.all() if not is_correct}


async def create_quiz(
    db: AsyncSession,
    user_id: int,
    wordbook_id: int | None,
    bookmarks: bool,
    count: int,
    now: datetime,
    rng: random.Random | None = None,
    wrong_only: bool = False,
) -> QuizSession:
    """퀴즈 세션을 만든다. 문항 수는 min(요청 count, 출제 가능한 단어 수)다.

    - 출제 원천은 단어장 하나 또는 본인 북마크 중 하나다 (스키마에서 상호 배타로 검증).
    - 원천 단어가 4개 미만이면 QuizSourceTooSmallError 가 된다.
    - 문항은 서버에 저장되며 만료 시각은 now + 30분이다.
    """
    rng = rng or random.Random()
    if wordbook_id is not None:
        await get_owned_wordbook(db, user_id, wordbook_id)

    user_words = await _all_user_words(db, user_id)
    if wrong_only:
        source = QUIZ_SOURCE_WRONG
        wrong_ids = await _recent_wrong_word_ids(db, user_id)
        candidates = [w for w in user_words if w.id in wrong_ids]
        if len(candidates) < QUIZ_MIN_SOURCE_WORDS:
            raise QuizSourceTooSmallError(
                f"복습 가능한 오답 단어가 4개 미만입니다 (현재 {len(candidates)}개)"
            )
    elif wordbook_id is not None:
        source = QUIZ_SOURCE_WORDBOOK
        candidates = [w for w in user_words if w.wordbook_id == wordbook_id]
    else:
        source = QUIZ_SOURCE_BOOKMARKS
        bookmarked_ids = set(
            (
                await db.execute(select(Bookmark.word_id).where(Bookmark.user_id == user_id))
            ).scalars()
        )
        candidates = [w for w in user_words if w.id in bookmarked_ids]

    if len(candidates) < QUIZ_MIN_SOURCE_WORDS:
        raise QuizSourceTooSmallError("퀴즈는 단어가 4개 이상 있어야 시작할 수 있습니다.")

    by_wordbook: dict[int, list[Word]] = {}
    for word in user_words:
        by_wordbook.setdefault(word.wordbook_id, []).append(word)

    questions: list[dict] = []
    for word in rng.sample(candidates, len(candidates)):
        if len(questions) >= count:
            break
        question = _build_question(word, by_wordbook, user_words, rng)
        if question is None:
            continue
        question["question_id"] = len(questions)
        questions.append(question)

    if not questions:
        raise QuizSourceTooSmallError("오답 보기를 만들 수 있는 단어가 부족합니다.")

    session = QuizSession(
        user_id=user_id,
        wordbook_id=wordbook_id,
        source=source,
        questions=questions,
        is_submitted=False,
        expires_at=now + QUIZ_TTL,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


# --- 퀴즈 제출·채점 (REQ-015, REQ-016, REQ-106) ---


def _validate_answers(answers: list[QuizAnswer], questions: list[dict]) -> dict[int, int]:
    """모든 문항에 정확히 한 번씩 답했는지 확인하고 {question_id: choice_index} 를 반환한다."""
    answered = {answer.question_id: answer.choice_index for answer in answers}
    expected = {question["question_id"] for question in questions}
    if len(answered) != len(answers) or set(answered) != expected:
        raise QuizAnswerError("모든 문항에 한 번씩만 답해야 합니다.")
    return answered


async def submit_quiz(
    db: AsyncSession,
    user_id: int,
    session_id: int,
    answers: list[QuizAnswer],
    now: datetime,
) -> QuizResultOut:
    """답안을 채점하고 문항별 학습 이력을 한 트랜잭션으로 기록한다 (REQ-106).

    - 세션 행을 FOR UPDATE 로 잠가, 같은 세션의 동시 제출 중 하나만 통과한다.
    - 검사 순서: 존재 여부(404) → 이미 제출(409) → 만료(400) → 답안 형식(400) → 단어 존재(409).
    - 성공하면 is_submitted=True 와 study_logs 다건 INSERT 가 함께 커밋된다.
    """
    row = (
        await db.execute(
            select(QuizSession)
            .where(QuizSession.id == session_id, QuizSession.user_id == user_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if row is None:
        raise QuizSessionNotFoundError
    if row.is_submitted:
        raise QuizAlreadySubmittedError
    if now >= row.expires_at:
        raise QuizExpiredError

    questions = row.questions
    answered = _validate_answers(answers, questions)

    word_ids = {question["word_id"] for question in questions}
    existing = set(
        (await db.execute(select(Word.id).where(Word.id.in_(word_ids)))).scalars()
    )
    if existing != word_ids:
        await db.rollback()
        raise QuizWordMissingError

    by_id = {question["question_id"]: question for question in questions}
    wrong_items: list[WrongItem] = []
    logs: list[StudyLog] = []
    correct_count = 0
    for question_id in sorted(by_id):
        question = by_id[question_id]
        choice_index = answered[question_id]
        is_correct = choice_index == question["correct_index"]
        logs.append(
            StudyLog(user_id=user_id, word_id=question["word_id"], is_correct=is_correct)
        )
        if is_correct:
            correct_count += 1
        else:
            wrong_items.append(
                WrongItem(
                    word_id=question["word_id"],
                    term=question["term"],
                    correct_meaning=question["choices"][question["correct_index"]],
                    selected_meaning=question["choices"][choice_index],
                )
            )

    row.is_submitted = True
    db.add_all(logs)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        if FK_STUDY_LOG_WORD in str(exc.orig):
            raise QuizWordMissingError from exc
        raise

    total = len(questions)
    return QuizResultOut(
        session_id=session_id,
        total=total,
        correct_count=correct_count,
        accuracy=round(correct_count / total * 100, 1),
        wrong_items=wrong_items,
    )


# --- 학습 이력 (REQ-016) ---


async def list_study_logs(db: AsyncSession, user_id: int, limit: int) -> list[tuple]:
    """본인의 최근 학습 이력을 최신순으로 반환한다. 각 행은 (word_id, term, is_correct, created_at)."""
    result = await db.execute(
        select(StudyLog.word_id, Word.term, StudyLog.is_correct, StudyLog.created_at)
        .join(Word, Word.id == StudyLog.word_id)
        .where(StudyLog.user_id == user_id)
        .order_by(StudyLog.created_at.desc(), StudyLog.id.desc())
        .limit(limit)
    )
    return [tuple(row) for row in result.all()]
