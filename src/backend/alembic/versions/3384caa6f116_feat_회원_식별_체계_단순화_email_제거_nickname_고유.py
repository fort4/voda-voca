"""feat: 회원 식별 체계 단순화 (email 제거, nickname 고유)

Revision ID: 3384caa6f116
Revises: 83b1cf291a93
Create Date: 2026-11-02 18:52:58.713610

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3384caa6f116'
down_revision: Union[str, Sequence[str], None] = '83b1cf291a93'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """email 을 제거하고 nickname 을 고유 키로 바꾼다.

    중복 닉네임이 있으면 고유 키를 만들 수 없으므로 마이그레이션을 중단한다 (데이터를 임의로 바꾸지 않는다).
    """
    conn = op.get_bind()
    duplicates = conn.execute(
        sa.text("SELECT nickname FROM users GROUP BY nickname HAVING COUNT(*) > 1 LIMIT 5")
    ).fetchall()
    if duplicates:
        names = ", ".join(row[0] for row in duplicates)
        raise RuntimeError(f"중복 닉네임이 있어 마이그레이션을 중단합니다: {names}")

    op.drop_index("uk_users_email", table_name="users")
    op.drop_column("users", "email")
    op.create_index("uk_users_nickname", "users", ["nickname"], unique=True)


def downgrade() -> None:
    """닉네임 고유 키를 되돌리고 email 컬럼을 NULL 허용으로 다시 만든다.

    제거된 이메일 값은 복구할 수 없다. 되돌린 뒤 email 은 모두 NULL 이며, UNIQUE 는 NULL 을 중복으로 보지 않는다.
    """
    op.drop_index("uk_users_nickname", table_name="users")
    op.add_column("users", sa.Column("email", sa.String(length=255), nullable=True))
    op.create_index("uk_users_email", "users", ["email"], unique=True)
