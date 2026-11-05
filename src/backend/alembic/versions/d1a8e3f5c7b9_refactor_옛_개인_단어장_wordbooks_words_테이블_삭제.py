"""refactor: 옛 개인 단어장 wordbooks, words 테이블 삭제

Revision ID: d1a8e3f5c7b9
Revises: c3f7a9d1e8b2
Create Date: 2026-11-05 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


# revision identifiers, used by Alembic.
revision: str = 'd1a8e3f5c7b9'
down_revision: Union[str, Sequence[str], None] = 'c3f7a9d1e8b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_BIGINT = mysql.BIGINT(unsigned=True)
_NOW = sa.text("(UTC_TIMESTAMP(3))")
_OPTIONS = dict(mysql_engine="InnoDB", mysql_charset="utf8mb4", mysql_collate="utf8mb4_0900_ai_ci")


def upgrade() -> None:
    """**파괴적 마이그레이션**: 두 테이블의 행이 모두 사라진다. 실행 전 mysqldump 백업을 받아야 한다.

    중앙 제공형 전환(c3f7a9d1e8b2)으로 이 테이블을 참조하는 곳이 없다. 자식(words) -> 부모(wordbooks) 순으로 지운다.
    """
    op.drop_table("words")
    op.drop_table("wordbooks")


def downgrade() -> None:
    """구조만 복원한다. 데이터는 복구되지 않으므로 백업 덤프로 되살려야 한다."""
    op.create_table(
        "wordbooks",
        sa.Column("id", _BIGINT, autoincrement=True, nullable=False),
        sa.Column("user_id", _BIGINT, nullable=False),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("description", sa.String(200), nullable=True),
        sa.Column("created_at", mysql.DATETIME(fsp=3), server_default=_NOW, nullable=False),
        sa.Column("updated_at", mysql.DATETIME(fsp=3), server_default=_NOW, nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_wordbooks_user", ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "name", name="uk_wordbooks_user_name"),
        sa.CheckConstraint("CHAR_LENGTH(TRIM(name)) > 0", name="ck_wordbooks_name_not_blank"),
        **_OPTIONS,
    )
    op.create_index("idx_wordbooks_user_updated", "wordbooks", ["user_id", "updated_at"])
    op.create_table(
        "words",
        sa.Column("id", _BIGINT, autoincrement=True, nullable=False),
        sa.Column("wordbook_id", _BIGINT, nullable=False),
        sa.Column("term", sa.String(100), nullable=False),
        sa.Column("meaning", sa.String(200), nullable=False),
        sa.Column("example", sa.String(500), nullable=True),
        sa.Column("created_at", mysql.DATETIME(fsp=3), server_default=_NOW, nullable=False),
        sa.Column("updated_at", mysql.DATETIME(fsp=3), server_default=_NOW, nullable=False),
        sa.Column("example_meaning", sa.String(500), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["wordbook_id"], ["wordbooks.id"], name="fk_words_wordbook", ondelete="CASCADE"),
        sa.UniqueConstraint("wordbook_id", "term", name="uk_words_wordbook_term"),
        sa.CheckConstraint(
            "CHAR_LENGTH(TRIM(term)) > 0 AND CHAR_LENGTH(TRIM(meaning)) > 0", name="ck_words_not_blank"
        ),
        **_OPTIONS,
    )
