# 2026-11-26 - voda-voca - 단어장 소유자 컬럼 추가: 표준 단어장(NULL)과 사용자별 개인 단어장을 구분한다 (#38, REQ-169)
# 파일 위치: src/backend/alembic/versions/0005_feat_단어장_소유자_컬럼.py
"""feat_단어장_소유자_컬럼

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '0005'
down_revision: Union[str, Sequence[str], None] = '0004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    batch_alter_table(테이블 재작성)을 쓰지 않는다. 재작성하면 COLLATE NOCASE 를 잃고, 부모 테이블을 지우는 과정에서
    ON DELETE CASCADE 가 단어·학습 이력·북마크를 지울 수 있다. op.add_column 은 SQLite 에서 FK 를 따로 만들지 못하므로
    열 정의에 REFERENCES 를 붙인 ADD COLUMN 을 직접 실행한다 (기본값이 NULL 이면 SQLite 가 허용한다).
    """
    op.execute(
        "ALTER TABLE system_vocabularies ADD COLUMN owner_id INTEGER "
        "CONSTRAINT fk_sysvoc_owner REFERENCES users (id) ON DELETE CASCADE"
    )
    op.create_index('idx_sysvoc_owner', 'system_vocabularies', ['owner_id'])

    # 관리자가 등록한 단어장은 지우지 않고 그 계정의 개인 단어장으로 바꾼다. 관리자 계정이 없으면 공용으로 둔다.
    # 표준 단어장에 더했던 단어(source='admin')는 이미 모두가 학습하던 것이라 그대로 둔다.
    admin = "(SELECT id FROM users WHERE lower(nickname) = 'admin')"
    op.execute(
        f"UPDATE system_vocabularies SET owner_id = {admin}, source = 'user' "
        f"WHERE source = 'admin' AND EXISTS {admin}"
    )
    op.execute(
        "UPDATE system_words SET source = 'user' WHERE vocabulary_id IN "
        "(SELECT id FROM system_vocabularies WHERE owner_id IS NOT NULL)"
    )


def downgrade() -> None:
    """Downgrade schema. 열만 지운다 (SQLite 3.35 이상). 바꾼 출처 값은 되돌리지 않는다."""
    op.drop_index('idx_sysvoc_owner', 'system_vocabularies')
    op.execute("ALTER TABLE system_vocabularies DROP COLUMN owner_id")
