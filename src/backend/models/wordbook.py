# 2026-11-02 - voda-voca - wordbooks 테이블 모델 (단어장, REQ-004~007, D1)
# 파일 위치: src/backend/models/wordbook.py

from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.mysql import BIGINT, DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import TABLE_OPTIONS, UTC_NOW_DEFAULT, Base, utcnow


class Wordbook(Base):
    __tablename__ = "wordbooks"
    __table_args__ = (
        # D1: 동일 사용자 내 단어장 이름 중복 금지
        UniqueConstraint("user_id", "name", name="uk_wordbooks_user_name"),
        # REQ-005: 최근 수정순 목록 조회를 커버하는 복합 인덱스
        Index("idx_wordbooks_user_updated", "user_id", "updated_at"),
        CheckConstraint("CHAR_LENGTH(TRIM(name)) > 0", name="ck_wordbooks_name_not_blank"),
        TABLE_OPTIONS,
    )

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("users.id", ondelete="CASCADE", name="fk_wordbooks_user"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=3), nullable=False, server_default=UTC_NOW_DEFAULT
    )
    updated_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=3), nullable=False, server_default=UTC_NOW_DEFAULT, onupdate=utcnow
    )
