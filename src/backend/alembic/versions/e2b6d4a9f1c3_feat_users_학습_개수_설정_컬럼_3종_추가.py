"""feat: users 학습 개수 설정 컬럼 3종 추가 (quiz_count, flashcard_count, daily_goal)

Revision ID: e2b6d4a9f1c3
Revises: d1a8e3f5c7b9
Create Date: 2026-11-10 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


# revision identifiers, used by Alembic.
revision: str = 'e2b6d4a9f1c3'
down_revision: Union[str, Sequence[str], None] = 'd1a8e3f5c7b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLUMNS = ("quiz_count", "flashcard_count", "daily_goal")


def upgrade() -> None:
    """컬럼 3개를 DEFAULT 10 으로 추가한다. 기존 사용자도 전부 10 이 된다. 허용 값(10/20/30)은 앱이 검증한다."""
    for name in _COLUMNS:
        op.add_column("users", sa.Column(name, mysql.SMALLINT(unsigned=True), nullable=False, server_default=sa.text("10")))
        op.create_check_constraint(f"ck_users_{name}_positive", "users", f"{name} > 0")


def downgrade() -> None:
    """설정값만 사라지고 다른 데이터에는 영향이 없다. CHECK 를 먼저 지운다."""
    for name in reversed(_COLUMNS):
        op.drop_constraint(f"ck_users_{name}_positive", "users", type_="check")
        op.drop_column("users", name)
