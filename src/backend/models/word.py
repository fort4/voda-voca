# 2026-11-02 - voda-voca - words 테이블 모델 (단어, REQ-008~011, REQ-105, D2, D5)
# 파일 위치: src/backend/models/word.py

from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.mysql import BIGINT, DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import TABLE_OPTIONS, UTC_NOW_DEFAULT, Base, utcnow


class Word(Base):
    __tablename__ = "words"
    __table_args__ = (
        # 동일 단어장 내 표제어 중복 금지. 접두사 검색(term LIKE 'x%')의 인덱스도 겸한다 (ADR-003).
        UniqueConstraint("wordbook_id", "term", name="uk_words_wordbook_term"),
        CheckConstraint(
            "CHAR_LENGTH(TRIM(term)) > 0 AND CHAR_LENGTH(TRIM(meaning)) > 0",
            name="ck_words_not_blank",
        ),
        TABLE_OPTIONS,
    )

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    wordbook_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("wordbooks.id", ondelete="CASCADE", name="fk_words_wordbook"),
        nullable=False,
    )
    term: Mapped[str] = mapped_column(String(100), nullable=False)
    meaning: Mapped[str] = mapped_column(String(200), nullable=False)
    example: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=3), nullable=False, server_default=UTC_NOW_DEFAULT
    )
    updated_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=3), nullable=False, server_default=UTC_NOW_DEFAULT, onupdate=utcnow
    )
