# 2026-11-02 - voda-voca - 학습 서비스·스키마 단위 테스트: 오답 선지 구성, 답안 검증, 요청 스키마 규칙 (DB 없이 실행)
# 파일 위치: src/backend/tests/test_study_units.py

import random
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from backend.schemas.study import QuizAnswer, QuizCreate
from backend.services import study as study_service
from backend.services.study import QuizAnswerError


def _word(word_id: int, wordbook_id: int, meaning: str) -> SimpleNamespace:
    """서비스가 쓰는 속성(id, wordbook_id, term, meaning)만 가진 가짜 단어."""
    return SimpleNamespace(
        id=word_id,
        wordbook_id=wordbook_id,
        term=f"t{word_id}",
        meaning=meaning,
        example=None,
        example_meaning=None,
    )


# --- 오답 선지 구성 (REQ-014, 결정 3) ---


def test_distractors_come_from_primary_pool_when_it_is_large_enough() -> None:
    target = _word(1, 10, "정답")
    primary = [target, _word(2, 10, "가"), _word(3, 10, "나"), _word(4, 10, "다")]
    fallback = [_word(5, 20, "라"), _word(6, 20, "마")]

    picked = study_service._pick_distractors(target, primary, fallback, random.Random(0))
    assert picked is not None
    assert set(picked) == {"가", "나", "다"}


def test_distractors_top_up_from_fallback_when_primary_is_short() -> None:
    target = _word(1, 10, "정답")
    primary = [target, _word(2, 10, "가")]
    fallback = [target, primary[1], _word(5, 20, "라"), _word(6, 20, "마")]

    picked = study_service._pick_distractors(target, primary, fallback, random.Random(1))
    assert picked is not None
    assert len(picked) == 3
    assert "가" in picked  # 원본 단어장의 뜻이 우선 포함된다
    assert len(set(picked)) == 3


def test_distractors_skip_duplicate_meanings_and_the_correct_meaning() -> None:
    target = _word(1, 10, "같은뜻")
    primary = [target, _word(2, 10, "같은뜻"), _word(3, 10, "가")]
    fallback = [_word(4, 20, "같은뜻"), _word(5, 20, "나"), _word(6, 20, "다")]

    picked = study_service._pick_distractors(target, primary, fallback, random.Random(2))
    assert picked is not None
    assert "같은뜻" not in picked
    assert set(picked) == {"가", "나", "다"}


def test_distractors_return_none_when_three_distinct_meanings_are_unavailable() -> None:
    target = _word(1, 10, "정답")
    primary = [target, _word(2, 10, "정답"), _word(3, 10, "가")]
    fallback = [_word(4, 20, "가")]

    assert study_service._pick_distractors(target, primary, fallback, random.Random(3)) is None


def test_build_question_marks_correct_index_and_has_four_unique_choices() -> None:
    words = [_word(i, 10, f"뜻{i}") for i in range(1, 6)]
    by_book = {10: words}
    question = study_service._build_question(words[0], by_book, words, random.Random(4))

    assert question is not None
    assert len(question["choices"]) == 4
    assert len(set(question["choices"])) == 4
    assert question["choices"][question["correct_index"]] == "뜻1"
    assert question["term"] == "t1"
    assert question["word_id"] == 1


# --- 답안 검증 ---


def _answers(*pairs: tuple[int, int]) -> list[QuizAnswer]:
    return [QuizAnswer(question_id=q, choice_index=c) for q, c in pairs]


def test_validate_answers_returns_mapping_when_exactly_one_per_question() -> None:
    questions = [{"question_id": 0}, {"question_id": 1}]
    assert study_service._validate_answers(_answers((0, 2), (1, 3)), questions) == {0: 2, 1: 3}


@pytest.mark.parametrize(
    "answers",
    [
        _answers((0, 1)),  # 누락
        _answers((0, 1), (0, 2), (1, 0)),  # 중복
        _answers((0, 1), (7, 0)),  # 알 수 없는 문항
    ],
)
def test_validate_answers_rejects_missing_duplicate_or_unknown(answers: list[QuizAnswer]) -> None:
    questions = [{"question_id": 0}, {"question_id": 1}]
    with pytest.raises(QuizAnswerError):
        study_service._validate_answers(answers, questions)


