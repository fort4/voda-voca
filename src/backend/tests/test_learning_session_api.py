# 2026-11-05 - voda-voca - 학습 세션 API 통합 테스트 (실제 MySQL): 세션 생성(워터폴 출제), 문항별 채점·진행도 갱신, 퀴즈/플래시카드 모드
# 파일 위치: src/backend/tests/test_learning_session_api.py

from collections.abc import AsyncIterator
from datetime import datetime, timedelta

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import delete, select, update

from backend.db.session import get_session_factory
from backend.main import app
from backend.models import QuizSession, StudyLog, SystemWord, User, UserWordProgress
from backend.routers import study_session as session_router
from backend.tests.helpers import auth_headers, signup_and_login, user_id_for_token

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


async def activate(client: httpx.AsyncClient, token: str, vocabulary_id: int) -> None:
    response = await client.post(
        "/api/users/me/active-vocabulary", json={"vocabulary_id": vocabulary_id}, headers=auth_headers(token)
    )
    assert response.status_code == 200, response.text


async def create(client: httpx.AsyncClient, token: str, **body) -> httpx.Response:
    return await client.post("/api/study/sessions", json=body, headers=auth_headers(token))


async def answer(client: httpx.AsyncClient, token: str, session_id: int, **body) -> httpx.Response:
    return await client.post(f"/api/study/sessions/{session_id}/answer", json=body, headers=auth_headers(token))


async def stored_session(session_id: int) -> QuizSession:
    async with get_session_factory()() as db:
        row = await db.get(QuizSession, session_id)
        assert row is not None
        return row


def key_of(session: QuizSession, question_id: int) -> dict:
    return next(q for q in session.questions if q["question_id"] == question_id)


async def progress_of(user_id: int, word_id: int) -> UserWordProgress | None:
    async with get_session_factory()() as db:
        return (
            await db.execute(
                select(UserWordProgress).where(UserWordProgress.user_id == user_id, UserWordProgress.word_id == word_id)
            )
        ).scalar_one_or_none()


async def put_progress(
    user_id: int, word_id: int, *, last_result: str = "CORRECT", memorized: bool = False, streak: int = 1, minutes: int = 0
) -> None:
    async with get_session_factory()() as db:
        db.add(
            UserWordProgress(
                user_id=user_id,
                word_id=word_id,
                correct_count=streak if last_result == "CORRECT" else 0,
                wrong_count=1 if last_result == "WRONG" else 0,
                consecutive_correct_count=streak if last_result == "CORRECT" else 0,
                is_memorized=memorized,
                last_result=last_result,
                last_studied_at=T0 + timedelta(minutes=minutes),
            )
        )
        await db.commit()


async def start(client, make_vocabulary, n_words=20, **body):
    """단어 n_words 개짜리 표준 단어장을 활성으로 두고 세션을 만든다. (토큰, 사용자 id, 단어장, 응답) 을 돌려준다."""
    vocab = await make_vocabulary([f"w{i:02d}" for i in range(n_words)], title="세션 테스트")
    _, token = await signup_and_login(client)
    await activate(client, token, vocab.id)
    user_id = await user_id_for_token(client, token)
    response = await create(client, token, **body)
    return token, user_id, vocab, response


# --- 세션 생성: 기본 ---


@pytest.mark.asyncio
async def test_create_requires_login(client: httpx.AsyncClient) -> None:
    assert (await client.post("/api/study/sessions", json={})).status_code == 401


