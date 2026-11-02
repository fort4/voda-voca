# 2026-11-02 - voda-voca - 단어장 API 통합 테스트 (실제 MySQL): CRUD, 페이징 경계, 소유권 404 격리, CASCADE
# 파일 위치: src/backend/tests/test_wordbook_api.py

import asyncio
from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import func, select

from backend.db.session import get_session_factory
from backend.main import app
from backend.models import Bookmark, StudyLog, User, Word, Wordbook
from backend.tests.helpers import DEFAULT_WORDBOOK_COUNT, DEFAULT_WORDBOOK_NAMES, auth_headers, signup_and_login


@pytest_asyncio.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def create(client: httpx.AsyncClient, token: str, name: str, description: str | None = None) -> dict:
    response = await client.post(
        "/api/wordbooks",
        json={"name": name, "description": description},
        headers=auth_headers(token),
    )
    assert response.status_code == 201, response.text
    return response.json()


# --- 생성 (REQ-004) ---


@pytest.mark.asyncio
async def test_create_returns_201_with_utc_timestamps(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    body = await create(client, token, "  토익  ", "  기출 단어  ")
    assert set(body) == {"id", "name", "description", "word_count", "created_at", "updated_at"}
    assert body["word_count"] == 0, "새 단어장은 단어가 없다"
    assert body["name"] == "토익"
    assert body["description"] == "기출 단어"
    assert body["created_at"].endswith("Z")
    assert body["updated_at"].endswith("Z")


@pytest.mark.asyncio
async def test_create_without_description_stores_null(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    body = await create(client, token, "메모 없음")
    assert body["description"] is None


@pytest.mark.asyncio
async def test_create_duplicate_name_is_409_case_insensitive(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    await create(client, token, "Vocab")
    response = await client.post(
        "/api/wordbooks", json={"name": "vocab"}, headers=auth_headers(token)
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "이미 같은 이름의 단어장이 있습니다."


@pytest.mark.asyncio
async def test_same_name_is_allowed_for_different_users(client: httpx.AsyncClient) -> None:
    _, token_a = await signup_and_login(client)
    _, token_b = await signup_and_login(client)
    await create(client, token_a, "공용 이름")
    await create(client, token_b, "공용 이름")


@pytest.mark.asyncio
async def test_create_blank_name_is_422(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    response = await client.post("/api/wordbooks", json={"name": "   "}, headers=auth_headers(token))
    assert response.status_code == 422


# --- 목록 및 페이징 (REQ-005, REQ-103) ---


@pytest.mark.asyncio
async def test_list_is_ordered_by_most_recently_updated(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    first = await create(client, token, "첫째")
    await asyncio.sleep(0.01)
    await create(client, token, "둘째")
    await asyncio.sleep(0.01)
    await create(client, token, "셋째")

    names = [i["name"] for i in (await client.get("/api/wordbooks", headers=auth_headers(token))).json()["items"]]
    assert names[:3] == ["셋째", "둘째", "첫째"]
    assert set(names[3:]) == set(DEFAULT_WORDBOOK_NAMES), "기본 단어장은 가입 시각 기준으로 뒤에 온다"

    await asyncio.sleep(0.01)
    rename = await client.patch(
        f"/api/wordbooks/{first['id']}", json={"name": "첫째-수정"}, headers=auth_headers(token)
    )
    assert rename.status_code == 200
    names = [i["name"] for i in (await client.get("/api/wordbooks", headers=auth_headers(token))).json()["items"]]
    assert names[:3] == ["첫째-수정", "셋째", "둘째"]


@pytest.mark.asyncio
async def test_list_default_page_size_is_20(client: httpx.AsyncClient) -> None:
    """가입 직후에는 기본 단어장 3종만 있다. 기본 페이지 크기는 20이다."""
    _, token = await signup_and_login(client)
    body = (await client.get("/api/wordbooks", headers=auth_headers(token))).json()
    assert body["total"] == DEFAULT_WORDBOOK_COUNT
    assert body["page"] == 1 and body["size"] == 20
    assert {i["name"] for i in body["items"]} == set(DEFAULT_WORDBOOK_NAMES)


@pytest.mark.asyncio
async def test_list_pagination_boundaries(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    for i in range(3):
        await create(client, token, f"단어장-{i}")

    def get(params: dict) -> httpx.Response:
        return client.get("/api/wordbooks", params=params, headers=auth_headers(token))

    total = 3 + DEFAULT_WORDBOOK_COUNT
    page1 = (await get({"page": 1, "size": 2})).json()
    assert len(page1["items"]) == 2 and page1["total"] == total

    page3 = (await get({"page": 3, "size": 2})).json()
    assert len(page3["items"]) == 2 and page3["total"] == total

    beyond = (await get({"page": 4, "size": 2})).json()
    assert beyond["items"] == [] and beyond["total"] == total

    everything = (await get({"page": 1, "size": 100})).json()
    assert len(everything["items"]) == total


@pytest.mark.asyncio
@pytest.mark.parametrize("params", [{"size": 0}, {"size": 101}, {"page": 0}, {"size": -1}])
async def test_list_rejects_out_of_range_paging(client: httpx.AsyncClient, params: dict) -> None:
    _, token = await signup_and_login(client)
    response = await client.get("/api/wordbooks", params=params, headers=auth_headers(token))
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_shows_only_own_wordbooks(client: httpx.AsyncClient) -> None:
    _, token_a = await signup_and_login(client)
    _, token_b = await signup_and_login(client)
    await create(client, token_a, "A의 단어장")
    await create(client, token_b, "B의 단어장")
    items = (await client.get("/api/wordbooks", headers=auth_headers(token_a))).json()["items"]
    names = {i["name"] for i in items}
    assert "A의 단어장" in names and "B의 단어장" not in names
    assert names == {"A의 단어장", *DEFAULT_WORDBOOK_NAMES}


# --- 상세, 수정, 삭제 및 소유권 격리 (REQ-003, REQ-006, REQ-007) ---


@pytest.mark.asyncio
async def test_get_own_wordbook(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    created = await create(client, token, "내 단어장")
    response = await client.get(f"/api/wordbooks/{created['id']}", headers=auth_headers(token))
    assert response.status_code == 200
    assert response.json()["name"] == "내 단어장"


@pytest.mark.asyncio
async def test_partial_update_changes_only_sent_fields(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    created = await create(client, token, "원래 이름", "원래 설명")
    response = await client.patch(
        f"/api/wordbooks/{created['id']}", json={"description": "새 설명"}, headers=auth_headers(token)
    )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "원래 이름"
    assert body["description"] == "새 설명"


@pytest.mark.asyncio
async def test_patch_description_to_null_clears_it(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    created = await create(client, token, "지울 설명", "설명")
    response = await client.patch(
        f"/api/wordbooks/{created['id']}", json={"description": None}, headers=auth_headers(token)
    )
    assert response.json()["description"] is None


@pytest.mark.asyncio
async def test_patch_name_to_null_is_422(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    created = await create(client, token, "이름")
    response = await client.patch(
        f"/api/wordbooks/{created['id']}", json={"name": None}, headers=auth_headers(token)
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_patch_without_changes_keeps_updated_at(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    created = await create(client, token, "변경 없음", "설명")
    response = await client.patch(
        f"/api/wordbooks/{created['id']}",
        json={"name": "변경 없음", "description": "설명"},
        headers=auth_headers(token),
    )
    assert response.status_code == 200
    assert response.json()["updated_at"] == created["updated_at"]


@pytest.mark.asyncio
async def test_patch_to_taken_name_is_409(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    await create(client, token, "기존")
    other = await create(client, token, "다른 것")
    response = await client.patch(
        f"/api/wordbooks/{other['id']}", json={"name": "기존"}, headers=auth_headers(token)
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_delete_own_wordbook_returns_204_and_removes_it(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    created = await create(client, token, "삭제 대상")
    response = await client.delete(f"/api/wordbooks/{created['id']}", headers=auth_headers(token))
    assert response.status_code == 204
    after = await client.get(f"/api/wordbooks/{created['id']}", headers=auth_headers(token))
    assert after.status_code == 404


@pytest.mark.asyncio
async def test_other_users_wordbook_is_404_for_get_patch_delete(client: httpx.AsyncClient) -> None:
    _, owner = await signup_and_login(client)
    _, intruder = await signup_and_login(client)
    secret = await create(client, owner, "비밀 단어장", "설명")
    url = f"/api/wordbooks/{secret['id']}"

    get_resp = await client.get(url, headers=auth_headers(intruder))
    patch_resp = await client.patch(url, json={"name": "탈취"}, headers=auth_headers(intruder))
    delete_resp = await client.delete(url, headers=auth_headers(intruder))

    assert get_resp.status_code == patch_resp.status_code == delete_resp.status_code == 404

    # 타인의 요청으로 데이터가 바뀌거나 지워지지 않았는지 소유자 기준으로 확인한다.
    still = (await client.get(url, headers=auth_headers(owner))).json()
    assert still["name"] == "비밀 단어장"
    assert still["description"] == "설명"


@pytest.mark.asyncio
async def test_other_users_missing_and_foreign_ids_give_identical_404(client: httpx.AsyncClient) -> None:
    """ID 열거 차단: 타인 소유 ID 와 존재하지 않는 ID 의 응답이 같아야 한다."""
    _, owner = await signup_and_login(client)
    _, intruder = await signup_and_login(client)
    foreign = await create(client, owner, "남의 것")

    foreign_resp = await client.get(f"/api/wordbooks/{foreign['id']}", headers=auth_headers(intruder))
    missing_resp = await client.get("/api/wordbooks/999999999", headers=auth_headers(intruder))

    assert foreign_resp.status_code == missing_resp.status_code == 404
    assert foreign_resp.json() == missing_resp.json()


@pytest.mark.asyncio
async def test_unauthenticated_requests_are_401(client: httpx.AsyncClient) -> None:
    assert (await client.get("/api/wordbooks")).status_code == 401
    assert (await client.post("/api/wordbooks", json={"name": "x"})).status_code == 401
    assert (await client.get("/api/wordbooks/1")).status_code == 401


# --- CASCADE 삭제 (REQ-007, REQ-104) ---


@pytest.mark.asyncio
async def test_delete_cascades_words_bookmarks_and_study_logs(client: httpx.AsyncClient) -> None:
    nickname, token = await signup_and_login(client)
    created = await create(client, token, "연쇄 삭제 대상")
    wordbook_id = created["id"]

    async with get_session_factory()() as session:
        user_id = (await session.execute(select(User.id).where(User.nickname == nickname))).scalar_one()
        word = Word(wordbook_id=wordbook_id, term="apple", meaning="사과")
        session.add(word)
        await session.flush()
        session.add(Bookmark(user_id=user_id, word_id=word.id))
        session.add(StudyLog(user_id=user_id, word_id=word.id, is_correct=True))
        await session.commit()
        word_id = word.id

    response = await client.delete(f"/api/wordbooks/{wordbook_id}", headers=auth_headers(token))
    assert response.status_code == 204

    async with get_session_factory()() as session:
        counts = {
            "wordbooks": await session.scalar(select(func.count()).select_from(Wordbook).where(Wordbook.id == wordbook_id)),
            "words": await session.scalar(select(func.count()).select_from(Word).where(Word.id == word_id)),
            "bookmarks": await session.scalar(select(func.count()).select_from(Bookmark).where(Bookmark.word_id == word_id)),
            "study_logs": await session.scalar(select(func.count()).select_from(StudyLog).where(StudyLog.word_id == word_id)),
        }
    assert counts == {"wordbooks": 0, "words": 0, "bookmarks": 0, "study_logs": 0}


# --- 단어 수 집계 (v1.1 Phase 2, word_count) ---


@pytest.mark.asyncio
async def test_list_word_counts_are_aggregated_per_wordbook(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    empty = await create(client, token, "빈 단어장")
    two = await create(client, token, "두 단어장")
    three = await create(client, token, "세 단어장")
    for term in ("apple", "pear"):
        await client.post(f"/api/wordbooks/{two['id']}/words", json={"term": term, "meaning": "뜻"}, headers=auth_headers(token))
    for term in ("kiwi", "plum", "lime"):
        await client.post(f"/api/wordbooks/{three['id']}/words", json={"term": term, "meaning": "뜻"}, headers=auth_headers(token))

    items = (await client.get("/api/wordbooks?size=100", headers=auth_headers(token))).json()["items"]
    counts = {i["name"]: i["word_count"] for i in items}
    assert counts["빈 단어장"] == 0
    assert counts["두 단어장"] == 2
    assert counts["세 단어장"] == 3
    assert all(counts[name] == 200 for name in DEFAULT_WORDBOOK_NAMES), "기본 단어장은 200개"
    assert empty["id"] != two["id"] != three["id"]


@pytest.mark.asyncio
async def test_get_and_patch_return_word_count(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    wb = await create(client, token, "단건")
    await client.post(f"/api/wordbooks/{wb['id']}/words", json={"term": "a1", "meaning": "뜻"}, headers=auth_headers(token))
    await client.post(f"/api/wordbooks/{wb['id']}/words", json={"term": "a2", "meaning": "뜻"}, headers=auth_headers(token))
    got = (await client.get(f"/api/wordbooks/{wb['id']}", headers=auth_headers(token))).json()
    assert got["word_count"] == 2
    patched = await client.patch(f"/api/wordbooks/{wb['id']}", json={"name": "단건-수정"}, headers=auth_headers(token))
    assert patched.json()["word_count"] == 2


# --- 중급 1,000제 추천 프리셋 (POST /api/wordbooks/presets/intermediate-1000) ---


def _write_synthetic_preset(directory, count: int = 1000) -> None:
    lines = ["term,meaning,example"]
    lines += [f"preset{i:04d},뜻{i},Example preset{i:04d}." for i in range(count)]
    (directory / "intermediate_1000.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")


@pytest.mark.asyncio
async def test_preset_creates_a_1000_word_wordbook_in_one_request(
    client: httpx.AsyncClient, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from backend.services import seed

    _write_synthetic_preset(tmp_path)
    monkeypatch.setattr(seed, "SEED_DIR", tmp_path)
    _, token = await signup_and_login(client)

    response = await client.post("/api/wordbooks/presets/intermediate-1000", headers=auth_headers(token))
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["name"] == "중급 필수 영단어 1,000"
    assert body["word_count"] == 1000

    listing = (await client.get("/api/wordbooks?size=100", headers=auth_headers(token))).json()["items"]
    preset = next(i for i in listing if i["id"] == body["id"])
    assert preset["word_count"] == 1000


@pytest.mark.asyncio
async def test_preset_twice_is_409_because_the_name_is_taken(
    client: httpx.AsyncClient, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from backend.services import seed

    _write_synthetic_preset(tmp_path)
    monkeypatch.setattr(seed, "SEED_DIR", tmp_path)
    _, token = await signup_and_login(client)
    assert (await client.post("/api/wordbooks/presets/intermediate-1000", headers=auth_headers(token))).status_code == 201
    again = await client.post("/api/wordbooks/presets/intermediate-1000", headers=auth_headers(token))
    assert again.status_code == 409


@pytest.mark.asyncio
async def test_preset_without_data_file_is_503(
    client: httpx.AsyncClient, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from backend.services import seed

    monkeypatch.setattr(seed, "SEED_DIR", tmp_path)  # intermediate_1000.csv 이 없다
    _, token = await signup_and_login(client)
    response = await client.post("/api/wordbooks/presets/intermediate-1000", headers=auth_headers(token))
    assert response.status_code == 503
    assert "준비되지 않았습니다" in response.json()["detail"]


@pytest.mark.asyncio
async def test_preset_requires_login(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/wordbooks/presets/intermediate-1000")
    assert response.status_code == 401
