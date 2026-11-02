# 2026-11-02 - voda-voca - 통합 테스트 공통 헬퍼: 가입/로그인, 쿠키 헤더
# 파일 위치: src/backend/tests/helpers.py

import uuid

import httpx

from backend.core.deps import SESSION_COOKIE_NAME

PASSWORD = "correct-horse-1"


def unique_email() -> str:
    """정리 패턴(tvoda-%@example.com)에 맞는 고유 이메일을 만든다."""
    return f"tvoda-{uuid.uuid4().hex[:12]}@example.com"


def auth_headers(token: str) -> dict[str, str]:
    """쿠키 헤더를 직접 실어 보낸다. httpx 클라이언트의 쿠키 jar 에 의존하지 않기 위함이다."""
    return {"Cookie": f"{SESSION_COOKIE_NAME}={token}"}


async def signup_and_login(client: httpx.AsyncClient, email: str | None = None) -> tuple[str, str]:
    """계정을 만들고 로그인해 (이메일, 세션 토큰)을 반환한다."""
    email = email or unique_email()
    signup = await client.post(
        "/api/auth/signup",
        json={"email": email, "password": PASSWORD, "nickname": "학습자"},
    )
    assert signup.status_code == 201, signup.text
    login = await client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200, login.text
    token = login.cookies[SESSION_COOKIE_NAME]
    client.cookies.clear()
    return email, token
