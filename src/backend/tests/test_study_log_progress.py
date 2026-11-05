# 2026-11-05 - voda-voca - 답 기록의 단일 진입점 테스트: study_logs 와 user_word_progress 를 함께 갱신 (이슈 #15, #17)
# 파일 위치: src/backend/tests/test_study_log_progress.py

import asyncio
from datetime import datetime, timedelta

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import func, select

from backend.db.session import get_session_factory
from backend.main import app
from backend.models import StudyLog, UserWordProgress
from backend.services.progress import ProgressState
from backend.services.study_log import record_result
from backend.tests.helpers import auth_headers, signup_and_login
from backend.tests.test_quiz_answers_api import answer, start_quiz
from backend.tests.test_study_api import _user_id_for_token, create_quiz, load_session, make_vocab, make_words, submit

T0 = datetime(2026, 11, 5, 9, 0, 0)


@pytest_asyncio.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def record(user_id: int, word_id: int, is_correct: bool, minutes: int = 0, mode: str = "quiz") -> ProgressState:
    async with get_session_factory()() as db:
        state = await record_result(db, user_id, word_id, is_correct, T0 + timedelta(minutes=minutes), mode)
        await db.commit()
        return state


async def progress_row(user_id: int, word_id: int) -> UserWordProgress | None:
    async with get_session_factory()() as db:
        return (
            await db.execute(
                select(UserWordProgress).where(UserWordProgress.user_id == user_id, UserWordProgress.word_id == word_id)
            )
        ).scalar_one_or_none()


async def setup(client):
    nickname, token = await signup_and_login(client)
    user_id = await _user_id_for_token(client, token)
    vocab = await make_vocab(client, token)
    words = list(await make_words(client, token, vocab, 4))
    return token, user_id, vocab, words


@pytest.mark.asyncio
async def test_first_correct_answer_creates_progress_and_log(client) -> None:
    _, user_id, _, words = await setup(client)
    state = await record(user_id, words[0], True)

    assert (state.correct_count, state.consecutive_correct_count, state.is_memorized) == (1, 1, False)
    row = await progress_row(user_id, words[0])
    assert row is not None
    assert (row.correct_count, row.wrong_count, row.consecutive_correct_count) == (1, 0, 1)
    assert row.last_result == "CORRECT" and row.last_studied_at == T0 and row.is_memorized is False
    async with get_session_factory()() as db:
        logs = (await db.execute(select(StudyLog).where(StudyLog.user_id == user_id))).scalars().all()
    assert len(logs) == 1 and logs[0].is_correct is True and logs[0].mode == "quiz"


@pytest.mark.asyncio
async def test_three_correct_in_a_row_memorize_and_a_wrong_answer_resets(client) -> None:
    _, user_id, _, words = await setup(client)
    word = words[0]
    for minute in range(3):
        await record(user_id, word, True, minute)
    row = await progress_row(user_id, word)
    assert row.is_memorized is True and row.consecutive_correct_count == 3

    await record(user_id, word, False, 10)
    row = await progress_row(user_id, word)
    assert row.is_memorized is False and row.consecutive_correct_count == 0
    assert (row.correct_count, row.wrong_count, row.last_result) == (3, 1, "WRONG")


@pytest.mark.asyncio
async def test_flashcard_mode_is_stored_on_the_log(client) -> None:
    _, user_id, _, words = await setup(client)
    await record(user_id, words[0], False, mode="flashcard")
    async with get_session_factory()() as db:
        mode = await db.scalar(select(StudyLog.mode).where(StudyLog.user_id == user_id))
    assert mode == "flashcard"


@pytest.mark.asyncio
async def test_progress_is_kept_per_user_and_per_word(client) -> None:
    _, user_a, _, words = await setup(client)
    _, token_b = await signup_and_login(client)
    user_b = await _user_id_for_token(client, token_b)

    await record(user_a, words[0], True)
    await record(user_b, words[0], False)
    await record(user_a, words[1], True)

    assert (await progress_row(user_a, words[0])).correct_count == 1
    assert (await progress_row(user_b, words[0])).wrong_count == 1
    assert (await progress_row(user_a, words[1])).correct_count == 1
    assert await progress_row(user_b, words[1]) is None


@pytest.mark.asyncio
async def test_concurrent_first_answers_create_one_row_and_count_every_answer(client) -> None:
    _, user_id, _, words = await setup(client)
    await asyncio.gather(*(record(user_id, words[0], True, minute) for minute in range(5)))

    async with get_session_factory()() as db:
        rows = await db.scalar(
            select(func.count()).select_from(UserWordProgress).where(UserWordProgress.user_id == user_id)
        )
    assert rows == 1
    row = await progress_row(user_id, words[0])
    assert (row.correct_count, row.consecutive_correct_count, row.is_memorized) == (5, 5, True)


# --- 옛 퀴즈 경로도 같은 함수를 거친다 ---


@pytest.mark.asyncio
async def test_legacy_quiz_answer_updates_progress(client) -> None:
    _, token = await signup_and_login(client)
    created, words = await start_quiz(client, token)
    user_id = await _user_id_for_token(client, token)
    question = created["questions"][0]
    word_id = (await load_session(created["session_id"])).questions[0]["word_id"]

    await answer(client, token, created["session_id"], question["question_id"], (question["correct_index"] + 1) % 4)

    row = await progress_row(user_id, word_id)
    assert row is not None and (row.wrong_count, row.last_result) == (1, "WRONG")
    assert word_id in words


@pytest.mark.asyncio
async def test_resending_the_same_answer_does_not_count_twice(client) -> None:
    _, token = await signup_and_login(client)
    created, _ = await start_quiz(client, token)
    user_id = await _user_id_for_token(client, token)
    question = created["questions"][0]
    word_id = (await load_session(created["session_id"])).questions[0]["word_id"]

    for _ in range(3):
        await answer(client, token, created["session_id"], question["question_id"], question["correct_index"])

    assert (await progress_row(user_id, word_id)).correct_count == 1


@pytest.mark.asyncio
async def test_legacy_submit_updates_progress_for_unrecorded_answers(client) -> None:
    _, token = await signup_and_login(client)
    user_id = await _user_id_for_token(client, token)
    vocab = await make_vocab(client, token)
    await make_words(client, token, vocab, 4)
    created = (await create_quiz(client, token, {"vocabulary_id": vocab})).json()
    session = await load_session(created["session_id"])
    answers = [{"question_id": q["question_id"], "choice_index": q["correct_index"]} for q in session.questions]

    response = await submit(client, token, created["session_id"], answers)

    assert response.status_code == 200, response.text
    for question in session.questions:
        row = await progress_row(user_id, question["word_id"])
        assert row is not None and row.correct_count == 1
