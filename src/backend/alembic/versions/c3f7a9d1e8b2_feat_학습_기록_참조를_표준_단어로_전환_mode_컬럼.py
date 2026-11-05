"""feat: 학습 기록·북마크·퀴즈 세션의 참조를 표준 단어장으로 전환하고 mode 컬럼 추가

Revision ID: c3f7a9d1e8b2
Revises: b1e5c0a7d2f4
Create Date: 2026-11-05 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


# revision identifiers, used by Alembic.
revision: str = 'c3f7a9d1e8b2'
down_revision: Union[str, Sequence[str], None] = 'b1e5c0a7d2f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_BIGINT = mysql.BIGINT(unsigned=True)


def upgrade() -> None:
    """**파괴적 마이그레이션**: study_logs, bookmarks, quiz_sessions 의 기존 행을 모두 지운다.

    옛 words/wordbooks 의 id 는 새 system_words/system_vocabularies 와 대응되지 않아 이관하지 않는다 (개발 DB, 실사용자 없음).
    실행 전 mysqldump 백업을 받아야 한다. MySQL DDL 은 트랜잭션이 아니므로 중간에 실패하면 일부만 적용될 수 있다.

    - study_logs.word_id, bookmarks.word_id: words.id -> system_words.id (CASCADE). bookmarks 의 (user_id, word_id) 유니크는 유지.
    - study_logs.mode, quiz_sessions.mode: VARCHAR(20) NOT NULL DEFAULT 'quiz', CHECK ('quiz', 'flashcard').
    - quiz_sessions.wordbook_id -> vocabulary_id (FK system_vocabularies.id, CASCADE).
    - quiz_sessions.source: 'wordbook' -> 'vocabulary' (CHECK 'vocabulary', 'bookmarks', 'wrong'). answers 구조는 그대로.
    wordbooks/words 테이블은 롤백 안전성을 위해 여기서 지우지 않는다 (레거시 정리 단계에서 삭제).
    """
    op.execute("DELETE FROM study_logs")
    op.execute("DELETE FROM bookmarks")
    op.execute("DELETE FROM quiz_sessions")

    # study_logs
    op.drop_constraint("fk_study_logs_word", "study_logs", type_="foreignkey")
    op.create_foreign_key(
        "fk_study_logs_word", "study_logs", "system_words", ["word_id"], ["id"], ondelete="CASCADE"
    )
    op.add_column("study_logs", sa.Column("mode", sa.String(length=20), server_default="quiz", nullable=False))
    op.create_check_constraint("ck_study_logs_mode", "study_logs", "mode IN ('quiz', 'flashcard')")

    # bookmarks
    op.drop_constraint("fk_bookmarks_word", "bookmarks", type_="foreignkey")
    op.create_foreign_key(
        "fk_bookmarks_word", "bookmarks", "system_words", ["word_id"], ["id"], ondelete="CASCADE"
    )

    # quiz_sessions
    op.drop_constraint("fk_quiz_sessions_wordbook", "quiz_sessions", type_="foreignkey")
    op.drop_index("fk_quiz_sessions_wordbook", table_name="quiz_sessions")  # FK 가 자동으로 만든 인덱스
    op.alter_column(
        "quiz_sessions",
        "wordbook_id",
        new_column_name="vocabulary_id",
        existing_type=_BIGINT,
        existing_nullable=True,
    )
    op.drop_constraint("ck_quiz_sessions_source", "quiz_sessions", type_="check")
    op.create_check_constraint(
        "ck_quiz_sessions_source", "quiz_sessions", "source IN ('vocabulary', 'bookmarks', 'wrong')"
    )
    op.create_foreign_key(
        "fk_quiz_sessions_vocabulary",
        "quiz_sessions",
        "system_vocabularies",
        ["vocabulary_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.add_column("quiz_sessions", sa.Column("mode", sa.String(length=20), server_default="quiz", nullable=False))
    op.create_check_constraint("ck_quiz_sessions_mode", "quiz_sessions", "mode IN ('quiz', 'flashcard')")


def downgrade() -> None:
    """스키마만 되돌린다. **데이터는 복원되지 않는다.**

    업그레이드에서 지운 기존 행은 이 마이그레이션이 되살리지 못한다 (mysqldump 백업으로만 복원 가능).
    업그레이드 이후에 쌓인 행은 system_words 를 가리키므로 옛 FK(words) 로 되돌리기 전에 지운다.
    """
    op.execute("DELETE FROM study_logs")
    op.execute("DELETE FROM bookmarks")
    op.execute("DELETE FROM quiz_sessions")

    # quiz_sessions
    op.drop_constraint("ck_quiz_sessions_mode", "quiz_sessions", type_="check")
    op.drop_column("quiz_sessions", "mode")
    op.drop_constraint("fk_quiz_sessions_vocabulary", "quiz_sessions", type_="foreignkey")
    op.drop_index("fk_quiz_sessions_vocabulary", table_name="quiz_sessions")
    op.drop_constraint("ck_quiz_sessions_source", "quiz_sessions", type_="check")
    op.create_check_constraint(
        "ck_quiz_sessions_source", "quiz_sessions", "source IN ('wordbook', 'bookmarks', 'wrong')"
    )
    op.alter_column(
        "quiz_sessions",
        "vocabulary_id",
        new_column_name="wordbook_id",
        existing_type=_BIGINT,
        existing_nullable=True,
    )
    op.create_foreign_key(
        "fk_quiz_sessions_wordbook", "quiz_sessions", "wordbooks", ["wordbook_id"], ["id"], ondelete="CASCADE"
    )

    # bookmarks
    op.drop_constraint("fk_bookmarks_word", "bookmarks", type_="foreignkey")
    op.create_foreign_key("fk_bookmarks_word", "bookmarks", "words", ["word_id"], ["id"], ondelete="CASCADE")

    # study_logs
    op.drop_constraint("ck_study_logs_mode", "study_logs", type_="check")
    op.drop_column("study_logs", "mode")
    op.drop_constraint("fk_study_logs_word", "study_logs", type_="foreignkey")
    op.create_foreign_key("fk_study_logs_word", "study_logs", "words", ["word_id"], ["id"], ondelete="CASCADE")
