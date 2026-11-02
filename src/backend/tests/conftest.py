# 2026-11-02 - voda-voca - 테스트 공통 fixture: 테스트마다 DB 커넥션 풀 정리
# 파일 위치: src/backend/tests/conftest.py

from collections.abc import AsyncIterator

import pytest_asyncio

from backend.db.session import dispose_engine


@pytest_asyncio.fixture(autouse=True)
async def _dispose_db_engine() -> AsyncIterator[None]:
    """각 테스트가 끝나면 엔진을 닫는다.

    pytest-asyncio 는 테스트마다 이벤트 루프를 새로 만든다. 풀에 남은 커넥션은 이전 루프에
    묶여 있으므로, 테스트 사이에 정리하지 않으면 다음 테스트에서 루프 불일치 오류가 난다.
    """
    yield
    await dispose_engine()
