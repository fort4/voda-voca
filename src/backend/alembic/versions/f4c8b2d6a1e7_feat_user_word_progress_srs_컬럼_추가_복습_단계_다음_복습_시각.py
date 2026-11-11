"""feat: user_word_progress 에 SRS 컬럼 추가 (interval_step, next_review_at)

Revision ID: f4c8b2d6a1e7
Revises: e2b6d4a9f1c3
Create Date: 2026-11-11 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


# revision identifiers, used by Alembic.
revision: str = 'f4c8b2d6a1e7'
down_revision: Union[str, Sequence[str], None] = 'e2b6d4a9f1c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """컬럼 두 개와 인덱스를 추가하고, 학습 이력이 있는 행을 연속 정답 수 기준으로 백필한다.

    백필 간격표는 services/srs.py 의 INTERVAL_DAYS (0, 1, 3, 7, 14, 30) 와 같아야 한다.
    """
    op.add_column("user_word_progress", sa.Column("interval_step", mysql.TINYINT(unsigned=True), nullable=False, server_default=sa.text("0")))
    op.add_column("user_word_progress", sa.Column("next_review_at", mysql.DATETIME(fsp=3), nullable=True))
    op.create_index("idx_uwp_user_next_review", "user_word_progress", ["user_id", "next_review_at"])
    op.execute("UPDATE user_word_progress SET interval_step = LEAST(consecutive_correct_count, 5) WHERE last_studied_at IS NOT NULL")
    op.execute(
        "UPDATE user_word_progress SET next_review_at = DATE_ADD(last_studied_at, INTERVAL "
        "ELT(interval_step + 1, 0, 1, 3, 7, 14, 30) DAY) WHERE last_studied_at IS NOT NULL"
    )


def downgrade() -> None:
    """SRS 값만 사라지고 기존 숙련 데이터에는 영향이 없다."""
    op.drop_index("idx_uwp_user_next_review", table_name="user_word_progress")
    op.drop_column("user_word_progress", "next_review_at")
    op.drop_column("user_word_progress", "interval_step")
