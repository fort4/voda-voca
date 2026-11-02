# 2026-11-02 - voda-voca - 인증 단위 테스트: bcrypt 해시, 세션 토큰 다이제스트
# 파일 위치: src/backend/tests/test_auth_units.py

import hashlib

import pytest

from backend.services.password import hash_password, verify_password
from backend.services.session import new_token, token_digest


@pytest.mark.asyncio
async def test_hash_is_bcrypt_and_not_plaintext() -> None:
    hashed = await hash_password("correct-horse")
    assert hashed.startswith("$2b$")
    assert "correct-horse" not in hashed


@pytest.mark.asyncio
async def test_verify_accepts_correct_password_and_rejects_wrong_one() -> None:
    hashed = await hash_password("correct-horse")
    assert await verify_password("correct-horse", hashed) is True
    assert await verify_password("wrong-horse00", hashed) is False


@pytest.mark.asyncio
async def test_same_password_produces_different_hashes() -> None:
    # 솔트가 매번 달라야 한다.
    assert await hash_password("same-password") != await hash_password("same-password")


@pytest.mark.asyncio
async def test_verify_over_72_bytes_returns_false_without_raising() -> None:
    hashed = await hash_password("short-pass1")
    assert await verify_password("a" * 73, hashed) is False


@pytest.mark.asyncio
async def test_verify_with_corrupted_hash_returns_false() -> None:
    assert await verify_password("anything-1", "not-a-bcrypt-hash") is False


def test_new_token_is_unique_and_url_safe() -> None:
    tokens = {new_token() for _ in range(100)}
    assert len(tokens) == 100
    assert all(len(t) >= 43 for t in tokens)
    assert all(c.isalnum() or c in "-_" for t in tokens for c in t)


def test_token_digest_is_sha256_of_token() -> None:
    token = "example-token"
    digest = token_digest(token)
    assert len(digest) == 32
    assert digest == hashlib.sha256(token.encode("ascii")).digest()
    assert digest != token.encode("ascii")


@pytest.mark.asyncio
async def test_signup_reraises_unexpected_integrity_error() -> None:
    """닉네임 중복이 아닌 무결성 오류는 NicknameAlreadyExists 로 바꾸지 않고 그대로 전파한다."""
    from sqlalchemy.exc import IntegrityError

    from backend.services.auth import signup

    class _FakeOrig(Exception):
        pass

    class _FakeDB:
        def add(self, _obj: object) -> None:
            pass

        async def commit(self) -> None:
            raise IntegrityError("INSERT", {}, _FakeOrig("Check constraint violated"))

        async def rollback(self) -> None:
            pass

    with pytest.raises(IntegrityError):
        await signup(_FakeDB(), "password-1", "닉네임")  # type: ignore[arg-type]
