# 2026-11-05 - voda-voca - system_vocabularies 테이블 모델: 서비스가 제공하는 읽기 전용 표준 단어장 카탈로그
# 파일 위치: src/backend/models/system_vocabulary.py

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import NOCASE, SOURCE_SEED, UTC_NOW_DEFAULT, Base, utcnow


class SystemVocabulary(Base):
    """표준 단어장. 일반 사용자는 만들거나 고치지 않는다. 서버 시드 파일 또는 관리자(source='admin', REQ-160)가 만든다.

    - slug: 시드 파일과 DB 행을 잇는 멱등 키 (예: 'beginner-200').
    - category: 자유 문자열이다. ENUM/CHECK 로 막지 않아야 새 카테고리(CONVERSATION, TOEIC 등)를
      스키마 변경 없이 시드만으로 추가할 수 있다. 탐색 필터용 인덱스를 둔다.
    - total_words: 시더가 실제 단어 수로 갱신하는 비정규화 값.
    - content_hash: 시드 내용이 같으면 쓰기를 건너뛰기 위한 해시.
    """

    __tablename__ = "system_vocabularies"
    __table_args__ = (
        UniqueConstraint("slug", name="uk_sysvoc_slug"),
        Index("idx_sysvoc_category", "category"),
        CheckConstraint("level BETWEEN 1 AND 5", name="ck_sysvoc_level_range"),
        CheckConstraint("length(trim(title)) > 0", name="ck_sysvoc_title_not_blank"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(50, collation=NOCASE), nullable=False)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    level: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    total_words: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source: Mapped[str] = mapped_column(String(10), nullable=False, server_default=SOURCE_SEED)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=UTC_NOW_DEFAULT
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=UTC_NOW_DEFAULT, onupdate=utcnow
    )