# --- 요청 스키마 ---


@pytest.mark.parametrize(
    ("payload", "valid"),
    [
        ({"wordbook_id": 1}, True),
        ({"bookmarks": True}, True),
        ({"wordbook_id": 1, "bookmarks": True}, False),
        ({}, False),
    ],
)
def test_quiz_create_accepts_exactly_one_source_only(payload: dict, valid: bool) -> None:
    if valid:
        QuizCreate(**payload)
    else:
        with pytest.raises(ValidationError):
            QuizCreate(**payload)


def test_quiz_create_defaults_count_to_ten() -> None:
    assert QuizCreate(wordbook_id=1).count == 10


def test_quiz_answer_choice_index_must_be_within_four_choices() -> None:
    QuizAnswer(question_id=0, choice_index=3)
    with pytest.raises(ValidationError):
        QuizAnswer(question_id=0, choice_index=4)
    with pytest.raises(ValidationError):
        QuizAnswer(question_id=-1, choice_index=0)


def test_build_question_returns_none_when_choices_cannot_be_filled() -> None:
    target = _word(1, 10, "정답")
    words = [target, _word(2, 10, "정답")]
    assert study_service._build_question(target, {10: words}, words, random.Random(5)) is None


# --- 제출 시 DB 레벨 경쟁 상태 처리 (fake 세션으로 commit 실패만 주입) ---


class _FakeResult:
    def __init__(self, value: object) -> None:
        self._value = value

    def scalar_one_or_none(self) -> object:
        return self._value

    def scalars(self) -> list:
        return list(self._value)


class _FakeSubmitSession:
    """submit_quiz 가 쓰는 최소 인터페이스: execute(세션 행, 단어 ID), add_all, commit, rollback."""

    def __init__(self, row: SimpleNamespace, word_ids: list[int], commit_error: Exception | None) -> None:
        self._responses = [_FakeResult(row), _FakeResult(word_ids)]
        self._commit_error = commit_error
        self.rolled_back = False
        self.logs: list[object] = []

    async def execute(self, _stmt: object) -> _FakeResult:
        return self._responses.pop(0)

    def add_all(self, objs: list) -> None:
        self.logs.extend(objs)

    async def commit(self) -> None:
        if self._commit_error is not None:
            raise self._commit_error

    async def rollback(self) -> None:
        self.rolled_back = True


def _submit_row() -> SimpleNamespace:
    from datetime import timedelta

    from backend.models.base import utcnow

    return SimpleNamespace(
        is_submitted=False,
        expires_at=utcnow() + timedelta(minutes=10),
        questions=[{"question_id": 0, "word_id": 7, "term": "t", "choices": ["a", "b", "c", "d"], "correct_index": 0}],
    )


@pytest.mark.asyncio
async def test_commit_fk_failure_on_study_logs_becomes_word_missing_and_rolls_back() -> None:
    from sqlalchemy.exc import IntegrityError

    from backend.models.base import utcnow

    error = IntegrityError("INSERT INTO study_logs", {}, Exception("Cannot add or update a child row: fk_study_logs_word"))
    db = _FakeSubmitSession(_submit_row(), word_ids=[7], commit_error=error)

    with pytest.raises(study_service.QuizWordMissingError):
        await study_service.submit_quiz(db, 1, 1, _answers((0, 0)), now=utcnow())
    assert db.rolled_back is True


@pytest.mark.asyncio
async def test_other_commit_integrity_errors_are_propagated_unchanged() -> None:
    from sqlalchemy.exc import IntegrityError

    from backend.models.base import utcnow

    error = IntegrityError("INSERT INTO study_logs", {}, Exception("some other constraint"))
    db = _FakeSubmitSession(_submit_row(), word_ids=[7], commit_error=error)

    with pytest.raises(IntegrityError):
        await study_service.submit_quiz(db, 1, 1, _answers((0, 0)), now=utcnow())
    assert db.rolled_back is True
