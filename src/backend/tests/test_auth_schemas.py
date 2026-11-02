# 2026-11-02 - voda-voca - 인증 스키마 단위 테스트: 닉네임 2~30자 경계, 비밀번호 8자·72바이트, 로그인 입력 완화
# 파일 위치: src/backend/tests/test_auth_schemas.py

import pytest
from pydantic import ValidationError

from backend.schemas.auth import LoginRequest, SignupRequest


def _signup(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {"nickname": "학습자", "password": "longenough1"}
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


def test_nickname_is_trimmed() -> None:
    assert SignupRequest(**_signup(nickname="  홍길동  ")).nickname == "홍길동"


@pytest.mark.parametrize("nickname", ["가", "a", " a ", "   "])
def test_nickname_shorter_than_2_chars_is_rejected(nickname: str) -> None:
    with pytest.raises(ValidationError):
        SignupRequest(**_signup(nickname=nickname))


def test_nickname_of_exactly_2_chars_is_accepted() -> None:
    assert SignupRequest(**_signup(nickname="ab")).nickname == "ab"


def test_nickname_of_30_chars_is_accepted_and_31_is_rejected() -> None:
    assert SignupRequest(**_signup(nickname="가" * 30)).nickname == "가" * 30
    with pytest.raises(ValidationError):
        SignupRequest(**_signup(nickname="가" * 31))


def test_nickname_length_is_checked_after_trimming() -> None:
    assert SignupRequest(**_signup(nickname="  ab  ")).nickname == "ab"
    with pytest.raises(ValidationError):
        SignupRequest(**_signup(nickname="  a  "))


def test_email_is_not_a_field_any_more() -> None:
    assert "email" not in SignupRequest.model_fields
    assert "email" not in LoginRequest.model_fields


def test_login_request_is_permissive_so_unknown_nicknames_get_401() -> None:
    assert LoginRequest(nickname="없는사람", password="x").nickname == "없는사람"
    with pytest.raises(ValidationError):
        LoginRequest(nickname="", password="x")
    with pytest.raises(ValidationError):
        LoginRequest(nickname="a", password="")
