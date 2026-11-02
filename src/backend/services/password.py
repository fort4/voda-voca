# 2026-11-02 - voda-voca - bcrypt 비밀번호 해시/검증 (REQ-110, ADR-002)
# 파일 위치: src/backend/services/password.py

import asyncio
from functools import lru_cache

import bcrypt

from backend.core.config import get_settings
from backend.schemas.auth import PASSWORD_MAX_BYTES


def _hash_sync(plain: str) -> str:
    salt = bcrypt.gensalt(rounds=get_settings().bcrypt_rounds)
    return bcrypt.hashpw(plain.encode("utf-8"), salt).decode("ascii")


def _verify_sync(plain: str, hashed: str) -> bool:
    # bcrypt 5.x 는 72바이트 초과 입력에 ValueError 를 던진다. 검증 단계에서는 일치하지 않는 것으로 본다.
    if len(plain.encode("utf-8")) > PASSWORD_MAX_BYTES:
        return False
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("ascii"))
    except ValueError:
        # 저장된 해시 형식이 깨졌을 때도 예외로 500 을 내지 않고 불일치로 처리한다.
        return False


async def hash_password(plain: str) -> str:
    """bcrypt 해시를 만든다. CPU 를 많이 쓰므로 스레드에서 실행해 이벤트 루프를 막지 않는다 (REQ-101)."""
    return await asyncio.to_thread(_hash_sync, plain)


async def verify_password(plain: str, hashed: str) -> bool:
    return await asyncio.to_thread(_verify_sync, plain, hashed)


@lru_cache
def _dummy_hash_sync() -> str:
    return _hash_sync("timing-equalization-dummy")


async def get_dummy_hash() -> str:
    """존재하지 않는 이메일로 로그인할 때 사용할 해시.

    계정이 없어도 bcrypt 비교를 한 번 수행해, 응답 시간으로 계정 존재 여부를 추측하지 못하게 한다 (REQ-002).
    """
    return await asyncio.to_thread(_dummy_hash_sync)
