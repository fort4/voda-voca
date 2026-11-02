# 2026-11-02 - voda-voca - 단어 API 요청/응답 스키마 및 입력 검증 (REQ-008~010, REQ-111)
# 파일 위치: src/backend/schemas/word.py

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from backend.schemas.common import to_utc_iso

TERM_MAX_CHARS = 100
MEANING_MAX_CHARS = 200
EXAMPLE_MAX_CHARS = 500
SEARCH_MAX_CHARS = 100


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
