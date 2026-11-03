# 2026-11-03 - voda-voca - 퀴즈 문항별 즉시 기록 API 통합 테스트 (실제 MySQL): 답 기록, 멱등·잠금, 슬라이딩 만료, 부분 완료, 세션 상세 조회 (이슈 #8)
# 파일 위치: src/backend/tests/test_quiz_answers_api.py

from collections.abc import AsyncIterator
from datetime import timedelta

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import select

from backend.db.session import get_session_factory
from backend.main import app
from backend.models import StudyLog
from backend.models.base import utcnow
from backend.routers import study as study_router
from backend.tests.helpers import auth_headers, signup_and_login
from backend.tests.test_study_api import (
    correct_answers,
    create_quiz,
    load_session,
    make_wordbook,
    make_words,
    study_log_count,
    submit,
)


@pytest_asyncio.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def start_quiz(client: httpx.AsyncClient, token: str, count: int = 4) -> tuple[dict, dict[int, str]]:
    """단어 4개짜리 단어장으로 퀴즈를 출제한다. (출제 응답, {word_id: 뜻}) 를 돌려준다."""
    wb = await make_wordbook(client, token)
    words = await make_words(client, token, wb, 4)
    response = await create_quiz(client, token, {"wordbook_id": wb, "count": count})
    assert response.status_code == 201, response.text
    return response.json(), words


async def answer(
    client: httpx.AsyncClient, token: str, session_id: int, question_id: int, choice_index: int
) -> httpx.Response:
    return await client.post(
        f"/api/study/quiz/sessions/{session_id}/answers",
        json={"question_id": question_id, "choice_index": choice_index},
        headers=auth_headers(token),
    )


async def logs_of(word_ids: set[int]) -> list[StudyLog]:
    async with get_session_factory()() as db:
        rows = await db.execute(select(StudyLog).where(StudyLog.word_id.in_(word_ids)).order_by(StudyLog.id))
        return list(rows.scalars().all())


def wrong_choice(question: dict) -> int:
    return (question["correct_index"] + 1) % 4


# --- 문항별 기록 ---


@pytest.mark.asyncio
async def test_answer_is_recorded_immediately_without_finishing(client: httpx.AsyncClient) -> None:
    """한 문항만 풀고 떠나도 그 답은 학습 이력에 남는다 (이슈 #8 의 핵심)."""
    _, token = await signup_and_login(client)
    created, words = await start_quiz(client, token)
    question = created["questions"][0]

    response = await answer(client, token, created["session_id"], question["question_id"], question["correct_index"])

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["is_correct"] is True
    assert body["selected_index"] == question["correct_index"]
    logs = await logs_of(set(words))
    assert len(logs) == 1 and logs[0].is_correct is True
    stored = await load_session(created["session_id"])
    assert stored.answers == {str(question["question_id"]): question["correct_index"]}
    assert stored.is_submitted is False, "답을 기록했다고 퀴즈가 끝난 것은 아니다"


