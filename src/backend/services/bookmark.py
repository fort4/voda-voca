# 2026-11-02 - voda-voca - 북마크 서비스: 멱등 등록/해제, 소유권 검증, 목록 조회 (REQ-017, REQ-018, REQ-105)
# 파일 위치: src/backend/services/bookmark.py

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Bookmark, Word, Wordbook
from backend.services.word import WordNotFoundError

UNIQUE_BOOKMARK_CONSTRAINT = "uk_bookmarks_user_word"
FK_BOOKMARK_WORD = "fk_bookmarks_word"


async def _ensure_owned_word(db: AsyncSession, user_id: int, word_id: int) -> None:
    """요청 사용자가 소유한 단어장에 속한 단어인지 확인한다.

    타인 단어와 없는 단어는 같은 WordNotFoundError 가 된다 (404 일원화, REQ-003).
    """
    result = await db.execute(
        select(Word.id)
        .join(Wordbook, Wordbook.id == Word.wordbook_id)
        .where(Word.id == word_id, Wordbook.user_id == user_id)
    )
    if result.scalar_one_or_none() is None:
        raise WordNotFoundError


async def set_bookmark(db: AsyncSession, user_id: int, word_id: int) -> None:
    """북마크를 등록한다. 이미 등록되어 있어도 성공으로 본다 (멱등, REQ-017).

    동시에 두 요청이 들어와도 uk_bookmarks_user_word 가 행을 하나만 허용하고,
    뒤의 요청은 중복 위반을 받아 성공으로 처리된다.
    """
    await _ensure_owned_word(db, user_id, word_id)
    db.add(Bookmark(user_id=user_id, word_id=word_id))
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        message = str(exc.orig)
        if UNIQUE_BOOKMARK_CONSTRAINT in message:
            return  # 이미 등록됨: 멱등 성공
        if FK_BOOKMARK_WORD in message:
            # 확인 후 등록 전에 단어가 삭제된 경우
            raise WordNotFoundError from exc
        raise


async def clear_bookmark(db: AsyncSession, user_id: int, word_id: int) -> None:
    """북마크를 해제한다. 없어도 성공이다 (멱등, REQ-017).

    요청 사용자의 행만 지우므로 다른 사용자의 북마크와 단어 존재 여부는 드러나지 않는다.
    """
    await db.execute(
        delete(Bookmark).where(Bookmark.user_id == user_id, Bookmark.word_id == word_id)
    )
    await db.commit()


async def list_bookmarks(
    db: AsyncSession, user_id: int, page: int, size: int
) -> tuple[list[tuple[Bookmark, Word, str]], int]:
    """본인 북마크를 최신 등록순(created_at DESC, id DESC)으로 한 페이지 반환한다 (REQ-018).

    각 항목은 (북마크, 단어, 단어장 이름)이다.
    """
    total = (
        await db.execute(
            select(func.count()).select_from(Bookmark).where(Bookmark.user_id == user_id)
        )
    ).scalar_one()

    result = await db.execute(
        select(Bookmark, Word, Wordbook.name)
        .join(Word, Word.id == Bookmark.word_id)
        .join(Wordbook, Wordbook.id == Word.wordbook_id)
        .where(Bookmark.user_id == user_id)
        .order_by(Bookmark.created_at.desc(), Bookmark.id.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    return [tuple(row) for row in result.all()], total
