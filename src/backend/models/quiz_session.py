# 2026-11-02 - voda-voca - quiz_sessions 테이블 모델 (퀴즈 출제 상태, 만료 30분, 1회 제출, REQ-014~016)
# 파일 위치: src/backend/models/quiz_session.py

from datetime import datetime

from sqlalchemy import JSON, Boolean, CheckConstraint, ForeignKey, Index, String
from sqlalchemy.dialects.mysql import BIGINT, DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import TABLE_OPTIONS, UTC_NOW_DEFAULT, Base

QUIZ_SOURCE_WORDBOOK = "wordbook"
QUIZ_SOURCE_BOOKMARKS = "bookmarks"
QUIZ_SOURCE_WRONG = "wrong"


class QuizSession(Base):
    """퀴즈 출제 1회분의 서버 측 상태.

    - questions: 문항 목록(JSON). 각 문항은 word_id, term, choices(4개), correct_index 를 가진다.
      정답 인덱스를 클라이언트에 보내지 않기 위해 서버가 이 값을 보관한다.
    - is_submitted: 제출이 한 번이라도 성공하면 True. 같은 세션의 재제출을 막는다 (409).
    - expires_at: 출제 시각 + 30분. 지나면 제출을 거부한다 (400).
    - wordbook_id: source 가 'wordbook' 일 때만 값이 있다. 북마크 퀴즈는 NULL.
    """

    __tablename__ = "quiz_sessions"
    __table_args__ = (
        CheckConstraint(
            "source IN ('wordbook', 'bookmarks', 'wrong')",
            name="ck_quiz_sessions_source",
        ),
        Index("idx_quiz_sessions_user", "user_id"),
        TABLE_OPTIONS,
    )

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("users.id", ondelete="CASCADE", name="fk_quiz_sessions_user"),
        nullable=False,
    )
    wordbook_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("wordbooks.id", ondelete="CASCADE", name="fk_quiz_sessions_wordbook"),
        nullable=True,
    )
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    questions: Mapped[list[dict]] = mapped_column(JSON, nullable=False)
    is_submitted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    expires_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=3), nullable=False, server_default=UTC_NOW_DEFAULT
    )
