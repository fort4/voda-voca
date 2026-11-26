# 2026-11-26 - voda-voca - 학습 이력에 일차 컬럼 추가 (REQ-165, VOCA-FR-014)
# 파일 위치: src/backend/alembic/versions/0004_feat_학습_일차_컬럼.py
"""feat_학습_일차_컬럼

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0004'
down_revision: Union[str, Sequence[str], None] = '0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    batch_alter_table(테이블 재작성)을 쓰지 않고 ADD COLUMN 만 쓴다. 기존 이력은 일차를 비워 둔다(NULL).
    지난 기록의 일차는 그때의 학습량을 알 수 없어 만들어 넣지 않는다.
    """
    op.add_column('study_logs', sa.Column('study_day', sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema. DROP COLUMN 도 재작성 없이 처리한다 (SQLite 3.35 이상)."""
    op.drop_column('study_logs', 'study_day')
