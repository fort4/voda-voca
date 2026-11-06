# 2026-11-02 - voda-voca - 학습 서비스·스키마 단위 테스트: 오답 선지 구성, DB 경쟁 상태 처리 (DB 없이 실행)
# 파일 위치: src/backend/tests/test_study_units.py

import random
from types import SimpleNamespace

import pytest

from backend.services import study as study_service


def _word(word_id: int, vocabulary_id: int, meaning: str) -> SimpleNamespace:
    """서비스가 쓰는 속성(id, vocabulary_id, term, meaning, 예문, 발음기호)만 가진 가짜 단어."""
    return SimpleNamespace(
        id=word_id,
        vocabulary_id=vocabulary_id,
        term=f"t{word_id}",
        meaning=meaning,
        example=None,
        example_meaning=None,
        phonetic=None,
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


def test_question_carries_the_example_and_its_translation_or_none() -> None:
    """출제 문항에는 예문과 예문 뜻이 함께 실린다. 예문이 없으면 뜻도 None 이다."""

    def word(word_id: int, example: str | None, translation: str | None) -> SimpleNamespace:
        return SimpleNamespace(
            id=word_id,
            vocabulary_id=10,
            term=f"t{word_id}",
            meaning=f"뜻{word_id}",
            example=example,
            example_meaning=translation,
            phonetic=None,
        )

    with_translation = [word(1, "e1", "해석1")] + [word(i, "e", None) for i in range(2, 6)]
    question = study_service._build_question(with_translation[0], {10: with_translation}, with_translation, random.Random(1))
    assert question is not None
    assert question["example"] == "e1"
    assert question["example_meaning"] == "해석1"

    no_example = [word(1, None, None)] + [word(i, None, None) for i in range(2, 6)]
    question = study_service._build_question(no_example[0], {10: no_example}, no_example, random.Random(1))
    assert question is not None
    assert question["example"] is None
    assert question["example_meaning"] is None


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


def test_build_question_returns_none_when_choices_cannot_be_filled() -> None:
    target = _word(1, 10, "정답")
    words = [target, _word(2, 10, "정답")]
    assert study_service._build_question(target, {10: words}, words, random.Random(5)) is None


# --- 제출 시 DB 레벨 경쟁 상태 처리 (fake 세션으로 commit 실패만 주입) ---


class _FakeSession:
    """commit_logs / record_one 이 쓰는 최소 인터페이스: commit, rollback."""

    def __init__(self, commit_error: Exception | None = None) -> None:
        self._commit_error = commit_error
        self.rolled_back = False

    async def commit(self) -> None:
        if self._commit_error is not None:
            raise self._commit_error

    async def rollback(self) -> None:
        self.rolled_back = True


def _integrity_error(message: str):
    from sqlalchemy.exc import IntegrityError

    return IntegrityError("INSERT", {}, Exception(message))


@pytest.mark.asyncio
async def test_commit_fk_failure_on_study_logs_becomes_word_missing_and_rolls_back() -> None:
    db = _FakeSession(_integrity_error("Cannot add or update a child row: fk_study_logs_word"))

    with pytest.raises(study_service.QuizWordMissingError):
        await study_service.commit_logs(db)
    assert db.rolled_back is True


@pytest.mark.asyncio
async def test_other_commit_integrity_errors_are_propagated_unchanged() -> None:
    from sqlalchemy.exc import IntegrityError

    db = _FakeSession(_integrity_error("some other constraint"))

    with pytest.raises(IntegrityError):
        await study_service.commit_logs(db)
    assert db.rolled_back is True


@pytest.mark.asyncio
@pytest.mark.parametrize("fk_name", ["fk_uwp_word", "fk_study_logs_word"])
async def test_word_fk_failure_while_recording_becomes_word_missing(
    monkeypatch: pytest.MonkeyPatch, fk_name: str
) -> None:
    """진행도 갱신 중 단어가 지워져 FK 가 걸려도 같은 오류(409)로 다루고 롤백한다."""
    from backend.models.base import utcnow

    async def _boom(*_args, **_kwargs):
        raise _integrity_error(f"Cannot add or update a child row: {fk_name}")

    monkeypatch.setattr(study_service, "record_result", _boom)
    db = _FakeSession()

    with pytest.raises(study_service.QuizWordMissingError):
        await study_service.record_one(db, 1, 7, True, utcnow(), "quiz")
    assert db.rolled_back is True


@pytest.mark.asyncio
async def test_unrelated_integrity_error_while_recording_is_propagated(monkeypatch: pytest.MonkeyPatch) -> None:
    from sqlalchemy.exc import IntegrityError

    from backend.models.base import utcnow

    async def _boom(*_args, **_kwargs):
        raise _integrity_error("some other constraint")

    monkeypatch.setattr(study_service, "record_result", _boom)
    db = _FakeSession()

    with pytest.raises(IntegrityError):
        await study_service.record_one(db, 1, 7, True, utcnow(), "quiz")
    assert db.rolled_back is True
