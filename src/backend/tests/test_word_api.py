# 2026-11-02 - voda-voca - 단어 API 통합 테스트 (실제 MySQL): CRUD, 접두사 검색, 격리, 중복, CASCADE, 인덱스 사용
# 파일 위치: src/backend/tests/test_word_api.py

from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.dialects import mysql

from backend.db.session import get_session_factory
from backend.main import app
from backend.models import Bookmark, StudyLog, User, Word
from backend.services.word import _list_query
from backend.tests.helpers import auth_headers, signup_and_login


@pytest_asyncio.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def make_wordbook(client: httpx.AsyncClient, token: str, name: str = "단어장") -> int:
    response = await client.post("/api/wordbooks", json={"name": name}, headers=auth_headers(token))
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def make_word(
    client: httpx.AsyncClient, token: str, wordbook_id: int, term: str, meaning: str = "뜻"
) -> dict:
    response = await client.post(
        f"/api/wordbooks/{wordbook_id}/words",
        json={"term": term, "meaning": meaning},
        headers=auth_headers(token),
    )
    assert response.status_code == 201, response.text
    return response.json()


async def search(client: httpx.AsyncClient, token: str, wordbook_id: int, q: str | None = None, **params) -> dict:
    query = dict(params)
    if q is not None:
        query["q"] = q
    response = await client.get(
        f"/api/wordbooks/{wordbook_id}/words", params=query, headers=auth_headers(token)
    )
    assert response.status_code == 200, response.text
    return response.json()


def terms(page: dict) -> list[str]:
    return [item["term"] for item in page["items"]]


# --- 생성 (REQ-008) ---


@pytest.mark.asyncio
async def test_create_word_returns_201_with_fields(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    wb = await make_wordbook(client, token)
    response = await client.post(
        f"/api/wordbooks/{wb}/words",
        json={"term": " apple ", "meaning": "사과", "example": "An apple."},
        headers=auth_headers(token),
    )
    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"id", "wordbook_id", "term", "meaning", "example", "created_at", "updated_at", "bookmarked"}
    assert body["bookmarked"] is False
    assert (body["wordbook_id"], body["term"], body["meaning"], body["example"]) == (wb, "apple", "사과", "An apple.")
    assert body["created_at"].endswith("Z")


