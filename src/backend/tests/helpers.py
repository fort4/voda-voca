# 2026-11-02 - voda-voca - 통합 테스트 공통 헬퍼: 닉네임 가입/로그인, 쿠키 헤더 (회원 체계 단순화 후)
# 파일 위치: src/backend/tests/helpers.py

import uuid
from dataclasses import dataclass

import httpx

from backend.core.deps import SESSION_COOKIE_NAME

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
