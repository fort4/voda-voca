# 2026-11-02 - voda-voca - 단어 스키마 및 LIKE 이스케이프 단위 테스트
# 파일 위치: src/backend/tests/test_word_schemas.py

import pytest
from pydantic import ValidationError

from backend.schemas.word import WordCreate, WordUpdate
from backend.services.word import escape_like


def test_create_strips_fields() -> None:
    body = WordCreate(term="  apple  ", meaning="  사과 ", example="  An apple a day. ")
    assert (body.term, body.meaning, body.example) == ("apple", "사과", "An apple a day.")


def test_create_blank_example_becomes_none() -> None:
    assert WordCreate(term="a", meaning="b", example="   ").example is None


def test_create_example_is_optional() -> None:
    assert WordCreate(term="a", meaning="b").example is None


@pytest.mark.parametrize("term", ["", "   "])
def test_create_blank_term_is_rejected(term: str) -> None:
    with pytest.raises(ValidationError):
        WordCreate(term=term, meaning="뜻")


def test_term_length_is_checked_after_strip() -> None:
    assert WordCreate(term="  " + "a" * 100 + "  ", meaning="뜻").term == "a" * 100
    with pytest.raises(ValidationError):
        WordCreate(term="a" * 101, meaning="뜻")


def test_meaning_limit_is_200_chars() -> None:
    assert len(WordCreate(term="a", meaning="가" * 200).meaning) == 200
    with pytest.raises(ValidationError):
        WordCreate(term="a", meaning="가" * 201)


def test_example_limit_is_500_chars() -> None:
    assert len(WordCreate(term="a", meaning="b", example="x" * 500).example or "") == 500
    with pytest.raises(ValidationError):
        WordCreate(term="a", meaning="b", example="x" * 501)


def test_update_term_and_meaning_cannot_be_null() -> None:
    with pytest.raises(ValidationError):
        WordUpdate(term=None)
    with pytest.raises(ValidationError):
        WordUpdate(meaning=None)


def test_update_example_can_be_cleared() -> None:
    assert WordUpdate(example=None).model_dump(exclude_unset=True) == {"example": None}


def test_update_only_reports_sent_fields() -> None:
    assert WordUpdate(meaning="새 뜻").model_dump(exclude_unset=True) == {"meaning": "새 뜻"}


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("apple", "apple"),          # 특수문자 없음: 그대로
        ("100%", "100\\%"),          # % 는 리터럴로
        ("a_b", "a\\_b"),            # _ 는 리터럴로
        ("c:\\temp", "c:\\\\temp"),  # \ 는 먼저 두 번 써서 이스케이프 자신을 보호
        ("a%_\\", "a\\%\\_\\\\"),     # 세 문자가 섞여도 각각 한 번만 이스케이프
        ("café", "café"),            # 일반 유니코드: 그대로
    ],
)
def test_escape_like(raw: str, expected: str) -> None:
    assert escape_like(raw) == expected
