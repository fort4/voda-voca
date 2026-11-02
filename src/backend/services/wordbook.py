# 2026-11-02 - voda-voca - 단어장 서비스: 소유권 검증, CRUD, 페이징 (REQ-003~007, REQ-105, REQ-106)
# 파일 위치: src/backend/services/wordbook.py

from sqlalchemy import func, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Word, Wordbook
from backend.schemas.wordbook import WordbookCreate, WordbookUpdate
from backend.services.seed import load_preset

UNIQUE_NAME_CONSTRAINT = "uk_wordbooks_user_name"


class WordbookNotFoundError(Exception):
    """단어장이 없거나 다른 사용자의 것이다. 두 경우를 구분하지 않는다 (404 일원화, REQ-003)."""


class WordbookNameTakenError(Exception):
    """같은 사용자의 다른 단어장과 이름이 겹친다 (D1)."""


async def get_owned_wordbook(db: AsyncSession, user_id: int, wordbook_id: int) -> Wordbook:
    """요청 사용자가 소유한 단어장만 반환한다.

    다른 사용자의 단어장과 존재하지 않는 ID 는 같은 예외가 된다.
    응답이 달라지면 ID 열거로 타인 단어장의 존재를 확인할 수 있으므로 구분하지 않는다.
    이후 단어·북마크 API 도 단어장 소유자 검증에 이 함수를 쓴다.
    """
    result = await db.execute(
        select(Wordbook).where(Wordbook.id == wordbook_id, Wordbook.user_id == user_id)
    )
    wordbook = result.scalar_one_or_none()
    if wordbook is None:
        raise WordbookNotFoundError
    return wordbook


async def _commit_checking_name(db: AsyncSession) -> None:
    """커밋하면서 이름 UNIQUE 위반만 WordbookNameTakenError 로 바꾼다.

    애플리케이션 검사 대신 DB 제약을 기준으로 삼아 동시 요청에도 중복을 막는다 (REQ-105).
    """
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        if UNIQUE_NAME_CONSTRAINT in str(exc.orig):
            raise WordbookNameTakenError from exc
        raise


async def create_wordbook(db: AsyncSession, user_id: int, data: WordbookCreate) -> Wordbook:
    wordbook = Wordbook(user_id=user_id, name=data.name, description=data.description)
    db.add(wordbook)
    await _commit_checking_name(db)
    await db.refresh(wordbook)
    return wordbook


async def count_words(db: AsyncSession, wordbook_id: int) -> int:
    """단어장 하나의 단어 수. 단건 응답(상세·수정)에 쓴다. 목록은 list_wordbooks 가 한 번에 센다."""
    return (
        await db.execute(select(func.count(Word.id)).where(Word.wordbook_id == wordbook_id))
    ).scalar_one()


async def list_wordbooks(
    db: AsyncSession, user_id: int, page: int, size: int
) -> tuple[list[tuple[Wordbook, int]], int]:
    """본인 단어장을 최근 수정순으로 한 페이지 반환하고, 전체 개수도 함께 반환한다 (REQ-005).

    각 단어장의 단어 수는 words 와 LEFT JOIN 한 GROUP BY 한 번으로 센다 (N+1 방지). 단어가 없으면 0 이다.
    정렬 키 뒤에 id 를 붙여 수정 시각이 같은 행의 순서도 항상 같게 한다.
    """
    total = (
        await db.execute(
            select(func.count()).select_from(Wordbook).where(Wordbook.user_id == user_id)
        )
    ).scalar_one()

    result = await db.execute(
        select(Wordbook, func.count(Word.id))
        .outerjoin(Word, Word.wordbook_id == Wordbook.id)
        .where(Wordbook.user_id == user_id)
        .group_by(Wordbook.id)
        .order_by(Wordbook.updated_at.desc(), Wordbook.id.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    return [(wordbook, count) for wordbook, count in result.all()], total


async def create_preset_wordbook(db: AsyncSession, user_id: int, key: str) -> Wordbook:
    """추천 프리셋 단어장을 만든다. 단어장과 단어 1,000건을 한 트랜잭션으로 넣는다 (All-or-Nothing).

    데이터 파일이 없으면 SeedDataMissingError, 같은 이름의 단어장이 있으면 WordbookNameTakenError.
    """
    name, words = load_preset(key)
    wordbook = Wordbook(user_id=user_id, name=name)
    db.add(wordbook)
    try:
        await db.flush()
        await db.execute(
            insert(Word),
            [
                {"wordbook_id": wordbook.id, "term": w.term, "meaning": w.meaning, "example": w.example, "example_meaning": w.example_meaning}
                for w in words
            ],
        )
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        if UNIQUE_NAME_CONSTRAINT in str(exc.orig):
            raise WordbookNameTakenError from exc
        raise
    await db.refresh(wordbook)
    return wordbook


async def update_wordbook(
    db: AsyncSession, user_id: int, wordbook_id: int, data: WordbookUpdate
) -> Wordbook:
    """요청에 포함된 필드만 수정한다.

    값이 실제로 바뀌지 않으면 SQLAlchemy 가 UPDATE 를 보내지 않으므로 updated_at 도 바뀌지 않는다 (REQ-006).
    """
    wordbook = await get_owned_wordbook(db, user_id, wordbook_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(wordbook, field, value)
    await _commit_checking_name(db)
    return wordbook


async def delete_wordbook(db: AsyncSession, user_id: int, wordbook_id: int) -> None:
    """단어장을 삭제한다. 단어·북마크·학습 이력은 DB의 ON DELETE CASCADE 로 함께 삭제된다 (REQ-007, REQ-106)."""
    wordbook = await get_owned_wordbook(db, user_id, wordbook_id)
    await db.delete(wordbook)
    await db.commit()
