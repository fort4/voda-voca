# 2026-11-05 - voda-voca - user_word_progress 테이블 모델: 사용자별 단어 학습 요약 (출제·숙련 판정용)
# 파일 위치: src/backend/models/user_word_progress.py

from datetime import datetime

from sqlalchemy import Boolean, Enum, ForeignKey, Index, UniqueConstraint, text
from sqlalchemy.dialects.mysql import BIGINT, DATETIME, INTEGER
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import TABLE_OPTIONS, Base


class UserWordProgress(Base):
    """사용자×단어 1행. study_logs 를 매번 훑지 않고 세션 출제와 숙련 판정을 빠르게 하기 위한 요약이다.

    숙련 규칙 (이슈 #15 안 A): consecutive_correct_count >= 3 이면 is_memorized = True,
    오답 1회면 consecutive_correct_count = 0, is_memorized = False. 갱신은 services/progress.py 가 맡는다.
    """

    __tablename__ = "user_word_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "word_id", name="uk_uwp_user_word"),
        Index("idx_uwp_user_result", "user_id", "last_result"),
        Index("idx_uwp_user_memorized", "user_id", "is_memorized"),
        Index("idx_uwp_word", "word_id"),
        TABLE_OPTIONS,
    )

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("users.id", ondelete="CASCADE", name="fk_uwp_user"),
        nullable=False,
    )
    word_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("system_words.id", ondelete="CASCADE", name="fk_uwp_word"),
        nullable=False,
    )
    correct_count: Mapped[int] = mapped_column(INTEGER(unsigned=True), nullable=False, server_default=text("0"))
    wrong_count: Mapped[int] = mapped_column(INTEGER(unsigned=True), nullable=False, server_default=text("0"))
    consecutive_correct_count: Mapped[int] = mapped_column(
        INTEGER(unsigned=True), nullable=False, server_default=text("0")
    )
    is_memorized: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("0"))
    last_result: Mapped[str | None] = mapped_column(
        Enum("CORRECT", "WRONG", name="uwp_last_result"), nullable=True
    )
    last_studied_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=3), nullable=True)
