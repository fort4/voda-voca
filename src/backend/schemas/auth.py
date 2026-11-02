# 2026-11-02 - voda-voca - 인증 API 요청/응답 스키마: 닉네임·비밀번호 기반 가입과 로그인 (REQ-001, REQ-002, REQ-111)
# 파일 위치: src/backend/schemas/auth.py

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from backend.schemas.common import to_utc_iso

# bcrypt 입력 한계 (ADR-002). 초과 시 bcrypt 5.x 는 ValueError 를 던진다.
PASSWORD_MAX_BYTES = 72
PASSWORD_MIN_CHARS = 8
NICKNAME_MIN_CHARS = 2
NICKNAME_MAX_CHARS = 30


class SignupRequest(BaseModel):
    """가입 입력. 이메일은 받지 않는다. 닉네임이 로그인 식별자이며 중복될 수 없다."""

    nickname: str = Field(description="닉네임 (2~30자, 공백 제거 후 기준, 중복 불가)")
    password: str = Field(min_length=PASSWORD_MIN_CHARS)

    @field_validator("nickname")
    @classmethod
    def _check_nickname(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("닉네임은 공백만으로 만들 수 없습니다.")
        if not (NICKNAME_MIN_CHARS <= len(stripped) <= NICKNAME_MAX_CHARS):
            raise ValueError(f"닉네임은 {NICKNAME_MIN_CHARS}자 이상 {NICKNAME_MAX_CHARS}자 이하여야 합니다.")
        return stripped

    @field_validator("password")
    @classmethod
    def _limit_password_bytes(cls, value: str) -> str:
        if len(value.encode("utf-8")) > PASSWORD_MAX_BYTES:
            raise ValueError(f"비밀번호는 UTF-8 기준 {PASSWORD_MAX_BYTES}바이트 이하여야 합니다.")
        return value


class LoginRequest(BaseModel):
    """로그인 입력은 형식 검증을 느슨하게 둔다. 없는 닉네임도 422 가 아니라 일반 401 로 응답한다."""

    nickname: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=1)


class UserOut(BaseModel):
    """클라이언트에 노출하는 사용자 정보. 비밀번호 해시는 포함하지 않는다."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    nickname: str
    created_at: datetime

    @field_serializer("created_at")
    def _serialize_utc(self, value: datetime) -> str:
        return to_utc_iso(value)
