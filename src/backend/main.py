# 2026-11-02 - voda-voca - FastAPI 애플리케이션 진입점 및 DB 연결 헬스체크
# 파일 위치: src/backend/main.py

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Response
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import dispose_engine, get_db_session
from backend.routers.auth import router as auth_router


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """앱 종료 시 DB 커넥션 풀을 정리한다."""
    yield
    await dispose_engine()


app = FastAPI(title="voda-voca", lifespan=lifespan)
app.include_router(auth_router)


@app.get("/health")
async def health(
    response: Response,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    """프로세스와 DB 연결 상태를 확인한다.

    - DB 응답 성공: 200 {"status": "ok", "db": "connected"}
    - DB 응답 실패: 503 {"status": "error", "db": "disconnected"}
    """
    try:
        await session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        response.status_code = 503
        return {"status": "error", "db": "disconnected"}
    return {"status": "ok", "db": "connected"}