@pytest.mark.asyncio
async def test_create_defaults_to_a_10_question_quiz_without_leaking_answers(client, make_vocabulary) -> None:
    token, user_id, vocab, response = await start(client, make_vocabulary, n_words=30)

    assert response.status_code == 201, response.text
    body = response.json()
    assert (body["mode"], body["vocabulary_id"], body["vocabulary_title"], body["total_questions"]) == (
        "quiz", vocab.id, "세션 테스트", 10
    )
    assert body["expires_at"] == "2026-11-05T09:30:00Z"
    assert len(body["items"]) == 10  # 사용자 설정 기본값 (REQ-147)
    assert [i["question_id"] for i in body["items"]] == list(range(10))
    meanings = {f"{t}의 뜻" for t in vocab.word_ids}
    for item in body["items"]:
        assert len(item["options"]) == 4 and len(set(item["options"])) == 4
        assert set(item["options"]) <= meanings, "오답 보기는 같은 단어장에서만 뽑는다"
        assert item["context"] == f"I like {item['term']}."
        assert not ({"correct_index", "meaning", "example_meaning"} & {k for k, v in item.items() if v is not None})
    assert len({i["word_id"] for i in body["items"]}) == 10
    row = await stored_session(body["session_id"])
    assert (row.mode, row.source, row.vocabulary_id, row.user_id, row.is_submitted, row.answers) == (
        "quiz", "vocabulary", vocab.id, user_id, False, {}
    )
    assert all(q["choices"][q["correct_index"]] == f"{q['term']}의 뜻" for q in row.questions)


@pytest.mark.asyncio
async def test_create_respects_count_and_validates_input(client, make_vocabulary) -> None:
    token, _, _, response = await start(client, make_vocabulary, count=5)
    assert len(response.json()["items"]) == 5
    for bad in ({"count": 0}, {"count": 31}, {"mode": "spelling"}, {"include_memorized": "maybe"}):
        assert (await create(client, token, **bad)).status_code == 422, bad


@pytest.mark.asyncio
async def test_small_vocabulary_returns_all_its_words(client, make_vocabulary) -> None:
    _, _, _, response = await start(client, make_vocabulary, n_words=6)
    assert response.status_code == 201
    assert len(response.json()["items"]) == 6


@pytest.mark.asyncio
async def test_quiz_needs_four_words_but_flashcards_do_not(client, make_vocabulary) -> None:
    _, _, _, quiz = await start(client, make_vocabulary, n_words=3)
    assert quiz.status_code == 400
    _, _, _, cards = await start(client, make_vocabulary, n_words=2, mode="flashcard")
    assert cards.status_code == 201
    assert len(cards.json()["items"]) == 2


@pytest.mark.asyncio
async def test_flashcard_items_carry_the_back_side_and_no_options(client, make_vocabulary) -> None:
    _, _, _, response = await start(client, make_vocabulary, n_words=5, mode="flashcard")
    body = response.json()
    assert body["mode"] == "flashcard"
    item = body["items"][0]
    assert item["options"] is None
    assert item["meaning"] == f"{item['term']}의 뜻"
    assert item["example_meaning"] == f"나는 {item['term']}을(를) 좋아한다."
    assert item["context"] == f"I like {item['term']}."


# --- 세션 생성: 출제 알고리즘 ---


@pytest.mark.asyncio
async def test_waterfall_composition_wrong_review_unseen(client, make_vocabulary) -> None:
    vocab = await make_vocabulary([f"w{i:02d}" for i in range(60)])
    _, token = await signup_and_login(client)
    await activate(client, token, vocab.id)
    user_id = await user_id_for_token(client, token)
    for i in range(10):  # w00..w09 오답. 번호가 클수록 최근
        await put_progress(user_id, vocab.word_ids[f"w{i:02d}"], last_result="WRONG", minutes=i)
    for i in range(10, 15):  # w10..w14 복습 대상
        await put_progress(user_id, vocab.word_ids[f"w{i:02d}"], minutes=i)

    body = (await create(client, token, count=15)).json()

    assert body["composition"] == {"wrong": 4, "review": 1, "unseen": 10}
    terms = {i["term"] for i in body["items"]}
    assert {"w06", "w07", "w08", "w09"} <= terms, "오답은 최근에 틀린 것부터 4개"
    assert len(terms & {f"w{i:02d}" for i in range(10, 15)}) == 1
    assert {f"w{i:02d}" for i in range(15, 25)} <= terms, "미학습은 단어장 순서대로 10개"
    assert len(terms) == 15


