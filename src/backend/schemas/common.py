# 2026-11-02 - voda-voca - 스키마 공용 헬퍼 (UTC 시각 직렬화, REQ-109)
# 파일 위치: src/backend/schemas/common.py

from datetime import UTC, datetime


def to_utc_iso(value: datetime) -> str:
    """DB 에서 읽은 시각을 'Z' 가 붙은 ISO 8601 문자열로 바꾼다.

    DATETIME 값은 tzinfo 가 없지만 저장 기준은 UTC 이다. 클라이언트가 KST 로 변환하도록 'Z' 를 명시한다.
    """
    aware = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    return aware.isoformat().replace("+00:00", "Z")
