# 2026-11-05 - voda-voca - 복습 세션 API 통합 테스트 (실제 MySQL): 세션 생성의 source(all/bookmarks/wrong) 분기, 오답 단어 목록 엔드포인트
# 파일 위치: src/backend/tests/test_review_session_api.py

from collections.abc import AsyncIterator
from datetime import datetime, timedelta

import httpx
import pytest
import pytest_asyncio

from backend.db.session import get_session_factory
from backend.main import app
from backend.models import StudyLog
from backend.routers import study_session as session_router
from backend.tests.helpers import auth_headers, signup_and_login
from backend.tests.test_learning_session_api import activate, answer, create, stored_session
from backend.tests.test_study_api import _user_id_for_token

NOW = datetime(2026, 11, 5, 9, 0, 0)
T0 = datetime(2026, 11, 1, 9, 0, 0)


@pytest_asyncio.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(session_router, "_now", lambda: NOW)


# --- 도우미 ---


async def bookmark(client: httpx.AsyncClient, token: str, word_id: int) -> None:
    response = await client.put(f"/api/bookmarks/{word_id}", headers=auth_headers(token))
    assert response.status_code == 204, response.text


async def log(user_id: int, word_id: int, correct: bool, minutes: int) -> None:
    """학습 이력 1건 (분 단위로 시각을 벌려 '가장 최근 결과'를 정한다)."""
    async with get_session_factory()() as db:
        db.add(StudyLog(user_id=user_id, word_id=word_id, is_correct=correct, created_at=T0 + timedelta(minutes=minutes)))
        await db.commit()


async def setup(client, make_vocabulary, n=8, title="복습 테스트"):
    vocab = await make_vocabulary([f"r{i:02d}" for i in range(n)], title=title)
    _, token = await signup_and_login(client)
    user_id = await _user_id_for_token(client, token)
    return token, user_id, vocab


def ids(vocab, *terms: str) -> list[int]:
    return [vocab.word_ids[t] for t in terms]


# --- source 검증 ---


@pytest.mark.asyncio
async def test_unknown_source_is_rejected(client, make_vocabulary) -> None:
    token, _, _ = await setup(client, make_vocabulary)
    assert (await create(client, token, source="everything")).status_code == 422


@pytest.mark.asyncio
async def test_source_defaults_to_all_and_keeps_the_waterfall(client, make_vocabulary) -> None:
    token, _, vocab = await setup(client, make_vocabulary, n=20)
    await activate(client, token, vocab.id)
    explicit = await create(client, token, source="all")
    default = await create(client, token)
    for response in (explicit, default):
        assert response.status_code == 201
        assert response.json()["vocabulary_id"] == vocab.id
        assert (await stored_session(response.json()["session_id"])).source == "vocabulary"


# --- 북마크 복습 ---


@pytest.mark.asyncio
async def test_bookmark_session_draws_only_bookmarked_words_across_vocabularies(client, make_vocabulary) -> None:
    token, _, first = await setup(client, make_vocabulary, title="첫째")
    second = await make_vocabulary([f"s{i:02d}" for i in range(6)], title="둘째")
    marked = ids(first, "r00", "r01", "r02") + ids(second, "s00", "s01")
    for word_id in marked:
        await bookmark(client, token, word_id)

    response = await create(client, token, source="bookmarks")

    assert response.status_code == 201, response.text
    body = response.json()
    assert (body["mode"], body["vocabulary_id"], body["vocabulary_title"], body["total_questions"]) == (
        "quiz", None, "북마크 복습", 5
    )
    assert {item["word_id"] for item in body["items"]} == set(marked)
    row = await stored_session(body["session_id"])
    assert (row.source, row.vocabulary_id) == ("bookmarks", None)
    for question in row.questions:  # 오답 보기는 그 단어가 속한 단어장에서만 뽑는다
        owner = first if question["word_id"] in first.word_ids.values() else second
        assert set(question["choices"]) <= {f"{t}의 뜻" for t in owner.word_ids}


@pytest.mark.asyncio
async def test_review_session_never_leaks_answers(client, make_vocabulary) -> None:
    token, _, vocab = await setup(client, make_vocabulary)
    for word_id in ids(vocab, "r00", "r01", "r02", "r03"):
        await bookmark(client, token, word_id)
    body = (await create(client, token, source="bookmarks")).json()
    for item in body["items"]:
        assert len(item["options"]) == 4
        assert not ({"correct_index", "meaning", "example_meaning"} & {k for k, v in item.items() if v is not None})


