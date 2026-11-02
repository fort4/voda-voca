# 2026-11-02 - voda-voca - 로그인 세션 생성/조회/삭제 (sessions 테이블, REQ-002, ADR-001)
# 파일 위치: src/backend/services/session.py

import hashlib
import secrets
from datetime import timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import get_settings
from backend.models import AuthSession, User
from backend.models.base import utcnow

# 쿠키 토큰 길이 (바이트). token_urlsafe(32) 는 약 43자의 URL 안전 문자열을 만든다.
TOKEN_BYTES = 32


def new_token() -> str:
    """클라이언트 쿠키에 담길 무작위 토큰 원문을 만든다. DB 에는 저장하지 않는다."""
    return secrets.token_urlsafe(TOKEN_BYTES)


def token_digest(token: str) -> bytes:
    """토큰의 SHA-256 다이제스트(32바이트). sessions.id 로 저장한다.

    DB 가 노출되어도 유효한 세션 토큰이 복원되지 않도록 하기 위함이다 (ADR-001).
    """
    return hashlib.sha256(token.encode("ascii")).digest()


async def create_session(db: AsyncSession, user_id: int) -> str:
    """새 세션을 만들고 쿠키에 담을 토큰 원문을 반환한다. 로그인할 때마다 새 토큰을 발급한다."""
    token = new_token()
    expires_at = utcnow() + timedelta(days=get_settings().session_ttl_days)
    db.add(AuthSession(id=token_digest(token), user_id=user_id, expires_at=expires_at))
    await db.commit()
    return token


async def resolve_user(db: AsyncSession, token: str) -> User | None:
    """토큰에 해당하는 유효한 사용자를 반환한다.

    만료되었거나 존재하지 않는 세션이면 None 을 반환한다 (REQ-002).
    """
    statement = (
        select(User)
        .join(AuthSession, AuthSession.user_id == User.id)
        .where(
            AuthSession.id == token_digest(token),
            AuthSession.expires_at > utcnow(),
        )
    )
    result = await db.execute(statement)
    return result.scalar_one_or_none()


async def delete_session(db: AsyncSession, token: str) -> None:
    """세션 행을 삭제해 즉시 무효화한다 (로그아웃). 이미 없어도 오류가 나지 않는다."""
    await db.execute(delete(AuthSession).where(AuthSession.id == token_digest(token)))
    await db.commit()
