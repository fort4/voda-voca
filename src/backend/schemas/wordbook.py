# 2026-11-02 - voda-voca - 단어장 API 요청/응답 스키마 및 입력 검증 (REQ-004~007, REQ-111)
# 파일 위치: src/backend/schemas/wordbook.py

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from backend.schemas.common import to_utc_iso

NAME_MAX_CHARS = 50
DESCRIPTION_MAX_CHARS = 200


def _clean_name(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError("단어장 이름은 공백만으로 만들 수 없습니다.")
    if len(stripped) > NAME_MAX_CHARS:
        raise ValueError(f"단어장 이름은 {NAME_MAX_CHARS}자 이하여야 합니다.")
    return stripped


def _clean_description(value: str | None) -> str | None:
    """설명은 공백 제거 후 비면 None 으로 저장한다 (선택 항목)."""
    if value is None:
        return None
    stripped = value.strip()
    if len(stripped) > DESCRIPTION_MAX_CHARS:
        raise ValueError(f"설명은 {DESCRIPTION_MAX_CHARS}자 이하여야 합니다.")
    return stripped or None


class WordbookCreate(BaseModel):
    name: str = Field(description="단어장 이름 (1~50자, 필수)")
    description: str | None = Field(default=None, description="설명 (0~200자, 선택)")

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        return _clean_name(value)

    @field_validator("description")
    @classmethod
    def _validate_description(cls, value: str | None) -> str | None:
        return _clean_description(value)


class WordbookUpdate(BaseModel):
    """부분 수정. 요청에 포함된 필드만 바꾼다.

    name 은 null 로 바꿀 수 없다. description 은 null 로 지울 수 있다.
    """

    name: str | None = None
    description: str | None = None

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("단어장 이름은 null 로 바꿀 수 없습니다.")
        return _clean_name(value)

    @field_validator("description")
    @classmethod
    def _validate_description(cls, value: str | None) -> str | None:
        return _clean_description(value)


class WordbookOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    word_count: int = Field(default=0, ge=0, description="이 단어장에 속한 단어 수 (목록은 한 번의 집계 쿼리로 채운다)")
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_at", "updated_at")
    def _serialize_utc(self, value: datetime) -> str:
        return to_utc_iso(value)


class WordbookPage(BaseModel):
    items: list[WordbookOut]
    total: int
    page: int
    size: int
