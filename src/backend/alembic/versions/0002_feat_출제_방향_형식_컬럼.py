# 2026-11-25 - voda-voca - 출제 방향·형식 컬럼 추가: quiz_sessions, study_logs (VOCA-FR-023·024·026)
# 파일 위치: src/backend/alembic/versions/0002_feat_출제_방향_형식_컬럼.py
"""feat_출제_방향_형식_컬럼

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-25 17:15:07.905467

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0002'
down_revision: Union[str, Sequence[str], None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('quiz_sessions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('direction', sa.String(length=10), server_default='en_to_ko', nullable=False))
        batch_op.add_column(sa.Column('format', sa.String(length=10), server_default='choice', nullable=False))
        batch_op.create_check_constraint('ck_quiz_sessions_direction', "direction IN ('en_to_ko', 'ko_to_en', 'mixed')")
        batch_op.create_check_constraint('ck_quiz_sessions_format', "format IN ('choice', 'ox')")

    with op.batch_alter_table('study_logs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('direction', sa.String(length=10), server_default='en_to_ko', nullable=False))
        batch_op.add_column(sa.Column('format', sa.String(length=10), server_default='choice', nullable=False))
        batch_op.create_check_constraint('ck_study_logs_direction', "direction IN ('en_to_ko', 'ko_to_en')")
        batch_op.create_check_constraint('ck_study_logs_format', "format IN ('choice', 'ox')")


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('study_logs', schema=None) as batch_op:
        batch_op.drop_constraint('ck_study_logs_format', type_='check')
        batch_op.drop_constraint('ck_study_logs_direction', type_='check')
        batch_op.drop_column('format')
        batch_op.drop_column('direction')

    with op.batch_alter_table('quiz_sessions', schema=None) as batch_op:
        batch_op.drop_constraint('ck_quiz_sessions_format', type_='check')
        batch_op.drop_constraint('ck_quiz_sessions_direction', type_='check')
        batch_op.drop_column('format')
        batch_op.drop_column('direction')

