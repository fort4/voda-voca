"""feat: words 테이블 example_meaning 컬럼 추가 (예문 한글 뜻)

Revision ID: 4454ed2683cb
Revises: aa1c92a9c7f9
Create Date: 2026-11-02 21:08:13.353545

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4454ed2683cb'
down_revision: Union[str, Sequence[str], None] = 'aa1c92a9c7f9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """words 에 예문 한글 뜻(example_meaning, 선택)을 추가한다. 기존 행은 NULL 이다."""
    op.add_column(
        "words",
        sa.Column("example_meaning", sa.String(length=500), nullable=True),
    )


def downgrade() -> None:
    """예문 한글 뜻 컬럼을 제거한다. 저장된 해석은 함께 사라진다."""
    op.drop_column("words", "example_meaning")
