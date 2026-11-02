# 2026-11-02 - voda-voca - sessions 테이블 모델 (로그인 세션, REQ-001, REQ-002, ADR-001)
# 파일 위치: src/backend/models/session.py

from datetime import datetime

from sqlalchemy import ForeignKey, Index
from sqlalchemy.dialects.mysql import BIGINT, BINARY, DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import TABLE_OPTIONS, UTC_NOW_DEFAULT, Base


class AuthSession(Base):
    """로그인 세션. 클래스명은 SQLAlchemy Session 과의 혼동을 피하려고 AuthSession 으로 둔다.

    id 는 클라이언트 쿠키 토큰 원문이 아니라 그 토큰의 SHA-256 다이제스트(32바이트)다.
    DB가 노출되어도 유효한 세션 토큰이 노출되지 않도록 하기 위함이다.
    """

    __tablename__ = "sessions"
    __table_args__ = (
        Index("idx_sessions_user", "user_id"),
        Index("idx_sessions_expires", "expires_at"),
        TABLE_OPTIONS,
    )

    id: Mapped[bytes] = mapped_column(BINARY(32), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("users.id", ondelete="CASCADE", name="fk_sessions_user"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=3), nullable=False, server_default=UTC_NOW_DEFAULT
    )
    # 절대 만료 시각 (UTC). 기본 수명 14일은 REQ-002 기본값이다.
    expires_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), nullable=False)
