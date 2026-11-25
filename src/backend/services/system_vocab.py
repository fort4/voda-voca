# 2026-11-05 - voda-voca - 표준 단어장 서비스: 카탈로그와 내 진행률, 단어 목록·검색, 활성 단어장 변경
# 파일 위치: src/backend/services/system_vocab.py

from sqlalchemy import Integer, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Bookmark, SystemVocabulary, SystemWord, User, UserWordProgress
from backend.schemas.vocabulary import UserProgressOut, VocabularyOut
from backend.services.errors import VocabularyNotFoundError


def _entry(
    vocabulary: SystemVocabulary, studied: int, memorized: int, active_vocabulary_id: int | None
) -> VocabularyOut:
    total = vocabulary.total_words
    rate = round(studied / total * 100, 1) if total else 0.0
    return VocabularyOut(
        id=vocabulary.id,
        slug=vocabulary.slug,
        title=vocabulary.title,
        category=vocabulary.category,
        level=vocabulary.level,
        description=vocabulary.description,
        total_words=total,
        source=vocabulary.source,
        user_progress=UserProgressOut(
            studied_words=studied,
            memorized_words=memorized,
            progress_rate=min(rate, 100.0),
            is_active=vocabulary.id == active_vocabulary_id,
        ),
    )


async def _progress_by_vocabulary(
    db: AsyncSession, user_id: int, vocabulary_ids: list[int] | None = None
) -> dict[int, tuple[int, int]]:
    """{단어장 id: (풀어 본 단어 수, 숙련 단어 수)}. 단어장 전체를 한 번의 GROUP BY 로 구한다."""
    memorized = func.coalesce(func.sum(case((UserWordProgress.is_memorized.is_(True), 1), else_=0), type_=Integer), 0)
    query = (
        select(SystemWord.vocabulary_id, func.count(UserWordProgress.id), memorized)
        .join(SystemWord, SystemWord.id == UserWordProgress.word_id)
        .where(UserWordProgress.user_id == user_id)
        .group_by(SystemWord.vocabulary_id)
    )
    if vocabulary_ids is not None:
        query = query.where(SystemWord.vocabulary_id.in_(vocabulary_ids))
    return {vocabulary_id: (int(studied), int(done)) for vocabulary_id, studied, done in (await db.execute(query)).all()}


async def list_vocabularies(
    db: AsyncSession, user: User, category: str | None, level: int | None
) -> list[VocabularyOut]:
    """카탈로그. sort_order, id 순이며 category, level 로 거를 수 있다."""
    query = select(SystemVocabulary).order_by(SystemVocabulary.sort_order, SystemVocabulary.id)
    if category is not None:
        query = query.where(SystemVocabulary.category == category)
    if level is not None:
        query = query.where(SystemVocabulary.level == level)
    vocabularies = list((await db.execute(query)).scalars().all())
    progress = await _progress_by_vocabulary(db, user.id)
    return [
        _entry(v, *progress.get(v.id, (0, 0)), active_vocabulary_id=user.active_vocabulary_id) for v in vocabularies
    ]


async def vocabulary_entry(db: AsyncSession, user: User, vocabulary: SystemVocabulary) -> VocabularyOut:
    """단어장 하나의 카탈로그 항목 (내 진행률 포함)."""
    progress = await _progress_by_vocabulary(db, user.id, [vocabulary.id])
    return _entry(vocabulary, *progress.get(vocabulary.id, (0, 0)), active_vocabulary_id=user.active_vocabulary_id)


async def is_bookmarked(db: AsyncSession, user_id: int, word_id: int) -> bool:
    found = await db.execute(select(Bookmark.id).where(Bookmark.user_id == user_id, Bookmark.word_id == word_id))
    return found.scalar_one_or_none() is not None


async def get_vocabulary(db: AsyncSession, vocabulary_id: int) -> SystemVocabulary:
    vocabulary = (
        await db.execute(select(SystemVocabulary).where(SystemVocabulary.id == vocabulary_id))
    ).scalar_one_or_none()
    if vocabulary is None:
        raise VocabularyNotFoundError
    return vocabulary


def _word_conditions(vocabulary_id: int, query: str | None) -> list:
    """목록과 전체 수가 같은 조건을 쓴다. 빈 검색어는 거르지 않는다.

    autoescape 로 검색어의 %, _ 를 일반 문자로 만든다 (REQ-113). SQLite 의 LIKE 는 영문 대소문자를 구분하지 않는다.
    """
    conditions = [SystemWord.vocabulary_id == vocabulary_id]
    text = (query or "").strip()
    if text:
        conditions.append(
            or_(SystemWord.term.contains(text, autoescape=True), SystemWord.meaning.contains(text, autoescape=True))
        )
    return conditions


async def list_words(
    db: AsyncSession, user_id: int, vocabulary_id: int, page: int, size: int, query: str | None = None
) -> tuple[list[tuple[SystemWord, bool]], int]:
    """단어장의 단어를 order_index 순으로 한 페이지. (단어, 내 북마크 여부) 목록과 (검색 조건에 맞는) 전체 수를 돌려준다."""
    await get_vocabulary(db, vocabulary_id)
    conditions = _word_conditions(vocabulary_id, query)
    total = (await db.execute(select(func.count()).select_from(SystemWord).where(*conditions))).scalar_one()
    flag = Bookmark.id.is_not(None).label("bookmarked")
    rows = await db.execute(
        select(SystemWord, flag)
        .outerjoin(Bookmark, (Bookmark.word_id == SystemWord.id) & (Bookmark.user_id == user_id))
        .where(*conditions)
        .order_by(SystemWord.order_index, SystemWord.id)
        .offset((page - 1) * size)
        .limit(size)
    )
    return [(word, bool(bookmarked)) for word, bookmarked in rows.all()], int(total)


async def set_active_vocabulary(db: AsyncSession, user: User, vocabulary_id: int) -> VocabularyOut:
    """활성 단어장을 바꾸고 그 단어장의 카탈로그 항목(내 진행률 포함)을 돌려준다. 같은 값이면 그대로 성공한다."""
    vocabulary = await get_vocabulary(db, vocabulary_id)
    user.active_vocabulary_id = vocabulary.id
    await db.commit()
    return await vocabulary_entry(db, user, vocabulary)
