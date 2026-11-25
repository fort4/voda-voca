# 2026-11-02 - voda-voca - SQLAlchemy 2.0 DeclarativeBase, 공통 타입/시각 헬퍼 (2026-11-25 SQLite 전환)
# 파일 위치: src/backend/models/base.py

from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.orm import DeclarativeBase


def utcnow() -> datetime:
    """UTC 현재 시각을 tzinfo 없는 datetime 으로 반환한다.

    DateTime 컬럼은 타임존 정보를 저장하지 않으므로 UTC 값임을 코드에서 명확히 한다 (REQ-109).
    updated_at 의 갱신 시각으로 사용한다 (SQLite 에는 MySQL 의 ON UPDATE 가 없어 앱에서 설정한다).
    """
    return datetime.now(UTC).replace(tzinfo=None)


# 생성 시각 기본값: DB 측에서 UTC 로 채운다 (데이터 설계서 §2.2, §2.3).
# strftime 의 %f 는 밀리초(SS.SSS)만 주므로 뒤에 000 을 붙여 6자리 마이크로초로 맞춘다.
# SQLAlchemy 의 SQLite DateTime 은 소수부를 마이크로초 정수로 읽기 때문에, 3자리면 0.123초가 0.000123초가 된다.
UTC_NOW_DEFAULT = text("(strftime('%Y-%m-%d %H:%M:%f000', 'now'))")

# 대소문자를 무시하고 비교·고유 판정하는 컬럼용 콜레이션 (MySQL utf8mb4_0900_ai_ci 의 대소문자 무시 부분을 대신한다).
# SQLite NOCASE 는 ASCII 만 접는다. 악센트 무시는 지원하지 않으며, 필요한 곳은 앱(system_seed)이 정규화한다.
NOCASE = "NOCASE"


class Base(DeclarativeBase):
    """모든 ORM 모델의 베이스. `Base.metadata` 가 Alembic autogenerate 의 기준이다."""


# 표준 콘텐츠의 출처 (system_vocabularies.source, system_words.source). 관리자 등록분만 수정·삭제할 수 있다 (REQ-160, 161).
SOURCE_SEED = "seed"
SOURCE_ADMIN = "admin"
