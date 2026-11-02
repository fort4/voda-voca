# 2026-11-02 - voda-voca - 단어 API 요청/응답 스키마 및 입력 검증, 일괄 등록 스키마 (REQ-008~010, REQ-111, 일괄 등록)
# 파일 위치: src/backend/schemas/word.py

import unicodedata
from datetime import datetime
from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from backend.schemas.common import to_utc_iso

TERM_MAX_CHARS = 100
MEANING_MAX_CHARS = 200
EXAMPLE_MAX_CHARS = 500
SEARCH_MAX_CHARS = 100
BULK_MAX_ITEMS = 100


def _clean_required(value: str, label: str, max_chars: int) -> str:
    """필수 텍스트: 공백 제거 후 비어 있으면 거부하고, 길이는 제거 후 기준으로 본다."""
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{label}은(는) 공백만으로 만들 수 없습니다.")
    if len(stripped) > max_chars:
        raise ValueError(f"{label}은(는) {max_chars}자 이하여야 합니다.")
    return stripped


def _clean_optional(value: str | None, label: str, max_chars: int) -> str | None:
    """선택 텍스트: 공백 제거 후 비면 None 으로 저장한다."""
    if value is None:
        return None
    stripped = value.strip()
    if len(stripped) > max_chars:
        raise ValueError(f"{label}은(는) {max_chars}자 이하여야 합니다.")
    return stripped or None


class WordCreate(BaseModel):
    term: str = Field(description="표제어 (1~100자, 필수)")
    meaning: str = Field(description="뜻 (1~200자, 필수)")
    example: str | None = Field(default=None, description="예문 (0~500자, 선택)")

    @field_validator("term")
    @classmethod
    def _validate_term(cls, value: str) -> str:
        return _clean_required(value, "표제어", TERM_MAX_CHARS)

    @field_validator("meaning")
    @classmethod
    def _validate_meaning(cls, value: str) -> str:
        return _clean_required(value, "뜻", MEANING_MAX_CHARS)

    @field_validator("example")
    @classmethod
    def _validate_example(cls, value: str | None) -> str | None:
        return _clean_optional(value, "예문", EXAMPLE_MAX_CHARS)


class WordUpdate(BaseModel):
    """부분 수정. 요청에 포함된 필드만 바꾼다.

    term, meaning 은 null 로 바꿀 수 없다. example 은 null 로 지울 수 있다.
    """

    term: str | None = None
    meaning: str | None = None
    example: str | None = None

    @field_validator("term")
    @classmethod
    def _validate_term(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("표제어는 null 로 바꿀 수 없습니다.")
        return _clean_required(value, "표제어", TERM_MAX_CHARS)

    @field_validator("meaning")
    @classmethod
    def _validate_meaning(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("뜻은 null 로 바꿀 수 없습니다.")
        return _clean_required(value, "뜻", MEANING_MAX_CHARS)

    @field_validator("example")
    @classmethod
    def _validate_example(cls, value: str | None) -> str | None:
        return _clean_optional(value, "예문", EXAMPLE_MAX_CHARS)


class WordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    wordbook_id: int
    term: str
    meaning: str
    example: str | None
    created_at: datetime
    updated_at: datetime
    # 요청 사용자가 이 단어를 북마크했는지 여부 (단어 목록/상세 응답에서 채운다)
    bookmarked: bool = False

    @field_serializer("created_at", "updated_at")
    def _serialize_utc(self, value: datetime) -> str:
        return to_utc_iso(value)


class WordPage(BaseModel):
    items: list[WordOut]
    total: int
    page: int
    size: int


def term_key(term: str) -> str:
    """일괄 등록 요청 안의 중복 판정용 키.

    DB 콜레이션 utf8mb4_0900_ai_ci 처럼 대소문자와 악센트를 무시한다 (Apple = apple, café = cafe).
    DB 콜레이션과 완전히 같은 규칙은 아니다. 최종 판정은 DB UNIQUE 제약(409)이 한다.
    """
    decomposed = unicodedata.normalize("NFKD", term)
    without_marks = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return without_marks.casefold()


class WordBulkCreate(BaseModel):
    """단어 일괄 등록 요청. 한 번에 1~100건이며, 요청 안에서 표제어가 겹치면 422 다."""

    items: list[WordCreate] = Field(
        min_length=1,
        max_length=BULK_MAX_ITEMS,
        description=f"등록할 단어 목록 (1~{BULK_MAX_ITEMS}건, 전부 성공하거나 전부 실패)",
    )

    @model_validator(mode="after")
    def _no_duplicate_terms_in_request(self) -> Self:
        seen: set[str] = set()
        duplicates: list[str] = []
        for item in self.items:
            key = term_key(item.term)
            if key in seen:
                duplicates.append(item.term)
            seen.add(key)
        if duplicates:
            unique = list(dict.fromkeys(duplicates))
            raise ValueError(f"요청 안에 같은 표제어가 있습니다: {', '.join(unique)}")
        return self


class WordBulkOut(BaseModel):
    """일괄 등록 성공 응답. 입력 순서대로 생성된 단어 목록이다."""

    items: list[WordOut]
    count: int


class WordBulkConflictOut(BaseModel):
    """일괄 등록 409 응답 본문. conflict_term 은 기존 단어와 겹친 요청 표제어다 (찾지 못하면 null)."""

    detail: str
    conflict_term: str | None
