# 2026-11-02 - voda-voca - 북마크 라우터: PUT/DELETE(멱등 등록·해제), 목록 조회 (REQ-017, REQ-018)
# 파일 위치: src/backend/routers/bookmark.py

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.deps import get_current_user
from backend.db.session import get_db_session
from backend.models import User
from backend.schemas.bookmark import BookmarkOut, BookmarkPage
from backend.services import bookmark as bookmark_service
from backend.services.errors import WordNotFoundError

router = APIRouter(prefix="/api/bookmarks", tags=["bookmarks"])

WORD_NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="단어를 찾을 수 없습니다.",
)

PAGE_SIZE_DEFAULT = 20
PAGE_SIZE_MAX = 100


@router.put("/{word_id}", status_code=status.HTTP_204_NO_CONTENT)
async def put_bookmark(
    word_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """북마크 등록. 여러 번 호출해도 결과는 같다 (멱등)."""
    try:
        await bookmark_service.set_bookmark(db, user.id, word_id)
    except WordNotFoundError as exc:
        raise WORD_NOT_FOUND from exc


@router.delete("/{word_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bookmark(
    word_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """북마크 해제. 없어도 204 다 (멱등)."""
    await bookmark_service.clear_bookmark(db, user.id, word_id)


@router.get("", response_model=BookmarkPage)
async def list_bookmarks(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=PAGE_SIZE_DEFAULT, ge=1, le=PAGE_SIZE_MAX),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> BookmarkPage:
    rows, total = await bookmark_service.list_bookmarks(db, user.id, page, size)
    items = [
        BookmarkOut(
            word_id=bookmark.word_id,
            vocabulary_id=word.vocabulary_id,
            vocabulary_title=vocabulary.title,
            term=word.term,
            meaning=word.meaning,
            example=word.example,
            example_meaning=word.example_meaning,
            pos=word.pos,
            phonetic=word.phonetic,
            bookmarked_at=bookmark.created_at,
        )
        for bookmark, word, vocabulary in rows
    ]
    return BookmarkPage(items=items, total=total, page=page, size=size)
