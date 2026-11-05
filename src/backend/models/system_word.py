# 2026-11-05 - voda-voca - system_words 테이블 모델: 표준 단어장에 속한 읽기 전용 단어
# 파일 위치: src/backend/models/system_word.py

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.dialects.mysql import BIGINT, INTEGER, TINYINT
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import TABLE_OPTIONS, Base


class SystemWord(Base):
    """표준 단어. 이름은 기존 words 와 같게 유지한다 (term, meaning, example, example_meaning).

    pos, phonetic, level 은 확장용 필드다. DDL 에는 있지만 1단계에서는 채우거나 읽지 않는다.
    """

    __tablename__ = "system_words"
    __table_args__ = (
        UniqueConstraint("vocabulary_id", "term", name="uk_sysword_vocab_term"),
        Index("idx_sysword_vocab_order", "vocabulary_id", "order_index"),
        CheckConstraint(
            "CHAR_LENGTH(TRIM(term)) > 0 AND CHAR_LENGTH(TRIM(meaning)) > 0",
            name="ck_sysword_not_blank",
        ),
        TABLE_OPTIONS,
    )

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    vocabulary_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("system_vocabularies.id", ondelete="CASCADE", name="fk_sysword_vocabulary"),
        nullable=False,
    )
    term: Mapped[str] = mapped_column(String(100), nullable=False)
    meaning: Mapped[str] = mapped_column(String(200), nullable=False)
    example: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # 예문이 없으면 항상 NULL (기존 words 와 같은 규칙).
    example_meaning: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # 확장 필드 (1단계 미사용)
    pos: Mapped[str | None] = mapped_column(String(20), nullable=True)
    phonetic: Mapped[str | None] = mapped_column(String(100), nullable=True)
    level: Mapped[int | None] = mapped_column(TINYINT, nullable=True)
    order_index: Mapped[int] = mapped_column(INTEGER, nullable=False, server_default=text("0"))
