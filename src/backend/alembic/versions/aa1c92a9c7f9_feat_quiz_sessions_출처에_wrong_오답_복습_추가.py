"""feat: quiz_sessions 출처에 wrong(오답 복습) 추가

Revision ID: aa1c92a9c7f9
Revises: 3384caa6f116
Create Date: 2026-11-02 20:30:27.053409

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'aa1c92a9c7f9'
down_revision: Union[str, Sequence[str], None] = '3384caa6f116'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """quiz_sessions.source 의 CHECK 제약에 'wrong'(오답 복습) 을 추가한다. 기존 행은 그대로 유효하다."""
    op.drop_constraint("ck_quiz_sessions_source", "quiz_sessions", type_="check")
    op.create_check_constraint(
        "ck_quiz_sessions_source",
        "quiz_sessions",
        "source IN ('wordbook', 'bookmarks', 'wrong')",
    )


def downgrade() -> None:
    """'wrong' 행이 남아 있으면 제약을 되돌릴 수 없으므로 먼저 삭제한다 (세션은 임시 데이터다)."""
    op.execute("DELETE FROM quiz_sessions WHERE source = 'wrong'")
    op.drop_constraint("ck_quiz_sessions_source", "quiz_sessions", type_="check")
    op.create_check_constraint(
        "ck_quiz_sessions_source",
        "quiz_sessions",
        "source IN ('wordbook', 'bookmarks')",
    )
