# 2026-11-02 - voda-voca - 단어 서비스: 소속/소유권 검증, CRUD, 표제어 접두사 검색 (REQ-008~011, REQ-009, REQ-105, REQ-113)
# 파일 위치: src/backend/services/word.py

from sqlalchemy import Select, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Word
from backend.schemas.word import WordCreate, WordUpdate
from backend.services.wordbook import get_owned_wordbook

UNIQUE_TERM_CONSTRAINT = "uk_words_wordbook_term"
LIKE_ESCAPE_CHAR = "\\"


class WordNotFoundError(Exception):
    """단어가 없거나 요청한 단어장에 속하지 않는다. 두 경우를 구분하지 않는다 (404 일원화)."""


class WordTermTakenError(Exception):
    """같은 단어장 안에 같은 표제어가 이미 있다 (uk_words_wordbook_term)."""


def escape_like(text: str) -> str:
    """LIKE 패턴에서 특수 의미가 있는 문자(\\, %, _)를 리터럴로 바꾼다.

    먼저 이스케이프 문자 자신을 바꿔야 뒤에 붙이는 이스케이프가 꼬이지 않는다.
    예: 'a%_\\' -> 'a\\%\\_\\\\'
    """
    return (
        text.replace(LIKE_ESCAPE_CHAR, LIKE_ESCAPE_CHAR * 2)
        .replace("%", LIKE_ESCAPE_CHAR + "%")
        .replace("_", LIKE_ESCAPE_CHAR + "_")
    )


def _list_query(wordbook_id: int, prefix: str | None) -> Select:
    """목록 조회 쿼리. 접두사가 있으면 term LIKE 'prefix%' 조건을 붙인다.

    조건 컬럼(wordbook_id, term)과 정렬 키(term, id)가 uk_words_wordbook_term 인덱스와 일치하므로
    filesort 없이 인덱스 순서대로 읽는다 (REQ-103).
    """
    statement = select(Word).where(Word.wordbook_id == wordbook_id)
    if prefix:
        statement = statement.where(
            Word.term.like(escape_like(prefix) + "%", escape=LIKE_ESCAPE_CHAR)
        )
    return statement.order_by(Word.term.asc(), Word.id.asc())


async def get_owned_word(
    db: AsyncSession, user_id: int, wordbook_id: int, word_id: int
) -> Word:
    """단어장 소유자를 먼저 확인하고, 그 단어장에 속한 단어만 반환한다.

    단어장이 없거나 타인 소유이면 WordbookNotFoundError 가 그대로 전파된다 (라우터가 404 로 바꾼다).
    단어가 없거나 다른 단어장 소속이면 WordNotFoundError 가 된다.
    """
    await get_owned_wordbook(db, user_id, wordbook_id)
    result = await db.execute(
        select(Word).where(Word.id == word_id, Word.wordbook_id == wordbook_id)
    )
    word = result.scalar_one_or_none()
    if word is None:
        raise WordNotFoundError
    return word


async def _commit_checking_term(db: AsyncSession) -> None:
    """커밋하면서 표제어 UNIQUE 위반만 WordTermTakenError 로 바꾼다 (REQ-105)."""
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        if UNIQUE_TERM_CONSTRAINT in str(exc.orig):
            raise WordTermTakenError from exc
        raise


async def create_word(
    db: AsyncSession, user_id: int, wordbook_id: int, data: WordCreate
) -> Word:
    await get_owned_wordbook(db, user_id, wordbook_id)
    word = Word(
        wordbook_id=wordbook_id,
        term=data.term,
        meaning=data.meaning,
        example=data.example,
    )
    db.add(word)
    await _commit_checking_term(db)
    await db.refresh(word)
    return word


async def list_words(
    db: AsyncSession,
    user_id: int,
    wordbook_id: int,
    prefix: str | None,
    page: int,
    size: int,
) -> tuple[list[Word], int]:
    """표제어 접두사로 검색한 단어 한 페이지와 전체 개수를 반환한다.

    prefix 는 앞뒤 공백을 제거한 값이다. 비어 있으면 전체 목록을 반환한다.
    """
    await get_owned_wordbook(db, user_id, wordbook_id)
    cleaned = prefix.strip() if prefix else None

    base = _list_query(wordbook_id, cleaned)
    total = (
        await db.execute(select(func.count()).select_from(base.order_by(None).subquery()))
    ).scalar_one()
    result = await db.execute(base.offset((page - 1) * size).limit(size))
    return list(result.scalars().all()), total


async def get_word(db: AsyncSession, user_id: int, wordbook_id: int, word_id: int) -> Word:
    return await get_owned_word(db, user_id, wordbook_id, word_id)


async def update_word(
    db: AsyncSession, user_id: int, wordbook_id: int, word_id: int, data: WordUpdate
) -> Word:
    """요청에 포함된 필드만 수정한다. 값이 같으면 UPDATE 가 나가지 않아 updated_at 도 그대로다."""
    word = await get_owned_word(db, user_id, wordbook_id, word_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(word, field, value)
    await _commit_checking_term(db)
    return word


async def delete_word(db: AsyncSession, user_id: int, wordbook_id: int, word_id: int) -> None:
    """단어를 삭제한다. 북마크와 학습 이력은 DB의 ON DELETE CASCADE 로 함께 삭제된다 (REQ-011)."""
    word = await get_owned_word(db, user_id, wordbook_id, word_id)
    await db.delete(word)
    await db.commit()
