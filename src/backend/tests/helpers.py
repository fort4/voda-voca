# 2026-11-05 - voda-voca - 통합 테스트 공통 헬퍼: 닉네임 가입/로그인, 쿠키 헤더, 표준 단어장·단어 시드, 사용자 id 조회
# 파일 위치: src/backend/tests/helpers.py

import uuid
from dataclasses import dataclass

import httpx
from sqlalchemy import delete, func, select

from backend.core.deps import SESSION_COOKIE_NAME
from backend.db.session import get_session_factory
from backend.models import StudyLog, SystemVocabulary, SystemWord, User

PASSWORD = "correct-horse-1"

TEST_NICKNAME_PREFIX = "tvoda-"


def unique_nickname() -> str:
    """정리 패턴(tvoda-%)에 맞는 고유 닉네임을 만든다. 2~30자 범위 안이다 (14자)."""
    return f"{TEST_NICKNAME_PREFIX}{uuid.uuid4().hex[:8]}"


def auth_headers(token: str) -> dict[str, str]:
    """쿠키 헤더를 직접 실어 보낸다. httpx 클라이언트의 쿠키 jar 에 의존하지 않기 위함이다."""
    return {"Cookie": f"{SESSION_COOKIE_NAME}={token}"}


async def signup_and_login(client: httpx.AsyncClient, nickname: str | None = None) -> tuple[str, str]:
    """계정을 만들고 로그인해 (닉네임, 세션 토큰)을 반환한다."""
    nickname = nickname or unique_nickname()
    signup = await client.post("/api/auth/signup", json={"nickname": nickname, "password": PASSWORD})
    assert signup.status_code == 201, signup.text
    login = await client.post("/api/auth/login", json={"nickname": nickname, "password": PASSWORD})
    assert login.status_code == 200, login.text
    token = login.cookies[SESSION_COOKIE_NAME]
    client.cookies.clear()
    return nickname, token


@dataclass(frozen=True)
class TestVocabulary:
    """테스트용 표준 단어장. slug 가 tvoda- 로 시작하므로 conftest 가 테스트 뒤에 지운다."""

    __test__ = False  # pytest 가 테스트 클래스로 수집하지 않게 한다

    id: int
    slug: str
    title: str
    word_ids: dict[str, int]  # term -> system_words.id


TEST_VOCABULARY_SLUG_PREFIX = "tvoda-"


async def make_vocab(client: httpx.AsyncClient, token: str, name: str = "단어장") -> int:
    """표준 단어장(공용 콘텐츠)을 DB 에 직접 만든다. client, token 은 기존 호출부와 맞추기 위한 인자다."""
    async with get_session_factory()() as db:
        vocabulary = SystemVocabulary(
            slug=f"{TEST_VOCABULARY_SLUG_PREFIX}{uuid.uuid4().hex[:10]}", title=name, category="ELEMENTARY", level=1
        )
        db.add(vocabulary)
        await db.commit()
        return vocabulary.id


async def make_word(
    client: httpx.AsyncClient,
    token: str,
    vocabulary_id: int,
    term: str,
    meaning: str,
    example: str | None = None,
    example_meaning: str | None = None,
) -> int:
    async with get_session_factory()() as db:
        order = await db.scalar(
            select(func.count()).select_from(SystemWord).where(SystemWord.vocabulary_id == vocabulary_id)
        )
        word = SystemWord(
            vocabulary_id=vocabulary_id,
            term=term,
            meaning=meaning,
            example=example,
            example_meaning=example_meaning if example else None,
            order_index=order or 0,
        )
        db.add(word)
        await db.commit()
        return word.id


async def make_words(
    client: httpx.AsyncClient, token: str, vocabulary_id: int, count: int, prefix: str = "w"
) -> dict[int, str]:
    """단어를 count 개 만들고 {word_id: meaning} 을 돌려준다. 뜻은 모두 다르다."""
    result: dict[int, str] = {}
    for i in range(count):
        meaning = f"{prefix}-뜻-{i}"
        word_id = await make_word(client, token, vocabulary_id, f"{prefix}term{i:02d}", meaning)
        result[word_id] = meaning
    return result


async def delete_word(word_id: int) -> None:
    """표준 단어는 사용자가 지울 수 없으므로 DB 에서 직접 지운다 (시드 정리 같은 운영 상황의 재현)."""
    async with get_session_factory()() as db:
        await db.execute(delete(SystemWord).where(SystemWord.id == word_id))
        await db.commit()


async def study_log_count() -> int:
    """study_logs 전체 행 수. 테스트 간 격리는 카운트 차이(delta)로 확인한다."""
    async with get_session_factory()() as db:
        return (await db.execute(select(func.count()).select_from(StudyLog))).scalar_one()


async def user_id_for_token(client: httpx.AsyncClient, token: str) -> int:
    me = (await client.get("/api/auth/me", headers=auth_headers(token))).json()
    async with get_session_factory()() as session:
        return (await session.execute(select(User.id).where(User.nickname == me["nickname"]))).scalar_one()
