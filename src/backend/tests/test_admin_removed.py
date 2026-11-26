# 2026-11-26 - voda-voca - 관리자 제거 회귀 검사: 관리 API·관리자 계정·초기 비밀번호가 다시 생기지 않는지 확인 (#41)
# 파일 위치: src/backend/tests/test_admin_removed.py

import re
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import delete, func, select

from backend.db.session import get_session_factory
from backend.main import app, lifespan
from backend.models import User
from backend.tests.helpers import auth_headers, signup_and_login

SRC_DIR = Path(__file__).resolve().parents[2]


@pytest_asyncio.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture(autouse=True)
async def _no_admin_account() -> AsyncIterator[None]:
    async def clean() -> None:
        async with get_session_factory()() as db:
            await db.execute(delete(User).where(User.nickname == "admin"))
            await db.commit()

    await clean()
    yield
    await clean()


def test_there_is_no_admin_api() -> None:
    assert [path for path in app.openapi()["paths"] if "admin" in path] == []


@pytest.mark.asyncio
async def test_startup_creates_no_account() -> None:
    async with lifespan(app):
        pass
    async with get_session_factory()() as db:
        assert await db.scalar(select(func.count()).select_from(User).where(User.nickname == "admin")) == 0


@pytest.mark.asyncio
async def test_the_nickname_admin_is_an_ordinary_one(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client, "admin")

    me = (await client.get("/api/auth/me", headers=auth_headers(token))).json()
    deleted = await client.delete("/api/auth/me", headers=auth_headers(token))

    assert "is_admin" not in me
    assert deleted.status_code == 204, deleted.text


def test_no_initial_password_is_left_in_the_code() -> None:
    """비밀값을 코드에 두지 않는다 (VOCA-NFR-004)."""
    files = [
        path
        for pattern in ("backend/**/*.py", "frontend/js/**/*.js", "frontend/*.html")
        for path in SRC_DIR.glob(pattern)
        if "tests" not in path.parts
    ]
    assert len(files) > 40
    hits = [str(p) for p in files if re.search(r"admin1234|ADMIN_INITIAL_PASSWORD", p.read_text(encoding="utf-8"))]
    assert hits == []
