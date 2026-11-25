# 2026-11-05 - voda-voca - 학습 공통 서비스: 4지선다 문항 생성, 세션 잠금·마감 계산, 답 기록 보조, 학습 이력 조회 (세션 러너와 통계가 공유, REQ-015, REQ-016, REQ-106)
# 파일 위치: src/backend/services/study.py

import random
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.errors import is_foreign_key_violation
from backend.models import QuizSession, StudyLog, SystemWord
from backend.schemas.study import QUIZ_CHOICE_COUNT
from backend.services.progress import ProgressState
from backend.services.study_log import record_result

QUIZ_TTL = timedelta(minutes=30)


def deadline_from(now: datetime) -> datetime:
    """세션 마감 시각: now + 30분을 DB 컬럼 정밀도(DATETIME(3), 밀리초)로 맞춘다.

    마이크로초를 그대로 두면 첫 응답(메모리 값)과 재전송 응답(DB 에서 읽은 값)의 expires_at 이 달라져
    "같은 답을 다시 보내면 같은 응답" 이라는 멱등 계약이 깨진다.
    """
    end = now + QUIZ_TTL
    return end.replace(microsecond=end.microsecond // 1000 * 1000)


QUIZ_MIN_SOURCE_WORDS = 4  # 출제 원천 최소 단어 수 (REQ-014, REQ-019)
DISTRACTOR_COUNT = QUIZ_CHOICE_COUNT - 1  # 오답 3개 + 정답 1개 = 4지선다


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


async def _all_words(db: AsyncSession) -> list[SystemWord]:
    """모든 표준 단어. 오답 보기의 보충 풀로 쓴다 (표준 단어장 전체가 수백 건 규모다)."""
    return list((await db.execute(select(SystemWord))).scalars().all())


def _pick_distractors(
    word: SystemWord,
    primary: list[SystemWord],
    fallback: list[SystemWord],
    rng: random.Random,
    field: str = "meaning",
    count: int = DISTRACTOR_COUNT,
) -> list[str] | None:
    """정답 단어와 다른 값(field: 영→한은 meaning, 한→영은 term) count 개를 고른다.

    1순위는 primary(원본 표준 단어장), 부족하면 fallback(모든 표준 단어)에서 보충한다.
    값이 같은 단어는 건너뛰어 선지가 중복되지 않게 한다. count 개를 못 채우면 None.
    """
    used = {getattr(word, field)}
    picked: list[str] = []
    for pool in (primary, fallback):
        for other in rng.sample(pool, len(pool)):
            value = getattr(other, field)
            if other.id == word.id or value in used:
                continue
            used.add(value)
            picked.append(value)
            if len(picked) == count:
                return picked
    return None


# 출제 방향(FR-023)과 형식(FR-024). mixed 는 요청 값이고, 문항에는 항상 실제 방향이 저장된다.
DIRECTION_EN_TO_KO = "en_to_ko"
DIRECTION_KO_TO_EN = "ko_to_en"
DIRECTION_MIXED = "mixed"
FORMAT_CHOICE = "choice"
FORMAT_OX = "ox"
OX_CHOICES = ["O", "X"]  # 답은 choice_index 0(O), 1(X)


def build_quiz_question(
    word: SystemWord,
    by_vocabulary: dict[int, list[SystemWord]],
    all_words: list[SystemWord],
    rng: random.Random,
    direction: str = DIRECTION_EN_TO_KO,
    fmt: str = FORMAT_CHOICE,
) -> dict | None:
    """단어 하나에 대한 문항을 만든다. 보기를 못 채우면 None.

    - 방향: en_to_ko 는 단어를 보고 뜻을, ko_to_en 은 뜻을 보고 단어를 답한다. mixed 는 문항마다 무작위로 정한다.
    - 형식: choice 는 4지선다, ox 는 제시한 보기가 맞는지(O) 틀린지(X) 답한다. OX 는 50% 확률로 참을 제시한다.
    - prompt 는 화면에 보일 문제 문구, term·meaning 은 채점 응답과 결과 화면용 정답이다.
    """
    if direction == DIRECTION_MIXED:
        direction = rng.choice([DIRECTION_EN_TO_KO, DIRECTION_KO_TO_EN])
    en_to_ko = direction == DIRECTION_EN_TO_KO
    field = "meaning" if en_to_ko else "term"
    primary = by_vocabulary.get(word.vocabulary_id, [])
    answer = getattr(word, field)

    question = {
        "word_id": word.id,
        "term": word.term,
        "meaning": word.meaning,
        "direction": direction,
        "format": fmt,
        "prompt": word.term if en_to_ko else word.meaning,
        "example": word.example,
        "example_meaning": word.example_meaning,
        "phonetic": word.phonetic,  # 퀴즈 출제 응답에는 싣지 않고, 채점 응답에서만 공개한다
        "pos": word.pos,  # 품사: 출제·채점 응답 모두에 싣는다 (v2.2)
    }
    if fmt == FORMAT_OX:
        is_true = rng.random() < 0.5
        if is_true:
            proposed = answer
        else:
            wrong = _pick_distractors(word, primary, all_words, rng, field, count=1)
            if wrong is None:
                return None
            proposed = wrong[0]
        question.update(choices=list(OX_CHOICES), correct_index=0 if is_true else 1, proposed=proposed)
        return question

    distractors = _pick_distractors(word, primary, all_words, rng, field)
    if distractors is None:
        return None
    choices = distractors + [answer]
    rng.shuffle(choices)
    question.update(choices=choices, correct_index=choices.index(answer))
    return question


def _build_question(
    word: SystemWord,
    by_vocabulary: dict[int, list[SystemWord]],
    all_words: list[SystemWord],
    rng: random.Random,
) -> dict | None:
    """영→한 4지선다 문항 (옛 호출부 호환)."""
    return build_quiz_question(word, by_vocabulary, all_words, rng)


# --- 세션 잠금·답 기록 보조 (세션 러너 services/learning_session.py 가 사용) ---


async def lock_session(db: AsyncSession, user_id: int, session_id: int) -> QuizSession:
    """세션 행을 가져온다. 같은 세션의 동시 요청(재전송, 중복 제출)은 트랜잭션이 BEGIN IMMEDIATE 로 시작해
    쓰기가 한 번에 하나씩 처리되므로(db/session.py) 순서대로 처리된다. (SQLite 에는 행 잠금이 없다.)"""
    query = select(QuizSession).where(QuizSession.id == session_id, QuizSession.user_id == user_id)
    row = (await db.execute(query)).scalar_one_or_none()
    if row is None:
        raise QuizSessionNotFoundError
    return row


def recorded_answers(row: QuizSession) -> dict[int, int]:
    """JSON 에 저장된 {"문항번호": 선지} 를 {int: int} 로 읽는다."""
    return {int(question_id): choice for question_id, choice in (row.answers or {}).items()}


async def record_one(
    db: AsyncSession,
    user_id: int,
    word_id: int,
    is_correct: bool,
    now: datetime,
    mode: str,
    direction: str = DIRECTION_EN_TO_KO,
    fmt: str = FORMAT_CHOICE,
) -> ProgressState:
    """답 하나를 기록하되, 확인 후 단어가 지워진 경쟁 상황의 FK 위반을 QuizWordMissingError 로 바꾼다."""
    try:
        return await record_result(db, user_id, word_id, is_correct, now, mode, direction, fmt)
    except IntegrityError as exc:
        await db.rollback()
        if is_foreign_key_violation(exc):  # 인증된 사용자 기준이라 걸릴 수 있는 외래키는 단어뿐이다
            raise QuizWordMissingError from exc
        raise


async def commit_logs(db: AsyncSession) -> None:
    """커밋하면서 단어 삭제로 인한 FK 위반만 QuizWordMissingError 로 바꾼다."""
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        if is_foreign_key_violation(exc):  # 인증된 사용자 기준이라 걸릴 수 있는 외래키는 단어뿐이다
            raise QuizWordMissingError from exc
        raise


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
