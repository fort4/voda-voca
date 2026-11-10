# 2026-11-05 - voda-voca - 발음기호(phonetic) API 통합 테스트 (실제 MySQL): 단어 목록, 퀴즈 출제 비노출, 플래시카드 뒷면, 채점 응답, 옛 세션 호환 (v2.2)
# 파일 위치: src/backend/tests/test_phonetic_api.py

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

NOW = datetime(2026, 11, 5, 9, 0, 0)

# 모든 단어에 발음기호를 준다. 퀴즈 출제 응답 어디에도 이 값이 새어 나가면 안 된다.
IPA = {
    "apple": "ˈæpəl",
    "banana": "bəˈnænə",
    "cherry": "ˈtʃɛri",
    "date": "deɪt",
    "elder": "ˈɛldər",
    "fig": "fɪɡ",
    "grape": "ɡreɪp",
    "honey": "ˈhʌni",
}
TERMS = list(IPA)


@pytest_asyncio.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(session_router, "_now", lambda: NOW)


async def setup(client, make_vocabulary, phonetics=IPA, terms=TERMS):
    vocab = await make_vocabulary(terms, title="발음 테스트", phonetics=phonetics)
    _, token = await signup_and_login(client)
    response = await client.post("/api/users/me/active-vocabulary", json={"vocabulary_id": vocab.id}, headers=auth_headers(token))
    assert response.status_code == 200, response.text
    return token, vocab


async def create(client, token, **body) -> httpx.Response:
    return await client.post("/api/study/sessions", json=body, headers=auth_headers(token))


async def answer(client, token, session_id: int, **body) -> httpx.Response:
    return await client.post(f"/api/study/sessions/{session_id}/answer", json=body, headers=auth_headers(token))


async def stored(session_id: int) -> QuizSession:
    async with get_session_factory()() as db:
        row = await db.get(QuizSession, session_id)
        assert row is not None
        return row


def only_ipa(text: str) -> bool:
    return any(value in text for value in IPA.values())


# --- 단어 목록 (해설과 별개로 읽기 전용 조회) ---


@pytest.mark.asyncio
async def test_word_list_returns_phonetic_or_null(client, make_vocabulary) -> None:
    token, vocab = await setup(client, make_vocabulary, phonetics={"apple": IPA["apple"]}, terms=["apple", "banana"])
    response = await client.get(f"/api/vocabularies/{vocab.id}/words", headers=auth_headers(token))
    assert response.status_code == 200, response.text
    by_term = {item["term"]: item for item in response.json()["items"]}
    assert by_term["apple"]["phonetic"] == IPA["apple"]
    assert "phonetic" in by_term["banana"] and by_term["banana"]["phonetic"] is None


# --- 퀴즈 출제: 발음기호 비노출 ---


@pytest.mark.asyncio
async def test_quiz_questions_never_carry_phonetic(client, make_vocabulary) -> None:
    token, _ = await setup(client, make_vocabulary)
    response = await create(client, token, mode="quiz")
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["items"], "문항이 있어야 의미 있는 검사다"
    for item in body["items"]:
        assert "phonetic" in item and item["phonetic"] is None, "필드는 있되 항상 null (meaning 등과 같은 패턴)"
    assert not only_ipa(response.text), "응답 어디에도 발음기호 값이 없어야 한다"


@pytest.mark.asyncio
async def test_quiz_snapshot_keeps_phonetic_for_grading_only(client, make_vocabulary) -> None:
    token, _ = await setup(client, make_vocabulary)
    session_id = (await create(client, token, mode="quiz")).json()["session_id"]
    row = await stored(session_id)
    assert {q["term"]: q["phonetic"] for q in row.questions} == {q["term"]: IPA[q["term"]] for q in row.questions}


# --- 플래시카드: 뒷면 정보로 함께 내려간다 ---


@pytest.mark.asyncio
async def test_flashcard_items_carry_phonetic_on_the_back(client, make_vocabulary) -> None:
    token, _ = await setup(client, make_vocabulary, phonetics={"apple": IPA["apple"]}, terms=["apple", "banana"])
    response = await create(client, token, mode="flashcard")
    assert response.status_code == 201, response.text
    by_term = {item["term"]: item for item in response.json()["items"]}
    assert by_term["apple"]["phonetic"] == IPA["apple"]
    assert by_term["banana"]["phonetic"] is None


# --- 채점 응답: 퀴즈와 플래시카드 모두 ---


@pytest.mark.asyncio
async def test_quiz_answer_response_carries_phonetic_for_right_and_wrong_choices(client, make_vocabulary) -> None:
    token, _ = await setup(client, make_vocabulary)
    created = (await create(client, token, mode="quiz")).json()
    row = await stored(created["session_id"])
    for item in created["items"][:2]:
        key = next(q for q in row.questions if q["question_id"] == item["question_id"])
        wrong = (key["correct_index"] + 1) % 4 if item is created["items"][0] else key["correct_index"]
        response = await answer(client, token, created["session_id"], question_id=item["question_id"], choice_index=wrong)
        assert response.status_code == 200, response.text
        assert response.json()["phonetic"] == IPA[item["term"]]


