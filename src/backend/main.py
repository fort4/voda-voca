# 2026-11-02 - voda-voca - FastAPI 애플리케이션 진입점 및 DB 연결 헬스체크
# 파일 위치: src/backend/main.py

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import Depends, FastAPI, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import dispose_engine, get_db_session
from backend.routers.auth import router as auth_router
from backend.routers.bookmark import router as bookmark_router
from backend.routers.study import router as study_router
from backend.services.system_seed import init_system_seeds


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """앱 시작 시 표준 단어장 시드를 적재하고(멱등), 종료 시 DB 커넥션 풀을 정리한다."""
    await init_system_seeds()
    yield
    await dispose_engine()


app = FastAPI(title="voda-voca", lifespan=lifespan)
app.include_router(auth_router)
app.include_router(bookmark_router)
app.include_router(study_router)


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


# 정적 프론트엔드 (같은 출처 배포, 2026-11-02). 모든 API 라우트를 등록한 뒤 마지막에 붙인다.
# 라우트가 먼저 매칭되므로 /api, /health 는 정적 파일 마운트에 가려지지 않는다.
FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
