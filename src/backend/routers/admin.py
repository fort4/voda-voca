# 2026-11-26 - voda-voca - 관리 라우터: 관리자 단어장과 단어의 생성·수정·삭제 (관리자만, REQ-159~161)
# 파일 위치: src/backend/routers/admin.py

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.deps import get_admin_user
from backend.db.session import get_db_session
from backend.models import User
from backend.routers.vocabulary import VOCABULARY_NOT_FOUND, word_out
from backend.schemas.admin import VocabularyCreate, VocabularyUpdate, WordInput
from backend.schemas.vocabulary import VocabularyOut, VocabularyWordOut
from backend.services import admin_content, system_vocab
from backend.services.errors import VocabularyNotFoundError, WordNotFoundError

# 라우터 전체에 관리자 검사를 건다. 새 경로를 더해도 검사가 빠지지 않는다.
router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(get_admin_user)])


@asynccontextmanager
async def _http_errors() -> AsyncIterator[None]:
    """서비스 예외를 HTTP 응답으로 바꾼다. 화면은 문구가 아니라 X-Error-Code 로 분기한다."""
    try:
        yield
    except VocabularyNotFoundError as exc:
        raise VOCABULARY_NOT_FOUND from exc
    except WordNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="단어를 찾을 수 없습니다.") from exc
    except admin_content.SeedReadOnlyError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="표준 단어장의 내용은 수정하거나 삭제할 수 없습니다.",
            headers={"X-Error-Code": "SEED_READ_ONLY"},
        ) from exc
    except admin_content.DuplicateTermError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이 단어장에 이미 있는 표제어입니다.",
            headers={"X-Error-Code": "TERM_TAKEN"},
        ) from exc


@router.post("/vocabularies", status_code=status.HTTP_201_CREATED, response_model=VocabularyOut)
async def create_vocabulary(
    body: VocabularyCreate,
    user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db_session),
) -> VocabularyOut:
    vocabulary = await admin_content.create_vocabulary(db, body)
    return await system_vocab.vocabulary_entry(db, user, vocabulary)


@router.patch("/vocabularies/{vocabulary_id}", response_model=VocabularyOut)
async def update_vocabulary(
    vocabulary_id: int,
    body: VocabularyUpdate,
    user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db_session),
) -> VocabularyOut:
    async with _http_errors():
        vocabulary = await admin_content.update_vocabulary(db, vocabulary_id, body)
    return await system_vocab.vocabulary_entry(db, user, vocabulary)


@router.delete("/vocabularies/{vocabulary_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vocabulary(vocabulary_id: int, db: AsyncSession = Depends(get_db_session)) -> None:
    async with _http_errors():
        await admin_content.delete_vocabulary(db, vocabulary_id)


@router.post(
    "/vocabularies/{vocabulary_id}/words", status_code=status.HTTP_201_CREATED, response_model=VocabularyWordOut
)
async def add_word(
    vocabulary_id: int, body: WordInput, db: AsyncSession = Depends(get_db_session)
) -> VocabularyWordOut:
    async with _http_errors():
        word = await admin_content.add_word(db, vocabulary_id, body)
    return word_out(word, bookmarked=False)


@router.put("/words/{word_id}", response_model=VocabularyWordOut)
async def update_word(
    word_id: int,
    body: WordInput,
    user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db_session),
) -> VocabularyWordOut:
    async with _http_errors():
        word = await admin_content.update_word(db, word_id, body)
    return word_out(word, bookmarked=await system_vocab.is_bookmarked(db, user.id, word.id))


@router.delete("/words/{word_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_word(word_id: int, db: AsyncSession = Depends(get_db_session)) -> None:
    async with _http_errors():
        await admin_content.delete_word(db, word_id)
