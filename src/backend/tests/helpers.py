# 2026-11-02 - voda-voca - 통합 테스트 공통 헬퍼: 닉네임 가입/로그인, 쿠키 헤더 (회원 체계 단순화 후)
# 파일 위치: src/backend/tests/helpers.py

import uuid

import httpx

from backend.core.deps import SESSION_COOKIE_NAME

PASSWORD = "correct-horse-1"

# 가입하면 자동으로 생기는 기본 단어장 3종 (초/중/고 200제). 목록 개수 검증에 쓴다.
DEFAULT_WORDBOOK_NAMES = ("초급 필수 영단어 200", "중급 핵심 영단어 200", "고급 심화 영단어 200")
DEFAULT_WORDBOOK_COUNT = len(DEFAULT_WORDBOOK_NAMES)
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
