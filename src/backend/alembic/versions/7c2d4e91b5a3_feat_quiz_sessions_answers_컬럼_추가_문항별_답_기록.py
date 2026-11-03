"""feat: quiz_sessions 에 answers 컬럼 추가 (문항별 답 기록)

Revision ID: 7c2d4e91b5a3
Revises: 4454ed2683cb
Create Date: 2026-11-03 10:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7c2d4e91b5a3'
down_revision: Union[str, Sequence[str], None] = '4454ed2683cb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """quiz_sessions 에 answers(JSON) 를 추가한다. {"문항번호": 고른 선지 번호} 형태이며 기존 행은 {} 이다.

    문항마다 답을 서버에 기록하고(중도 이탈에도 유실되지 않게), 같은 답의 재전송을 멱등으로 처리하고,
    결과 화면을 서버에서 다시 만들기 위한 컬럼이다 (이슈 #8). 이미 제출된 과거 세션은 {} 로 남으므로
    과거 결과를 다시 만들 수는 없다 (과거 결과는 sessionStorage 에만 있었다).
    MySQL 8 의 JSON 컬럼 기본값은 표현식 형태여야 해서 (JSON_OBJECT()) 를 쓴다.
    """
    op.add_column(
        "quiz_sessions",
        sa.Column("answers", sa.JSON(), server_default=sa.text("(JSON_OBJECT())"), nullable=False),
    )


def downgrade() -> None:
    """answers 를 제거한다. 이미 기록된 문항별 답 요약은 사라지지만 study_logs 는 그대로 남는다."""
    op.drop_column("quiz_sessions", "answers")
