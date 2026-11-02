# 2026-11-02 - voda-voca - 테스트 공통 fixture: 엔진 정리, 빠른 bcrypt, 테스트 계정 정리
# 파일 위치: src/backend/tests/conftest.py

from collections.abc import AsyncIterator, Iterator

import pytest
import pytest_asyncio
from sqlalchemy import delete

from backend.core.config import get_settings
from backend.core.rate_limit import login_rate_limiter
from backend.db.session import dispose_engine, get_session_factory
from backend.models import User

# 테스트 계정 닉네임 패턴. 정리(cleanup) 시 이 패턴만 지운다.
TEST_NICKNAME_LIKE = "tvoda-%"


@pytest_asyncio.fixture(autouse=True)
async def _dispose_db_engine() -> AsyncIterator[None]:
    """각 테스트가 끝나면 엔진을 닫는다.

    pytest-asyncio 는 테스트마다 이벤트 루프를 새로 만든다. 풀에 남은 커넥션은 이전 루프에
    묶여 있으므로, 테스트 사이에 정리하지 않으면 다음 테스트에서 루프 불일치 오류가 난다.
    """
    yield
    await dispose_engine()


@pytest.fixture(autouse=True)
def _reset_login_rate_limiter() -> Iterator[None]:
    """로그인 실패 집계는 프로세스 전역이다. 테스트마다 비워 서로의 실패가 섞이지 않게 한다."""
    login_rate_limiter.clear()
    yield
    login_rate_limiter.clear()


@pytest.fixture(autouse=True)
def _fast_bcrypt(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """테스트에서는 bcrypt cost 를 4 로 낮춰 실행 시간을 줄인다. 운영 기본값은 12 이다."""
    monkeypatch.setenv("BCRYPT_ROUNDS", "4")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest_asyncio.fixture(autouse=True)
async def _cleanup_test_users() -> AsyncIterator[None]:
    """테스트 계정(과 그 세션, FK CASCADE)을 테스트 전후로 지운다."""
    await _delete_test_users()
    yield
    await _delete_test_users()
    await dispose_engine()


async def _delete_test_users() -> None:
    async with get_session_factory()() as session:
        await session.execute(delete(User).where(User.nickname.like(TEST_NICKNAME_LIKE)))
        await session.commit()
