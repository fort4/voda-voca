# 2026-11-02 - voda-voca - 비동기 DB 엔진(SQLite), 세션 팩토리, FastAPI 세션 의존성 제공 (2026-11-25 SQLite 전환)
# 파일 위치: src/backend/db/session.py

from collections.abc import AsyncIterator
from functools import lru_cache
from pathlib import Path

from sqlalchemy import event

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.core.config import get_settings


# 쓰기 충돌 시 즉시 실패하지 않고 기다리는 시간(ms). SQLite 는 쓰기를 한 번에 하나만 허용한다.
BUSY_TIMEOUT_MS = 5000


def _apply_sqlite_pragmas(dbapi_connection, _record) -> None:  # noqa: ANN001
    """연결이 만들어질 때마다 SQLite 동작 설정을 건다 (PRAGMA 는 연결 단위 설정이다).

    - foreign_keys=ON: 기본은 꺼져 있어 ON DELETE CASCADE 가 동작하지 않는다.
    - journal_mode=WAL: 읽기가 쓰기를 막지 않는다. 동시 요청이 있는 웹 서버에 알맞다.
    - synchronous=NORMAL: WAL 에서 안전하면서 쓰기가 빠르다.
    - busy_timeout: 잠금 충돌 시 대기한다.
    """
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
    finally:
        cursor.close()


def _disable_driver_autobegin(dbapi_connection, _record) -> None:  # noqa: ANN001
    """드라이버가 멋대로 BEGIN 하지 않게 한다. 트랜잭션 시작은 아래 _begin_immediate 가 정한다."""
    dbapi_connection.isolation_level = None


def _begin_immediate(connection) -> None:  # noqa: ANN001
    """모든 트랜잭션을 BEGIN IMMEDIATE 로 시작해 쓰기 잠금을 처음에 잡는다.

    MySQL 의 SELECT ... FOR UPDATE(행 잠금)를 대신한다. 기본(DEFERRED)은 읽기로 시작한 트랜잭션이 나중에 쓰기로
    올라갈 때, 그 사이 다른 연결이 커밋했다면 busy_timeout 과 무관하게 즉시 SQLITE_BUSY 로 실패한다. 요청마다
    인증이 먼저 읽기 때문에 실제로 일어난다. IMMEDIATE 는 시작 시점에 busy_timeout 만큼 기다려 순서대로 진행한다.
    대가: 읽기 요청도 쓰기 잠금을 잠깐 잡는다. 단일 컨테이너의 소규모 서비스에서는 허용 가능하다 (ADR-010).
    """
    connection.exec_driver_sql("BEGIN IMMEDIATE")


@lru_cache
def get_engine() -> AsyncEngine:
    """비동기 엔진을 생성한다 (프로세스당 1개).

    - DB 파일의 상위 디렉터리가 없으면 만든다. 빈 DB 로 처음 실행할 수 있어야 한다 (VOCA-NFR-003).
    - 서버가 없는 파일 DB 라 pool_pre_ping(끊긴 커넥션 확인)은 필요 없다.
    - echo=False: SQL 로그는 기본적으로 끈다. 디버깅 시 필요하면 일시적으로 켠다.
    """
    settings = get_settings()
    try:
        Path(settings.db_path).expanduser().parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass  # 만들 수 없으면 첫 연결에서 SQLAlchemyError 로 드러난다 (/health 가 503 으로 응답하도록 여기서는 예외를 내지 않는다)
    engine = create_async_engine(settings.database_url, echo=False)
    event.listen(engine.sync_engine, "connect", _apply_sqlite_pragmas)
    event.listen(engine.sync_engine, "connect", _disable_driver_autobegin)
    event.listen(engine.sync_engine, "begin", _begin_immediate)
    return engine


@lru_cache
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """세션 팩토리. expire_on_commit=False 로 커밋 후에도 객체 속성을 읽을 수 있게 한다.

    비동기 세션에서는 커밋 후 지연 로딩이 막혀 있으므로, 응답 직렬화 중 예외를 피하려고 끈다.
    """
    return async_sessionmaker(get_engine(), expire_on_commit=False)


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """FastAPI 의존성 주입용 세션 제너레이터.

    요청마다 새 세션을 열고, 요청이 끝나면 닫는다 (커넥션은 풀에 반납된다).
    사용 예: `session: AsyncSession = Depends(get_db_session)`

    예외 처리 순서를 고정한다.
    - 요청 처리 중 예외가 나면 `rollback()`을 await 하여 미완료 트랜잭션을 먼저 되돌린다.
    - 그 뒤 `finally`에서 `close()`로 세션을 닫아 커넥션을 풀에 반납한다.
    - `rollback()`이 실패하면 그 예외가 전파되고, 원래 예외는 `__context__`에 남는다.
      `finally`의 `close()`는 rollback 실패와 무관하게 항상 호출된다.
    """
    session = get_session_factory()()
    try:
        yield session
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def dispose_engine() -> None:
    """앱 종료 시 커넥션 풀을 정리한다. 엔진을 만든 적이 없으면 아무 일도 하지 않는다."""
    if get_engine.cache_info().currsize:
        await get_engine().dispose()
        get_engine.cache_clear()
        get_session_factory.cache_clear()
