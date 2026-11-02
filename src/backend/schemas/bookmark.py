# 2026-11-02 - voda-voca - 북마크 API 응답 스키마 (REQ-017, REQ-018)
# 파일 위치: src/backend/schemas/bookmark.py

from datetime import datetime

from pydantic import BaseModel, Field, field_serializer

from backend.schemas.common import to_utc_iso


class BookmarkOut(BaseModel):
    """북마크 목록의 한 항목. 단어 정보와 단어장 이름을 함께 담는다."""

    word_id: int
    wordbook_id: int
    wordbook_name: str
    term: str
    meaning: str
    example: str | None
    example_meaning: str | None = None
    bookmarked_at: datetime = Field(description="북마크 등록 시각 (UTC)")

    @field_serializer("bookmarked_at")
    def _serialize_utc(self, value: datetime) -> str:
        return to_utc_iso(value)


class BookmarkPage(BaseModel):
    items: list[BookmarkOut]
    total: int
    page: int
    size: int
