# 2026-11-02 - voda-voca - 학습 API 통합 테스트 (실제 MySQL): 플래시카드, 퀴즈 출제·제출, 만료·중복 차단, 이력 기록
# 파일 위치: src/backend/tests/test_study_api.py

import asyncio
from collections.abc import AsyncIterator
from datetime import timedelta

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import func, select

from backend.db.session import get_session_factory
from backend.main import app
from backend.models import QuizSession, StudyLog
from backend.models.base import utcnow
from backend.routers import study as study_router
from backend.tests.helpers import auth_headers, signup_and_login


@pytest_asyncio.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# --- 공통 헬퍼 ---


async def make_wordbook(client: httpx.AsyncClient, token: str, name: str = "단어장") -> int:
    response = await client.post("/api/wordbooks", json={"name": name}, headers=auth_headers(token))
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def make_word(
    client: httpx.AsyncClient, token: str, wordbook_id: int, term: str, meaning: str
) -> int:
    response = await client.post(
        f"/api/wordbooks/{wordbook_id}/words",
        json={"term": term, "meaning": meaning},
        headers=auth_headers(token),
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def make_words(
    client: httpx.AsyncClient, token: str, wordbook_id: int, count: int, prefix: str = "w"
) -> dict[int, str]:
    """단어를 count 개 만들고 {word_id: meaning} 을 돌려준다. 뜻은 모두 다르다."""
    result: dict[int, str] = {}
    for i in range(count):
        meaning = f"{prefix}-뜻-{i}"
        word_id = await make_word(client, token, wordbook_id, f"{prefix}term{i:02d}", meaning)
        result[word_id] = meaning
    return result


async def create_quiz(
    client: httpx.AsyncClient, token: str, body: dict
) -> httpx.Response:
    return await client.post("/api/study/quiz/sessions", json=body, headers=auth_headers(token))


async def load_session(session_id: int) -> QuizSession:
    """서버에 저장된 세션 행(정답 인덱스 포함)을 DB에서 직접 읽는다. 테스트 검증 전용."""
    async with get_session_factory()() as db:
        row = await db.get(QuizSession, session_id)
        assert row is not None
        return row


def correct_answers(session: QuizSession) -> list[dict]:
    return [
        {"question_id": q["question_id"], "choice_index": q["correct_index"]}
        for q in session.questions
    ]


async def submit(
    client: httpx.AsyncClient, token: str, session_id: int, answers: list[dict]
) -> httpx.Response:
    return await client.post(
        f"/api/study/quiz/sessions/{session_id}/submit",
        json={"answers": answers},
        headers=auth_headers(token),
    )


async def study_log_count() -> int:
    """study_logs 전체 행 수. 테스트 간 격리는 카운트 차이(delta)로 확인한다."""
    async with get_session_factory()() as db:
        return (await db.execute(select(func.count()).select_from(StudyLog))).scalar_one()


# --- 플래시카드 (REQ-012, 013, 019) ---


@pytest.mark.asyncio
async def test_flashcards_by_wordbook_include_bookmark_flag(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    wb = await make_wordbook(client, token)
    words = await make_words(client, token, wb, 3)
    first = next(iter(words))
    await client.put(f"/api/bookmarks/{first}", headers=auth_headers(token))

    response = await client.get(
        "/api/study/flashcards", params={"wordbook_id": wb}, headers=auth_headers(token)
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 3
    by_id = {item["word_id"]: item for item in body["items"]}
    assert by_id[first]["bookmarked"] is True
    assert all(item["bookmarked"] is False for wid, item in by_id.items() if wid != first)
    assert all({"term", "meaning", "example"} <= item.keys() for item in body["items"])


@pytest.mark.asyncio
async def test_flashcards_bookmarked_only_returns_own_bookmarks(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    wb_a = await make_wordbook(client, token, "A")
    wb_b = await make_wordbook(client, token, "B")
    a_words = await make_words(client, token, wb_a, 2, prefix="a")
    b_words = await make_words(client, token, wb_b, 2, prefix="b")
    picked = [next(iter(a_words)), next(iter(b_words))]
    for word_id in picked:
        await client.put(f"/api/bookmarks/{word_id}", headers=auth_headers(token))

    response = await client.get(
        "/api/study/flashcards", params={"bookmarked": "true"}, headers=auth_headers(token)
    )
    body = response.json()
    assert body["total"] == 2
    assert {item["word_id"] for item in body["items"]} == set(picked)


@pytest.mark.asyncio
async def test_flashcards_without_source_is_422(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    response = await client.get("/api/study/flashcards", headers=auth_headers(token))
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_flashcards_other_users_wordbook_is_404(client: httpx.AsyncClient) -> None:
    _, owner = await signup_and_login(client)
    _, intruder = await signup_and_login(client)
    wb = await make_wordbook(client, owner)
    await make_words(client, owner, wb, 2)

    response = await client.get(
        "/api/study/flashcards", params={"wordbook_id": wb}, headers=auth_headers(intruder)
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_flashcards_shuffle_returns_the_same_set(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    wb = await make_wordbook(client, token)
    words = await make_words(client, token, wb, 8)

    response = await client.get(
        "/api/study/flashcards",
        params={"wordbook_id": wb, "shuffle": "true"},
        headers=auth_headers(token),
    )
    assert response.status_code == 200
    assert {item["word_id"] for item in response.json()["items"]} == set(words)


# --- 퀴즈 출제 (REQ-014, REQ-019) ---


@pytest.mark.asyncio
async def test_quiz_fills_distractors_from_the_whole_pool_when_wordbook_meanings_are_identical(
    client: httpx.AsyncClient,
) -> None:
    """원천 단어장의 뜻이 모두 같아도, 사용자 전체 단어(기본 단어장 포함)에서 오답을 채운다."""
    _, token = await signup_and_login(client)
    wb = await make_wordbook(client, token)
    for i in range(4):
        await make_word(client, token, wb, f"same{i}", "똑같은뜻")

    response = await create_quiz(client, token, {"wordbook_id": wb, "count": 4})
    assert response.status_code == 201, response.text
    body = response.json()
    session = await load_session(body["session_id"])
    for stored, shown in zip(session.questions, body["questions"], strict=True):
        assert len(set(shown["choices"])) == 4
        assert shown["choices"][stored["correct_index"]] == "똑같은뜻"
        assert all(c != "똑같은뜻" for i, c in enumerate(shown["choices"]) if i != stored["correct_index"])


@pytest.mark.asyncio
async def test_quiz_needs_at_least_four_words(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    wb = await make_wordbook(client, token)
    await make_words(client, token, wb, 3)

    response = await create_quiz(client, token, {"wordbook_id": wb})
    assert response.status_code == 400
    assert "4개 이상" in response.json()["detail"]


@pytest.mark.asyncio
async def test_quiz_count_is_min_of_request_and_available(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    wb = await make_wordbook(client, token)
    await make_words(client, token, wb, 6)

    capped = await create_quiz(client, token, {"wordbook_id": wb, "count": 10})
    assert capped.status_code == 201, capped.text
    assert len(capped.json()["questions"]) == 6

    small = await create_quiz(client, token, {"wordbook_id": wb, "count": 2})
    assert len(small.json()["questions"]) == 2


@pytest.mark.asyncio
async def test_quiz_response_carries_answer_key_and_example_for_instant_feedback(client: httpx.AsyncClient) -> None:
    """즉각 피드백: 문항마다 정답 인덱스와 해설 예문을 준다. 값은 저장된 세션과 같아야 한다."""
    _, token = await signup_and_login(client)
    wb = await make_wordbook(client, token)
    words = await make_words(client, token, wb, 5)
    for word_id in words:
        await client.patch(f"/api/wordbooks/{wb}/words/{word_id}", json={"example": f"Example of {words[word_id]}."}, headers=auth_headers(token))

    response = await create_quiz(client, token, {"wordbook_id": wb})
    body = response.json()
    assert "expires_at" in body and body["expires_at"].endswith("Z")
    session = await load_session(body["session_id"])
    for stored, shown in zip(session.questions, body["questions"], strict=True):
        assert len(shown["choices"]) == 4
        assert len(set(shown["choices"])) == 4
        assert shown["correct_index"] == stored["correct_index"]
        assert 0 <= shown["correct_index"] <= 3
        assert shown["choices"][shown["correct_index"]] == words[stored["word_id"]]
        assert shown["example"] == f"Example of {words[stored['word_id']]}."


@pytest.mark.asyncio
async def test_distractors_come_from_the_original_wordbook_first(client: httpx.AsyncClient) -> None:
    """북마크 퀴즈의 오답은 단어가 속한 원본 단어장에서 먼저 뽑힌다 (결정 3)."""
    _, token = await signup_and_login(client)
    wb_a = await make_wordbook(client, token, "A")
    wb_b = await make_wordbook(client, token, "B")
    a_words = await make_words(client, token, wb_a, 4, prefix="a")
    b_words = await make_words(client, token, wb_b, 4, prefix="b")
    for word_id in [*a_words, *b_words]:
        await client.put(f"/api/bookmarks/{word_id}", headers=auth_headers(token))

    response = await create_quiz(client, token, {"bookmarks": True, "count": 8})
    assert response.status_code == 201, response.text
    session = await load_session(response.json()["session_id"])
    for question in session.questions:
        own_book = a_words if question["word_id"] in a_words else b_words
        distractors = [c for i, c in enumerate(question["choices"]) if i != question["correct_index"]]
        assert set(distractors) <= set(own_book.values())


@pytest.mark.asyncio
async def test_bookmark_quiz_needs_four_bookmarks(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    wb = await make_wordbook(client, token)
    words = await make_words(client, token, wb, 5)
    for word_id in list(words)[:3]:
        await client.put(f"/api/bookmarks/{word_id}", headers=auth_headers(token))

    response = await create_quiz(client, token, {"bookmarks": True})
    assert response.status_code == 400

    await client.put(f"/api/bookmarks/{list(words)[3]}", headers=auth_headers(token))
    ok = await create_quiz(client, token, {"bookmarks": True})
    assert ok.status_code == 201, ok.text
    session = await load_session(ok.json()["session_id"])
    assert session.source == "bookmarks"
    assert session.wordbook_id is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body",
    [
        {},
        {"wordbook_id": 1, "bookmarks": True},
        {"count": 0, "wordbook_id": 1},
        {"count": 51, "wordbook_id": 1},
    ],
)
async def test_quiz_rejects_invalid_body(client: httpx.AsyncClient, body: dict) -> None:
    _, token = await signup_and_login(client)
    response = await create_quiz(client, token, body)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_quiz_other_users_wordbook_is_404(client: httpx.AsyncClient) -> None:
    _, owner = await signup_and_login(client)
    _, intruder = await signup_and_login(client)
    wb = await make_wordbook(client, owner)
    await make_words(client, owner, wb, 4)

    response = await create_quiz(client, intruder, {"wordbook_id": wb})
    assert response.status_code == 404


# --- 퀴즈 제출·채점·이력 (REQ-015, REQ-016, REQ-106) ---


@pytest.mark.asyncio
async def test_submit_grades_and_records_one_log_per_question(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    wb = await make_wordbook(client, token)
    words = await make_words(client, token, wb, 4)
    created = (await create_quiz(client, token, {"wordbook_id": wb})).json()
    session = await load_session(created["session_id"])
    before = await study_log_count()

    answers = correct_answers(session)
    answers[0]["choice_index"] = (answers[0]["choice_index"] + 1) % 4
    answers[1]["choice_index"] = (answers[1]["choice_index"] + 1) % 4

    response = await submit(client, token, created["session_id"], answers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 4
    assert body["correct_count"] == 2
    assert body["accuracy"] == 50.0
    assert len(body["wrong_items"]) == 2
    for item in body["wrong_items"]:
        assert item["correct_meaning"] == words[item["word_id"]]
        assert item["selected_meaning"] != item["correct_meaning"]

    assert await study_log_count() - before == 4
    async with get_session_factory()() as db:
        logs = (
            await db.execute(select(StudyLog).where(StudyLog.word_id.in_(words)))
        ).scalars().all()
    assert sum(1 for log in logs if log.is_correct) == 2

    stored = await load_session(created["session_id"])
    assert stored.is_submitted is True


@pytest.mark.asyncio
async def test_submit_twice_is_409_and_logs_are_not_duplicated(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    wb = await make_wordbook(client, token)
    await make_words(client, token, wb, 4)
    created = (await create_quiz(client, token, {"wordbook_id": wb})).json()
    answers = correct_answers(await load_session(created["session_id"]))

    first = await submit(client, token, created["session_id"], answers)
    assert first.status_code == 200
    before = await study_log_count()

    second = await submit(client, token, created["session_id"], answers)
    assert second.status_code == 409
    assert await study_log_count() == before


@pytest.mark.asyncio
async def test_concurrent_submits_only_one_succeeds(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    wb = await make_wordbook(client, token)
    await make_words(client, token, wb, 4)
    created = (await create_quiz(client, token, {"wordbook_id": wb})).json()
    answers = correct_answers(await load_session(created["session_id"]))

    before = await study_log_count()
    responses = await asyncio.gather(
        *(submit(client, token, created["session_id"], answers) for _ in range(4))
    )
    statuses = sorted(r.status_code for r in responses)
    assert statuses == [200, 409, 409, 409]
    assert await study_log_count() - before == 4


@pytest.mark.asyncio
async def test_submit_after_expiry_is_400(client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _, token = await signup_and_login(client)
    wb = await make_wordbook(client, token)
    await make_words(client, token, wb, 4)
    created = (await create_quiz(client, token, {"wordbook_id": wb})).json()
    answers = correct_answers(await load_session(created["session_id"]))

    later = utcnow() + timedelta(minutes=31)
    monkeypatch.setattr(study_router, "_now", lambda: later)
    response = await submit(client, token, created["session_id"], answers)
    assert response.status_code == 400
    assert (await load_session(created["session_id"])).is_submitted is False


@pytest.mark.asyncio
async def test_submit_just_before_expiry_is_accepted(client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _, token = await signup_and_login(client)
    wb = await make_wordbook(client, token)
    await make_words(client, token, wb, 4)
    created = (await create_quiz(client, token, {"wordbook_id": wb})).json()
    answers = correct_answers(await load_session(created["session_id"]))

    almost = utcnow() + timedelta(minutes=29, seconds=59)
    monkeypatch.setattr(study_router, "_now", lambda: almost)
    response = await submit(client, token, created["session_id"], answers)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_submit_with_bad_answer_set_is_400(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    wb = await make_wordbook(client, token)
    await make_words(client, token, wb, 4)
    created = (await create_quiz(client, token, {"wordbook_id": wb})).json()
    answers = correct_answers(await load_session(created["session_id"]))

    missing = answers[:-1]
    duplicate = [*answers, answers[0]]
    unknown = [*answers[:-1], {"question_id": 99, "choice_index": 0}]
    for bad in (missing, duplicate, unknown):
        response = await submit(client, token, created["session_id"], bad)
        assert response.status_code == 400, bad

    # 잘못된 제출은 세션을 소모하지 않는다
    assert (await load_session(created["session_id"])).is_submitted is False


@pytest.mark.asyncio
async def test_submit_with_out_of_range_choice_is_422(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    wb = await make_wordbook(client, token)
    await make_words(client, token, wb, 4)
    created = (await create_quiz(client, token, {"wordbook_id": wb})).json()

    answers = [{"question_id": i, "choice_index": 4} for i in range(4)]
    response = await submit(client, token, created["session_id"], answers)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_submit_other_users_session_is_404(client: httpx.AsyncClient) -> None:
    _, owner = await signup_and_login(client)
    _, intruder = await signup_and_login(client)
    wb = await make_wordbook(client, owner)
    await make_words(client, owner, wb, 4)
    created = (await create_quiz(client, owner, {"wordbook_id": wb})).json()
    answers = correct_answers(await load_session(created["session_id"]))

    response = await submit(client, intruder, created["session_id"], answers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_deleted_word_blocks_submit_without_partial_write(client: httpx.AsyncClient) -> None:
    """문항 단어가 중간에 삭제되면 409. 세션은 제출되지 않고 이력도 한 줄도 남지 않는다 (REQ-106)."""
    _, token = await signup_and_login(client)
    wb = await make_wordbook(client, token)
    words = await make_words(client, token, wb, 4)
    created = (await create_quiz(client, token, {"wordbook_id": wb, "count": 4})).json()
    answers = correct_answers(await load_session(created["session_id"]))
    before = await study_log_count()

    victim = next(iter(words))
    deleted = await client.delete(f"/api/wordbooks/{wb}/words/{victim}", headers=auth_headers(token))
    assert deleted.status_code == 204

    response = await submit(client, token, created["session_id"], answers)
    assert response.status_code == 409
    assert (await load_session(created["session_id"])).is_submitted is False
    assert await study_log_count() == before


# --- 학습 이력 (REQ-016) ---


@pytest.mark.asyncio
async def test_logs_are_newest_first_and_limited(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    wb = await make_wordbook(client, token)
    await make_words(client, token, wb, 4)
    for _ in range(2):
        created = (await create_quiz(client, token, {"wordbook_id": wb})).json()
        answers = correct_answers(await load_session(created["session_id"]))
        assert (await submit(client, token, created["session_id"], answers)).status_code == 200

    response = await client.get("/api/study/logs", params={"limit": 5}, headers=auth_headers(token))
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 5  # 전체 8건 중 limit 5
    stamps = [item["created_at"] for item in items]
    assert stamps == sorted(stamps, reverse=True)
    assert all(item["created_at"].endswith("Z") for item in items)
    assert all(item["is_correct"] is True for item in items)


@pytest.mark.asyncio
async def test_logs_are_scoped_to_the_requesting_user(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    _, other = await signup_and_login(client)
    wb = await make_wordbook(client, token)
    await make_words(client, token, wb, 4)
    created = (await create_quiz(client, token, {"wordbook_id": wb})).json()
    await submit(client, token, created["session_id"], correct_answers(await load_session(created["session_id"])))

    response = await client.get("/api/study/logs", headers=auth_headers(other))
    assert response.status_code == 200
    assert response.json()["items"] == []


@pytest.mark.asyncio
async def test_study_endpoints_require_login(client: httpx.AsyncClient) -> None:
    assert (await client.get("/api/study/flashcards", params={"bookmarked": "true"})).status_code == 401
    assert (await client.post("/api/study/quiz/sessions", json={"bookmarks": True})).status_code == 401
    assert (await client.post("/api/study/quiz/sessions/1/submit", json={"answers": [{"question_id": 0, "choice_index": 0}]})).status_code == 401
    assert (await client.get("/api/study/logs")).status_code == 401
