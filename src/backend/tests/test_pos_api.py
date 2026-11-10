# 2026-11-10 - voda-voca - 품사(pos) API 통합 테스트 (실제 MySQL): 단어 목록, 퀴즈·플래시카드 출제, 채점 응답, 옛 세션 호환 (v2.2 품사 노출)
# 파일 위치: src/backend/tests/test_pos_api.py

from collections.abc import AsyncIterator
from datetime import datetime

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.orm.attributes import flag_modified

from backend.db.session import get_session_factory
from backend.main import app
from backend.models import QuizSession
from backend.routers import study_session as session_router
from backend.tests.helpers import auth_headers, signup_and_login

NOW = datetime(2026, 11, 10, 9, 0, 0)

# 품사는 퀴즈 문제 화면에서도 보인다 (발음기호와 달리 채점 전 노출을 막지 않는다). 일부 단어는 품사가 없다.
POS = {"apple": "noun", "banana": "noun", "cherry": "adjective", "date": "verb", "elder": "adjective", "fig": "noun"}
TERMS = ["apple", "banana", "cherry", "date", "elder", "fig", "grape", "honey"]  # grape, honey 는 품사 없음


@pytest_asyncio.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(session_router, "_now", lambda: NOW)


async def setup(client, make_vocabulary):
    vocab = await make_vocabulary(TERMS, title="품사 테스트", parts_of_speech=POS)
    _, token = await signup_and_login(client)
    response = await client.post("/api/users/me/active-vocabulary", json={"vocabulary_id": vocab.id}, headers=auth_headers(token))
    assert response.status_code == 200, response.text
    return token, vocab


async def create(client, token, **body) -> httpx.Response:
    return await client.post("/api/study/sessions", json=body, headers=auth_headers(token))


async def answer(client, token, session_id: int, **body) -> httpx.Response:
    return await client.post(f"/api/study/sessions/{session_id}/answer", json=body, headers=auth_headers(token))


@pytest.mark.asyncio
async def test_word_list_returns_pos_or_null(client, make_vocabulary) -> None:
    token, vocab = await setup(client, make_vocabulary)
    response = await client.get(f"/api/vocabularies/{vocab.id}/words", params={"size": 20}, headers=auth_headers(token))
    by_term = {i["term"]: i for i in response.json()["items"]}
    assert by_term["apple"]["pos"] == "noun" and by_term["date"]["pos"] == "verb"
    assert "pos" in by_term["grape"] and by_term["grape"]["pos"] is None


@pytest.mark.asyncio
async def test_quiz_items_carry_pos_on_the_question_screen(client, make_vocabulary) -> None:
    token, _ = await setup(client, make_vocabulary)
    items = (await create(client, token, mode="quiz", count=8)).json()["items"]
    assert {i["term"]: i["pos"] for i in items} == {t: POS.get(t) for t in TERMS}


@pytest.mark.asyncio
async def test_flashcard_items_carry_pos(client, make_vocabulary) -> None:
    token, _ = await setup(client, make_vocabulary)
    items = (await create(client, token, mode="flashcard", count=8)).json()["items"]
    assert {i["term"]: i["pos"] for i in items} == {t: POS.get(t) for t in TERMS}


@pytest.mark.asyncio
@pytest.mark.parametrize("mode,body", [("quiz", {"choice_index": 0}), ("flashcard", {"known": True})])
async def test_answer_response_carries_pos_and_is_stable_on_resend(client, make_vocabulary, mode: str, body: dict) -> None:
    token, _ = await setup(client, make_vocabulary)
    created = (await create(client, token, mode=mode, count=8)).json()
    item = created["items"][0]
    first = await answer(client, token, created["session_id"], question_id=item["question_id"], **body)
    again = await answer(client, token, created["session_id"], question_id=item["question_id"], **body)
    assert first.json()["pos"] == POS.get(item["term"]) == again.json()["pos"]


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["quiz", "flashcard"])
async def test_old_sessions_without_the_snapshot_key_return_null_pos(client, make_vocabulary, mode: str) -> None:
    token, _ = await setup(client, make_vocabulary)
    created = (await create(client, token, mode=mode, count=8)).json()
    async with get_session_factory()() as db:
        row = await db.get(QuizSession, created["session_id"])
        for question in row.questions:
            question.pop("pos", None)
        flag_modified(row, "questions")
        await db.commit()
    body = {"choice_index": 0} if mode == "quiz" else {"known": True}
    response = await answer(client, token, created["session_id"], question_id=0, **body)
    assert response.status_code == 200 and response.json()["pos"] is None
