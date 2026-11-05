# 2026-11-02 - voda-voca - users 테이블 모델: 닉네임 고유 키 기반 계정 (REQ-001~003, REQ-110, 회원 체계 단순화)
# 파일 위치: src/backend/models/user.py

from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.mysql import BIGINT, DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import TABLE_OPTIONS, UTC_NOW_DEFAULT, Base, utcnow


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("nickname", name="uk_users_nickname"),
        CheckConstraint("CHAR_LENGTH(TRIM(nickname)) > 0", name="ck_users_nickname_not_blank"),
        TABLE_OPTIONS,
    )

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    # bcrypt 해시 문자열 (ADR-002). 평문은 저장하지 않는다.
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    nickname: Mapped[str] = mapped_column(String(50), nullable=False)
    # 사용자가 지금 집중해서 학습하는 표준 단어장. 단어장이 지워지면 NULL 로 돌아간다.
    active_vocabulary_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("system_vocabularies.id", ondelete="SET NULL", name="fk_users_active_vocabulary"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=3), nullable=False, server_default=UTC_NOW_DEFAULT
    )
    updated_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=3), nullable=False, server_default=UTC_NOW_DEFAULT, onupdate=utcnow
    )
