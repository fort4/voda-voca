# 2026-11-02 - voda-voca - 회원가입 및 자격 증명 확인 로직 (REQ-001, REQ-002, REQ-003)
# 파일 위치: src/backend/services/auth.py

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import User
from backend.services.password import get_dummy_hash, hash_password, verify_password

UNIQUE_EMAIL_CONSTRAINT = "uk_users_email"


class EmailAlreadyExistsError(Exception):
    """이미 등록된 이메일로 가입을 시도했을 때."""


class InvalidCredentialsError(Exception):
    """이메일 또는 비밀번호가 올바르지 않을 때. 어느 쪽이 틀렸는지는 구분하지 않는다 (REQ-002)."""


async def signup(db: AsyncSession, email: str, password: str, nickname: str) -> User:
    """계정을 만든다. 이메일 중복은 애플리케이션 검사가 아니라 UNIQUE 제약 위반으로 판정한다 (REQ-105).

    동시에 같은 이메일로 가입해도 한 쪽만 성공하도록 DB 제약을 최종 방어선으로 쓴다.
    """
    user = User(
        email=email,
        password_hash=await hash_password(password),
        nickname=nickname,
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        if UNIQUE_EMAIL_CONSTRAINT in str(exc.orig):
            raise EmailAlreadyExistsError from exc
        raise
    await db.refresh(user)
    return user


async def authenticate(db: AsyncSession, email: str, password: str) -> User:
    """이메일과 비밀번호를 확인해 사용자를 반환한다. 실패하면 InvalidCredentialsError."""
    result = await db.execute(select(User).where(User.email == email.strip().lower()))
    user = result.scalar_one_or_none()

    if user is None:
        # 계정이 없어도 같은 비용의 검증을 수행해 응답 시간 차이를 줄인다 (REQ-002).
        await verify_password(password, await get_dummy_hash())
        raise InvalidCredentialsError

    if not await verify_password(password, user.password_hash):
        raise InvalidCredentialsError
    return user
