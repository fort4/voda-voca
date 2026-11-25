# 2026-11-25 - voda-voca - 출제 방향(영→한/한→영/섞기)·형식(4지선다/OX) 문항 생성 단위 테스트 (VOCA-FR-023, 024, DB 없이 실행)
# 파일 위치: src/backend/tests/test_quiz_variants_units.py

import random
from collections import Counter
from types import SimpleNamespace

import pytest

from backend.services import study as study_service

pytestmark = pytest.mark.no_db


def _word(word_id: int) -> SimpleNamespace:
    return SimpleNamespace(
        id=word_id,
        vocabulary_id=10,
        term=f"t{word_id}",
        meaning=f"뜻{word_id}",
        example=None,
        example_meaning=None,
        phonetic=None,
        pos=None,
    )


WORDS = [_word(i) for i in range(1, 7)]
BY_VOCAB = {10: WORDS}


def build(direction: str, fmt: str, seed: int = 0, target: SimpleNamespace = WORDS[0]) -> dict:
    question = study_service.build_quiz_question(target, BY_VOCAB, [], random.Random(seed), direction, fmt)
    assert question is not None
    return question


# --- 4지선다 ---


def test_choice_en_to_ko_keeps_the_existing_shape() -> None:
    q = build("en_to_ko", "choice")
    assert (q["direction"], q["format"]) == ("en_to_ko", "choice")
    assert q["prompt"] == "t1"
    assert q["term"] == "t1" and q["meaning"] == "뜻1"
    assert q["choices"][q["correct_index"]] == "뜻1"
    assert len(set(q["choices"])) == 4


def test_choice_ko_to_en_shows_the_meaning_and_offers_english_terms() -> None:
    q = build("ko_to_en", "choice")
    assert (q["direction"], q["format"]) == ("ko_to_en", "choice")
    assert q["prompt"] == "뜻1"
    assert q["choices"][q["correct_index"]] == "t1"
    assert len(set(q["choices"])) == 4
    assert all(choice.startswith("t") for choice in q["choices"])


# --- OX ---


def test_ox_choices_are_o_and_x() -> None:
    q = build("en_to_ko", "ox")
    assert q["format"] == "ox"
    assert q["choices"] == ["O", "X"]
    assert q["correct_index"] in (0, 1)


@pytest.mark.parametrize("direction, prompt_of, proposed_of", [("en_to_ko", "t1", "뜻"), ("ko_to_en", "뜻1", "t")])
def test_ox_proposed_matches_the_correct_index(direction: str, prompt_of: str, proposed_of: str) -> None:
    seen = set()
    for seed in range(40):
        q = build(direction, "ox", seed)
        assert q["prompt"] == prompt_of
        true_proposed = "뜻1" if direction == "en_to_ko" else "t1"
        is_true = q["proposed"] == true_proposed
        assert q["correct_index"] == (0 if is_true else 1)
        assert q["proposed"].startswith(proposed_of)
        seen.add(is_true)
    assert seen == {True, False}  # 참과 거짓이 모두 나온다


def test_ox_is_roughly_balanced() -> None:
    counts = Counter(build("en_to_ko", "ox", seed)["correct_index"] for seed in range(400))
    assert 140 < counts[0] < 260


# --- 섞기 / 실패 ---


def test_mixed_direction_resolves_to_a_concrete_direction_per_question() -> None:
    directions = {build("mixed", "choice", seed)["direction"] for seed in range(40)}
    assert directions == {"en_to_ko", "ko_to_en"}


def test_returns_none_when_distractors_are_unavailable() -> None:
    words = [_word(1), _word(2)]
    assert study_service.build_quiz_question(words[0], {10: words}, [], random.Random(0), "en_to_ko", "choice") is None


def test_ox_works_with_only_one_other_word() -> None:
    words = [_word(1), _word(2)]
    q = study_service.build_quiz_question(words[0], {10: words}, [], random.Random(0), "en_to_ko", "ox")
    assert q is not None


def test_legacy_build_question_is_en_to_ko_choice() -> None:
    q = study_service._build_question(WORDS[0], BY_VOCAB, [], random.Random(1))
    assert q is not None and (q["direction"], q["format"]) == ("en_to_ko", "choice")
