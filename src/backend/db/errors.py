# 2026-11-25 - voda-voca - SQLite 무결성 오류 판별: 어떤 제약을 어겼는지 오류 메시지에서 읽는다 (ADR-010)
# 파일 위치: src/backend/db/errors.py
"""MySQL 은 오류 메시지에 제약 이름(uk_users_nickname 등)을 실어 주었지만, SQLite 는 다르다.

- 유니크 위반: `UNIQUE constraint failed: users.nickname` (테이블.컬럼 목록, 제약 이름 없음)
- 외래키 위반: `FOREIGN KEY constraint failed` (어느 외래키인지 알려 주지 않음)

그래서 유니크는 테이블·컬럼으로 판별하고, 외래키는 호출하는 쪽이 "그 쓰기에서 걸릴 수 있는 외래키가 하나뿐"임을 알 때만 쓴다.
"""

from sqlalchemy.exc import IntegrityError

_UNIQUE_PREFIX = "UNIQUE constraint failed:"
_FOREIGN_KEY_MESSAGE = "FOREIGN KEY constraint failed"


def is_unique_violation(exc: IntegrityError, table: str, *columns: str) -> bool:
    """`table` 의 `columns` 조합에 대한 유니크 위반인지 확인한다 (컬럼 순서는 무관, 일부만 겹치면 아니다)."""
    message = str(exc.orig)
    if not message.startswith(_UNIQUE_PREFIX):
        return False
    failed = {part.strip() for part in message[len(_UNIQUE_PREFIX):].split(",")}
    return failed == {f"{table}.{column}" for column in columns}


def is_foreign_key_violation(exc: IntegrityError) -> bool:
    """외래키 위반인지 확인한다. 어느 외래키인지는 SQLite 가 알려 주지 않는다."""
    return _FOREIGN_KEY_MESSAGE in str(exc.orig)
