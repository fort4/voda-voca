# 2026-11-05 - voda-voca - 학습 서비스: 플래시카드 조회, 퀴즈 출제(4지선다), 답안 채점·학습 이력 기록, 이력 조회 (표준 단어장 기준, REQ-012~016, REQ-019, REQ-106)
# 파일 위치: src/backend/services/study.py

import random
from datetime import datetime, timedelta

from sqlalchemy import and_, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Bookmark, QuizSession, StudyLog, SystemVocabulary, SystemWord
from backend.models.quiz_session import QUIZ_SOURCE_BOOKMARKS, QUIZ_SOURCE_VOCABULARY, QUIZ_SOURCE_WRONG
from backend.schemas.study import (
    QUIZ_CHOICE_COUNT,
    QuizAnswer,
    QuizAnswerOut,
    QuizItemOut,
    QuizResultOut,
    QuizSessionDetailOut,
    WrongItem,
)
from backend.services.stats import wrong_word_ids
from backend.services.study_log import add_study_log
from backend.services.errors import VocabularyNotFoundError

QUIZ_TTL = timedelta(minutes=30)
QUIZ_MIN_SOURCE_WORDS = 4  # 출제 원천 최소 단어 수 (REQ-014, REQ-019)
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


class QuizAnswerLockedError(StudyError):
    """이미 답한 문항에 다른 답을 보냈다. 화면도 한 번 고른 답을 잠그므로 서버도 바꾸지 않는다 (409)."""


class FlashcardOffsetWithShuffleError(StudyError):
    """무작위 순서와 offset 을 함께 요청했다. 순서가 매번 달라 이어 받기가 성립하지 않는다 (422)."""


async def _ensure_vocabulary_exists(db: AsyncSession, vocabulary_id: int) -> None:
    """표준 단어장은 모든 사용자가 공유한다. 소유권 검사 없이 존재만 확인한다."""
    found = await db.execute(select(SystemVocabulary.id).where(SystemVocabulary.id == vocabulary_id))
    if found.scalar_one_or_none() is None:
        raise VocabularyNotFoundError


# --- 플래시카드 (REQ-012, 013, 019) ---


async def list_flashcards(
    db: AsyncSession,
    user_id: int,
    vocabulary_id: int | None,
    bookmarked: bool,
    shuffle: bool,
    limit: int,
    offset: int = 0,
) -> tuple[list[tuple[SystemWord, bool]], int]:
    """플래시카드 세트를 반환한다. 표준 단어장 범위, 북마크 범위, 또는 둘의 교집합.

    - vocabulary_id 가 있으면 단어장이 있는지 먼저 확인한다 (없으면 VocabularyNotFoundError).
    - shuffle=True 이면 무작위 순서, 아니면 표제어 순서다.
    - offset 은 표제어 순서에서 건너뛸 개수다. 한 번에 limit 개를 넘는 세트를 이어 받을 때 쓴다.
      무작위 순서는 요청마다 달라 이어 받을 수 없으므로 shuffle=True 와 함께 쓸 수 없다 (FlashcardOffsetWithShuffleError).
    - 반환값은 (단어, 북마크 여부) 목록과 조건에 맞는 전체 개수다.
    """
    if shuffle and offset:
        raise FlashcardOffsetWithShuffleError
    if vocabulary_id is not None:
        await _ensure_vocabulary_exists(db, vocabulary_id)

    flag = Bookmark.id.is_not(None).label("bookmarked")
    base = select(SystemWord, flag).outerjoin(
        Bookmark, and_(Bookmark.word_id == SystemWord.id, Bookmark.user_id == user_id)
    )
    conditions = []
    if vocabulary_id is not None:
        conditions.append(SystemWord.vocabulary_id == vocabulary_id)
    if bookmarked:
        conditions.append(Bookmark.id.is_not(None))
    base = base.where(*conditions)

    total = (
        await db.execute(select(func.count()).select_from(base.subquery()))
    ).scalar_one()

    ordering = (func.rand(),) if shuffle else (SystemWord.term.asc(), SystemWord.id.asc())
    result = await db.execute(base.order_by(*ordering).offset(offset).limit(limit))
    return [(word, bool(flag_value)) for word, flag_value in result.all()], total


# --- 퀴즈 출제 (REQ-014, REQ-019) ---


async def _all_words(db: AsyncSession) -> list[SystemWord]:
    """모든 표준 단어. 오답 보기의 보충 풀로 쓴다 (표준 단어장 전체가 수백 건 규모다)."""
    return list((await db.execute(select(SystemWord))).scalars().all())


