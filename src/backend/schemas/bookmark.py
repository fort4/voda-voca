# 2026-11-05 - voda-voca - 북마크 API 응답 스키마 (REQ-017, REQ-018)
# 파일 위치: src/backend/schemas/bookmark.py

from datetime import datetime

from pydantic import BaseModel, Field, field_serializer

from backend.schemas.common import to_utc_iso


class BookmarkOut(BaseModel):
    """북마크 목록의 한 항목. 단어 정보와 표준 단어장 정보를 함께 담는다."""

    word_id: int
    vocabulary_id: int
    vocabulary_title: str
    term: str
    meaning: str
    example: str | None
    example_meaning: str | None = None
    pos: str | None = None
    phonetic: str | None = None
    bookmarked_at: datetime = Field(description="북마크 등록 시각 (UTC)")

    @field_serializer("bookmarked_at")
    def _serialize_utc(self, value: datetime) -> str:
        return to_utc_iso(value)


class BookmarkPage(BaseModel):
    items: list[BookmarkOut]
    total: int
    page: int
    size: int
