# 2026-11-02 - voda-voca - 인증 스키마 단위 테스트: 비밀번호 길이, 이메일 정규화, 닉네임 검증
# 파일 위치: src/backend/tests/test_auth_schemas.py

import pytest
from pydantic import ValidationError

from backend.schemas.auth import SignupRequest


def _signup(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "email": "tvoda-schema@example.com",
        "password": "longenough1",
        "nickname": "학습자",
    }
    data.update(overrides)
    return data


def test_password_shorter_than_8_chars_is_rejected() -> None:
    with pytest.raises(ValidationError):
        SignupRequest(**_signup(password="1234567"))


def test_password_of_exactly_8_chars_is_accepted() -> None:
    assert SignupRequest(**_signup(password="12345678")).password == "12345678"


def test_password_72_bytes_is_accepted() -> None:
    password = "a" * 72
    assert SignupRequest(**_signup(password=password)).password == password


def test_password_over_72_bytes_is_rejected() -> None:
    with pytest.raises(ValidationError):
        SignupRequest(**_signup(password="a" * 73))


def test_multibyte_password_counts_utf8_bytes() -> None:
    # 한글 1자는 3바이트. 25자 = 75바이트 이므로 거부되어야 한다.
    with pytest.raises(ValidationError):
        SignupRequest(**_signup(password="가" * 25))
    # 24자 = 72바이트 이므로 허용되어야 한다.
    assert SignupRequest(**_signup(password="가" * 24)).password == "가" * 24


def test_email_is_trimmed_and_lowercased() -> None:
    request = SignupRequest(**_signup(email="  TVoda-Mixed@Example.COM "))
    assert request.email == "tvoda-mixed@example.com"


def test_invalid_email_is_rejected() -> None:
    with pytest.raises(ValidationError):
        SignupRequest(**_signup(email="not-an-email"))


def test_nickname_is_trimmed() -> None:
    assert SignupRequest(**_signup(nickname="  홍길동  ")).nickname == "홍길동"


def test_blank_nickname_is_rejected() -> None:
    with pytest.raises(ValidationError):
        SignupRequest(**_signup(nickname="   "))


def test_nickname_over_50_chars_is_rejected() -> None:
    with pytest.raises(ValidationError):
        SignupRequest(**_signup(nickname="가" * 51))


def test_email_over_255_chars_is_rejected() -> None:
    local = "a" * 250
    with pytest.raises(ValidationError):
        SignupRequest(**_signup(email=f"{local}@example.com"))
