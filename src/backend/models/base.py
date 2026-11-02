# 2026-11-02 - voda-voca - SQLAlchemy 2.0 DeclarativeBase, 공통 타입/시각 헬퍼
# 파일 위치: src/backend/models/base.py

from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.orm import DeclarativeBase


def utcnow() -> datetime:
    """UTC 현재 시각을 tzinfo 없는 datetime 으로 반환한다.

    DATETIME 컬럼은 타임존 정보를 저장하지 않으므로 UTC 값임을 코드에서 명확히 한다 (REQ-109).
    updated_at 의 갱신 시각으로 사용한다. MySQL ON UPDATE 는 UTC_TIMESTAMP 를 쓸 수 없어 앱에서 설정한다.
    """
    return datetime.now(UTC).replace(tzinfo=None)


# 생성 시각 기본값: DB 측에서 UTC 로 채운다 (데이터 설계서 §2.2, §2.3).
UTC_NOW_DEFAULT = text("(UTC_TIMESTAMP(3))")

# 모든 테이블의 엔진/문자셋/콜레이션 (데이터 설계서 §2.1, REQ-108).
TABLE_OPTIONS = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_0900_ai_ci",
}


class Base(DeclarativeBase):
    """모든 ORM 모델의 베이스. `Base.metadata` 가 Alembic autogenerate 의 기준이다."""