@pytest.mark.asyncio
async def test_unseen_shortage_is_filled_by_review(client, make_vocabulary) -> None:
    vocab = await make_vocabulary([f"w{i:02d}" for i in range(20)])
    _, token = await signup_and_login(client)
    await activate(client, token, vocab.id)
    user_id = await user_id_for_token(client, token)
    for i in range(17):  # 미학습은 w17..w19 세 개뿐
        await put_progress(user_id, vocab.word_ids[f"w{i:02d}"], minutes=i)

    body = (await create(client, token, count=15)).json()

    assert body["composition"] == {"wrong": 0, "review": 12, "unseen": 3}
    assert len(body["items"]) == 15


@pytest.mark.asyncio
async def test_memorized_words_are_excluded_unless_requested(client, make_vocabulary) -> None:
    vocab = await make_vocabulary([f"w{i:02d}" for i in range(6)])
    _, token = await signup_and_login(client)
    await activate(client, token, vocab.id)
    user_id = await user_id_for_token(client, token)
    for term in ("w00", "w01"):
        await put_progress(user_id, vocab.word_ids[term], memorized=True, streak=3)

    default = (await create(client, token)).json()
    included = (await create(client, token, include_memorized=True)).json()

    assert {i["term"] for i in default["items"]} == {"w02", "w03", "w04", "w05"}
    assert {"w00", "w01"} <= {i["term"] for i in included["items"]}
    assert len(included["items"]) == 6


@pytest.mark.asyncio
async def test_all_words_memorized_gives_409_with_a_hint_code(client, make_vocabulary) -> None:
    vocab = await make_vocabulary([f"w{i}" for i in range(4)])
    _, token = await signup_and_login(client)
    await activate(client, token, vocab.id)
    user_id = await user_id_for_token(client, token)
    for term in vocab.word_ids:
        await put_progress(user_id, vocab.word_ids[term], memorized=True, streak=3)

    blocked = await create(client, token)
    assert blocked.status_code == 409
    assert blocked.headers["X-Error-Code"] == "NO_WORDS_TO_STUDY"
    assert (await create(client, token, include_memorized=True)).status_code == 201


@pytest.mark.asyncio
async def test_other_users_progress_does_not_change_my_session(client, make_vocabulary) -> None:
    vocab = await make_vocabulary([f"w{i:02d}" for i in range(8)])
    _, mine = await signup_and_login(client)
    _, theirs = await signup_and_login(client)
    for token in (mine, theirs):
        await activate(client, token, vocab.id)
    their_id = await user_id_for_token(client, theirs)
    for term in vocab.word_ids:
        await put_progress(their_id, vocab.word_ids[term], memorized=True, streak=3)

    assert len((await create(client, mine)).json()["items"]) == 8


@pytest.mark.asyncio
async def test_missing_active_vocabulary_falls_back_to_the_default_and_is_saved(client) -> None:
    _, token = await signup_and_login(client)
    user_id = await user_id_for_token(client, token)
    async with get_session_factory()() as db:
        await db.execute(update(User).where(User.id == user_id).values(active_vocabulary_id=None))
        await db.commit()

    response = await create(client, token)

    assert response.status_code == 201, response.text
    assert response.json()["vocabulary_title"] == "초급 필수 영단어 200"
    async with get_session_factory()() as db:
        assert (await db.execute(select(User.active_vocabulary_id).where(User.id == user_id))).scalar_one() is not None


# --- 답 기록: 퀴즈 ---


async def first_session(client, make_vocabulary, n_words=8, **body):
    token, user_id, vocab, response = await start(client, make_vocabulary, n_words=n_words, **body)
    assert response.status_code == 201, response.text
    created = response.json()
    return token, user_id, vocab, created, await stored_session(created["session_id"])