@pytest.mark.asyncio
async def test_create_duplicate_term_is_409_case_insensitive(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    wb = await make_wordbook(client, token)
    await make_word(client, token, wb, "Apple")
    response = await client.post(
        f"/api/wordbooks/{wb}/words", json={"term": "apple", "meaning": "다른 뜻"}, headers=auth_headers(token)
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "같은 단어장에 이미 있는 표제어입니다."


@pytest.mark.asyncio
async def test_create_duplicate_term_is_409_accent_insensitive(client: httpx.AsyncClient) -> None:
    """utf8mb4_0900_ai_ci 는 악센트도 무시한다. café 와 cafe 는 같은 표제어로 본다 (설계 D2, 확정)."""
    _, token = await signup_and_login(client)
    wb = await make_wordbook(client, token)
    await make_word(client, token, wb, "café")
    response = await client.post(
        f"/api/wordbooks/{wb}/words", json={"term": "cafe", "meaning": "카페"}, headers=auth_headers(token)
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_same_term_is_allowed_in_different_wordbooks(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    wb1 = await make_wordbook(client, token, "첫째")
    wb2 = await make_wordbook(client, token, "둘째")
    await make_word(client, token, wb1, "apple")
    await make_word(client, token, wb2, "apple")


@pytest.mark.asyncio
async def test_create_blank_term_is_422(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    wb = await make_wordbook(client, token)
    response = await client.post(
        f"/api/wordbooks/{wb}/words", json={"term": "  ", "meaning": "뜻"}, headers=auth_headers(token)
    )
    assert response.status_code == 422


# --- 목록, 정렬, 페이징 (REQ-009, REQ-103) ---


@pytest.mark.asyncio
async def test_list_is_ordered_by_term_then_id(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    wb = await make_wordbook(client, token)
    for term in ["banana", "apple", "cherry"]:
        await make_word(client, token, wb, term)
    assert terms(await search(client, token, wb)) == ["apple", "banana", "cherry"]


@pytest.mark.asyncio
async def test_list_pagination_boundaries(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    wb = await make_wordbook(client, token)
    for term in ["a1", "a2", "a3"]:
        await make_word(client, token, wb, term)

    page1 = await search(client, token, wb, page=1, size=2)
    assert terms(page1) == ["a1", "a2"] and page1["total"] == 3 and page1["size"] == 2
    page2 = await search(client, token, wb, page=2, size=2)
    assert terms(page2) == ["a3"]
    beyond = await search(client, token, wb, page=3, size=2)
    assert beyond["items"] == [] and beyond["total"] == 3


@pytest.mark.asyncio
async def test_list_default_size_is_20(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    wb = await make_wordbook(client, token)
    assert await search(client, token, wb) == {"items": [], "total": 0, "page": 1, "size": 20}


@pytest.mark.asyncio
@pytest.mark.parametrize("params", [{"size": 0}, {"size": 101}, {"page": 0}])
async def test_list_rejects_out_of_range_paging(client: httpx.AsyncClient, params: dict) -> None:
    _, token = await signup_and_login(client)
    wb = await make_wordbook(client, token)
    response = await client.get(f"/api/wordbooks/{wb}/words", params=params, headers=auth_headers(token))
    assert response.status_code == 422


# --- 접두사 검색 (REQ-009, REQ-113) ---


@pytest.mark.asyncio
async def test_prefix_search_matches_start_of_term_only(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    wb = await make_wordbook(client, token)
    for term in ["apple", "apricot", "banana", "pineapple"]:
        await make_word(client, token, wb, term)
    page = await search(client, token, wb, q="ap")
    assert terms(page) == ["apple", "apricot"]
    assert page["total"] == 2


@pytest.mark.asyncio
async def test_prefix_search_is_case_insensitive(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    wb = await make_wordbook(client, token)
    await make_word(client, token, wb, "Apple")
    assert terms(await search(client, token, wb, q="AP")) == ["Apple"]


@pytest.mark.asyncio
async def test_prefix_search_is_accent_insensitive(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    wb = await make_wordbook(client, token)
    await make_word(client, token, wb, "café")
    assert terms(await search(client, token, wb, q="cafe")) == ["café"]


@pytest.mark.asyncio
async def test_wildcard_characters_in_query_are_literal(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    wb = await make_wordbook(client, token)
    for term in ["a%b", "axb", "a_c", "abc", "x\\y", "xzy"]:
        await make_word(client, token, wb, term)

    # % 가 와일드카드였다면 axb, abc 도 걸렸을 것이다.
    assert terms(await search(client, token, wb, q="a%")) == ["a%b"]
    # _ 가 와일드카드였다면 axb, abc 도 걸렸을 것이다.
    assert terms(await search(client, token, wb, q="a_")) == ["a_c"]
    # 백슬래시가 이스케이프 문자로 해석되면 결과가 달라진다.
    assert terms(await search(client, token, wb, q="x\\")) == ["x\\y"]


@pytest.mark.asyncio
@pytest.mark.parametrize("q", [None, "", "   "])
async def test_empty_or_blank_query_returns_everything(client: httpx.AsyncClient, q: str | None) -> None:
    _, token = await signup_and_login(client)
    wb = await make_wordbook(client, token)
    for term in ["one", "two"]:
        await make_word(client, token, wb, term)
    page = await search(client, token, wb, q=q)
    assert terms(page) == ["one", "two"] and page["total"] == 2


@pytest.mark.asyncio
async def test_search_total_counts_only_matches(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    wb = await make_wordbook(client, token)
    for term in ["ab1", "ab2", "ab3", "zz"]:
        await make_word(client, token, wb, term)
    page = await search(client, token, wb, q="ab", page=1, size=2)
    assert len(page["items"]) == 2 and page["total"] == 3


@pytest.mark.asyncio
async def test_search_query_longer_than_limit_is_422(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    wb = await make_wordbook(client, token)
    response = await client.get(f"/api/wordbooks/{wb}/words", params={"q": "a" * 101}, headers=auth_headers(token))
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_selective_prefix_search_uses_unique_index(client: httpx.AsyncClient) -> None:
    """선택적인 접두사 검색이 uk_words_wordbook_term 인덱스 범위 스캔을 쓰고 filesort 가 없는지 확인한다.

    실제 실행과 같은 바인딩 파라미터로 EXPLAIN 한다. literal 로 렌더링하면 % 가 이중 이스케이프되어 실행 계획이 달라진다.
    넓은 접두사(예: 33% 매칭)에서는 옵티마이저가 전체 스캔을 고를 수 있으므로 여기서는 단언하지 않는다 (REQ-103).
    """
    email, token = await signup_and_login(client)
    wb = await make_wordbook(client, token)

    async with get_session_factory()() as session:
        user_id = (await session.execute(select(User.id).where(User.email == email))).scalar_one()
        session.add_all(
            [Word(wordbook_id=wb, term=f"word{i:04d}", meaning="뜻") for i in range(300)]
        )
        await session.commit()
        await session.execute(text("ANALYZE TABLE words"))

        compiled = _list_query(wb, "word0001", user_id).compile(dialect=mysql.dialect())
        names = list(compiled.positiontup)
        named_sql = str(compiled)
        for name in names:
            named_sql = named_sql.replace("%s", f":{name}", 1)
        params = {name: compiled.params[name] for name in names}
        rows = (
            await session.execute(text("EXPLAIN " + named_sql), params)
        ).mappings().all()

    # 조인이 늘었으므로 실행 계획은 여러 행이다. 구동 테이블(words)의 행을 본다.
    words_row = next(r for r in rows if r["table"] == "words")
    assert words_row["key"] == "uk_words_wordbook_term", dict(words_row)
    assert words_row["type"] == "range", dict(words_row)
    assert "filesort" not in (words_row["Extra"] or "").lower(), dict(words_row)


# --- 조회, 수정, 삭제 (REQ-010, REQ-011) ---


@pytest.mark.asyncio
async def test_get_patch_delete_roundtrip(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    wb = await make_wordbook(client, token)
    created = await make_word(client, token, wb, "apple", "사과")
    url = f"/api/wordbooks/{wb}/words/{created['id']}"

    assert (await client.get(url, headers=auth_headers(token))).json()["term"] == "apple"

    patched = await client.patch(url, json={"meaning": "사과(과일)"}, headers=auth_headers(token))
    assert patched.status_code == 200
    assert patched.json()["meaning"] == "사과(과일)"
    assert patched.json()["term"] == "apple"

    assert (await client.delete(url, headers=auth_headers(token))).status_code == 204
    assert (await client.get(url, headers=auth_headers(token))).status_code == 404


@pytest.mark.asyncio
async def test_patch_example_to_null_clears_it(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    wb = await make_wordbook(client, token)
    word = await client.post(
        f"/api/wordbooks/{wb}/words",
        json={"term": "tree", "meaning": "나무", "example": "A tall tree."},
        headers=auth_headers(token),
    )
    response = await client.patch(
        f"/api/wordbooks/{wb}/words/{word.json()['id']}", json={"example": None}, headers=auth_headers(token)
    )
    assert response.json()["example"] is None


@pytest.mark.asyncio
async def test_patch_term_to_taken_term_is_409(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    wb = await make_wordbook(client, token)
    await make_word(client, token, wb, "apple")
    other = await make_word(client, token, wb, "banana")
    response = await client.patch(
        f"/api/wordbooks/{wb}/words/{other['id']}", json={"term": "APPLE"}, headers=auth_headers(token)
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_patch_term_to_null_is_422(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    wb = await make_wordbook(client, token)
    word = await make_word(client, token, wb, "apple")
    response = await client.patch(
        f"/api/wordbooks/{wb}/words/{word['id']}", json={"term": None}, headers=auth_headers(token)
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_patch_without_changes_keeps_updated_at(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    wb = await make_wordbook(client, token)
    word = await make_word(client, token, wb, "apple", "사과")
    response = await client.patch(
        f"/api/wordbooks/{wb}/words/{word['id']}",
        json={"term": "apple", "meaning": "사과"},
        headers=auth_headers(token),
    )
    assert response.json()["updated_at"] == word["updated_at"]


# --- 소유권 격리 및 소속 검증 (REQ-003, 404 일원화) ---


@pytest.mark.asyncio
async def test_other_users_wordbook_is_404_for_every_word_operation(client: httpx.AsyncClient) -> None:
    _, owner = await signup_and_login(client)
    _, intruder = await signup_and_login(client)
    wb = await make_wordbook(client, owner, "비밀")
    word = await make_word(client, owner, wb, "secret", "비밀 뜻")
    base = f"/api/wordbooks/{wb}/words"

    responses = [
        await client.get(base, headers=auth_headers(intruder)),
        await client.post(base, json={"term": "x", "meaning": "y"}, headers=auth_headers(intruder)),
        await client.get(f"{base}/{word['id']}", headers=auth_headers(intruder)),
        await client.patch(f"{base}/{word['id']}", json={"meaning": "탈취"}, headers=auth_headers(intruder)),
        await client.delete(f"{base}/{word['id']}", headers=auth_headers(intruder)),
    ]
    assert all(r.status_code == 404 for r in responses)
    assert len({r.text for r in responses}) == 1  # 단어장 수준의 같은 404 본문이어야 한다

    still = (await client.get(f"{base}/{word['id']}", headers=auth_headers(owner))).json()
    assert (still["meaning"], still["term"]) == ("비밀 뜻", "secret")


@pytest.mark.asyncio
async def test_word_in_other_wordbook_of_same_user_is_404(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    wb1 = await make_wordbook(client, token, "첫째")
    wb2 = await make_wordbook(client, token, "둘째")
    word_in_wb2 = await make_word(client, token, wb2, "apple")

    response = await client.get(f"/api/wordbooks/{wb1}/words/{word_in_wb2['id']}", headers=auth_headers(token))
    missing = await client.get(f"/api/wordbooks/{wb1}/words/999999999", headers=auth_headers(token))

    assert response.status_code == missing.status_code == 404
    assert response.json() == missing.json()

    patch = await client.patch(
        f"/api/wordbooks/{wb1}/words/{word_in_wb2['id']}", json={"meaning": "변경"}, headers=auth_headers(token)
    )
    assert patch.status_code == 404
    assert patch.json() == missing.json()

    delete = await client.delete(f"/api/wordbooks/{wb1}/words/{word_in_wb2['id']}", headers=auth_headers(token))
    assert delete.status_code == 404
    still = await client.get(f"/api/wordbooks/{wb2}/words/{word_in_wb2['id']}", headers=auth_headers(token))
    assert still.status_code == 200


@pytest.mark.asyncio
async def test_foreign_and_missing_word_ids_give_identical_404(client: httpx.AsyncClient) -> None:
    _, owner = await signup_and_login(client)
    _, intruder = await signup_and_login(client)
    wb = await make_wordbook(client, owner)
    foreign = await make_word(client, owner, wb, "남의 것")

    foreign_resp = await client.get(f"/api/wordbooks/{wb}/words/{foreign['id']}", headers=auth_headers(intruder))
    missing_resp = await client.get(f"/api/wordbooks/{wb}/words/999999999", headers=auth_headers(intruder))
    assert foreign_resp.status_code == missing_resp.status_code == 404
    assert foreign_resp.json() == missing_resp.json()


@pytest.mark.asyncio
async def test_unauthenticated_word_requests_are_401(client: httpx.AsyncClient) -> None:
    assert (await client.get("/api/wordbooks/1/words")).status_code == 401
    assert (await client.post("/api/wordbooks/1/words", json={"term": "a", "meaning": "b"})).status_code == 401


# --- CASCADE (REQ-011, REQ-104) ---


@pytest.mark.asyncio
async def test_deleting_word_cascades_bookmarks_and_study_logs(client: httpx.AsyncClient) -> None:
    email, token = await signup_and_login(client)
    wb = await make_wordbook(client, token)
    word = await make_word(client, token, wb, "apple")

    async with get_session_factory()() as session:
        user_id = (await session.execute(select(User.id).where(User.email == email))).scalar_one()
        session.add(Bookmark(user_id=user_id, word_id=word["id"]))
        session.add(StudyLog(user_id=user_id, word_id=word["id"], is_correct=False))
        await session.commit()

    response = await client.delete(f"/api/wordbooks/{wb}/words/{word['id']}", headers=auth_headers(token))
    assert response.status_code == 204

    async with get_session_factory()() as session:
        bookmarks = (await session.execute(select(Bookmark).where(Bookmark.word_id == word["id"]))).scalars().all()
        logs = (await session.execute(select(StudyLog).where(StudyLog.word_id == word["id"]))).scalars().all()
    assert bookmarks == [] and logs == []


# --- 일괄 등록 (POST /api/wordbooks/{id}/words/bulk) ---


def _bulk_body(*terms: str, meaning: str = "뜻") -> dict:
    return {"items": [{"term": t, "meaning": f"{meaning}-{t}"} for t in terms]}


async def bulk(client: httpx.AsyncClient, token: str, wordbook_id: int, body: dict) -> httpx.Response:
    return await client.post(
        f"/api/wordbooks/{wordbook_id}/words/bulk", json=body, headers=auth_headers(token)
    )


@pytest.mark.asyncio
async def test_bulk_create_success_returns_all_words_in_order(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    wb = await make_wordbook(client, token)

    response = await bulk(client, token, wb, {
        "items": [
            {"term": "banana", "meaning": "바나나", "example": "I eat a banana."},
            {"term": "apple", "meaning": "사과"},
            {"term": "cherry", "meaning": "체리", "example": "  "},
        ]
    })
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["count"] == 3
    assert [item["term"] for item in body["items"]] == ["banana", "apple", "cherry"]
    assert all(item["bookmarked"] is False for item in body["items"])
    assert body["items"][0]["example"] == "I eat a banana."
    assert body["items"][1]["example"] is None
    assert body["items"][2]["example"] is None  # 공백 예문은 null 로 저장
    assert all(item["created_at"].endswith("Z") for item in body["items"])

    page = await search(client, token, wb)
    assert page["total"] == 3
    assert terms(page) == ["apple", "banana", "cherry"]


@pytest.mark.asyncio
async def test_bulk_accepts_exactly_100_items(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    wb = await make_wordbook(client, token)
    names = [f"word{i:03d}" for i in range(100)]

    response = await bulk(client, token, wb, _bulk_body(*names))
    assert response.status_code == 201, response.text
    assert response.json()["count"] == 100
    assert (await search(client, token, wb, size=100))["total"] == 100


@pytest.mark.asyncio
async def test_bulk_over_100_items_is_422_and_stores_nothing(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    wb = await make_wordbook(client, token)
    names = [f"word{i:03d}" for i in range(101)]

    response = await bulk(client, token, wb, _bulk_body(*names))
    assert response.status_code == 422
    assert (await search(client, token, wb))["total"] == 0


@pytest.mark.asyncio
async def test_bulk_empty_items_is_422(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    wb = await make_wordbook(client, token)
    assert (await bulk(client, token, wb, {"items": []})).status_code == 422


@pytest.mark.asyncio
async def test_bulk_duplicate_in_request_is_422_and_stores_nothing(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    wb = await make_wordbook(client, token)

    response = await bulk(client, token, wb, _bulk_body("apple", "Apple", "pear"))
    assert response.status_code == 422
    assert (await search(client, token, wb))["total"] == 0


@pytest.mark.asyncio
async def test_bulk_item_field_error_is_422(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    wb = await make_wordbook(client, token)
    body = {"items": [{"term": "apple", "meaning": "사과"}, {"term": "pear", "meaning": "   "}]}

    assert (await bulk(client, token, wb, body)).status_code == 422
    assert (await search(client, token, wb))["total"] == 0


@pytest.mark.asyncio
async def test_bulk_conflict_with_existing_word_is_409_and_rolls_back_everything(
    client: httpx.AsyncClient,
) -> None:
    """기존 단어와 겹치면 409. 요청한 새 단어 중 겹치지 않은 것도 저장되지 않는다 (All-or-Nothing)."""
    _, token = await signup_and_login(client)
    wb = await make_wordbook(client, token)
    await make_word(client, token, wb, "apple")

    # "Apple" 은 DB 콜레이션상 기존 "apple" 과 같은 표제어다. 요청 안에서는 겹치지 않으므로 DB 가 막는다.
    response = await bulk(client, token, wb, _bulk_body("banana", "cherry", "Apple"))
    assert response.status_code == 409, response.text
    assert "전체 등록을 취소" in response.json()["detail"]
    assert response.json()["conflict_term"] == "Apple"  # 요청한 표제어 그대로

    page = await search(client, token, wb)
    assert page["total"] == 1
    assert terms(page) == ["apple"]

    # 롤백 후 같은 단어장에 정상 요청은 다시 성공한다
    retry = await bulk(client, token, wb, _bulk_body("banana", "cherry"))
    assert retry.status_code == 201
    assert (await search(client, token, wb))["total"] == 3


@pytest.mark.asyncio
async def test_bulk_same_term_in_other_wordbook_is_allowed(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    wb_a = await make_wordbook(client, token, "A")
    wb_b = await make_wordbook(client, token, "B")
    await make_word(client, token, wb_a, "apple")

    response = await bulk(client, token, wb_b, _bulk_body("apple", "pear"))
    assert response.status_code == 201, response.text


@pytest.mark.asyncio
async def test_bulk_into_other_users_wordbook_is_404(client: httpx.AsyncClient) -> None:
    _, owner = await signup_and_login(client)
    _, intruder = await signup_and_login(client)
    wb = await make_wordbook(client, owner)

    foreign = await bulk(client, intruder, wb, _bulk_body("apple"))
    missing = await bulk(client, intruder, 987654321, _bulk_body("apple"))
    assert foreign.status_code == 404
    assert missing.status_code == 404
    assert foreign.json() == missing.json()
    assert (await search(client, owner, wb))["total"] == 0


@pytest.mark.asyncio
async def test_bulk_requires_login(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/wordbooks/1/words/bulk", json=_bulk_body("apple"))
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_bulk_409_names_the_first_conflicting_requested_term(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    wb = await make_wordbook(client, token)
    await make_word(client, token, wb, "pear")
    await make_word(client, token, wb, "plum")

    response = await bulk(client, token, wb, _bulk_body("kiwi", "plum", "pear"))
    assert response.status_code == 409
    assert response.json()["conflict_term"] == "plum"  # 요청 순서상 먼저 겹친 표제어
    assert set(response.json()) == {"detail", "conflict_term"}