@pytest.mark.asyncio
async def test_bookmark_session_respects_count(client, make_vocabulary) -> None:
    token, _, vocab = await setup(client, make_vocabulary)
    for word_id in vocab.word_ids.values():
        await bookmark(client, token, word_id)
    body = (await create(client, token, source="bookmarks", count=5)).json()
    assert body["total_questions"] == 5 and len({i["word_id"] for i in body["items"]}) == 5


@pytest.mark.asyncio
async def test_memorized_words_are_included_in_review_even_without_the_flag(client, make_vocabulary) -> None:
    from backend.tests.test_learning_session_api import put_progress

    token, user_id, vocab = await setup(client, make_vocabulary)
    marked = ids(vocab, "r00", "r01", "r02", "r03")
    for word_id in marked:
        await bookmark(client, token, word_id)
    await put_progress(user_id, marked[0], memorized=True, streak=3)

    body = (await create(client, token, source="bookmarks", include_memorized=False)).json()

    assert marked[0] in {item["word_id"] for item in body["items"]}, "복습은 사용자가 고른 풀이므로 숙련 단어도 뺀 채 만들지 않는다"


@pytest.mark.asyncio
async def test_empty_bookmarks_return_409_no_words(client, make_vocabulary) -> None:
    token, _, _ = await setup(client, make_vocabulary)
    response = await create(client, token, source="bookmarks")
    assert response.status_code == 409
    assert response.headers["X-Error-Code"] == "NO_WORDS_TO_STUDY"


@pytest.mark.asyncio
async def test_quiz_review_needs_four_words_but_flashcards_do_not(client, make_vocabulary) -> None:
    token, _, vocab = await setup(client, make_vocabulary)
    for word_id in ids(vocab, "r00", "r01"):
        await bookmark(client, token, word_id)

    assert (await create(client, token, source="bookmarks")).status_code == 400
    cards = await create(client, token, source="bookmarks", mode="flashcard")
    assert cards.status_code == 201
    item = cards.json()["items"][0]
    assert item["options"] is None and item["meaning"] == f"{item['term']}의 뜻"


@pytest.mark.asyncio
async def test_other_users_bookmarks_are_not_used(client, make_vocabulary) -> None:
    token, _, vocab = await setup(client, make_vocabulary)
    _, other = await signup_and_login(client)
    for word_id in ids(vocab, "r00", "r01", "r02", "r03"):
        await bookmark(client, other, word_id)

    assert (await create(client, token, source="bookmarks")).status_code == 409


@pytest.mark.asyncio
async def test_review_session_does_not_change_the_active_vocabulary(client, make_vocabulary) -> None:
    token, _, vocab = await setup(client, make_vocabulary)
    other = await make_vocabulary(["x1", "x2", "x3", "x4"], title="다른 단어장")
    await activate(client, token, vocab.id)
    for word_id in other.word_ids.values():
        await bookmark(client, token, word_id)

    assert (await create(client, token, source="bookmarks")).status_code == 201

    catalog = (await client.get("/api/vocabularies", headers=auth_headers(token))).json()
    assert [v["id"] for v in catalog if v["user_progress"]["is_active"]] == [vocab.id]


# --- 오답 복습 ---


@pytest.mark.asyncio
async def test_wrong_session_uses_words_whose_latest_result_is_wrong(client, make_vocabulary) -> None:
    token, user_id, vocab = await setup(client, make_vocabulary)
    wrong_a, wrong_b, wrong_c, fixed, never = ids(vocab, "r00", "r01", "r02", "r03", "r04")
    await log(user_id, wrong_a, False, 1)
    await log(user_id, wrong_b, False, 2)
    await log(user_id, wrong_c, True, 3)
    await log(user_id, wrong_c, False, 4)
    await log(user_id, fixed, False, 5)
    await log(user_id, fixed, True, 6)  # 다시 맞혔으므로 대상이 아니다

    response = await create(client, token, source="wrong", mode="flashcard")

    assert response.status_code == 201, response.text
    body = response.json()
    assert {i["word_id"] for i in body["items"]} == {wrong_a, wrong_b, wrong_c}
    assert (body["vocabulary_id"], body["vocabulary_title"]) == (None, "오답 복습")
    assert body["composition"] == {"wrong": 3, "review": 0, "unseen": 0}
    assert (await stored_session(body["session_id"])).source == "wrong"
    assert never not in {i["word_id"] for i in body["items"]}


