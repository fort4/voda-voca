# 2026-11-05 - voda-voca - system_words 테이블 모델: 표준 단어장에 속한 읽기 전용 단어
# 파일 위치: src/backend/models/system_word.py

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.dialects.mysql import BIGINT, INTEGER, TINYINT
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import TABLE_OPTIONS, Base


class SystemWord(Base):
    """표준 단어. 이름은 기존 words 와 같게 유지한다 (term, meaning, example, example_meaning).

    phonetic(미국식 IPA, 슬래시 없음)은 v2.2 부터 시드로 채우고 API 로 내보낸다. pos(품사, 영문 소문자)는 v2.2 신규
    단어장(exam-core-200, business-practical-200)부터 시드로 채우고 API 로 내보낸다(화면이 한글 라벨을 입힌다).
    level 은 확장용 필드로 DDL 에만 있고 아직 채우거나 읽지 않는다.
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
    # 품사(영문 소문자). v2.2 신규 단어장부터 시드로 채우고 API 로 내보낸다. level 은 아직 미사용
    pos: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # 미국식 IPA. 슬래시 없이 저장하고 화면에서 /…/ 를 입힌다. 없으면 NULL.
    phonetic: Mapped[str | None] = mapped_column(String(100), nullable=True)
    level: Mapped[int | None] = mapped_column(TINYINT, nullable=True)
    order_index: Mapped[int] = mapped_column(INTEGER, nullable=False, server_default=text("0"))
