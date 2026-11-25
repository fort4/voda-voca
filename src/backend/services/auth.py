# 2026-11-26 - voda-voca - 회원가입(기본 학습 단어장 지정), 닉네임 로그인 인증, 닉네임 중복 확인, 비밀번호 변경, 회원 탈퇴 로직 (REQ-001~003, REQ-105, REQ-158, REQ-159, REQ-164)
# 파일 위치: src/backend/services/auth.py

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.admin import is_admin_nickname
from backend.db.errors import is_unique_violation
from backend.models import AuthSession, SystemVocabulary, User
from backend.services.password import get_dummy_hash, hash_password, verify_password
from backend.services.session import token_digest

# 가입 직후 학습 단어장으로 지정할 표준 단어장 (초급 200제). 시드 파일의 slug 와 같아야 한다.
DEFAULT_VOCABULARY_SLUG = "beginner-200"


class NicknameAlreadyExistsError(Exception):
    """이미 사용 중인 닉네임으로 가입을 시도했을 때."""


class InvalidCredentialsError(Exception):
    """닉네임 또는 비밀번호가 올바르지 않을 때. 어느 쪽이 틀렸는지는 구분하지 않는다 (REQ-002)."""


def normalize_nickname(nickname: str) -> str:
    """로그인 식별용 정규화. 앞뒤 공백만 제거한다.

    대소문자 구분은 DB 콜레이션(NOCASE)이 맡는다. 같은 닉네임은 대소문자와 무관하게 하나만 존재한다.
    """
    return nickname.strip()


async def find_user_id(db: AsyncSession, nickname: str) -> int | None:
    """닉네임의 계정 id (대소문자·앞뒤 공백 무시). 없으면 None."""
    found = await db.execute(select(User.id).where(User.nickname == normalize_nickname(nickname)))
    return found.scalar_one_or_none()


async def is_nickname_available(db: AsyncSession, nickname: str) -> bool:
    """가입에 쓸 수 있는 닉네임인지 본다. 관리자 닉네임은 계정이 없어도 쓸 수 없다."""
    return not is_admin_nickname(nickname) and await find_user_id(db, nickname) is None


async def signup(db: AsyncSession, password: str, nickname: str) -> User:
    """일반 가입. 관리자 닉네임은 예약어라 이미 사용 중인 것으로 본다 (REQ-159)."""
    if is_admin_nickname(nickname):
        raise NicknameAlreadyExistsError
    return await create_user(db, password, nickname)


async def create_user(db: AsyncSession, password: str, nickname: str) -> User:
    """계정을 만들고 기본 표준 단어장(초급 200제)을 학습 단어장으로 지정한다. 한 트랜잭션이다.

    - 닉네임 중복은 UNIQUE 제약 위반으로 판정한다 (REQ-105). 사전 조회가 아니라 제약으로 막아야 동시 가입에도 안전하다. 실패하면 계정이 남지 않는다.
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
        if is_unique_violation(exc, "users", "nickname"):
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


async def change_password(db: AsyncSession, user: User, current: str, new: str, session_token: str) -> None:
    """현재 비밀번호를 확인해 바꾸고, 지금 세션을 뺀 본인의 세션을 모두 지운다. 틀리면 InvalidCredentialsError.

    bcrypt 계산은 수백 ms 가 걸리므로 먼저 트랜잭션을 끝내 SQLite 쓰기 잠금을 놓는다. 그 사이에 비밀번호가 바뀌면
    아래 UPDATE 의 조건(이전 해시)에 걸려 한 행도 바뀌지 않는다.
    """
    user_id, old_hash = user.id, user.password_hash
    await db.commit()
    if not await verify_password(current, old_hash):
        raise InvalidCredentialsError
    new_hash = await hash_password(new)
    result = await db.execute(
        update(User).where(User.id == user_id, User.password_hash == old_hash).values(password_hash=new_hash)
    )
    if result.rowcount != 1:
        await db.rollback()
        raise InvalidCredentialsError
    await db.execute(
        delete(AuthSession).where(AuthSession.user_id == user_id, AuthSession.id != token_digest(session_token))
    )
    await db.commit()


async def delete_account(db: AsyncSession, user_id: int) -> None:
    """회원 탈퇴. users 행을 지우면 DB 의 ON DELETE CASCADE 가 세션, 북마크, 학습 이력,
    단어 진행도, 퀴즈 세션을 함께 지운다. 표준 단어장과 단어는 공용 콘텐츠라 그대로 남는다."""
    await db.execute(delete(User).where(User.id == user_id))
    await db.commit()
