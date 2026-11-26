# 2026-11-02 - voda-voca - study_logs 테이블 모델 (문항별 학습 이력, REQ-016, D4. 일차 REQ-165)
# 파일 위치: src/backend/models/study_log.py

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import UTC_NOW_DEFAULT, Base

STUDY_MODE_QUIZ = "quiz"
STUDY_MODE_FLASHCARD = "flashcard"


class StudyLog(Base):
    """퀴즈 문항 답안 1건당 1행. 단어별 누적 카운터는 두지 않는다 (REQ-016 확정).

    최근 학습 이력 조회: WHERE user_id = ? ORDER BY created_at DESC, id DESC LIMIT 100
    (idx_study_logs_user_created 를 역방향으로 읽는다).
    """

    __tablename__ = "study_logs"
    __table_args__ = (
        Index("idx_study_logs_user_created", "user_id", "created_at"),
        Index("idx_study_logs_word", "word_id"),
        CheckConstraint("mode IN ('quiz', 'flashcard')", name="ck_study_logs_mode"),
        CheckConstraint("direction IN ('en_to_ko', 'ko_to_en')", name="ck_study_logs_direction"),
        CheckConstraint("format IN ('choice', 'ox')", name="ck_study_logs_format"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE", name="fk_study_logs_user"),
        nullable=False,
    )
    word_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("system_words.id", ondelete="CASCADE", name="fk_study_logs_word"),
        nullable=False,
    )
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    # 학습 모드. 플래시카드의 '알아요/헷갈려요'는 정답/오답으로 기록하되 모드로 구분한다 (이슈 #17).
    mode: Mapped[str] = mapped_column(String(20), nullable=False, server_default=STUDY_MODE_QUIZ)
    # 문항 단위 방향·형식 (VOCA-FR-026). 섞기 세션도 이 문항의 실제 방향을 적는다. 플래시카드는 기본값이다.
    direction: Mapped[str] = mapped_column(String(10), nullable=False, server_default="en_to_ko")
    format: Mapped[str] = mapped_column(String(10), nullable=False, server_default="choice")
    # 몇 일차 학습인지 (REQ-165, VOCA-FR-014). 단어가 속한 단어장 기준이다. 0004 이전의 기록은 NULL 이다.
    study_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=UTC_NOW_DEFAULT
    )
