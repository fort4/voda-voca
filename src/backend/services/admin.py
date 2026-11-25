# 2026-11-26 - voda-voca - 서버 시작 때 관리자 계정을 준비한다. 이미 있으면 건드리지 않는다 (REQ-159)
# 파일 위치: src/backend/services/admin.py

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.admin import ADMIN_INITIAL_PASSWORD, ADMIN_NICKNAME
from backend.db.session import get_session_factory
from backend.services import auth as auth_service

logger = logging.getLogger(__name__)


async def ensure_admin_account(db: AsyncSession) -> bool:
    """관리자 계정이 없으면 초기 비밀번호로 만든다. 새로 만들었으면 True.

    바꾼 비밀번호를 지키기 위해 기존 계정은 절대 고치지 않는다. 여러 워커가 동시에 시작해도 UNIQUE 제약이 하나만 남긴다.
    """
    if await auth_service.find_user_id(db, ADMIN_NICKNAME) is not None:
        await db.commit()
        return False
    try:
        await auth_service.create_user(db, ADMIN_INITIAL_PASSWORD, ADMIN_NICKNAME)
    except auth_service.NicknameAlreadyExistsError:
        return False
    logger.warning("관리자 계정(%s)을 초기 비밀번호로 만들었습니다. 로그인해 바로 바꿔 주세요.", ADMIN_NICKNAME)
    return True


async def init_admin_account() -> bool:
    """앱 시작(lifespan) 시 호출한다."""
    async with get_session_factory()() as session:
        return await ensure_admin_account(session)