@pytest.mark.asyncio
async def test_wrong_session_without_wrong_words_is_409(client, make_vocabulary) -> None:
    token, user_id, vocab = await setup(client, make_vocabulary)
    await log(user_id, vocab.word_ids["r00"], True, 1)
    response = await create(client, token, source="wrong")
    assert response.status_code == 409
    assert response.headers["X-Error-Code"] == "NO_WORDS_TO_STUDY"


@pytest.mark.asyncio
async def test_answering_a_wrong_review_correctly_removes_it_from_the_wrong_list(client, make_vocabulary) -> None:
    token, user_id, vocab = await setup(client, make_vocabulary)
    targets = ids(vocab, "r00", "r01", "r02", "r03")
    for minute, word_id in enumerate(targets):
        await log(user_id, word_id, False, minute)
    body = (await create(client, token, source="wrong")).json()
    row = await stored_session(body["session_id"])
    first = row.questions[0]

    result = await answer(client, token, body["session_id"], question_id=0, choice_index=first["correct_index"])

    assert result.status_code == 200 and result.json()["is_correct"] is True
    wrong = (await client.get("/api/study/wrong-words", headers=auth_headers(token))).json()
    assert first["word_id"] not in {item["word_id"] for item in wrong["items"]}
    assert wrong["total"] == 3


# --- GET /api/study/wrong-words ---


@pytest.mark.asyncio
async def test_wrong_words_requires_login(client: httpx.AsyncClient) -> None:
    assert (await client.get("/api/study/wrong-words")).status_code == 401


@pytest.mark.asyncio
async def test_wrong_words_is_empty_for_a_new_user(client, make_vocabulary) -> None:
    token, _, _ = await setup(client, make_vocabulary)
    response = await client.get("/api/study/wrong-words", headers=auth_headers(token))
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "page": 1, "size": 20}


@pytest.mark.asyncio
async def test_wrong_words_lists_latest_wrong_first_with_word_info(client, make_vocabulary) -> None:
    token, user_id, vocab = await setup(client, make_vocabulary, title="오답 단어장")
    old, newer, fixed = ids(vocab, "r00", "r01", "r02")
    await log(user_id, old, False, 1)
    await log(user_id, newer, False, 5)
    await log(user_id, fixed, False, 7)
    await log(user_id, fixed, True, 8)
    await bookmark(client, token, newer)

    response = await client.get("/api/study/wrong-words", headers=auth_headers(token))

    body = response.json()
    assert body["total"] == 2
    assert [item["word_id"] for item in body["items"]] == [newer, old], "가장 최근에 틀린 단어가 먼저"
    first = body["items"][0]
    assert first["vocabulary_id"] == vocab.id and first["vocabulary_title"] == "오답 단어장"
    assert (first["term"], first["meaning"]) == ("r01", "r01의 뜻")
    assert first["example"] == "I like r01." and first["example_meaning"] == "나는 r01을(를) 좋아한다."
    assert first["bookmarked"] is True and body["items"][1]["bookmarked"] is False
    assert first["wrong_at"] == "2026-11-01T09:05:00Z"


@pytest.mark.asyncio
async def test_wrong_words_paginates(client, make_vocabulary) -> None:
    token, user_id, vocab = await setup(client, make_vocabulary)
    for minute, word_id in enumerate(vocab.word_ids.values()):
        await log(user_id, word_id, False, minute)

    page1 = (await client.get("/api/study/wrong-words?page=1&size=3", headers=auth_headers(token))).json()
    page3 = (await client.get("/api/study/wrong-words?page=3&size=3", headers=auth_headers(token))).json()
    beyond = (await client.get("/api/study/wrong-words?page=9&size=3", headers=auth_headers(token))).json()

    assert (page1["total"], page1["page"], page1["size"], len(page1["items"])) == (8, 1, 3, 3)
    assert len(page3["items"]) == 2
    assert beyond["items"] == [] and beyond["total"] == 8
    seen = [i["word_id"] for i in page1["items"]]
    assert len(set(seen)) == 3


@pytest.mark.asyncio
async def test_wrong_words_validates_paging_and_isolates_users(client, make_vocabulary) -> None:
    token, user_id, vocab = await setup(client, make_vocabulary)
    await log(user_id, vocab.word_ids["r00"], False, 1)
    _, other = await signup_and_login(client)

    for bad in ("page=0", "size=0", "size=101"):
        assert (await client.get(f"/api/study/wrong-words?{bad}", headers=auth_headers(token))).status_code == 422, bad
    assert (await client.get("/api/study/wrong-words", headers=auth_headers(other))).json()["total"] == 0
