# 2026-11-02 - voda-voca - 북마크 서비스 단위 테스트: 중복/FK 충돌의 분기 처리 (DB 없이 가짜 세션 사용)
# 파일 위치: src/backend/tests/test_bookmark_units.py

import pytest
from sqlalchemy.exc import IntegrityError

from backend.services import bookmark as bookmark_service
from backend.services.word import WordNotFoundError


class _FakeSession:
    def __init__(self, error: Exception | None) -> None:
        self.error = error
        self.added: list[object] = []
        self.rolled_back = False

    def add(self, obj: object) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        if self.error is not None:
            raise self.error

    async def rollback(self) -> None:
        self.rolled_back = True


def _integrity(message: str) -> IntegrityError:
    return IntegrityError("INSERT INTO bookmarks", {}, Exception(message))


@pytest.fixture
def owned(monkeypatch: pytest.MonkeyPatch) -> None:
    """소유권 검사는 통과한 것으로 두고, 커밋 충돌 분기만 검증한다."""

    async def _ok(*_args: object) -> None:
        return None

    monkeypatch.setattr(bookmark_service, "_ensure_owned_word", _ok)


@pytest.mark.asyncio
async def test_unique_conflict_is_treated_as_idempotent_success(owned: None) -> None:
    session = _FakeSession(_integrity("Duplicate entry '1-2' for key 'bookmarks.uk_bookmarks_user_word'"))
    await bookmark_service.set_bookmark(session, 1, 2)  # 예외 없이 끝나야 한다
    assert session.rolled_back is True


@pytest.mark.asyncio
async def test_foreign_key_conflict_becomes_word_not_found(owned: None) -> None:
    session = _FakeSession(_integrity("a foreign key constraint fails (`bookmarks`, CONSTRAINT `fk_bookmarks_word`)"))
    with pytest.raises(WordNotFoundError):
        await bookmark_service.set_bookmark(session, 1, 2)


@pytest.mark.asyncio
async def test_unrelated_integrity_error_is_reraised(owned: None) -> None:
    session = _FakeSession(_integrity("Check constraint violated"))
    with pytest.raises(IntegrityError):
        await bookmark_service.set_bookmark(session, 1, 2)
