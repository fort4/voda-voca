# 2026-11-26 - voda-voca - 인증 스키마 단위 테스트: 닉네임 2~30자, 비밀번호 8자·72바이트·확인, 로그인 입력 완화 (REQ-158)
# 파일 위치: src/backend/tests/test_auth_schemas.py

import pytest
from pydantic import ValidationError

from backend.schemas.auth import LoginRequest, SignupRequest, UserOut


pytestmark = pytest.mark.no_db  # MySQL 없이 통과해야 한다 (test_no_db_guard.py)


def _signup(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "nickname": "학습자",
        "password": "longenough1",
        "password_confirm": "longenough1",
    }
    data.update(overrides)
    if "password" in overrides and "password_confirm" not in overrides:
        data["password_confirm"] = overrides["password"]  # 비밀번호만 바꾸는 테스트는 확인란도 맞춘다
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


# --- 이메일은 받지 않는다 (사용자 결정: 닉네임·비밀번호만) ---


def test_email_is_not_a_field() -> None:
    assert "email" not in SignupRequest.model_fields
    assert "email" not in LoginRequest.model_fields
    assert "email" not in UserOut.model_fields


# --- 비밀번호 확인 (REQ-158) ---


def test_password_confirm_must_match() -> None:
    with pytest.raises(ValidationError) as raised:
        SignupRequest(**_signup(password="longenough1", password_confirm="longenough2"))
    assert any(e["loc"] == ("password_confirm",) for e in raised.value.errors())


def test_password_confirm_is_required() -> None:
    data = _signup()
    del data["password_confirm"]
    with pytest.raises(ValidationError):
        SignupRequest(**data)


def test_no_password_complexity_rule() -> None:
    """안전 비밀번호 정규식은 두지 않는다 (사용자 결정): 숫자만, 영문만이어도 길이만 맞으면 된다."""
    assert SignupRequest(**_signup(password="12345678")).password == "12345678"
    assert SignupRequest(**_signup(password="abcdefgh")).password == "abcdefgh"


# --- 로그인 입력 ---


def test_login_request_is_nickname_and_password_only() -> None:
    assert set(LoginRequest.model_fields) == {"nickname", "password"}


def test_login_request_is_permissive_so_unknown_nicknames_get_401() -> None:
    assert LoginRequest(nickname="없는사람", password="x").nickname == "없는사람"
    with pytest.raises(ValidationError):
        LoginRequest(nickname="", password="x")
    with pytest.raises(ValidationError):
        LoginRequest(nickname="a", password="")


def test_user_out_exposes_nickname_but_not_password_hash() -> None:
    assert set(UserOut.model_fields) == {"id", "nickname", "created_at"}
