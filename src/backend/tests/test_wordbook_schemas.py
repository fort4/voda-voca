# 2026-11-02 - voda-voca - 단어장 스키마 단위 테스트: 이름/설명 길이, 공백 처리, 부분 수정 규칙
# 파일 위치: src/backend/tests/test_wordbook_schemas.py

from datetime import datetime

import pytest
from pydantic import ValidationError

from backend.schemas.common import to_utc_iso
from backend.schemas.wordbook import WordbookCreate, WordbookUpdate


def test_create_strips_name_and_description() -> None:
    body = WordbookCreate(name="  토익 단어  ", description="  메모  ")
    assert body.name == "토익 단어"
    assert body.description == "메모"


def test_create_blank_description_becomes_none() -> None:
    assert WordbookCreate(name="a", description="   ").description is None


def test_create_description_is_optional() -> None:
    assert WordbookCreate(name="a").description is None


def test_create_blank_name_is_rejected() -> None:
    with pytest.raises(ValidationError):
        WordbookCreate(name="   ")


def test_create_name_of_50_chars_is_accepted_and_51_rejected() -> None:
    assert len(WordbookCreate(name="가" * 50).name) == 50
    with pytest.raises(ValidationError):
        WordbookCreate(name="가" * 51)


def test_length_is_checked_after_stripping_spaces() -> None:
    # 앞뒤 공백을 뺀 뒤 50자이면 허용되어야 한다.
    assert WordbookCreate(name="  " + "a" * 50 + "  ").name == "a" * 50


def test_create_description_over_200_chars_is_rejected() -> None:
    with pytest.raises(ValidationError):
        WordbookCreate(name="a", description="가" * 201)


def test_update_accepts_empty_body() -> None:
    assert WordbookUpdate().model_dump(exclude_unset=True) == {}


def test_update_only_reports_sent_fields() -> None:
    assert WordbookUpdate(name="새 이름").model_dump(exclude_unset=True) == {"name": "새 이름"}


def test_update_name_cannot_be_null() -> None:
    with pytest.raises(ValidationError):
        WordbookUpdate(name=None)


def test_update_description_can_be_cleared_with_null() -> None:
    body = WordbookUpdate(description=None)
    assert body.model_dump(exclude_unset=True) == {"description": None}


def test_update_blank_name_is_rejected() -> None:
    with pytest.raises(ValidationError):
        WordbookUpdate(name="  ")


def test_to_utc_iso_appends_z_to_naive_utc() -> None:
    assert to_utc_iso(datetime(2026, 11, 2, 4, 5, 6, 789000)) == "2026-11-02T04:05:06.789000Z"
