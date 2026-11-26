# 2026-11-26 - voda-voca - 개인 단어장 CSV 일괄 등록 통합 테스트: 소유자 확인, 과제 형식 2,000행, 중복 건너뛰기, 파일 전체 거부, 크기 상한, 쓰기 잠금 (#40, REQ-171)
# 파일 위치: src/backend/tests/test_user_csv_import_api.py

from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import func, select

from backend.db.session import get_session_factory
from backend.main import app
from backend.models import SystemVocabulary, SystemWord
from backend.services.csv_import import MAX_FILE_BYTES
from backend.tests.helpers import auth_headers, signup_and_login, unique_nickname, user_id_for_token

CSV = "term,meaning,example,example_meaning\nladle,국자,Use a ladle.,국자를 써.\nfork,포크,,\n"


@pytest_asyncio.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@dataclass
class Owner:
    token: str
    user_id: int


@pytest_asyncio.fixture
async def owner(client: httpx.AsyncClient) -> Owner:
    _, token = await signup_and_login(client)
    return Owner(token, await user_id_for_token(client, token))


@pytest_asyncio.fixture
async def make_mine(owner: Owner, make_vocabulary):
    """owner 의 개인 단어장을 만든다."""

    async def _make(terms):
        return await make_vocabulary(terms, owner_id=owner.user_id)

    return _make


def url(vocabulary_id: int) -> str:
    return f"/api/vocabularies/{vocabulary_id}/words/import"


async def upload(
    client: httpx.AsyncClient, token: str | None, vocabulary_id: int, content, content_type: str = "text/csv"
) -> httpx.Response:
    headers = {"Content-Type": content_type} | (auth_headers(token) if token else {})
    if isinstance(content, str):
        content = content.encode("utf-8")
    return await client.post(url(vocabulary_id), content=content, headers=headers)


async def words_of(vocabulary_id: int) -> list[SystemWord]:
    async with get_session_factory()() as db:
        rows = await db.scalars(
            select(SystemWord).where(SystemWord.vocabulary_id == vocabulary_id).order_by(SystemWord.order_index)
        )
        return list(rows)


async def total_words(vocabulary_id: int) -> int:
    async with get_session_factory()() as db:
        return await db.scalar(select(SystemVocabulary.total_words).where(SystemVocabulary.id == vocabulary_id))


async def word_count() -> int:
    async with get_session_factory()() as db:
        return await db.scalar(select(func.count()).select_from(SystemWord))


@pytest.mark.asyncio
async def test_import_requires_login_and_ownership(client: httpx.AsyncClient, make_mine, make_vocabulary) -> None:
    mine = await make_mine(["apple"])
    standard = await make_vocabulary(["apple"])
    _, other = await signup_and_login(client)
    before = await word_count()

    anonymous = await upload(client, None, mine.id, CSV)
    hidden = await upload(client, other, mine.id, CSV)
    read_only = await upload(client, other, standard.id, CSV)

    assert (anonymous.status_code, hidden.status_code, read_only.status_code) == (401, 404, 403)
    assert read_only.headers["X-Error-Code"] == "SEED_READ_ONLY"
    assert await word_count() == before


@pytest.mark.asyncio
async def test_the_course_file_format_with_2000_words_is_imported_at_once(
    client: httpx.AsyncClient, owner: Owner, make_mine
) -> None:
    """과제 제공 파일 형식: UTF-8 BOM, 열 이름 영단어,뜻, 2,000개 (VOCA-FR-003)."""
    vocab = await make_mine([])
    text = "\ufeff영단어,뜻\r\n" + "".join(f"word{i:04d},뜻 {i}\r\n" for i in range(2000))

    response = await upload(client, owner.token, vocab.id, text)

    assert response.status_code == 200, response.text
    assert response.json() == {"created": 2000, "skipped": 0}
    words = await words_of(vocab.id)
    assert (words[0].term, words[0].meaning, words[-1].term) == ("word0000", "뜻 0", "word1999")
    assert await total_words(vocab.id) == 2000


@pytest.mark.asyncio
async def test_rows_are_appended_after_existing_words(client: httpx.AsyncClient, owner: Owner, make_mine) -> None:
    vocab = await make_mine(["apple", "banana"])
    token = owner.token

    response = await upload(client, token, vocab.id, "﻿" + CSV, "text/csv; charset=utf-8")

    assert response.status_code == 200, response.text
    assert response.json() == {"created": 2, "skipped": 0}
    words = await words_of(vocab.id)
    assert [(w.term, w.order_index, w.source) for w in words] == [
        ("apple", 0, "user"), ("banana", 1, "user"), ("ladle", 2, "user"), ("fork", 3, "user"),
    ]
    assert (words[2].meaning, words[2].example, words[2].example_meaning) == ("국자", "Use a ladle.", "국자를 써.")
    assert (words[3].example, words[3].example_meaning) == (None, None)
    assert await total_words(vocab.id) == 4


@pytest.mark.asyncio
async def test_rows_start_at_zero_in_a_new_vocabulary(client: httpx.AsyncClient, owner: Owner) -> None:
    token = owner.token
    created = await client.post("/api/vocabularies", json={"title": "주방"}, headers=auth_headers(token))
    vocabulary_id = created.json()["id"]

    response = await upload(client, token, vocabulary_id, CSV)

    assert response.status_code == 200, response.text
    assert [w.order_index for w in await words_of(vocabulary_id)] == [0, 1]
    assert await total_words(vocabulary_id) == 2


