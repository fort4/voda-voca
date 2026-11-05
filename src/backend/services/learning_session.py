# 2026-11-05 - voda-voca - 학습 세션 서비스: 활성 단어장에서 워터폴로 출제하고(퀴즈/플래시카드), 문항별로 채점해 진행도를 갱신한다
# 파일 위치: src/backend/services/learning_session.py

import random
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import QuizSession, SystemVocabulary, SystemWord, User, UserWordProgress
from backend.models.quiz_session import QUIZ_SOURCE_VOCABULARY
from backend.models.study_log import STUDY_MODE_FLASHCARD, STUDY_MODE_QUIZ
from backend.schemas.learning_session import (
    CompositionOut,
    ProgressOut,
    SessionAnswerIn,
    SessionAnswerOut,
    SessionItemOut,
    SessionOut,
)
from backend.services.progress import ProgressState
from backend.services.session_picker import WordCandidate, select_session_words, split_pools
from backend.services.study import (
    QUIZ_MIN_SOURCE_WORDS,
    QUIZ_TTL,
    QuizAlreadySubmittedError,
    QuizAnswerError,
    QuizAnswerLockedError,
    QuizExpiredError,
    QuizSourceTooSmallError,
    QuizWordMissingError,
    StudyError,
    _build_question,
    commit_logs,
    lock_session,
    record_one,
    recorded_answers,
)
from backend.services.study_log import progress_state_of

FLASHCARD_KNOWN = 1  # 플래시카드 answers 의 값: 1=알아요, 0=헷갈려요
FLASHCARD_UNSURE = 0


class NoWordsToStudyError(StudyError):
    """출제할 단어가 없다. 숙련 단어를 제외했더니 남은 것이 없을 때 등 (409)."""


class NoVocabularyError(StudyError):
    """학습할 표준 단어장이 하나도 없다 (409)."""


async def _active_vocabulary(db: AsyncSession, user: User) -> SystemVocabulary:
    """사용자의 활성 단어장. 비어 있으면 첫 번째 표준 단어장(sort_order, id 순)을 활성으로 저장한다."""
    if user.active_vocabulary_id is not None:
        found = (
            await db.execute(select(SystemVocabulary).where(SystemVocabulary.id == user.active_vocabulary_id))
        ).scalar_one_or_none()
        if found is not None:
            return found
    default = (
        await db.execute(select(SystemVocabulary).order_by(SystemVocabulary.sort_order, SystemVocabulary.id).limit(1))
    ).scalar_one_or_none()
    if default is None:
        raise NoVocabularyError
    user.active_vocabulary_id = default.id  # 세션을 저장하는 커밋과 함께 반영된다
    return default


def _flashcard_question(word: SystemWord) -> dict:
    return {
        "word_id": word.id,
        "term": word.term,
        "meaning": word.meaning,
        "choices": [],
        "correct_index": None,
        "example": word.example,
        "example_meaning": word.example_meaning,
    }


def _item(question: dict, mode: str) -> SessionItemOut:
    if mode == STUDY_MODE_FLASHCARD:
        return SessionItemOut(
            question_id=question["question_id"],
            word_id=question["word_id"],
            term=question["term"],
            context=question.get("example"),
            meaning=question["meaning"],
            example_meaning=question.get("example_meaning"),
        )
    return SessionItemOut(
        question_id=question["question_id"],
        word_id=question["word_id"],
        term=question["term"],
        context=question.get("example"),
        options=question["choices"],
    )


