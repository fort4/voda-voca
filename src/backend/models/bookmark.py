# 2026-11-02 - voda-voca - bookmarks 테이블 모델 (북마크, REQ-017, REQ-018, REQ-105, D3)
# 파일 위치: src/backend/models/bookmark.py

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import UTC_NOW_DEFAULT, Base


class Bookmark(Base):
    """북마크. 대상은 모든 사용자가 공유하는 표준 단어(system_words)이며, 북마크 자체의 소유자는 user_id 다."""

    __tablename__ = "bookmarks"
    __table_args__ = (
        UniqueConstraint("user_id", "word_id", name="uk_bookmarks_user_word"),
        Index("idx_bookmarks_word", "word_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE", name="fk_bookmarks_user"),
        nullable=False,
    )
    word_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("system_words.id", ondelete="CASCADE", name="fk_bookmarks_word"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=UTC_NOW_DEFAULT
    )