@pytest.mark.asyncio
async def test_wrong_answer_is_recorded_as_incorrect(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    created, words = await start_quiz(client, token)
    question = created["questions"][0]

    response = await answer(client, token, created["session_id"], question["question_id"], wrong_choice(question))

    assert response.status_code == 200
    assert response.json()["is_correct"] is False
    assert [log.is_correct for log in await logs_of(set(words))] == [False]


@pytest.mark.asyncio
async def test_same_answer_again_is_idempotent(client: httpx.AsyncClient) -> None:
    """네트워크 재시도로 같은 답이 다시 와도 이력이 중복되지 않는다."""
    _, token = await signup_and_login(client)
    created, words = await start_quiz(client, token)
    question = created["questions"][0]
    args = (client, token, created["session_id"], question["question_id"], question["correct_index"])

    first = await answer(*args)
    second = await answer(*args)

    assert first.status_code == second.status_code == 200
    assert second.json()["is_correct"] is True
    assert len(await logs_of(set(words))) == 1


@pytest.mark.asyncio
async def test_different_answer_for_same_question_is_locked(client: httpx.AsyncClient) -> None:
    """화면은 한 번 고른 답을 잠근다. 서버도 같은 규칙으로 바꾸기를 거부한다."""
    _, token = await signup_and_login(client)
    created, words = await start_quiz(client, token)
    question = created["questions"][0]
    sid, qid = created["session_id"], question["question_id"]
    await answer(client, token, sid, qid, question["correct_index"])

    response = await answer(client, token, sid, qid, wrong_choice(question))

    assert response.status_code == 409
    assert response.headers["X-Error-Code"] == "QUIZ_ANSWER_LOCKED"
    assert [log.is_correct for log in await logs_of(set(words))] == [True]
    assert (await load_session(sid)).answers == {str(qid): question["correct_index"]}


@pytest.mark.asyncio
async def test_unknown_question_is_400_and_bad_choice_is_422(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    created, words = await start_quiz(client, token)

    unknown = await answer(client, token, created["session_id"], 99, 0)
    out_of_range = await answer(client, token, created["session_id"], 0, 4)

    assert unknown.status_code == 400
    assert unknown.headers["X-Error-Code"] == "QUIZ_ANSWER_INVALID"
    assert out_of_range.status_code == 422
    assert await logs_of(set(words)) == []


@pytest.mark.asyncio
async def test_answer_other_users_session_is_404_and_requires_login(client: httpx.AsyncClient) -> None:
    _, owner = await signup_and_login(client)
    _, intruder = await signup_and_login(client)
    created, words = await start_quiz(client, owner)

    stolen = await answer(client, intruder, created["session_id"], 0, 0)
    anonymous = await client.post(
        f"/api/study/quiz/sessions/{created['session_id']}/answers", json={"question_id": 0, "choice_index": 0}
    )

    assert stolen.status_code == 404
    assert anonymous.status_code == 401
    assert await logs_of(set(words)) == []


@pytest.mark.asyncio
async def test_answer_after_finishing_is_409(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    created, words = await start_quiz(client, token)
    finished = await submit(client, token, created["session_id"], [])
    assert finished.status_code == 200, finished.text

    response = await answer(client, token, created["session_id"], 0, 0)

    assert response.status_code == 409
    assert response.headers["X-Error-Code"] == "QUIZ_ALREADY_SUBMITTED"
    assert await logs_of(set(words)) == []


@pytest.mark.asyncio
async def test_deleted_word_blocks_only_that_answer(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    created, words = await start_quiz(client, token)
    victim = created["questions"][0]
    wordbook_id = (await load_session(created["session_id"])).wordbook_id
    deleted = await client.delete(
        f"/api/wordbooks/{wordbook_id}/words/{victim_word_id(await load_session(created['session_id']), victim)}",
        headers=auth_headers(token),
    )
    assert deleted.status_code == 204

    blocked = await answer(client, token, created["session_id"], victim["question_id"], 0)
    other = created["questions"][1]
    fine = await answer(client, token, created["session_id"], other["question_id"], other["correct_index"])

    assert blocked.status_code == 409
    assert blocked.headers["X-Error-Code"] == "QUIZ_WORD_MISSING"
    assert fine.status_code == 200, "삭제되지 않은 단어의 답은 계속 기록할 수 있다"


def victim_word_id(session, question: dict) -> int:
    return next(q["word_id"] for q in session.questions if q["question_id"] == question["question_id"])


# --- 만료 (마지막 응답 후 30분) ---


@pytest.mark.asyncio
async def test_answer_after_expiry_is_400_and_not_recorded(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, token = await signup_and_login(client)
    created, words = await start_quiz(client, token)
    later = utcnow() + timedelta(minutes=31)
    monkeypatch.setattr(study_router, "_now", lambda: later)

    response = await answer(client, token, created["session_id"], 0, 0)

    assert response.status_code == 400
    assert response.headers["X-Error-Code"] == "QUIZ_EXPIRED"
    assert await logs_of(set(words)) == []


@pytest.mark.asyncio
async def test_each_new_answer_extends_expiry_by_30_minutes(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """출제 후 20분에 답하면 마감이 그 시각 + 30분으로 밀린다. 그래서 출제 후 45분에도 이어 풀 수 있다."""
    _, token = await signup_and_login(client)
    created, words = await start_quiz(client, token)
    q0, q1 = created["questions"][0], created["questions"][1]
    t20 = utcnow() + timedelta(minutes=20)
    monkeypatch.setattr(study_router, "_now", lambda: t20)
    first = await answer(client, token, created["session_id"], q0["question_id"], q0["correct_index"])
    assert first.status_code == 200

    stored = await load_session(created["session_id"])
    assert stored.expires_at >= t20 + timedelta(minutes=29, seconds=59)

    t45 = utcnow() + timedelta(minutes=45)
    monkeypatch.setattr(study_router, "_now", lambda: t45)
    second = await answer(client, token, created["session_id"], q1["question_id"], q1["correct_index"])
    assert second.status_code == 200, "원래 마감(30분)을 지나도 마지막 응답 후 30분 안이면 계속 풀 수 있다"
    assert len(await logs_of(set(words))) == 2


# --- 완료(제출) ---


@pytest.mark.asyncio
async def test_finish_with_partial_answers_summarizes_only_answered(client: httpx.AsyncClient) -> None:
    """일부만 풀고 끝내도 된다. 요약은 푼 문항 기준이다."""
    _, token = await signup_and_login(client)
    created, words = await start_quiz(client, token)
    q0, q1 = created["questions"][0], created["questions"][1]
    sid = created["session_id"]
    await answer(client, token, sid, q0["question_id"], q0["correct_index"])
    await answer(client, token, sid, q1["question_id"], wrong_choice(q1))

    response = await submit(client, token, sid, [])

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["total"], body["answered"], body["correct_count"]) == (4, 2, 1)
    assert body["accuracy"] == 50.0
    assert [item["term"] for item in body["wrong_items"]] == [q1["term"]]
    assert (await load_session(sid)).is_submitted is True
    assert len(await logs_of(set(words))) == 2


@pytest.mark.asyncio
async def test_finish_with_no_answers_at_all_is_allowed(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    created, words = await start_quiz(client, token)

    response = await client.post(
        f"/api/study/quiz/sessions/{created['session_id']}/submit", json={}, headers=auth_headers(token)
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["total"], body["answered"], body["correct_count"], body["accuracy"]) == (4, 0, 0, 0.0)
    assert await logs_of(set(words)) == []


@pytest.mark.asyncio
async def test_finish_with_full_payload_does_not_duplicate_recorded_answers(client: httpx.AsyncClient) -> None:
    """이전 방식(마지막에 전체 제출)도 계속 동작한다. 이미 기록된 답은 다시 쓰지 않는다."""
    _, token = await signup_and_login(client)
    created, words = await start_quiz(client, token)
    sid = created["session_id"]
    q0 = created["questions"][0]
    await answer(client, token, sid, q0["question_id"], q0["correct_index"])
    before = await study_log_count()

    response = await submit(client, token, sid, correct_answers(await load_session(sid)))

    assert response.status_code == 200, response.text
    assert response.json()["answered"] == 4
    assert await study_log_count() == before + 3, "기록된 1건은 건너뛰고 나머지 3건만 새로 쓴다"
    assert len(await logs_of(set(words))) == 4


@pytest.mark.asyncio
async def test_finish_keeps_the_recorded_answer_when_payload_disagrees(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    created, words = await start_quiz(client, token)
    sid = created["session_id"]
    q0 = created["questions"][0]
    await answer(client, token, sid, q0["question_id"], q0["correct_index"])
    payload = correct_answers(await load_session(sid))
    payload[0] = {"question_id": q0["question_id"], "choice_index": wrong_choice(q0)}

    response = await submit(client, token, sid, payload)

    assert response.status_code == 200
    assert response.json()["correct_count"] == 4, "서버에 기록된 답이 우선한다"


# --- 세션 상세 조회 (결과 다시 보기) ---


@pytest.mark.asyncio
async def test_session_detail_shows_answers_and_summary(client: httpx.AsyncClient) -> None:
    _, token = await signup_and_login(client)
    created, _ = await start_quiz(client, token)
    sid = created["session_id"]
    q0, q1 = created["questions"][0], created["questions"][1]
    await answer(client, token, sid, q0["question_id"], q0["correct_index"])
    await answer(client, token, sid, q1["question_id"], wrong_choice(q1))
    await submit(client, token, sid, [])

    response = await client.get(f"/api/study/quiz/sessions/{sid}", headers=auth_headers(token))

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["is_submitted"] is True
    assert (body["total"], body["answered"], body["correct_count"], body["accuracy"]) == (4, 2, 1, 50.0)
    items = {item["question_id"]: item for item in body["items"]}
    assert items[q0["question_id"]]["selected_index"] == q0["correct_index"]
    assert items[q0["question_id"]]["is_correct"] is True
    assert items[q1["question_id"]]["selected_index"] == wrong_choice(q1)
    assert items[q1["question_id"]]["is_correct"] is False
    unanswered = [i for i in body["items"] if i["question_id"] not in (q0["question_id"], q1["question_id"])]
    assert len(unanswered) == 2
    assert all(i["selected_index"] is None and i["is_correct"] is None for i in unanswered)
    assert all({"term", "choices", "correct_index", "word_id"} <= i.keys() for i in body["items"])


@pytest.mark.asyncio
async def test_session_detail_is_private_to_the_owner(client: httpx.AsyncClient) -> None:
    _, owner = await signup_and_login(client)
    _, intruder = await signup_and_login(client)
    created, _ = await start_quiz(client, owner)
    path = f"/api/study/quiz/sessions/{created['session_id']}"

    assert (await client.get(path, headers=auth_headers(intruder))).status_code == 404
    assert (await client.get(path)).status_code == 401
    assert (await client.get("/api/study/quiz/sessions/999999999", headers=auth_headers(owner))).status_code == 404
