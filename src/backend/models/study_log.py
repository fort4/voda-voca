# 2026-11-02 - voda-voca - study_logs 테이블 모델 (문항별 학습 이력, REQ-016, D4)
# 파일 위치: src/backend/models/study_log.py

from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Index
from sqlalchemy.dialects.mysql import BIGINT, DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import TABLE_OPTIONS, UTC_NOW_DEFAULT, Base


class StudyLog(Base):
    """퀴즈 문항 답안 1건당 1행. 단어별 누적 카운터는 두지 않는다 (REQ-016 확정).

    최근 학습 이력 조회: WHERE user_id = ? ORDER BY created_at DESC, id DESC LIMIT 100
    (idx_study_logs_user_created 를 역방향으로 읽는다).
    """

    __tablename__ = "study_logs"
    __table_args__ = (
        Index("idx_study_logs_user_created", "user_id", "created_at"),
        Index("idx_study_logs_word", "word_id"),
        TABLE_OPTIONS,
    )

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("users.id", ondelete="CASCADE", name="fk_study_logs_user"),
        nullable=False,
    )
    word_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("words.id", ondelete="CASCADE", name="fk_study_logs_word"),
        nullable=False,
    )
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=3), nullable=False, server_default=UTC_NOW_DEFAULT
    )
