# 2026-11-02 - voda-voca - get_db_session 예외 시 rollback→close 순서 보장 단위 테스트
# 파일 위치: src/backend/tests/test_db_session.py

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.db import session as session_module


def _fake_session() -> MagicMock:
    fake = MagicMock()
    fake.rollback = AsyncMock()
    fake.close = AsyncMock()
    return fake


@pytest.fixture
def fake_session(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """팩토리 호출 시 같은 가짜 세션을 돌려준다. DB 연결 없이 호출 순서만 검증한다."""
    fake = _fake_session()
    monkeypatch.setattr(session_module, "get_session_factory", lambda: lambda: fake)
    return fake


@pytest.mark.asyncio
async def test_normal_exit_closes_without_rollback(fake_session: MagicMock) -> None:
    gen = session_module.get_db_session()
    yielded = await gen.__anext__()
    assert yielded is fake_session

    with pytest.raises(StopAsyncIteration):
        await gen.__anext__()

    fake_session.rollback.assert_not_awaited()
    fake_session.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_exception_rolls_back_then_closes_and_propagates(fake_session: MagicMock) -> None:
    gen = session_module.get_db_session()
    await gen.__anext__()

    with pytest.raises(ValueError, match="boom"):
        await gen.athrow(ValueError("boom"))

    fake_session.rollback.assert_awaited_once()
    fake_session.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_rollback_happens_before_close(fake_session: MagicMock) -> None:
    order: list[str] = []
    fake_session.rollback.side_effect = lambda: order.append("rollback")
    fake_session.close.side_effect = lambda: order.append("close")

    gen = session_module.get_db_session()
    await gen.__anext__()
    with pytest.raises(RuntimeError):
        await gen.athrow(RuntimeError("fail"))

    assert order == ["rollback", "close"]


@pytest.mark.asyncio
async def test_close_still_runs_when_rollback_fails(fake_session: MagicMock) -> None:
    fake_session.rollback.side_effect = OSError("connection lost")

    gen = session_module.get_db_session()
    await gen.__anext__()
    with pytest.raises(OSError, match="connection lost"):
        await gen.athrow(ValueError("original"))

    fake_session.close.assert_awaited_once()