@pytest.mark.asyncio
async def test_duplicates_are_skipped_and_counted(client: httpx.AsyncClient, owner: Owner, make_mine) -> None:
    vocab = await make_mine(["Cafe", "banana"])
    token = owner.token
    text = "term,meaning\ncafé,바뀌면 안 됨\nBANANA,바뀌면 안 됨\nladle,국자\nLadle,두 번째\n"

    response = await upload(client, token, vocab.id, text)

    assert response.status_code == 200, response.text
    assert response.json() == {"created": 1, "skipped": 3}
    words = await words_of(vocab.id)
    assert [(w.term, w.meaning) for w in words] == [
        ("Cafe", "Cafe의 뜻"), ("banana", "banana의 뜻"), ("ladle", "국자"),
    ]


@pytest.mark.asyncio
async def test_uploading_the_same_file_again_adds_nothing(client: httpx.AsyncClient, owner: Owner, make_mine) -> None:
    vocab = await make_mine(["apple"])
    token = owner.token
    await upload(client, token, vocab.id, CSV)

    again = await upload(client, token, vocab.id, CSV)

    assert (again.status_code, again.json()) == (200, {"created": 0, "skipped": 2})
    assert await total_words(vocab.id) == 3


@pytest.mark.asyncio
async def test_the_same_term_in_another_vocabulary_is_not_a_duplicate(
    client: httpx.AsyncClient, owner: Owner, make_mine
) -> None:
    await make_mine(["ladle"])
    token = owner.token
    target = await make_mine([])

    response = await upload(client, token, target.id, CSV)

    assert response.json() == {"created": 2, "skipped": 0}


@pytest.mark.asyncio
async def test_one_bad_row_rejects_the_whole_file(client: httpx.AsyncClient, owner: Owner, make_mine) -> None:
    vocab = await make_mine(["apple"])
    token = owner.token

    response = await upload(client, token, vocab.id, "term,meaning\nladle,국자\nfork,\n")

    assert response.status_code == 400, response.text
    assert response.headers["X-Error-Code"] == "CSV_INVALID"
    body = response.json()
    assert isinstance(body["detail"], str) and body["detail"]
    assert [e["row"] for e in body["errors"]] == [3]
    assert "뜻" in body["errors"][0]["message"]
    assert await total_words(vocab.id) == len(await words_of(vocab.id)) == 1


@pytest.mark.asyncio
async def test_a_file_that_is_not_utf8_is_rejected(client: httpx.AsyncClient, owner: Owner, make_mine) -> None:
    vocab = await make_mine(["apple"])
    token = owner.token

    response = await upload(client, token, vocab.id, CSV.encode("cp949"))

    assert (response.status_code, response.headers["X-Error-Code"]) == (400, "CSV_INVALID")
    assert "CSV UTF-8" in response.json()["detail"]
    assert response.json()["errors"] == []


def sized_csv(size: int) -> bytes:
    """빈 줄로 채워 정확히 size 바이트인 유효한 파일."""
    data = CSV.encode("utf-8")
    return data + b"\n" * (size - len(data))


@pytest.mark.asyncio
async def test_a_file_at_the_size_limit_is_accepted(client: httpx.AsyncClient, owner: Owner, make_mine) -> None:
    vocab = await make_mine(["apple"])
    token = owner.token

    response = await upload(client, token, vocab.id, sized_csv(MAX_FILE_BYTES))

    assert MAX_FILE_BYTES == 1024 * 1024
    assert response.status_code == 200, response.text


@pytest.mark.asyncio
@pytest.mark.parametrize("chunked", [False, True])
async def test_a_file_over_the_size_limit_is_rejected(
    client: httpx.AsyncClient, owner: Owner, make_mine, chunked: bool
) -> None:
    vocab = await make_mine(["apple"])
    token = owner.token
    data = sized_csv(MAX_FILE_BYTES + 1)

    async def chunks() -> AsyncIterator[bytes]:  # Content-Length 가 없는 전송
        for start in range(0, len(data), 64 * 1024):
            yield data[start : start + 64 * 1024]

    response = await upload(client, token, vocab.id, chunks() if chunked else data)

    assert response.status_code == 413, response.text
    assert response.headers["X-Error-Code"] == "CSV_TOO_LARGE"
    assert await total_words(vocab.id) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("content_type", ["text/plain", "application/json", "multipart/form-data; boundary=x"])
async def test_only_a_csv_body_is_accepted(client: httpx.AsyncClient, owner: Owner, make_mine, content_type: str) -> None:
    vocab = await make_mine(["apple"])
    token = owner.token

    response = await upload(client, token, vocab.id, CSV, content_type)

    assert response.status_code == 415, response.text
    assert await total_words(vocab.id) == 1


@pytest.mark.asyncio
async def test_unknown_vocabulary_is_404(client: httpx.AsyncClient, owner: Owner) -> None:
    token = owner.token

    response = await upload(client, token, 999_999, CSV)

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_a_slow_upload_does_not_block_other_writes(client: httpx.AsyncClient, owner: Owner, make_mine) -> None:
    """본문을 받는 동안 SQLite 쓰기 잠금을 쥐고 있으면 다른 사용자의 쓰기가 멈춘다."""
    vocab = await make_mine(["apple"])
    token = owner.token
    seen: list[int] = []

    async def slow_body() -> AsyncIterator[bytes]:
        yield b"term,meaning\n"
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as other:
            signup = await other.post(
                "/api/auth/signup",
                json={"nickname": unique_nickname(), "password": "pw-12345678", "password_confirm": "pw-12345678"},
            )
        seen.append(signup.status_code)
        yield "ladle,국자\n".encode("utf-8")

    response = await upload(client, token, vocab.id, slow_body())

    assert seen == [201]
    assert response.status_code == 200, response.text
