# 2026-11-02 - voda-voca - 단어장 라우터: /api/wordbooks CRUD (REQ-004~007, REQ-003)
# 파일 위치: src/backend/routers/wordbook.py

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.deps import get_current_user
from backend.db.session import get_db_session
from backend.models import User, Wordbook
from backend.schemas.wordbook import WordbookCreate, WordbookOut, WordbookPage, WordbookUpdate
from backend.services import wordbook as wordbook_service
from backend.services.seed import SeedDataMissingError

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


def _with_count(wordbook: Wordbook, count: int) -> WordbookOut:
    return WordbookOut.model_validate(wordbook).model_copy(update={"word_count": count})


@router.post("/presets/intermediate-1000", status_code=status.HTTP_201_CREATED, response_model=WordbookOut)
async def create_intermediate_preset(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> WordbookOut:
    """추천 프리셋 '중급 필수 영단어 1,000'을 내 단어장으로 추가한다 (단어 1,000건, 한 트랜잭션)."""
    try:
        wordbook = await wordbook_service.create_preset_wordbook(db, user.id, "intermediate-1000")
    except wordbook_service.WordbookNameTakenError as exc:
        raise NAME_TAKEN from exc
    except SeedDataMissingError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="추천 단어장 데이터가 아직 준비되지 않았습니다.",
        ) from exc
    count = await wordbook_service.count_words(db, wordbook.id)
    return _with_count(wordbook, count)


@router.get("", response_model=WordbookPage)
async def list_wordbooks(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=PAGE_SIZE_DEFAULT, ge=1, le=PAGE_SIZE_MAX),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> WordbookPage:
    rows, total = await wordbook_service.list_wordbooks(db, user.id, page, size)
    return WordbookPage(
        items=[_with_count(wordbook, count) for wordbook, count in rows],
        total=total,
        page=page,
        size=size,
    )


@router.get("/{wordbook_id}", response_model=WordbookOut)
async def get_wordbook(
    wordbook_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> WordbookOut:
    try:
        wordbook = await wordbook_service.get_owned_wordbook(db, user.id, wordbook_id)
    except wordbook_service.WordbookNotFoundError as exc:
        raise NOT_FOUND from exc
    return _with_count(wordbook, await wordbook_service.count_words(db, wordbook.id))


@router.patch("/{wordbook_id}", response_model=WordbookOut)
async def update_wordbook(
    wordbook_id: int,
    body: WordbookUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> WordbookOut:
    try:
        wordbook = await wordbook_service.update_wordbook(db, user.id, wordbook_id, body)
    except wordbook_service.WordbookNotFoundError as exc:
        raise NOT_FOUND from exc
    except wordbook_service.WordbookNameTakenError as exc:
        raise NAME_TAKEN from exc
    return _with_count(wordbook, await wordbook_service.count_words(db, wordbook.id))


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
