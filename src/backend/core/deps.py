# 2026-11-02 - voda-voca - 인증 의존성: 세션 쿠키로 현재 사용자 확인, 관리자 권한 검사 (REQ-002, REQ-003, REQ-159)
# 파일 위치: src/backend/core/deps.py

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db_session
from backend.models import User
from backend.services.session import resolve_user

SESSION_COOKIE_NAME = "voda_session"

UNAUTHENTICATED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="로그인이 필요합니다.",
)

ADMIN_ONLY = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="관리자만 사용할 수 있습니다.",
)


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> User:
    """세션 쿠키가 유효하면 로그인한 사용자를 반환하고, 아니면 401 을 던진다.

    만료된 세션, 삭제된 세션, 쿠키 없음은 모두 같은 401 로 처리한다.
    """
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        raise UNAUTHENTICATED

    user = await resolve_user(db, token)
    if user is None:
        raise UNAUTHENTICATED
    return user


async def get_admin_user(user: User = Depends(get_current_user)) -> User:
    """관리 API 용 의존성. 비로그인은 401, 일반 사용자는 403 이다."""
    if not user.is_admin:
        raise ADMIN_ONLY
    return user
