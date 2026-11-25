# 2026-11-26 - voda-voca - 관리자 콘텐츠 서비스: 관리자 단어장과 단어의 생성·수정·삭제, 일괄 등록. 시드 콘텐츠는 읽기 전용이다 (REQ-160~162)
# 파일 위치: src/backend/services/admin_content.py

import uuid
from dataclasses import dataclass

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.terms import term_key
from backend.models import SystemVocabulary, SystemWord
from backend.models.base import SOURCE_ADMIN
from backend.schemas.admin import VocabularyCreate, VocabularyUpdate, WordInput
from backend.services.errors import VocabularyNotFoundError, WordNotFoundError

ADMIN_SLUG_PREFIX = "admin-"  # 시드 slug 와 겹치지 않게 서버가 붙인다


class SeedReadOnlyError(Exception):
    """표준(시드) 콘텐츠는 수정·삭제할 수 없다."""


class DuplicateTermError(Exception):
    """같은 단어장에 같은 표제어(대소문자·악센트 무시)가 있다."""


async def _get_vocabulary(db: AsyncSession, vocabulary_id: int) -> SystemVocabulary:
    vocabulary = await db.get(SystemVocabulary, vocabulary_id)
    if vocabulary is None:
        raise VocabularyNotFoundError
    return vocabulary


async def _own_vocabulary(db: AsyncSession, vocabulary_id: int) -> SystemVocabulary:
    vocabulary = await _get_vocabulary(db, vocabulary_id)
    if vocabulary.source != SOURCE_ADMIN:
        raise SeedReadOnlyError
    return vocabulary


async def _own_word(db: AsyncSession, word_id: int) -> SystemWord:
    word = await db.get(SystemWord, word_id)
    if word is None:
        raise WordNotFoundError
    if word.source != SOURCE_ADMIN:
        raise SeedReadOnlyError
    return word


async def create_vocabulary(db: AsyncSession, data: VocabularyCreate) -> SystemVocabulary:
    last = await db.scalar(select(func.max(SystemVocabulary.sort_order)))
    vocabulary = SystemVocabulary(
        slug=f"{ADMIN_SLUG_PREFIX}{uuid.uuid4().hex[:12]}",
        title=data.title,
        description=data.description,
        category=data.category,
        level=data.level,
        sort_order=(last or 0) + 1,  # 표준 단어장 뒤에 보인다
        source=SOURCE_ADMIN,
    )
    db.add(vocabulary)
    await db.commit()
    await db.refresh(vocabulary)
    return vocabulary


async def update_vocabulary(db: AsyncSession, vocabulary_id: int, data: VocabularyUpdate) -> SystemVocabulary:
    vocabulary = await _own_vocabulary(db, vocabulary_id)
    for name in data.model_fields_set:
        setattr(vocabulary, name, getattr(data, name))
    await db.commit()
    await db.refresh(vocabulary)
    return vocabulary


async def delete_vocabulary(db: AsyncSession, vocabulary_id: int) -> None:
    """단어장을 지운다. DB 의 CASCADE 가 단어, 학습 이력, 진도, 북마크, 학습 세션을 함께 지우고 활성 선택은 비운다."""
    await _own_vocabulary(db, vocabulary_id)
    await db.execute(delete(SystemVocabulary).where(SystemVocabulary.id == vocabulary_id))
    await db.commit()


async def _ensure_term_free(db: AsyncSession, vocabulary_id: int, term: str, except_word_id: int | None = None) -> None:
    """트랜잭션이 BEGIN IMMEDIATE 라 확인과 저장 사이에 다른 쓰기가 끼어들지 않는다.

    term_key 는 DB 의 NOCASE 보다 넓게 같다고 보므로, 여기를 통과하면 UNIQUE 제약에 걸리지 않는다.
    """
    key = term_key(term)
    rows = await db.execute(select(SystemWord.id, SystemWord.term).where(SystemWord.vocabulary_id == vocabulary_id))
    if any(word_id != except_word_id and term_key(existing) == key for word_id, existing in rows.all()):
        raise DuplicateTermError


async def _next_order_index(db: AsyncSession, vocabulary_id: int) -> int:
    last = await db.scalar(
        select(func.max(SystemWord.order_index)).where(SystemWord.vocabulary_id == vocabulary_id)
    )
    return 0 if last is None else last + 1


async def refresh_total_words(db: AsyncSession, vocabulary: SystemVocabulary) -> None:
    await db.flush()
    total = await db.scalar(
        select(func.count()).select_from(SystemWord).where(SystemWord.vocabulary_id == vocabulary.id)
    )
    vocabulary.total_words = int(total or 0)


async def add_word(db: AsyncSession, vocabulary_id: int, data: WordInput) -> SystemWord:
    """단어를 단어장 끝에 더한다. 표준 단어장에도 더할 수 있다."""
    vocabulary = await _get_vocabulary(db, vocabulary_id)
    await _ensure_term_free(db, vocabulary_id, data.term)
    word = SystemWord(
        vocabulary_id=vocabulary_id,
        order_index=await _next_order_index(db, vocabulary_id),
        source=SOURCE_ADMIN,
        **data.model_dump(),
    )
    db.add(word)
    await refresh_total_words(db, vocabulary)
    await db.commit()
    return word


@dataclass(frozen=True)
class ImportResult:
    created: int
    skipped: int  # 이미 있거나 같은 파일에서 앞에 나온 표제어


async def import_words(db: AsyncSession, vocabulary_id: int, words: list[WordInput]) -> ImportResult:
    """여러 단어를 트랜잭션 하나로 단어장 끝에 더한다. 중복 표제어는 건너뛰고 기존 단어를 바꾸지 않는다 (REQ-162)."""
    vocabulary = await _get_vocabulary(db, vocabulary_id)
    terms = await db.scalars(select(SystemWord.term).where(SystemWord.vocabulary_id == vocabulary_id))
    taken = {term_key(term) for term in terms}
    order_index = await _next_order_index(db, vocabulary_id)
    created = 0
    for data in words:
        key = term_key(data.term)
        if key in taken:
            continue
        taken.add(key)
        db.add(
            SystemWord(
                vocabulary_id=vocabulary_id,
                order_index=order_index + created,
                source=SOURCE_ADMIN,
                **data.model_dump(),
            )
        )
        created += 1
    await refresh_total_words(db, vocabulary)
    await db.commit()
    return ImportResult(created=created, skipped=len(words) - created)


async def update_word(db: AsyncSession, word_id: int, data: WordInput) -> SystemWord:
    word = await _own_word(db, word_id)
    await _ensure_term_free(db, word.vocabulary_id, data.term, except_word_id=word.id)
    for name, value in data.model_dump().items():
        setattr(word, name, value)
    await db.commit()
    return word


async def delete_word(db: AsyncSession, word_id: int) -> None:
    """단어를 지운다. 모든 사용자의 이 단어 학습 이력, 진도, 북마크가 CASCADE 로 함께 지워진다."""
    word = await _own_word(db, word_id)
    vocabulary = await _get_vocabulary(db, word.vocabulary_id)
    await db.delete(word)
    await refresh_total_words(db, vocabulary)
    await db.commit()