@pytest.mark.asyncio
async def test_correct_answer_is_graded_and_updates_progress(client, make_vocabulary) -> None:
    token, user_id, _, created, row = await first_session(client, make_vocabulary)
    item = created["items"][0]
    key = key_of(row, item["question_id"])

    response = await answer(client, token, created["session_id"], question_id=item["question_id"], choice_index=key["correct_index"])

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["is_correct"], body["correct_index"], body["selected_index"]) == (True, key["correct_index"], key["correct_index"])
    assert (body["term"], body["meaning"]) == (item["term"], f"{item['term']}의 뜻")
    assert body["example"] == f"I like {item['term']}." and body["example_meaning"] == f"나는 {item['term']}을(를) 좋아한다."
    assert body["progress"] == {"correct_count": 1, "wrong_count": 0, "consecutive_correct_count": 1, "is_memorized": False}
    assert (body["answered"], body["total"], body["is_finished"]) == (1, 8, False)
    assert body["expires_at"] == "2026-11-05T09:30:00Z"
    stored = await stored_session(created["session_id"])
    assert stored.answers == {str(item["question_id"]): key["correct_index"]}
    row_progress = await progress_of(user_id, item["word_id"])
    assert (row_progress.correct_count, row_progress.last_result) == (1, "CORRECT")
    async with get_session_factory()() as db:
        logs = (await db.execute(select(StudyLog).where(StudyLog.user_id == user_id))).scalars().all()
    assert [(log.word_id, log.is_correct, log.mode) for log in logs] == [(item["word_id"], True, "quiz")]


@pytest.mark.asyncio
async def test_wrong_answer_resets_the_streak(client, make_vocabulary) -> None:
    token, user_id, _, created, row = await first_session(client, make_vocabulary)
    item = created["items"][0]
    key = key_of(row, item["question_id"])
    await put_progress(user_id, item["word_id"], streak=2)  # 연속 2회 정답 상태에서 시작

    response = await answer(client, token, created["session_id"], question_id=item["question_id"], choice_index=(key["correct_index"] + 1) % 4)

    body = response.json()
    assert body["is_correct"] is False
    assert body["progress"] == {"correct_count": 2, "wrong_count": 1, "consecutive_correct_count": 0, "is_memorized": False}
    assert (await progress_of(user_id, item["word_id"])).last_result == "WRONG"


@pytest.mark.asyncio
async def test_third_correct_in_a_row_memorizes_the_word(client, make_vocabulary) -> None:
    vocab = await make_vocabulary(["a", "b", "c", "d"])
    _, token = await signup_and_login(client)
    await activate(client, token, vocab.id)
    user_id = await user_id_for_token(client, token)
    for word_id in vocab.word_ids.values():
        await put_progress(user_id, word_id, streak=2)
    created = (await create(client, token, count=4)).json()
    row = await stored_session(created["session_id"])
    item = created["items"][0]

    body = (
        await answer(client, token, created["session_id"], question_id=item["question_id"], choice_index=key_of(row, item["question_id"])["correct_index"])
    ).json()

    assert body["progress"]["is_memorized"] is True and body["progress"]["consecutive_correct_count"] == 3
    assert (await progress_of(user_id, item["word_id"])).is_memorized is True


@pytest.mark.asyncio
async def test_resending_the_same_answer_is_safe_and_counted_once(client, make_vocabulary) -> None:
    token, user_id, _, created, row = await first_session(client, make_vocabulary)
    item = created["items"][0]
    choice = key_of(row, item["question_id"])["correct_index"]

    first = await answer(client, token, created["session_id"], question_id=item["question_id"], choice_index=choice)
    again = await answer(client, token, created["session_id"], question_id=item["question_id"], choice_index=choice)

    assert first.status_code == again.status_code == 200
    assert first.json() == again.json()
    assert (await progress_of(user_id, item["word_id"])).correct_count == 1
    async with get_session_factory()() as db:
        assert len((await db.execute(select(StudyLog).where(StudyLog.user_id == user_id))).scalars().all()) == 1


@pytest.mark.asyncio
async def test_changing_a_recorded_answer_is_409(client, make_vocabulary) -> None:
    token, _, _, created, row = await first_session(client, make_vocabulary)
    item = created["items"][0]
    choice = key_of(row, item["question_id"])["correct_index"]
    await answer(client, token, created["session_id"], question_id=item["question_id"], choice_index=choice)

    other = await answer(client, token, created["session_id"], question_id=item["question_id"], choice_index=(choice + 1) % 4)

    assert other.status_code == 409
    assert other.headers["X-Error-Code"] == "QUIZ_ANSWER_LOCKED"


