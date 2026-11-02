# 2026-11-02 - voda-voca - 단어 라우터: /api/wordbooks/{wordbook_id}/words CRUD 및 접두사 검색 (REQ-008~011)
# 파일 위치: src/backend/routers/word.py

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.deps import get_current_user
from backend.db.session import get_db_session
from backend.models import User, Word
from backend.schemas.word import SEARCH_MAX_CHARS, WordCreate, WordOut, WordPage, WordUpdate
from backend.services import word as word_service
from backend.services.wordbook import WordbookNotFoundError

router = APIRouter(prefix="/api/wordbooks/{wordbook_id}/words", tags=["words"])

WORDBOOK_NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="단어장을 찾을 수 없습니다.",
)
WORD_NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="단어를 찾을 수 없습니다.",
)
TERM_TAKEN = HTTPException(
    status_code=status.HTTP_409_CONFLICT,
    detail="같은 단어장에 이미 있는 표제어입니다.",
)

PAGE_SIZE_DEFAULT = 20
PAGE_SIZE_MAX = 100


@router.post("", status_code=status.HTTP_201_CREATED, response_model=WordOut)
async def create_word(
    wordbook_id: int,
    body: WordCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> Word:
    try:
        return await word_service.create_word(db, user.id, wordbook_id, body)
    except WordbookNotFoundError as exc:
        raise WORDBOOK_NOT_FOUND from exc
    except word_service.WordTermTakenError as exc:
        raise TERM_TAKEN from exc


@router.get("", response_model=WordPage)
async def list_words(
    wordbook_id: int,
    q: str | None = Query(default=None, max_length=SEARCH_MAX_CHARS, description="표제어 접두사"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=PAGE_SIZE_DEFAULT, ge=1, le=PAGE_SIZE_MAX),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> WordPage:
    try:
        items, total = await word_service.list_words(db, user.id, wordbook_id, q, page, size)
    except WordbookNotFoundError as exc:
        raise WORDBOOK_NOT_FOUND from exc
    return WordPage(
        items=[WordOut.model_validate(item) for item in items],
        total=total,
        page=page,
        size=size,
    )


@router.get("/{word_id}", response_model=WordOut)
async def get_word(
    wordbook_id: int,
    word_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> Word:
    try:
        return await word_service.get_word(db, user.id, wordbook_id, word_id)
    except WordbookNotFoundError as exc:
        raise WORDBOOK_NOT_FOUND from exc
    except word_service.WordNotFoundError as exc:
        raise WORD_NOT_FOUND from exc


@router.patch("/{word_id}", response_model=WordOut)
async def update_word(
    wordbook_id: int,
    word_id: int,
    body: WordUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> Word:
    try:
        return await word_service.update_word(db, user.id, wordbook_id, word_id, body)
    except WordbookNotFoundError as exc:
        raise WORDBOOK_NOT_FOUND from exc
    except word_service.WordNotFoundError as exc:
        raise WORD_NOT_FOUND from exc
    except word_service.WordTermTakenError as exc:
        raise TERM_TAKEN from exc


@router.delete("/{word_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_word(
    wordbook_id: int,
    word_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    try:
        await word_service.delete_word(db, user.id, wordbook_id, word_id)
    except WordbookNotFoundError as exc:
        raise WORDBOOK_NOT_FOUND from exc
    except word_service.WordNotFoundError as exc:
        raise WORD_NOT_FOUND from exc
