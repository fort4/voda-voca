# 2026-11-05 - voda-voca - 회원가입(기본 학습 단어장 지정), 닉네임·비밀번호 확인, 회원 탈퇴 로직 (REQ-001~003, REQ-105)
# 파일 위치: src/backend/services/auth.py

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import SystemVocabulary, User
from backend.services.password import get_dummy_hash, hash_password, verify_password

UNIQUE_NICKNAME_CONSTRAINT = "uk_users_nickname"
# 가입 직후 학습 단어장으로 지정할 표준 단어장 (초급 200제). 시드 파일의 slug 와 같아야 한다.
DEFAULT_VOCABULARY_SLUG = "beginner-200"


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
    """계정을 만들고 기본 표준 단어장(초급 200제)을 학습 단어장으로 지정한다. 한 트랜잭션이다.

    - 닉네임 중복은 UNIQUE 제약 위반으로 판정한다 (REQ-105). 실패하면 계정이 남지 않는다.
    - 단어장·단어를 사용자별로 복사하지 않는다. 표준 단어장은 모든 사용자가 공유하는 읽기 전용 콘텐츠다.
    - 기본 단어장이 아직 없으면(시드 전) 활성 단어장은 비워 두고 가입은 성공시킨다.
    """
    default_vocabulary_id = (
        await db.execute(select(SystemVocabulary.id).where(SystemVocabulary.slug == DEFAULT_VOCABULARY_SLUG))
    ).scalar_one_or_none()
    user = User(
        password_hash=await hash_password(password),
        nickname=normalize_nickname(nickname),
        active_vocabulary_id=default_vocabulary_id,
    )
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
    """회원 탈퇴. users 행을 지우면 DB 의 ON DELETE CASCADE 가 세션, 북마크, 학습 이력,
    단어 진행도, 퀴즈 세션을 함께 지운다. 표준 단어장과 단어는 공용 콘텐츠라 그대로 남는다."""
    await db.execute(delete(User).where(User.id == user_id))
    await db.commit()
