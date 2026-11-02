# 2026-11-02 - voda-voca - bookmarks 테이블 모델 (북마크, REQ-017, REQ-018, REQ-105, D3)
# 파일 위치: src/backend/models/bookmark.py

from datetime import datetime

from sqlalchemy import ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.mysql import BIGINT, DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import TABLE_OPTIONS, UTC_NOW_DEFAULT, Base


class Bookmark(Base):
    """북마크. 소유권(단어장 소유자 == 요청 사용자)은 DB가 아니라 서비스 계층에서 검증한다 (D3)."""

    __tablename__ = "bookmarks"
    __table_args__ = (
        UniqueConstraint("user_id", "word_id", name="uk_bookmarks_user_word"),
        Index("idx_bookmarks_word", "word_id"),
        TABLE_OPTIONS,
    )

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("users.id", ondelete="CASCADE", name="fk_bookmarks_user"),
        nullable=False,
    )
    word_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("words.id", ondelete="CASCADE", name="fk_bookmarks_word"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=3), nullable=False, server_default=UTC_NOW_DEFAULT
    )
