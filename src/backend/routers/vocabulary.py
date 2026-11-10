# 2026-11-05 - voda-voca - 표준 단어장 라우터: 카탈로그, 단어 목록, 활성 단어장 변경
# 파일 위치: src/backend/routers/vocabulary.py

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.deps import get_current_user
from backend.db.session import get_db_session
from backend.models import User
from backend.schemas.vocabulary import ActiveVocabularyIn, VocabularyOut, VocabularyWordOut, VocabularyWordPage
from backend.services import system_vocab
from backend.services.errors import VocabularyNotFoundError

router = APIRouter(prefix="/api/vocabularies", tags=["vocabularies"])
me_router = APIRouter(prefix="/api/users/me", tags=["users"])

VOCABULARY_NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="단어장을 찾을 수 없습니다.",
)

WORD_PAGE_SIZE_DEFAULT = 50
WORD_PAGE_SIZE_MAX = 200


@router.get("", response_model=list[VocabularyOut])
async def list_vocabularies(
    category: str | None = Query(default=None, max_length=50, description="카테고리로 거르기 (예: ELEMENTARY)"),
    level: int | None = Query(default=None, ge=1, le=5, description="레벨로 거르기"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> list[VocabularyOut]:
    """표준 단어장 카탈로그. 단어 수와 내 진행률(풀어 본 수, 숙련 수, 활성 여부)을 함께 준다."""
    return await system_vocab.list_vocabularies(db, user, category, level)


@router.get("/{vocabulary_id}/words", response_model=VocabularyWordPage)
async def list_vocabulary_words(
    vocabulary_id: int,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=WORD_PAGE_SIZE_DEFAULT, ge=1, le=WORD_PAGE_SIZE_MAX),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> VocabularyWordPage:
    """단어장의 단어 목록 (읽기 전용). 내 북마크 여부를 함께 준다."""
    try:
        rows, total = await system_vocab.list_words(db, user.id, vocabulary_id, page, size)
    except VocabularyNotFoundError as exc:
        raise VOCABULARY_NOT_FOUND from exc
    return VocabularyWordPage(
        vocabulary_id=vocabulary_id,
        items=[
            VocabularyWordOut(
                word_id=word.id,
                term=word.term,
                meaning=word.meaning,
                example=word.example,
                example_meaning=word.example_meaning,
                phonetic=word.phonetic,
                pos=word.pos,
                bookmarked=bookmarked,
            )
            for word, bookmarked in rows
        ],
        total=total,
        page=page,
        size=size,
    )


@me_router.post("/active-vocabulary", response_model=VocabularyOut)
async def set_active_vocabulary(
    body: ActiveVocabularyIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> VocabularyOut:
    """지금 학습할 단어장을 바꾼다. 같은 단어장을 다시 지정해도 성공한다."""
    try:
        return await system_vocab.set_active_vocabulary(db, user, body.vocabulary_id)
    except VocabularyNotFoundError as exc:
        raise VOCABULARY_NOT_FOUND from exc