@pytest.mark.asyncio
async def test_unknown_question_is_400(client, make_vocabulary) -> None:
    token, _, _, created, _ = await first_session(client, make_vocabulary)
    response = await answer(client, token, created["session_id"], question_id=99, choice_index=0)
    assert response.status_code == 400
    assert response.headers["X-Error-Code"] == "QUIZ_ANSWER_INVALID"


@pytest.mark.asyncio
async def test_other_users_or_missing_session_is_404(client, make_vocabulary) -> None:
    _, _, _, created, _ = await first_session(client, make_vocabulary)
    _, stranger = await signup_and_login(client)
    assert (await answer(client, stranger, created["session_id"], question_id=0, choice_index=0)).status_code == 404
    assert (await answer(client, stranger, 999999999, question_id=0, choice_index=0)).status_code == 404


@pytest.mark.asyncio
async def test_answer_requires_login_and_valid_body(client, make_vocabulary) -> None:
    token, _, _, created, _ = await first_session(client, make_vocabulary)
    assert (await client.post(f"/api/study/sessions/{created['session_id']}/answer", json={"question_id": 0, "choice_index": 0})).status_code == 401
    for bad in (
        {"question_id": 0},
        {"question_id": 0, "choice_index": 4},
        {"question_id": 0, "choice_index": -1},
        {"question_id": -1, "choice_index": 0},
        {"question_id": 0, "choice_index": 0, "known": True},
    ):
        assert (await answer(client, token, created["session_id"], **bad)).status_code == 422, bad


@pytest.mark.asyncio
async def test_answer_mode_must_match_the_session_mode(client, make_vocabulary) -> None:
    token, _, _, created, _ = await first_session(client, make_vocabulary)
    quiz_with_known = await answer(client, token, created["session_id"], question_id=0, known=True)
    assert quiz_with_known.status_code == 400 and quiz_with_known.headers["X-Error-Code"] == "QUIZ_ANSWER_INVALID"

    token2, _, _, cards, _ = await first_session(client, make_vocabulary, mode="flashcard")
    card_with_choice = await answer(client, token2, cards["session_id"], question_id=0, choice_index=0)
    assert card_with_choice.status_code == 400


@pytest.mark.asyncio
async def test_expired_session_rejects_new_answers_and_each_answer_extends_the_deadline(client, make_vocabulary, monkeypatch) -> None:
    token, _, _, created, row = await first_session(client, make_vocabulary)
    first, second = created["items"][0], created["items"][1]

    monkeypatch.setattr(session_router, "_now", lambda: NOW + timedelta(minutes=20))
    ok = await answer(client, token, created["session_id"], question_id=first["question_id"], choice_index=key_of(row, first["question_id"])["correct_index"])
    assert ok.json()["expires_at"] == "2026-11-05T09:50:00Z", "답할 때마다 마감이 30분 뒤로 밀린다"

    monkeypatch.setattr(session_router, "_now", lambda: NOW + timedelta(minutes=51))
    late = await answer(client, token, created["session_id"], question_id=second["question_id"], choice_index=0)
    assert late.status_code == 400 and late.headers["X-Error-Code"] == "QUIZ_EXPIRED"


@pytest.mark.asyncio
async def test_finishing_all_questions_closes_the_session(client, make_vocabulary) -> None:
    token, _, _, created, row = await first_session(client, make_vocabulary, n_words=4)
    last = None
    for item in created["items"]:
        last = await answer(client, token, created["session_id"], question_id=item["question_id"], choice_index=key_of(row, item["question_id"])["correct_index"])
        assert last.status_code == 200
    body = last.json()
    assert (body["answered"], body["total"], body["is_finished"]) == (4, 4, True)
    assert (await stored_session(created["session_id"])).is_submitted is True

    last_item = created["items"][-1]
    retry = await answer(client, token, created["session_id"], question_id=last_item["question_id"], choice_index=key_of(row, last_item["question_id"])["correct_index"])
    assert retry.status_code == 200, "마지막 답의 재전송은 세션이 끝난 뒤에도 안전하다 (네트워크 재시도)"
    assert retry.json()["is_finished"] is True


