# 2026-11-02 - voda-voca - 회원가입, 닉네임·비밀번호 확인, 회원 탈퇴 로직 (REQ-001, REQ-002, REQ-003, REQ-105)
# 파일 위치: src/backend/services/auth.py

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import User
from backend.services.password import get_dummy_hash, hash_password, verify_password

UNIQUE_NICKNAME_CONSTRAINT = "uk_users_nickname"


class NicknameAlreadyExistsError(Exception):
    """이미 사용 중인 닉네임으로 가입을 시도했을 때."""


class InvalidCredentialsError(Exception):
    """닉네임 또는 비밀번호가 올바르지 않을 때. 어느 쪽이 틀렸는지는 구분하지 않는다 (REQ-002)."""


def normalize_nickname(nickname: str) -> str:
    """로그인 식별용 정규화. 앞뒤 공백만 제거한다.

    대소문자 구분은 DB 콜레이션(utf8mb4_0900_ai_ci)이 맡는다. 같은 닉네임은 대소문자와 무관하게 하나만 존재한다.
    """
    return nickname.strip()


async def signup(db: AsyncSession, password: str, nickname: str) -> User:
    """계정을 만든다. 닉네임 중복은 애플리케이션 검사가 아니라 UNIQUE 제약 위반으로 판정한다 (REQ-105)."""
    user = User(password_hash=await hash_password(password), nickname=normalize_nickname(nickname))
    db.add(user)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        if UNIQUE_NICKNAME_CONSTRAINT in str(exc.orig):
            raise NicknameAlreadyExistsError from exc
        raise
    await db.refresh(user)
    return user


async def authenticate(db: AsyncSession, nickname: str, password: str) -> User:
    """닉네임과 비밀번호를 확인해 사용자를 반환한다. 실패하면 InvalidCredentialsError."""
    result = await db.execute(select(User).where(User.nickname == normalize_nickname(nickname)))
    user = result.scalar_one_or_none()

    if user is None:
        # 계정이 없어도 같은 비용의 검증을 수행해 응답 시간 차이를 줄인다 (REQ-002).
        await verify_password(password, await get_dummy_hash())
        raise InvalidCredentialsError

    if not await verify_password(password, user.password_hash):
        raise InvalidCredentialsError
    return user


async def delete_account(db: AsyncSession, user_id: int) -> None:
    """회원 탈퇴. users 행을 지우면 DB 의 ON DELETE CASCADE 가 세션, 단어장, 단어, 북마크,
    학습 이력, 퀴즈 세션을 함께 지운다 (REQ-007 과 같은 원칙, 회원 탈퇴 요구)."""
    await db.execute(delete(User).where(User.id == user_id))
    await db.commit()
