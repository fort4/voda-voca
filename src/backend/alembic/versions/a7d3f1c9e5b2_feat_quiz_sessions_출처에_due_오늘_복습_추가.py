"""feat: quiz_sessions 출처에 due(오늘 복습, SRS) 추가

Revision ID: a7d3f1c9e5b2
Revises: f4c8b2d6a1e7
Create Date: 2026-11-11 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'a7d3f1c9e5b2'
down_revision: Union[str, Sequence[str], None] = 'f4c8b2d6a1e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """source CHECK 제약에 'due' 를 추가한다. 기존 행은 그대로 유효하다."""
    op.drop_constraint("ck_quiz_sessions_source", "quiz_sessions", type_="check")
    op.create_check_constraint(
        "ck_quiz_sessions_source", "quiz_sessions", "source IN ('vocabulary', 'bookmarks', 'wrong', 'due')"
    )


def downgrade() -> None:
    """'due' 행이 남아 있으면 제약을 되돌릴 수 없으므로 먼저 삭제한다 (세션은 임시 데이터다)."""
    op.execute("DELETE FROM quiz_sessions WHERE source = 'due'")
    op.drop_constraint("ck_quiz_sessions_source", "quiz_sessions", type_="check")
    op.create_check_constraint(
        "ck_quiz_sessions_source", "quiz_sessions", "source IN ('vocabulary', 'bookmarks', 'wrong')"
    )