@pytest.mark.asyncio
async def test_deleted_word_blocks_only_that_answer(client, make_vocabulary) -> None:
    token, _, _, created, row = await first_session(client, make_vocabulary)
    victim, fine = created["items"][0], created["items"][1]
    async with get_session_factory()() as db:
        await db.execute(delete(SystemWord).where(SystemWord.id == victim["word_id"]))
        await db.commit()

    blocked = await answer(client, token, created["session_id"], question_id=victim["question_id"], choice_index=0)
    ok = await answer(client, token, created["session_id"], question_id=fine["question_id"], choice_index=key_of(row, fine["question_id"])["correct_index"])

    assert blocked.status_code == 409 and blocked.headers["X-Error-Code"] == "QUIZ_WORD_MISSING"
    assert ok.status_code == 200


# --- 답 기록: 플래시카드 ---


@pytest.mark.asyncio
async def test_flashcard_known_is_a_correct_answer_and_unsure_is_wrong(client, make_vocabulary) -> None:
    token, user_id, _, created, _ = await first_session(client, make_vocabulary, mode="flashcard")
    known_item, unsure_item = created["items"][0], created["items"][1]

    known = (await answer(client, token, created["session_id"], question_id=known_item["question_id"], known=True)).json()
    unsure = (await answer(client, token, created["session_id"], question_id=unsure_item["question_id"], known=False)).json()

    assert (known["is_correct"], known["known"], known["correct_index"], known["selected_index"]) == (True, True, None, None)
    assert known["meaning"] == f"{known_item['term']}의 뜻"
    assert (unsure["is_correct"], unsure["known"]) == (False, False)
    assert (await progress_of(user_id, known_item["word_id"])).last_result == "CORRECT"
    assert (await progress_of(user_id, unsure_item["word_id"])).last_result == "WRONG"
    async with get_session_factory()() as db:
        modes = {log.mode for log in (await db.execute(select(StudyLog).where(StudyLog.user_id == user_id))).scalars()}
    assert modes == {"flashcard"}
    stored = await stored_session(created["session_id"])
    assert stored.answers == {str(known_item["question_id"]): 1, str(unsure_item["question_id"]): 0}


@pytest.mark.asyncio
async def test_flashcard_resend_is_idempotent_and_change_is_locked(client, make_vocabulary) -> None:
    token, user_id, _, created, _ = await first_session(client, make_vocabulary, mode="flashcard")
    item = created["items"][0]

    first = await answer(client, token, created["session_id"], question_id=item["question_id"], known=True)
    again = await answer(client, token, created["session_id"], question_id=item["question_id"], known=True)
    changed = await answer(client, token, created["session_id"], question_id=item["question_id"], known=False)

    assert first.json() == again.json()
    assert changed.status_code == 409 and changed.headers["X-Error-Code"] == "QUIZ_ANSWER_LOCKED"
    assert (await progress_of(user_id, item["word_id"])).correct_count == 1


@pytest.mark.asyncio
async def test_resend_returns_the_identical_body_even_when_now_has_microseconds(client, make_vocabulary, monkeypatch) -> None:
    """실제 시각은 마이크로초를 가진다. 첫 응답과 DB 에서 읽은 재전송 응답의 expires_at 이 같아야 멱등 응답이다."""
    monkeypatch.setattr(session_router, "_now", lambda: NOW + timedelta(microseconds=123456))
    token, _, _, created, row = await first_session(client, make_vocabulary)
    item = created["items"][0]
    body = dict(question_id=item["question_id"], choice_index=key_of(row, item["question_id"])["correct_index"])

    first = await answer(client, token, created["session_id"], **body)
    again = await answer(client, token, created["session_id"], **body)

    assert first.json() == again.json()
    assert created["expires_at"] == "2026-11-05T09:30:00.123000Z", "마이크로초 123456 은 DB 정밀도인 밀리초(123000)로 잘린다"
    assert first.json()["expires_at"] == "2026-11-05T09:30:00.123000Z"
