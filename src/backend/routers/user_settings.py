# 2026-11-10 - voda-voca - 학습 개수 설정 라우터: 퀴즈·플래시카드 문항 수와 오늘의 목표 조회·수정 (REQ-147)
# 파일 위치: src/backend/routers/user_settings.py

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.deps import get_current_user
from backend.db.session import get_db_session
from backend.models import User
from backend.schemas.user_settings import UserSettingsOut, UserSettingsPatch

router = APIRouter(prefix="/api/users/me/settings", tags=["users"])


@router.get("", response_model=UserSettingsOut)
async def get_settings(user: User = Depends(get_current_user)) -> User:
    """내 학습 개수 설정과 선택 가능한 값 목록."""
    return user


@router.patch("", response_model=UserSettingsOut)
async def update_settings(
    body: UserSettingsPatch,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> User:
    """보낸 필드만 바꾼다. 빈 본문은 변경 없이 현재 값을 돌려준다."""
    changes = body.model_dump(exclude_unset=True)
    for name, value in changes.items():
        setattr(user, name, value)
    if changes:
        await db.commit()
    return user