async def create_session(
    db: AsyncSession,
    user: User,
    mode: str,
    count: int,
    include_memorized: bool,
    now: datetime,
    rng: random.Random | None = None,
) -> SessionOut:
    """활성 단어장에서 count 문항을 골라 세션을 만든다 (오답 30% 상한, 복습 10% 선확보, 나머지 미학습, 부족하면 복습)."""
    rng = rng or random.Random()
    vocabulary = await _active_vocabulary(db, user)

    rows = (
        await db.execute(
            select(SystemWord, UserWordProgress)
            .outerjoin(
                UserWordProgress,
                (UserWordProgress.word_id == SystemWord.id) & (UserWordProgress.user_id == user.id),
            )
            .where(SystemWord.vocabulary_id == vocabulary.id)
        )
    ).all()
    words = {word.id: word for word, _ in rows}
    if mode == STUDY_MODE_QUIZ and len(words) < QUIZ_MIN_SOURCE_WORDS:
        raise QuizSourceTooSmallError("퀴즈는 단어가 4개 이상 있는 단어장에서 시작할 수 있습니다.")

    candidates = [
        WordCandidate(word.id, word.order_index, None if progress is None else progress_state_of(progress))
        for word, progress in rows
    ]
    pools = split_pools(candidates, include_memorized)
    picked = select_session_words(pools.wrong, pools.unseen, pools.review, count, rng)
    if not picked.ids:
        raise NoWordsToStudyError

    by_vocabulary = {vocabulary.id: list(words.values())}
    questions: list[dict] = []
    for word_id in picked.ids:
        word = words[word_id]
        question = (
            _flashcard_question(word)
            if mode == STUDY_MODE_FLASHCARD
            else _build_question(word, by_vocabulary, [], rng)  # 오답 보기는 같은 단어장에서만
        )
        if question is None:
            continue
        question["question_id"] = len(questions)
        questions.append(question)
    if not questions:
        raise QuizSourceTooSmallError("오답 보기를 만들 수 있는 단어가 부족합니다.")

    session = QuizSession(
        user_id=user.id,
        vocabulary_id=vocabulary.id,
        source=QUIZ_SOURCE_VOCABULARY,
        mode=mode,
        questions=questions,
        answers={},
        is_submitted=False,
        expires_at=now + QUIZ_TTL,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return SessionOut(
        session_id=session.id,
        mode=mode,
        vocabulary_id=vocabulary.id,
        vocabulary_title=vocabulary.title,
        total_questions=len(questions),
        expires_at=session.expires_at,
        composition=CompositionOut(wrong=picked.wrong_count, review=picked.review_count, unseen=picked.unseen_count),
        items=[_item(question, mode) for question in questions],
    )


def _stored_value(row: QuizSession, answer: SessionAnswerIn) -> int:
    """answers 에 저장할 값: 퀴즈는 고른 선지 번호, 플래시카드는 1(알아요)/0(헷갈려요)."""
    if row.mode == STUDY_MODE_FLASHCARD:
        if answer.known is None:
            raise QuizAnswerError("플래시카드 세션에는 known 으로 답해야 합니다.")
        return FLASHCARD_KNOWN if answer.known else FLASHCARD_UNSURE
    if answer.choice_index is None:
        raise QuizAnswerError("퀴즈 세션에는 choice_index 로 답해야 합니다.")
    return answer.choice_index


def _judge(row: QuizSession, question: dict, value: int) -> bool:
    if row.mode == STUDY_MODE_FLASHCARD:
        return value == FLASHCARD_KNOWN
    return value == question["correct_index"]


def _answer_out(row: QuizSession, question: dict, value: int, progress: ProgressState) -> SessionAnswerOut:
    flashcard = row.mode == STUDY_MODE_FLASHCARD
    answered = len(recorded_answers(row))
    total = len(row.questions)
    return SessionAnswerOut(
        question_id=question["question_id"],
        is_correct=_judge(row, question, value),
        correct_index=None if flashcard else question["correct_index"],
        selected_index=None if flashcard else value,
        known=(value == FLASHCARD_KNOWN) if flashcard else None,
        term=question["term"],
        meaning=question["meaning"] if flashcard else question["choices"][question["correct_index"]],
        example=question.get("example"),
        example_meaning=question.get("example_meaning"),
        progress=ProgressOut(
            correct_count=progress.correct_count,
            wrong_count=progress.wrong_count,
            consecutive_correct_count=progress.consecutive_correct_count,
            is_memorized=progress.is_memorized,
        ),
        answered=answered,
        total=total,
        is_finished=row.is_submitted or answered >= total,
        expires_at=row.expires_at,
    )


async def record_session_answer(
    db: AsyncSession, user_id: int, session_id: int, answer: SessionAnswerIn, now: datetime
) -> SessionAnswerOut:
    """문항 하나를 채점해 이력·진행도·세션에 한 트랜잭션으로 기록하고, 해설과 갱신된 진행도를 돌려준다.

    검사 순서: 세션 존재(404) → 알 수 없는 문항(400) → 모드와 맞지 않는 답 형식(400)
    → 같은 답 재전송(멱등, 세션이 끝났어도 200) → 다른 답으로 변경(409) → 이미 끝난 세션(409)
    → 만료(400) → 단어 삭제(409). 마지막 문항에 답하면 세션이 끝난다.
    """
    row = await lock_session(db, user_id, session_id)
    question = next((q for q in row.questions if q["question_id"] == answer.question_id), None)
    if question is None:
        raise QuizAnswerError("알 수 없는 문항입니다.")
    value = _stored_value(row, answer)

    recorded = recorded_answers(row)
    if answer.question_id in recorded:
        if recorded[answer.question_id] != value:
            raise QuizAnswerLockedError
        current = (
            await db.execute(
                select(UserWordProgress).where(
                    UserWordProgress.user_id == user_id, UserWordProgress.word_id == question["word_id"]
                )
            )
        ).scalar_one_or_none()
        return _answer_out(row, question, value, progress_state_of(current) if current else ProgressState())

    if row.is_submitted:
        raise QuizAlreadySubmittedError
    if now >= row.expires_at:
        raise QuizExpiredError
    if (await db.execute(select(SystemWord.id).where(SystemWord.id == question["word_id"]))).scalar_one_or_none() is None:
        raise QuizWordMissingError

    state = await record_one(db, user_id, question["word_id"], _judge(row, question, value), now, row.mode)
    row.answers = {**(row.answers or {}), str(answer.question_id): value}
    row.expires_at = now + QUIZ_TTL
    if len(row.answers) >= len(row.questions):
        row.is_submitted = True
    await commit_logs(db)
    return _answer_out(row, question, value, state)