@pytest.mark.asyncio
async def test_flashcard_answer_response_carries_phonetic(client, make_vocabulary) -> None:
    token, _ = await setup(client, make_vocabulary)
    created = (await create(client, token, mode="flashcard")).json()
    item = created["items"][0]
    response = await answer(client, token, created["session_id"], question_id=item["question_id"], known=True)
    assert response.status_code == 200, response.text
    assert response.json()["phonetic"] == IPA[item["term"]]


@pytest.mark.asyncio
async def test_resending_the_same_answer_returns_the_same_phonetic(client, make_vocabulary) -> None:
    token, _ = await setup(client, make_vocabulary)
    created = (await create(client, token, mode="flashcard")).json()
    item = created["items"][0]
    first = await answer(client, token, created["session_id"], question_id=item["question_id"], known=True)
    again = await answer(client, token, created["session_id"], question_id=item["question_id"], known=True)
    assert first.json()["phonetic"] == again.json()["phonetic"] == IPA[item["term"]]


# --- 옛 세션(스냅샷에 phonetic 키가 없음)도 깨지지 않는다 ---


async def strip_phonetic(session_id: int) -> None:
    async with get_session_factory()() as db:
        row = await db.get(QuizSession, session_id)
        assert row is not None
        for question in row.questions:
            question.pop("phonetic", None)
        flag_modified(row, "questions")
        await db.commit()


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["quiz", "flashcard"])
async def test_old_sessions_without_the_snapshot_key_answer_with_null_phonetic(client, make_vocabulary, mode: str) -> None:
    token, _ = await setup(client, make_vocabulary)
    created = (await create(client, token, mode=mode)).json()
    await strip_phonetic(created["session_id"])
    item = created["items"][0]
    body = {"question_id": item["question_id"], "known": True} if mode == "flashcard" else {"question_id": item["question_id"], "choice_index": 0}
    response = await answer(client, token, created["session_id"], **body)
    assert response.status_code == 200, response.text
    assert response.json()["phonetic"] is None


# --- 복습 세션(북마크)에서도 같은 규칙 ---


async def bookmark_all(client, token, vocab) -> None:
    for word_id in vocab.word_ids.values():
        response = await client.put(f"/api/bookmarks/{word_id}", headers=auth_headers(token))
        assert response.status_code == 204, response.text


@pytest.mark.asyncio
async def test_bookmark_review_sessions_follow_the_same_rules(client, make_vocabulary) -> None:
    token, vocab = await setup(client, make_vocabulary)
    await bookmark_all(client, token, vocab)

    quiz = await create(client, token, mode="quiz", source="bookmarks")
    assert quiz.status_code == 201, quiz.text
    assert all(item["phonetic"] is None for item in quiz.json()["items"])
    assert not only_ipa(quiz.text)

    cards = await create(client, token, mode="flashcard", source="bookmarks")
    assert cards.status_code == 201, cards.text
    assert all(item["phonetic"] == IPA[item["term"]] for item in cards.json()["items"])


# ---------- v2.2 카탈로그 확충: 실제 신규 단어장으로 세션이 돌아가고 발음기호 규칙이 지켜진다 (이슈 #24) ----------


async def _activate_real(client, slug: str):
    _, token = await signup_and_login(client)
    items = (await client.get("/api/vocabularies", headers=auth_headers(token))).json()
    vocab = next(i for i in items if i["slug"] == slug)
    response = await client.post("/api/users/me/active-vocabulary", json={"vocabulary_id": vocab["id"]}, headers=auth_headers(token))
    assert response.status_code == 200, response.text
    return token


@pytest.mark.asyncio
@pytest.mark.parametrize("slug", ["exam-core-200", "business-practical-200"])
async def test_new_vocabulary_quiz_hides_phonetic_but_grading_reveals_it(client, slug: str) -> None:
    token = await _activate_real(client, slug)
    started = (await create(client, token, mode="quiz")).json()
    assert started["total_questions"] == 15
    assert all(item["phonetic"] is None for item in started["items"]), "퀴즈 출제에는 발음기호가 없다"
    graded = (await answer(client, token, started["session_id"], question_id=0, choice_index=0)).json()
    assert graded["phonetic"], "채점 응답에는 발음기호가 있다"


@pytest.mark.asyncio
@pytest.mark.parametrize("slug", ["exam-core-200", "business-practical-200"])
async def test_new_vocabulary_flashcards_carry_phonetic_on_the_back(client, slug: str) -> None:
    token = await _activate_real(client, slug)
    started = (await create(client, token, mode="flashcard")).json()
    assert started["items"] and all(item["phonetic"] for item in started["items"])

