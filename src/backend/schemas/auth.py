# 2026-11-02 - voda-voca - 인증 API 요청/응답 스키마 및 입력 검증 (REQ-001, REQ-002, REQ-111)
# 파일 위치: src/backend/schemas/auth.py

from datetime import UTC, datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_serializer,
    field_validator,
)

# bcrypt 입력 한계 (ADR-002). 초과 시 bcrypt 5.x 는 ValueError 를 던진다.
PASSWORD_MAX_BYTES = 72
PASSWORD_MIN_CHARS = 8
EMAIL_MAX_CHARS = 255


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=PASSWORD_MIN_CHARS)
    nickname: str = Field(min_length=1, max_length=50)

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        if len(value) > EMAIL_MAX_CHARS:
            raise ValueError(f"이메일은 {EMAIL_MAX_CHARS}자 이하여야 합니다.")
        return value.strip().lower()

    @field_validator("password")
    @classmethod
    def _limit_password_bytes(cls, value: str) -> str:
        if len(value.encode("utf-8")) > PASSWORD_MAX_BYTES:
            raise ValueError(f"비밀번호는 UTF-8 기준 {PASSWORD_MAX_BYTES}바이트 이하여야 합니다.")
        return value

    @field_validator("nickname")
    @classmethod
    def _strip_nickname(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("닉네임은 공백만으로 만들 수 없습니다.")
        return stripped


class LoginRequest(BaseModel):
    """로그인 입력은 형식 검증을 느슨하게 둔다.

    잘못된 이메일 형식이어도 422 로 형식을 노출하지 않고, 서비스 계층에서 일반 401 로 응답한다.
    """

    email: str = Field(min_length=1, max_length=EMAIL_MAX_CHARS)
    password: str = Field(min_length=1)


class UserOut(BaseModel):
    """클라이언트에 노출하는 사용자 정보. 비밀번호 해시는 포함하지 않는다."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    nickname: str
    created_at: datetime

    @field_serializer("created_at")
    def _serialize_utc(self, value: datetime) -> str:
        """DB 에서 읽은 값은 UTC 이지만 tzinfo 가 없다. 'Z' 를 붙여 UTC 임을 명시한다 (REQ-109)."""
        return value.replace(tzinfo=UTC).isoformat().replace("+00:00", "Z")
