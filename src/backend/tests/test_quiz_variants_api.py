# 2026-11-25 - voda-voca - 출제 방향·형식 API 통합 테스트: 한→영, OX, 섞기, 이력 컬럼 (VOCA-FR-023, 024, 026)
# 파일 위치: src/backend/tests/test_quiz_variants_api.py

from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import select

from backend.db.session import get_session_factory
from backend.main import app
from backend.models import StudyLog
from backend.routers import study_session as session_router
from backend.tests.helpers import auth_headers
from backend.tests.test_learning_session_api import NOW, answer, create, key_of, start, stored_session


@pytest_asyncio.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(session_router, "_now", lambda: NOW)


async def logs_of(user_id: int) -> list[StudyLog]:
    async with get_session_factory()() as db:
        return list((await db.execute(select(StudyLog).where(StudyLog.user_id == user_id).order_by(StudyLog.id))).scalars())


# --- 기본값과 검증 ---


@pytest.mark.asyncio
async def test_default_is_en_to_ko_choice_and_items_describe_it(client, make_vocabulary) -> None:
    _, _, _, response = await start(client, make_vocabulary, count=5)
    assert response.status_code == 201, response.text
    for item in response.json()["items"]:
        assert (item["direction"], item["format"]) == ("en_to_ko", "choice")
        assert item["prompt"] == item["term"]
        assert item["proposed"] is None
        assert len(item["options"]) == 4


@pytest.mark.asyncio
async def test_invalid_direction_or_format_is_422(client, make_vocabulary) -> None:
    token, *_ = await start(client, make_vocabulary, count=5)
    for bad in ({"direction": "up"}, {"format": "short"}, {"direction": None}, {"format": None}):
        assert (await create(client, token, **bad)).status_code == 422, bad


@pytest.mark.asyncio
async def test_session_row_stores_the_requested_direction_and_format(client, make_vocabulary) -> None:
    _, _, _, response = await start(client, make_vocabulary, count=5, direction="mixed", format="ox")
    row = await stored_session(response.json()["session_id"])
    assert (row.direction, row.format) == ("mixed", "ox")


# --- 한→영 4지선다 ---


@pytest.mark.asyncio
async def test_ko_to_en_choice_hides_the_term_and_grades_by_term(client, make_vocabulary) -> None:
    token, user_id, _, response = await start(client, make_vocabulary, count=5, direction="ko_to_en")
    body = response.json()
    session = await stored_session(body["session_id"])
    for item in body["items"]:
        assert item["term"] is None, "한→영 문제에서 정답인 영단어를 미리 보내면 안 된다"
        assert item["prompt"].endswith("의 뜻")
        assert all(not option.endswith("의 뜻") for option in item["options"])
        assert item["direction"] == "ko_to_en"
        assert item["context"] is None, "예문에는 정답 단어가 들어 있으므로 풀기 전에는 보내지 않는다"
    first = body["items"][0]
    key = key_of(session, first["question_id"])
    result = await answer(client, token, body["session_id"], question_id=first["question_id"], choice_index=key["correct_index"])
    assert result.status_code == 200, result.text
    out = result.json()
    assert out["is_correct"] is True
    assert out["term"] == key["term"] and out["meaning"] == f"{key['term']}의 뜻"
    logs = await logs_of(user_id)
    assert (logs[0].direction, logs[0].format) == ("ko_to_en", "choice")


# --- OX ---


@pytest.mark.asyncio
async def test_ox_items_and_grading(client, make_vocabulary) -> None:
    token, user_id, _, response = await start(client, make_vocabulary, count=8, format="ox")
    body = response.json()
    session = await stored_session(body["session_id"])
    for item in body["items"]:
        assert item["options"] == ["O", "X"]
        assert item["proposed"] is not None
        assert item["format"] == "ox"
    right, wrong = body["items"][0], body["items"][1]
    key_r, key_w = key_of(session, right["question_id"]), key_of(session, wrong["question_id"])
    ok = await answer(client, token, body["session_id"], question_id=right["question_id"], choice_index=key_r["correct_index"])
    bad = await answer(client, token, body["session_id"], question_id=wrong["question_id"], choice_index=1 - key_w["correct_index"])
    assert ok.json()["is_correct"] is True and bad.json()["is_correct"] is False
    assert ok.json()["meaning"] == f"{key_r['term']}의 뜻"  # OX 도 정답 뜻을 해설로 준다
    assert [(log.format, log.is_correct) for log in await logs_of(user_id)] == [("ox", True), ("ox", False)]


@pytest.mark.asyncio
async def test_ox_rejects_choice_index_beyond_two(client, make_vocabulary) -> None:
    token, user_id, _, response = await start(client, make_vocabulary, count=5, format="ox")
    body = response.json()
    result = await answer(client, token, body["session_id"], question_id=0, choice_index=2)
    assert result.status_code == 400
    assert result.headers["X-Error-Code"] == "QUIZ_ANSWER_INVALID"
    assert await logs_of(user_id) == []


@pytest.mark.asyncio
async def test_ox_ko_to_en_proposes_an_english_term(client, make_vocabulary) -> None:
    _, _, _, response = await start(client, make_vocabulary, count=6, direction="ko_to_en", format="ox")
    for item in response.json()["items"]:
        assert item["term"] is None and item["prompt"].endswith("의 뜻")
        assert not item["proposed"].endswith("의 뜻")


# --- 섞기 ---


@pytest.mark.asyncio
async def test_mixed_direction_logs_the_actual_direction_per_question(client, make_vocabulary) -> None:
    token, user_id, _, response = await start(client, make_vocabulary, n_words=30, count=30, direction="mixed")
    body = response.json()
    session = await stored_session(body["session_id"])
    assert {i["direction"] for i in body["items"]} == {"en_to_ko", "ko_to_en"}
    for item in body["items"]:
        key = key_of(session, item["question_id"])
        await answer(client, token, body["session_id"], question_id=item["question_id"], choice_index=key["correct_index"])
    logged = {log.direction for log in await logs_of(user_id)}
    assert logged == {"en_to_ko", "ko_to_en"}, "mixed 가 아니라 실제 방향이 기록돼야 한다"


# --- 플래시카드와 복습 ---


@pytest.mark.asyncio
async def test_flashcard_ignores_direction_and_format(client, make_vocabulary) -> None:
    _, _, _, response = await start(client, make_vocabulary, n_words=5, mode="flashcard", direction="ko_to_en", format="ox")
    assert response.status_code == 201
    item = response.json()["items"][0]
    assert item["term"] is not None and item["options"] is None


@pytest.mark.asyncio
async def test_bookmark_review_session_accepts_direction_and_format(client, make_vocabulary) -> None:
    token, _, _, response = await start(client, make_vocabulary, count=10)
    for item in response.json()["items"][:5]:
        await client.put(f"/api/bookmarks/{item['word_id']}", headers=auth_headers(token))
    review = await create(client, token, source="bookmarks", direction="ko_to_en", format="ox", count=5)
    assert review.status_code == 201, review.text
    assert all(i["format"] == "ox" and i["term"] is None for i in review.json()["items"])
