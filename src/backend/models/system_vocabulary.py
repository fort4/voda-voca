# 2026-11-05 - voda-voca - system_vocabularies 테이블 모델: 읽기 전용 표준 단어장과 사용자별 개인 단어장
# 파일 위치: src/backend/models/system_vocabulary.py

from datetime import datetime

from sqlalchemy import CheckConstraint, ColumnElement, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, or_, text
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import NOCASE, SOURCE_SEED, UTC_NOW_DEFAULT, Base, utcnow


class SystemVocabulary(Base):
    """단어장. owner_id 가 NULL 이면 모두가 보는 읽기 전용 표준 단어장(서버 시드), 값이 있으면 그 사용자만 보고 고치는
    개인 단어장이다 (source='user', REQ-169).

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
        Index("idx_sysvoc_owner", "owner_id"),
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
    # 개인 단어장의 소유자. 탈퇴하면 단어장과 단어, 그 학습 기록이 함께 지워진다.
    # users.active_vocabulary_id 와 서로 참조하므로 use_alter 로 테이블 생성 순서의 순환을 끊는다.
    owner_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE", name="fk_sysvoc_owner", use_alter=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=UTC_NOW_DEFAULT
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=UTC_NOW_DEFAULT, onupdate=utcnow
    )


def visible_to(user_id: int) -> ColumnElement[bool]:
    """이 사용자에게 보이는 단어장: 표준 단어장과 본인의 개인 단어장.

    단어장이나 그 단어를 찾는 모든 조회는 이 조건을 써야 한다 (REQ-169). 안 보이는 단어장은 없는 것(404)과 같게 다룬다.
    """
    return or_(SystemVocabulary.owner_id.is_(None), SystemVocabulary.owner_id == user_id)
