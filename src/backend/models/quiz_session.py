# 2026-11-02 - voda-voca - quiz_sessions 테이블 모델 (퀴즈 출제 상태, 만료 30분, 1회 제출, REQ-014~016)
# 파일 위치: src/backend/models/quiz_session.py

from datetime import datetime

from sqlalchemy import JSON, Boolean, CheckConstraint, ForeignKey, Index, String, text
from sqlalchemy.dialects.mysql import BIGINT, DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import TABLE_OPTIONS, UTC_NOW_DEFAULT, Base

QUIZ_SOURCE_VOCABULARY = "vocabulary"
QUIZ_SOURCE_BOOKMARKS = "bookmarks"
QUIZ_SOURCE_WRONG = "wrong"


class QuizSession(Base):
    """퀴즈 출제 1회분의 서버 측 상태.

    - questions: 문항 목록(JSON). 각 문항은 word_id, term, choices(4개), correct_index 를 가진다.
      정답 인덱스를 클라이언트에 보내지 않기 위해 서버가 이 값을 보관한다.
    - answers: {"문항번호": 고른 선지 번호}. 답을 고를 때마다 서버에 기록하고(study_logs 와 같은 트랜잭션),
      같은 답의 재전송을 멱등으로, 다른 답으로 바꾸기를 거부하는 근거가 된다. 결과 화면도 이 값으로 다시 만든다 (이슈 #8).
    - is_submitted: 퀴즈를 끝내면 True. 이후 답 기록과 재제출을 막는다 (409).
    - expires_at: 마지막으로 답을 기록한 시각 + 30분 (처음에는 출제 시각 + 30분). 지나면 새 답을 거부한다 (400).
    - vocabulary_id: source 가 'vocabulary' 일 때만 값이 있다. 북마크·오답 복습은 NULL.
    - mode: 'quiz' | 'flashcard'. 플래시카드도 같은 세션 구조와 문항별 기록을 쓴다 (이슈 #17).
    """

    __tablename__ = "quiz_sessions"
    __table_args__ = (
        CheckConstraint(
            "source IN ('vocabulary', 'bookmarks', 'wrong')",
            name="ck_quiz_sessions_source",
        ),
        CheckConstraint("mode IN ('quiz', 'flashcard')", name="ck_quiz_sessions_mode"),
        Index("idx_quiz_sessions_user", "user_id"),
        TABLE_OPTIONS,
    )

    id: Mapped[int] = mapped_column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("users.id", ondelete="CASCADE", name="fk_quiz_sessions_user"),
        nullable=False,
    )
    vocabulary_id: Mapped[int | None] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey("system_vocabularies.id", ondelete="CASCADE", name="fk_quiz_sessions_vocabulary"),
        nullable=True,
    )
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    mode: Mapped[str] = mapped_column(String(20), nullable=False, server_default="quiz")
    questions: Mapped[list[dict]] = mapped_column(JSON, nullable=False)
    answers: Mapped[dict] = mapped_column(JSON, nullable=False, server_default=text("(JSON_OBJECT())"))
    is_submitted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    expires_at: Mapped[datetime] = mapped_column(DATETIME(fsp=3), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=3), nullable=False, server_default=UTC_NOW_DEFAULT
    )
