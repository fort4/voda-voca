# 2026-11-05 - voda-voca - 학습 이력 API 통합 테스트 (실제 MySQL): 최신순·limit·사용자 분리·로그인 필요 (REQ-016)
# 파일 위치: src/backend/tests/test_study_logs_api.py

from collections.abc import AsyncIterator
from datetime import timedelta

import httpx
import pytest
import pytest_asyncio

from backend.db.session import get_session_factory
from backend.main import app
from backend.models import StudyLog
from backend.models.base import utcnow
from backend.tests.helpers import auth_headers, make_vocab, make_words, signup_and_login, user_id_for_token


@pytest_asyncio.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def seed_logs(user_id: int, word_ids: list[int]) -> None:
    """word_ids 순서대로 1초 간격의 정답 이력을 직접 심는다 (출제 API 를 거치지 않는다)."""
    start = utcnow() - timedelta(minutes=10)
    async with get_session_factory()() as db:
        for i, word_id in enumerate(word_ids):
            db.add(StudyLog(user_id=user_id, word_id=word_id, is_correct=True, created_at=start + timedelta(seconds=i)))
        await db.commit()


@pytest.mark.asyncio
async def test_logs_are_newest_first_and_limited(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    wb = await make_vocab(client, token)
    words = list(await make_words(client, token, wb, 4))
    await seed_logs(await user_id_for_token(client, token), words + words)

    response = await client.get("/api/study/logs", params={"limit": 5}, headers=auth_headers(token))

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 5  # 전체 8건 중 limit 5
    stamps = [item["created_at"] for item in items]
    assert stamps == sorted(stamps, reverse=True)
    assert all(item["created_at"].endswith("Z") for item in items)
    assert all(item["is_correct"] is True for item in items)
    assert all(item["vocabulary_id"] == wb for item in items)  # 진행률 계산이 단어장을 알아야 한다


@pytest.mark.asyncio
async def test_logs_are_scoped_to_the_requesting_user(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    _, other = await signup_and_login(client)
    wb = await make_vocab(client, token)
    words = list(await make_words(client, token, wb, 4))
    await seed_logs(await user_id_for_token(client, token), words)

    response = await client.get("/api/study/logs", headers=auth_headers(other))

    assert response.status_code == 200
    assert response.json()["items"] == []


@pytest.mark.asyncio
async def test_logs_require_login(client: httpx.AsyncClient) -> None:
    assert (await client.get("/api/study/logs")).status_code == 401
