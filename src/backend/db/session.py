# 2026-11-02 - voda-voca - 비동기 DB 엔진, 세션 팩토리, FastAPI 세션 의존성 제공
# 파일 위치: src/backend/db/session.py

from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.core.config import get_settings


@lru_cache
def get_engine() -> AsyncEngine:
    """비동기 엔진을 생성한다 (프로세스당 1개).

    - pool_pre_ping=True: 체크아웃 전에 연결 상태를 확인해, MySQL의 wait_timeout 으로 끊긴
      커넥션을 요청 중에 만나 실패하는 일을 줄인다.
    - echo=False: SQL 로그는 기본적으로 끈다. 디버깅 시 필요하면 일시적으로 켠다.
    """
    return create_async_engine(
        get_settings().database_url,
        echo=False,
        pool_pre_ping=True,
    )


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
