# 2026-11-02 - voda-voca - 단어장 라우터: /api/wordbooks CRUD (REQ-004~007, REQ-003)
# 파일 위치: src/backend/routers/wordbook.py

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.deps import get_current_user
from backend.db.session import get_db_session
from backend.models import User, Wordbook
from backend.schemas.wordbook import WordbookCreate, WordbookOut, WordbookPage, WordbookUpdate
from backend.services import wordbook as wordbook_service

router = APIRouter(prefix="/api/wordbooks", tags=["wordbooks"])

NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="단어장을 찾을 수 없습니다.")
NAME_TAKEN = HTTPException(
    status_code=status.HTTP_409_CONFLICT,
    detail="이미 같은 이름의 단어장이 있습니다.",
)

PAGE_SIZE_DEFAULT = 20
PAGE_SIZE_MAX = 100


@router.post("", status_code=status.HTTP_201_CREATED, response_model=WordbookOut)
async def create_wordbook(
    body: WordbookCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> Wordbook:
    try:
        return await wordbook_service.create_wordbook(db, user.id, body)
    except wordbook_service.WordbookNameTakenError as exc:
        raise NAME_TAKEN from exc


@router.get("", response_model=WordbookPage)
async def list_wordbooks(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=PAGE_SIZE_DEFAULT, ge=1, le=PAGE_SIZE_MAX),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> WordbookPage:
    items, total = await wordbook_service.list_wordbooks(db, user.id, page, size)
    return WordbookPage(
        items=[WordbookOut.model_validate(item) for item in items],
        total=total,
        page=page,
        size=size,
    )


@router.get("/{wordbook_id}", response_model=WordbookOut)
async def get_wordbook(
    wordbook_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> Wordbook:
    try:
        return await wordbook_service.get_owned_wordbook(db, user.id, wordbook_id)
    except wordbook_service.WordbookNotFoundError as exc:
        raise NOT_FOUND from exc


@router.patch("/{wordbook_id}", response_model=WordbookOut)
async def update_wordbook(
    wordbook_id: int,
    body: WordbookUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> Wordbook:
    try:
        return await wordbook_service.update_wordbook(db, user.id, wordbook_id, body)
    except wordbook_service.WordbookNotFoundError as exc:
        raise NOT_FOUND from exc
    except wordbook_service.WordbookNameTakenError as exc:
        raise NAME_TAKEN from exc


@router.delete("/{wordbook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_wordbook(
    wordbook_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    try:
        await wordbook_service.delete_wordbook(db, user.id, wordbook_id)
    except wordbook_service.WordbookNotFoundError as exc:
        raise NOT_FOUND from exc
