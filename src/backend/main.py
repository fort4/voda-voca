# 2026-11-02 - voda-voca - FastAPI 애플리케이션 진입점 및 DB 연결 헬스체크
# 파일 위치: src/backend/main.py

import mimetypes
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import Depends, FastAPI, Response
from fastapi.staticfiles import StaticFiles
from starlette.types import Scope
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import dispose_engine, get_db_session
from backend.routers.auth import router as auth_router
from backend.routers.bookmark import router as bookmark_router
from backend.routers.study import router as study_router
from backend.routers.study_session import router as study_session_router
from backend.routers.user_settings import router as user_settings_router
from backend.routers.vocabulary import me_router as me_vocabulary_router
from backend.routers.vocabulary import router as vocabulary_router
from backend.services.admin import init_admin_account
from backend.services.system_seed import init_system_seeds


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """앱 시작 시 표준 단어장 시드를 적재하고 관리자 계정을 준비하며(둘 다 멱등), 종료 시 DB 커넥션 풀을 정리한다."""
    await init_system_seeds()
    await init_admin_account()  # 기본 학습 단어장을 지정하므로 시드 다음에 한다
    yield
    await dispose_engine()


app = FastAPI(title="voda-voca", lifespan=lifespan)
app.include_router(auth_router)
app.include_router(bookmark_router)
app.include_router(study_router)
app.include_router(study_session_router)
app.include_router(vocabulary_router)
app.include_router(me_vocabulary_router)
app.include_router(user_settings_router)


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


# vendor/ 는 폴더·파일명에 버전이 들어 있어(tailwindcss-3.4.17.js, sweetalert2-11.10.5/) 내용이 바뀌면 경로도 바뀐다.
# 그래서 브라우저가 1년간 서버에 묻지 않고 저장해 두어도 안전하다 (2026-11-25). app.js·app.css 는 이름에 버전이 없고
# 자주 고치므로 긴 캐시를 주지 않는다(ETag 로 매번 확인).
VENDOR_CACHE_CONTROL = "public, max-age=31536000, immutable"


class FrontendStaticFiles(StaticFiles):
    """정적 프론트엔드 서빙. vendor/ 아래 파일에만 긴 캐시 헤더를 붙인다."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        response = await super().get_response(path, scope)
        if path.startswith("vendor/") and response.status_code in (200, 304):
            response.headers["Cache-Control"] = VENDOR_CACHE_CONTROL
        return response


# woff2 의 MIME 타입을 직접 등록한다 (2026-11-25). 파이썬은 OS 의 mime.types 를 읽는데 slim 컨테이너에는 그 파일이 없어
# 호스트에서는 font/woff2, 컨테이너에서는 application/octet-stream 으로 달라진다. 환경과 무관하게 같게 맞춘다.
mimetypes.add_type("font/woff2", ".woff2")

# 정적 프론트엔드 (같은 출처 배포, 2026-11-02). 모든 API 라우트를 등록한 뒤 마지막에 붙인다.
# 라우트가 먼저 매칭되므로 /api, /health 는 정적 파일 마운트에 가려지지 않는다.
FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"
app.mount("/", FrontendStaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
