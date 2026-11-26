# 2026-11-26 - voda-voca - 인증 API 요청/응답 스키마: 닉네임·비밀번호(+확인) 가입과 로그인, 닉네임 중복 확인, 비밀번호 변경 (REQ-001, REQ-002, REQ-111, REQ-158, REQ-164)
# 파일 위치: src/backend/schemas/auth.py

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_serializer, field_validator

from backend.schemas.common import to_utc_iso

# bcrypt 입력 한계 (ADR-002). 초과 시 bcrypt 5.x 는 ValueError 를 던진다.
PASSWORD_MAX_BYTES = 72
PASSWORD_MIN_CHARS = 8
NICKNAME_MIN_CHARS = 2
NICKNAME_MAX_CHARS = 30


def check_nickname_rule(value: str) -> str:
    """공백을 지운 닉네임을 돌려준다. 길이 규칙이 틀리면 ValueError."""
    stripped = value.strip()
    if not stripped:
        raise ValueError("닉네임은 공백만으로 만들 수 없습니다.")
    if not (NICKNAME_MIN_CHARS <= len(stripped) <= NICKNAME_MAX_CHARS):
        raise ValueError(f"닉네임은 {NICKNAME_MIN_CHARS}자 이상 {NICKNAME_MAX_CHARS}자 이하여야 합니다.")
    return stripped


def check_password_bytes(value: str) -> str:
    """bcrypt 입력 한계를 넘으면 ValueError (ADR-002). 글자 수 하한은 Field(min_length) 가 본다."""
    if len(value.encode("utf-8")) > PASSWORD_MAX_BYTES:
        raise ValueError(f"비밀번호는 UTF-8 기준 {PASSWORD_MAX_BYTES}바이트 이하여야 합니다.")
    return value


class SignupRequest(BaseModel):
    """가입 입력. 닉네임이 로그인 식별자이며 중복될 수 없다. 이메일은 받지 않는다 (REQ-158, 사용자 결정).

    비밀번호 복잡도 정규식은 두지 않는다 (사용자 결정). 길이(8자 이상, 72바이트 이하)만 본다.
    """

    nickname: str = Field(description="닉네임 (2~30자, 공백 제거 후 기준, 중복 불가)")
    password: str = Field(min_length=PASSWORD_MIN_CHARS)
    password_confirm: str = Field(description="비밀번호 확인. password 와 같아야 한다")

    @field_validator("nickname")
    @classmethod
    def _check_nickname(cls, value: str) -> str:
        return check_nickname_rule(value)

    @field_validator("password")
    @classmethod
    def _limit_password_bytes(cls, value: str) -> str:
        return check_password_bytes(value)

    @field_validator("password_confirm")
    @classmethod
    def _confirm_matches(cls, value: str, info: ValidationInfo) -> str:
        # 오류가 password_confirm 필드에 붙어야 화면이 확인란 아래에 메시지를 보인다. password 가 이미 틀렸으면 비교하지 않는다.
        if "password" in info.data and value != info.data["password"]:
            raise ValueError("비밀번호가 일치하지 않습니다.")
        return value


class LoginRequest(BaseModel):
    """로그인 입력은 형식 검증을 느슨하게 둔다. 없는 닉네임도 422 가 아니라 일반 401 로 응답한다."""

    nickname: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=1)


class PasswordChangeRequest(BaseModel):
    """비밀번호 변경 입력 (REQ-164). 새 비밀번호 규칙은 가입(REQ-001)과 같고, 지금 비밀번호와 달라야 한다."""

    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=PASSWORD_MIN_CHARS)
    new_password_confirm: str

    @field_validator("new_password")
    @classmethod
    def _check_new_password(cls, value: str, info: ValidationInfo) -> str:
        if value == info.data.get("current_password"):
            raise ValueError("현재 비밀번호와 다른 비밀번호를 입력해 주세요.")
        return check_password_bytes(value)

    @field_validator("new_password_confirm")
    @classmethod
    def _confirm_matches(cls, value: str, info: ValidationInfo) -> str:
        if "new_password" in info.data and value != info.data["new_password"]:
            raise ValueError("비밀번호가 일치하지 않습니다.")
        return value


class AvailabilityOut(BaseModel):
    """중복 확인 응답. true 면 지금 가입에 쓸 수 있다."""

    available: bool


class UserOut(BaseModel):
    """클라이언트에 노출하는 사용자 정보. 비밀번호 해시는 포함하지 않는다."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    nickname: str
    created_at: datetime

    @field_serializer("created_at")
    def _serialize_utc(self, value: datetime) -> str:
        return to_utc_iso(value)
