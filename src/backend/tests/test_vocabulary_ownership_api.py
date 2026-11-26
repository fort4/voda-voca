# 2026-11-26 - voda-voca - 개인 단어장 접근 통제 통합 테스트: 남의 단어장은 어디에서도 보이거나 쓰이지 않는다 (#38, REQ-169)
# 파일 위치: src/backend/tests/test_vocabulary_ownership_api.py

from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import func, select, update

from backend.db.session import get_session_factory
from backend.main import app
from backend.models import Bookmark, SystemVocabulary, SystemWord, User
from backend.tests.helpers import TestVocabulary, auth_headers, signup_and_login, user_id_for_token


@pytest_asyncio.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@dataclass
class Scene:
    owner: str
    owner_id: int
    other: str
    other_id: int
    mine: TestVocabulary  # owner 의 개인 단어장


@pytest_asyncio.fixture
async def scene(client: httpx.AsyncClient, make_vocabulary) -> Scene:
    _, owner = await signup_and_login(client)
    _, other = await signup_and_login(client)
    owner_id = await user_id_for_token(client, owner)
    mine = await make_vocabulary([f"own{i}" for i in range(6)], title="내 단어장", owner_id=owner_id)
    return Scene(owner, owner_id, other, await user_id_for_token(client, other), mine)


async def get(client, token: str, url: str) -> httpx.Response:
    return await client.get(url, headers=auth_headers(token))


async def activate(client, token: str, vocabulary_id: int) -> httpx.Response:
    return await client.post(
        "/api/users/me/active-vocabulary", json={"vocabulary_id": vocabulary_id}, headers=auth_headers(token)
    )


async def catalogue(client, token: str) -> dict[int, dict]:
    return {v["id"]: v for v in (await get(client, token, "/api/vocabularies")).json()}


@pytest.mark.asyncio
async def test_the_owner_sees_the_vocabulary_marked_as_mine(client, scene: Scene) -> None:
    listed = await catalogue(client, scene.owner)

    assert listed[scene.mine.id]["is_mine"] is True
    assert [v["is_mine"] for i, v in listed.items() if i != scene.mine.id] == [False] * (len(listed) - 1)


@pytest.mark.asyncio
async def test_another_user_does_not_see_it_in_the_catalogue(client, scene: Scene) -> None:
    assert scene.mine.id not in await catalogue(client, scene.other)
    filtered = await get(client, scene.other, "/api/vocabularies?category=ELEMENTARY")
    assert scene.mine.id not in [v["id"] for v in filtered.json()]


@pytest.mark.asyncio
@pytest.mark.parametrize("query", ["", "?q=own"])
async def test_another_user_cannot_read_or_search_the_words(client, scene: Scene, query: str) -> None:
    url = f"/api/vocabularies/{scene.mine.id}/words{query}"

    assert (await get(client, scene.owner, url)).json()["total"] == 6
    hidden = await get(client, scene.other, url)
    missing = await get(client, scene.other, f"/api/vocabularies/999999/words{query}")
    assert (hidden.status_code, hidden.json()) == (404, missing.json()), "없는 단어장과 구별되지 않는다"


@pytest.mark.asyncio
async def test_another_user_cannot_choose_it_for_study(client, scene: Scene) -> None:
    assert (await activate(client, scene.other, scene.mine.id)).status_code == 404
    assert (await activate(client, scene.owner, scene.mine.id)).status_code == 200


@pytest.mark.asyncio
async def test_another_user_cannot_bookmark_its_words(client, scene: Scene) -> None:
    word_id = scene.mine.word_ids["own0"]

    denied = await client.put(f"/api/bookmarks/{word_id}", headers=auth_headers(scene.other))
    allowed = await client.put(f"/api/bookmarks/{word_id}", headers=auth_headers(scene.owner))

    assert denied.status_code == 404 and allowed.status_code < 300
    async with get_session_factory()() as db:
        owners = (await db.execute(select(Bookmark.user_id).where(Bookmark.word_id == word_id))).scalars().all()
    assert owners == [scene.owner_id]


@pytest.mark.asyncio
async def test_statistics_count_only_visible_vocabularies(client, scene: Scene) -> None:
    mine = (await get(client, scene.owner, "/api/study/stats")).json()
    theirs = (await get(client, scene.other, "/api/study/stats")).json()

    assert scene.mine.id in [p["vocabulary_id"] for p in mine["vocabulary_progress"]]
    assert scene.mine.id not in [p["vocabulary_id"] for p in theirs["vocabulary_progress"]]
    assert mine["total_words"] == theirs["total_words"] + 6


@pytest.mark.asyncio
async def test_the_default_study_vocabulary_is_a_standard_one(client, scene: Scene) -> None:
    """누군가의 개인 단어장이 목록 맨 앞에 있어도 다른 사람의 기본 단어장이 되지 않는다."""
    async with get_session_factory()() as db:
        await db.execute(update(SystemVocabulary).where(SystemVocabulary.id == scene.mine.id).values(sort_order=-1))
        await db.execute(update(User).where(User.id == scene.other_id).values(active_vocabulary_id=None))
        await db.commit()

    session = await client.post("/api/study/sessions", json={}, headers=auth_headers(scene.other))

    assert session.status_code == 201, session.text
    assert session.json()["vocabulary_id"] != scene.mine.id


@pytest.mark.asyncio
async def test_a_stale_choice_of_someone_elses_vocabulary_is_ignored(client, scene: Scene) -> None:
    async with get_session_factory()() as db:
        await db.execute(update(User).where(User.id == scene.other_id).values(active_vocabulary_id=scene.mine.id))
        await db.commit()

    stats = (await get(client, scene.other, "/api/study/stats")).json()
    session = await client.post("/api/study/sessions", json={}, headers=auth_headers(scene.other))

    assert stats["day_progress"] is None
    assert session.json()["vocabulary_id"] != scene.mine.id


@pytest.mark.asyncio
async def test_the_owner_can_study_it(client, scene: Scene) -> None:
    await activate(client, scene.owner, scene.mine.id)

    session = await client.post("/api/study/sessions", json={}, headers=auth_headers(scene.owner))

    body = session.json()
    assert (body["vocabulary_id"], body["total_questions"]) == (scene.mine.id, 6)


@pytest.mark.asyncio
async def test_deleting_the_account_removes_the_personal_vocabulary(client, scene: Scene) -> None:
    deleted = await client.delete("/api/auth/me", headers=auth_headers(scene.owner))

    assert deleted.status_code == 204, deleted.text
    async with get_session_factory()() as db:
        assert await db.get(SystemVocabulary, scene.mine.id) is None
        left = await db.scalar(select(func.count()).select_from(SystemWord).where(SystemWord.vocabulary_id == scene.mine.id))
    assert left == 0
