"""feat: 중앙 제공형 단어장 테이블(system_vocabularies, system_words, user_word_progress) 추가

Revision ID: b1e5c0a7d2f4
Revises: 7c2d4e91b5a3
Create Date: 2026-11-05 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


# revision identifiers, used by Alembic.
revision: str = 'b1e5c0a7d2f4'
down_revision: Union[str, Sequence[str], None] = '7c2d4e91b5a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE_OPTIONS = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_0900_ai_ci",
}
_UTC_NOW = sa.text("(UTC_TIMESTAMP(3))")


def upgrade() -> None:
    """추가만 하는 마이그레이션이다. 기존 테이블과 데이터는 건드리지 않는다.

    - system_vocabularies: 서비스가 제공하는 읽기 전용 단어장. category 는 자유 문자열(VARCHAR(50)) + 인덱스.
    - system_words: 표준 단어. 이름은 기존 words 와 같다. pos/phonetic/level 은 확장 필드(NULL 허용).
    - user_word_progress: 사용자×단어 학습 요약 (출제, 숙련 판정).
    - users.active_vocabulary_id: 현재 학습 중인 단어장.
    기존 study_logs/bookmarks/quiz_sessions 의 참조 교체와 wordbooks/words 삭제는 별도 전환 마이그레이션(B-4)에서 한다.
    """
    op.create_table(
        "system_vocabularies",
        sa.Column("id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("slug", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=100), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("level", mysql.INTEGER(), server_default=sa.text("1"), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("total_words", mysql.INTEGER(unsigned=True), server_default=sa.text("0"), nullable=False),
        sa.Column("sort_order", mysql.INTEGER(), server_default=sa.text("0"), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("created_at", mysql.DATETIME(fsp=3), server_default=_UTC_NOW, nullable=False),
        sa.Column("updated_at", mysql.DATETIME(fsp=3), server_default=_UTC_NOW, nullable=False),
        sa.CheckConstraint("level BETWEEN 1 AND 5", name="ck_sysvoc_level_range"),
        sa.CheckConstraint("CHAR_LENGTH(TRIM(title)) > 0", name="ck_sysvoc_title_not_blank"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uk_sysvoc_slug"),
        **_TABLE_OPTIONS,
    )
    op.create_index("idx_sysvoc_category", "system_vocabularies", ["category"], unique=False)

    op.create_table(
        "system_words",
        sa.Column("id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("vocabulary_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("term", sa.String(length=100), nullable=False),
        sa.Column("meaning", sa.String(length=200), nullable=False),
        sa.Column("example", sa.String(length=500), nullable=True),
        sa.Column("example_meaning", sa.String(length=500), nullable=True),
        sa.Column("pos", sa.String(length=20), nullable=True),
        sa.Column("phonetic", sa.String(length=100), nullable=True),
        sa.Column("level", mysql.TINYINT(), nullable=True),
        sa.Column("order_index", mysql.INTEGER(), server_default=sa.text("0"), nullable=False),
        sa.CheckConstraint(
            "CHAR_LENGTH(TRIM(term)) > 0 AND CHAR_LENGTH(TRIM(meaning)) > 0", name="ck_sysword_not_blank"
        ),
        sa.ForeignKeyConstraint(
            ["vocabulary_id"], ["system_vocabularies.id"], name="fk_sysword_vocabulary", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("vocabulary_id", "term", name="uk_sysword_vocab_term"),
        **_TABLE_OPTIONS,
    )
    op.create_index("idx_sysword_vocab_order", "system_words", ["vocabulary_id", "order_index"], unique=False)

    op.create_table(
        "user_word_progress",
        sa.Column("id", mysql.BIGINT(unsigned=True), autoincrement=True, nullable=False),
        sa.Column("user_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("word_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("correct_count", mysql.INTEGER(unsigned=True), server_default=sa.text("0"), nullable=False),
        sa.Column("wrong_count", mysql.INTEGER(unsigned=True), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "consecutive_correct_count", mysql.INTEGER(unsigned=True), server_default=sa.text("0"), nullable=False
        ),
        sa.Column("is_memorized", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        sa.Column("last_result", sa.Enum("CORRECT", "WRONG", name="uwp_last_result"), nullable=True),
        sa.Column("last_studied_at", mysql.DATETIME(fsp=3), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_uwp_user", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["word_id"], ["system_words.id"], name="fk_uwp_word", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "word_id", name="uk_uwp_user_word"),
        **_TABLE_OPTIONS,
    )
    op.create_index("idx_uwp_user_result", "user_word_progress", ["user_id", "last_result"], unique=False)
    op.create_index("idx_uwp_user_memorized", "user_word_progress", ["user_id", "is_memorized"], unique=False)
    op.create_index("idx_uwp_word", "user_word_progress", ["word_id"], unique=False)

    op.add_column("users", sa.Column("active_vocabulary_id", mysql.BIGINT(unsigned=True), nullable=True))
    op.create_foreign_key(
        "fk_users_active_vocabulary",
        "users",
        "system_vocabularies",
        ["active_vocabulary_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """추가한 것을 되돌린다. 새 테이블에 쌓인 데이터(진행도, 시드)는 함께 사라진다."""
    op.drop_constraint("fk_users_active_vocabulary", "users", type_="foreignkey")
    op.drop_column("users", "active_vocabulary_id")
    op.drop_table("user_word_progress")
    op.drop_table("system_words")
    op.drop_table("system_vocabularies")
