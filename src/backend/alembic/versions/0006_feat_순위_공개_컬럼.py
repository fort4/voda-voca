# 2026-11-26 - voda-voca - 순위 공개 컬럼 추가: 사용자가 정하는 학습 순위 공개 여부 (#42, REQ-173)
# 파일 위치: src/backend/alembic/versions/0006_feat_순위_공개_컬럼.py
"""feat_순위_공개_컬럼

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '0006'
down_revision: Union[str, Sequence[str], None] = '0005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema. 기존 계정은 모두 비공개(0)다.

    batch_alter_table(테이블 재작성)을 쓰지 않는다. users 를 다시 만들면 nickname 의 COLLATE NOCASE 를 잃고,
    부모 테이블을 지우는 과정에서 ON DELETE CASCADE 가 학습 기록을 지울 수 있다.
    """
    op.execute("ALTER TABLE users ADD COLUMN ranking_public BOOLEAN NOT NULL DEFAULT 0")


def downgrade() -> None:
    """Downgrade schema. 열만 지운다 (SQLite 3.35 이상)."""
    op.execute("ALTER TABLE users DROP COLUMN ranking_public")
