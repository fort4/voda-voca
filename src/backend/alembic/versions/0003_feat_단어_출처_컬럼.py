# 2026-11-26 - voda-voca - 단어·단어장의 출처 컬럼 추가: 시드와 관리자 등록분을 구분한다 (REQ-160, REQ-161)
# 파일 위치: src/backend/alembic/versions/0003_feat_단어_출처_컬럼.py
"""feat_단어_출처_컬럼

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0003'
down_revision: Union[str, Sequence[str], None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = ('system_vocabularies', 'system_words')


def upgrade() -> None:
    """Upgrade schema.

    batch_alter_table(테이블 재작성)을 쓰지 않는다. 재작성하면 COLLATE NOCASE 를 잃고, 부모 테이블을 지우는 과정에서
    ON DELETE CASCADE 가 학습 이력·북마크를 지울 수 있다. SQLite 의 ADD COLUMN 은 기존 행을 건드리지 않는다.
    값의 제한(seed|admin)은 CHECK 대신 앱이 지킨다 (CHECK 를 나중에 붙이려면 재작성이 필요하다).
    """
    for table in TABLES:
        op.add_column(table, sa.Column('source', sa.String(length=10), server_default='seed', nullable=False))


def downgrade() -> None:
    """Downgrade schema. DROP COLUMN 도 재작성 없이 처리한다 (SQLite 3.35 이상)."""
    for table in TABLES:
        op.drop_column(table, 'source')