def _pick_distractors(
    word: SystemWord,
    primary: list[SystemWord],
    fallback: list[SystemWord],
    rng: random.Random,
) -> list[str] | None:
    """정답 단어와 다른 뜻 3개를 고른다.

    1순위는 primary(원본 표준 단어장), 부족하면 fallback(모든 표준 단어)에서 보충한다.
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
    word: SystemWord,
    by_vocabulary: dict[int, list[SystemWord]],
    all_words: list[SystemWord],
    rng: random.Random,
) -> dict | None:
    """단어 하나에 대한 4지선다 문항을 만든다. 오답 보기를 못 채우면 None."""
    distractors = _pick_distractors(
        word,
        primary=by_vocabulary.get(word.vocabulary_id, []),
        fallback=all_words,
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
        "example_meaning": word.example_meaning,
    }


async def create_quiz(
    db: AsyncSession,
    user_id: int,
    vocabulary_id: int | None,
    bookmarks: bool,
    count: int,
    now: datetime,
    rng: random.Random | None = None,
    wrong_only: bool = False,
) -> QuizSession:
    """퀴즈 세션을 만든다. 문항 수는 min(요청 count, 출제 가능한 단어 수)다.

    - 출제 원천은 표준 단어장 하나, 본인 북마크, 오답 복습 중 하나다 (스키마에서 상호 배타로 검증).
    - 원천 단어가 4개 미만이면 QuizSourceTooSmallError 가 된다.
    - 문항은 서버에 저장되며 만료 시각은 now + 30분이다.
    """
    rng = rng or random.Random()
    if vocabulary_id is not None:
        await _ensure_vocabulary_exists(db, vocabulary_id)

    all_words = await _all_words(db)
    if wrong_only:
        source = QUIZ_SOURCE_WRONG
        wrong_ids = await wrong_word_ids(db, user_id)  # 단어별 마지막 결과가 오답인 단어 (통계의 오답 단어 수와 같은 규칙)
        candidates = [w for w in all_words if w.id in wrong_ids]
        if len(candidates) < QUIZ_MIN_SOURCE_WORDS:
            raise QuizSourceTooSmallError(
                f"복습 가능한 오답 단어가 4개 미만입니다 (현재 {len(candidates)}개)"
            )
    elif vocabulary_id is not None:
        source = QUIZ_SOURCE_VOCABULARY
        candidates = [w for w in all_words if w.vocabulary_id == vocabulary_id]
    else:
        source = QUIZ_SOURCE_BOOKMARKS
        bookmarked_ids = set(
            (
                await db.execute(select(Bookmark.word_id).where(Bookmark.user_id == user_id))
            ).scalars()
        )
        candidates = [w for w in all_words if w.id in bookmarked_ids]

    if len(candidates) < QUIZ_MIN_SOURCE_WORDS:
        raise QuizSourceTooSmallError("퀴즈는 단어가 4개 이상 있어야 시작할 수 있습니다.")

    by_vocabulary: dict[int, list[SystemWord]] = {}
    for word in all_words:
        by_vocabulary.setdefault(word.vocabulary_id, []).append(word)

    questions: list[dict] = []
    for word in rng.sample(candidates, len(candidates)):
        if len(questions) >= count:
            break
        question = _build_question(word, by_vocabulary, all_words, rng)
        if question is None:
            continue
        question["question_id"] = len(questions)
        questions.append(question)

    if not questions:
        raise QuizSourceTooSmallError("오답 보기를 만들 수 있는 단어가 부족합니다.")

    session = QuizSession(
        user_id=user_id,
        vocabulary_id=vocabulary_id,
        source=source,
        questions=questions,
        answers={},
        is_submitted=False,
        expires_at=now + QUIZ_TTL,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


# --- 퀴즈 답 기록·완료·상세 (REQ-015, REQ-016, REQ-106, 이슈 #8) ---
#
# 답은 문항마다 record_answer 로 바로 기록한다. 중간에 닫거나 앱이 종료돼도 푼 답은 학습 이력에 남는다.
# submit_quiz 는 "퀴즈 끝내기"다. 일부만 풀고 끝낼 수 있고, 이전 방식처럼 전체 답을 함께 보내도 된다.


async def _lock_session(db: AsyncSession, user_id: int, session_id: int) -> QuizSession:
    """세션 행을 FOR UPDATE 로 잠가 가져온다. 같은 세션의 동시 요청(재전송, 중복 제출)이 순서대로 처리된다."""
    row = (
        await db.execute(
            select(QuizSession)
            .where(QuizSession.id == session_id, QuizSession.user_id == user_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if row is None:
        raise QuizSessionNotFoundError
    return row


def _recorded_answers(row: QuizSession) -> dict[int, int]:
    """JSON 에 저장된 {"문항번호": 선지} 를 {int: int} 로 읽는다."""
    return {int(question_id): choice for question_id, choice in (row.answers or {}).items()}


async def _commit_logs(db: AsyncSession) -> None:
    """커밋하면서 단어 삭제로 인한 FK 위반만 QuizWordMissingError 로 바꾼다."""
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        if FK_STUDY_LOG_WORD in str(exc.orig):
            raise QuizWordMissingError from exc
        raise


async def record_answer(
    db: AsyncSession, user_id: int, session_id: int, answer: QuizAnswer, now: datetime
) -> QuizAnswerOut:
    """답 1건을 학습 이력과 세션에 한 트랜잭션으로 기록하고, 마감을 지금 + 30분으로 미룬다.

    - 검사 순서: 존재(404) → 이미 끝남(409) → 알 수 없는 문항(400) → 같은 답 재전송(멱등, 200)
      → 다른 답으로 변경(409) → 만료(400) → 단어 삭제(409).
    - 같은 답을 다시 보내면 이력을 늘리지 않고 같은 결과를 돌려준다. 재시도해도 안전하다.
    """
    row = await _lock_session(db, user_id, session_id)
    if row.is_submitted:
        raise QuizAlreadySubmittedError
    question = next((q for q in row.questions if q["question_id"] == answer.question_id), None)
    if question is None:
        raise QuizAnswerError("알 수 없는 문항입니다.")

    correct_index = question["correct_index"]
    recorded = _recorded_answers(row)
    if answer.question_id in recorded:
        if recorded[answer.question_id] != answer.choice_index:
            raise QuizAnswerLockedError
        return QuizAnswerOut(
            question_id=answer.question_id,
            selected_index=answer.choice_index,
            correct_index=correct_index,
            is_correct=answer.choice_index == correct_index,
            expires_at=row.expires_at,
        )
    if now >= row.expires_at:
        raise QuizExpiredError
    if (await db.execute(select(SystemWord.id).where(SystemWord.id == question["word_id"]))).scalar_one_or_none() is None:
        raise QuizWordMissingError

    is_correct = answer.choice_index == correct_index
    add_study_log(db, user_id, question["word_id"], is_correct, mode=row.mode)
    # JSON 컬럼은 내부를 바꿔도 변경으로 감지되지 않는다. 새 dict 를 대입한다.
    row.answers = {**(row.answers or {}), str(answer.question_id): answer.choice_index}
    row.expires_at = now + QUIZ_TTL
    await _commit_logs(db)
    return QuizAnswerOut(
        question_id=answer.question_id,
        selected_index=answer.choice_index,
        correct_index=correct_index,
        is_correct=is_correct,
        expires_at=row.expires_at,
    )


def _validate_answers(answers: list[QuizAnswer], questions: list[dict]) -> dict[int, int]:
    """보낸 답이 서로 겹치지 않고 모두 이 세션의 문항인지 확인한다. 일부만 보내는 것은 허용한다."""
    answered = {answer.question_id: answer.choice_index for answer in answers}
    known = {question["question_id"] for question in questions}
    if len(answered) != len(answers) or not set(answered) <= known:
        raise QuizAnswerError("같은 문항에 두 번 답했거나 알 수 없는 문항이 있습니다.")
    return answered


def _summarize(row: QuizSession, recorded: dict[int, int]) -> tuple[int, int, float]:
    """(푼 문항 수, 맞힌 문항 수, 푼 문항 기준 정답률). 푼 문항이 없으면 정답률은 0 이다."""
    correct = sum(
        1
        for question in row.questions
        if recorded.get(question["question_id"]) == question["correct_index"]
    )
    answered = len(recorded)
    return answered, correct, round(correct / answered * 100, 1) if answered else 0.0


async def submit_quiz(
    db: AsyncSession,
    user_id: int,
    session_id: int,
    answers: list[QuizAnswer],
    now: datetime,
) -> QuizResultOut:
    """퀴즈를 끝내고 요약을 돌려준다. 푼 문항이 일부여도 된다.

    - 같은 세션의 동시 제출은 행 잠금으로 하나만 통과한다. 검사 순서: 존재(404) → 이미 끝남(409)
      → 답안 형식(400) → [아직 기록되지 않은 답이 있을 때만] 만료(400) → 단어 존재(409).
    - 이미 기록된 문항은 서버 값이 우선이고 다시 쓰지 않는다. 기록되지 않은 답만 학습 이력에 추가한다.
    - 새로 기록할 답이 없으면 만료된 세션도 끝낼 수 있다 (푼 답은 이미 저장되어 있다).
    """
    row = await _lock_session(db, user_id, session_id)
    if row.is_submitted:
        raise QuizAlreadySubmittedError

    by_id = {question["question_id"]: question for question in row.questions}
    sent = _validate_answers(answers, row.questions)
    recorded = _recorded_answers(row)
    fresh = {question_id: choice for question_id, choice in sent.items() if question_id not in recorded}

    if fresh:
        if now >= row.expires_at:
            raise QuizExpiredError
        word_ids = {by_id[question_id]["word_id"] for question_id in fresh}
        existing = set((await db.execute(select(SystemWord.id).where(SystemWord.id.in_(word_ids)))).scalars())
        if existing != word_ids:
            await db.rollback()
            raise QuizWordMissingError
        for question_id in sorted(fresh):
            question = by_id[question_id]
            add_study_log(
                db, user_id, question["word_id"], fresh[question_id] == question["correct_index"], mode=row.mode
            )
        recorded = {**recorded, **fresh}
        row.answers = {str(question_id): choice for question_id, choice in recorded.items()}

    row.is_submitted = True
    await _commit_logs(db)

    answered, correct, accuracy = _summarize(row, recorded)
    wrong_items = [
        WrongItem(
            word_id=question["word_id"],
            term=question["term"],
            correct_meaning=question["choices"][question["correct_index"]],
            selected_meaning=question["choices"][recorded[question["question_id"]]],
        )
        for question in row.questions
        if question["question_id"] in recorded
        and recorded[question["question_id"]] != question["correct_index"]
    ]
    return QuizResultOut(
        session_id=session_id,
        total=len(row.questions),
        answered=answered,
        correct_count=correct,
        accuracy=accuracy,
        wrong_items=wrong_items,
    )


async def get_quiz_session(db: AsyncSession, user_id: int, session_id: int) -> QuizSessionDetailOut:
    """본인 세션의 문항, 내가 고른 답, 요약을 돌려준다. 끝나지 않은 세션도 볼 수 있다. 타인 세션은 404 다."""
    row = (
        await db.execute(
            select(QuizSession).where(QuizSession.id == session_id, QuizSession.user_id == user_id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise QuizSessionNotFoundError
    recorded = _recorded_answers(row)
    answered, correct, accuracy = _summarize(row, recorded)
    items = []
    for question in row.questions:
        selected = recorded.get(question["question_id"])
        items.append(
            QuizItemOut(
                question_id=question["question_id"],
                word_id=question["word_id"],
                term=question["term"],
                choices=question["choices"],
                correct_index=question["correct_index"],
                selected_index=selected,
                is_correct=None if selected is None else selected == question["correct_index"],
                example=question.get("example"),
                example_meaning=question.get("example_meaning"),
            )
        )
    return QuizSessionDetailOut(
        session_id=row.id,
        source=row.source,
        vocabulary_id=row.vocabulary_id,
        is_submitted=row.is_submitted,
        expires_at=row.expires_at,
        total=len(row.questions),
        answered=answered,
        correct_count=correct,
        accuracy=accuracy,
        items=items,
    )


# --- 학습 이력 (REQ-016) ---


async def list_study_logs(db: AsyncSession, user_id: int, limit: int) -> list[tuple]:
    """본인의 최근 학습 이력을 최신순으로 반환한다. 각 행은 (word_id, vocabulary_id, term, is_correct, created_at)."""
    result = await db.execute(
        select(StudyLog.word_id, SystemWord.vocabulary_id, SystemWord.term, StudyLog.is_correct, StudyLog.created_at)
        .join(SystemWord, SystemWord.id == StudyLog.word_id)
        .where(StudyLog.user_id == user_id)
        .order_by(StudyLog.created_at.desc(), StudyLog.id.desc())
        .limit(limit)
    )
    return [tuple(row) for row in result.all()]
