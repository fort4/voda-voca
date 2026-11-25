# 2026-11-26 - voda-voca - 시드 로더와 관리자 등록분의 공존 테스트: 보존, 경고 제외, 같은 표제어는 시드 우선 (REQ-160, REQ-161)
# 파일 위치: src/backend/tests/test_system_seed_admin_words.py

from pathlib import Path

import pytest
from sqlalchemy import select

from backend.db.session import get_session_factory
from backend.models import StudyLog, SystemVocabulary, SystemWord, User
from backend.services.system_seed import seed_system_vocabularies
from backend.tests.test_system_seed import PREFIX, _simple_seed, _word

SLUG = f"{PREFIX}a"


async def seed(root: Path):
    async with get_session_factory()() as db:
        return await seed_system_vocabularies(db, root)


async def add_admin_word(term: str, meaning: str = "관리자 뜻") -> int:
    async with get_session_factory()() as db:
        vocabulary = (await db.execute(select(SystemVocabulary).where(SystemVocabulary.slug == SLUG))).scalar_one()
        row = SystemWord(
            vocabulary_id=vocabulary.id, term=term, meaning=meaning, order_index=99, source="admin"
        )
        db.add(row)
        await db.commit()
        return row.id


async def words() -> dict[str, tuple[int, str, str]]:
    async with get_session_factory()() as db:
        rows = await db.execute(
            select(SystemWord)
            .join(SystemVocabulary, SystemVocabulary.id == SystemWord.vocabulary_id)
            .where(SystemVocabulary.slug == SLUG)
        )
        return {w.term: (w.id, w.meaning, w.source) for w in rows.scalars()}


@pytest.mark.asyncio
async def test_seeded_rows_are_marked_as_seed(tmp_path: Path) -> None:
    await seed(_simple_seed(tmp_path))

    assert {source for _, _, source in (await words()).values()} == {"seed"}
    async with get_session_factory()() as db:
        assert await db.scalar(select(SystemVocabulary.source).where(SystemVocabulary.slug == SLUG)) == "seed"


@pytest.mark.asyncio
async def test_reseeding_keeps_admin_words_without_warning(tmp_path: Path) -> None:
    await seed(_simple_seed(tmp_path))
    admin_id = await add_admin_word("ladle")

    report = await seed(_simple_seed(tmp_path, words=[_word("apple", "새 사과"), _word("book"), _word("cat")]))

    assert (await words())["ladle"] == (admin_id, "관리자 뜻", "admin")
    assert report.warnings == []
    assert report.items[0].total_words == 4


@pytest.mark.asyncio
async def test_seed_takes_over_an_admin_word_with_the_same_term_and_keeps_history(tmp_path: Path) -> None:
    await seed(_simple_seed(tmp_path))
    admin_id = await add_admin_word("Café")
    async with get_session_factory()() as db:
        user = User(nickname=f"{PREFIX}seed", password_hash="x")
        db.add(user)
        await db.flush()
        db.add(StudyLog(user_id=user.id, word_id=admin_id, is_correct=True, mode="quiz"))
        await db.commit()

    new_words = [_word("apple"), _word("book"), _word("cat"), _word("cafe", "카페")]
    await seed(_simple_seed(tmp_path, words=new_words))

    after = await words()
    assert after["cafe"] == (admin_id, "카페", "seed"), "행 id 를 유지해 이력을 보존한다"
    assert "Café" not in after
    async with get_session_factory()() as db:
        assert await db.scalar(select(StudyLog.word_id).where(StudyLog.word_id == admin_id)) == admin_id


@pytest.mark.asyncio
async def test_identical_content_still_becomes_a_seed_word(tmp_path: Path) -> None:
    """내용이 우연히 같아도 출처는 시드가 된다 (이후 수정·삭제 대상에서 빠진다)."""
    await seed(_simple_seed(tmp_path))
    async with get_session_factory()() as db:
        vocabulary = (await db.execute(select(SystemVocabulary).where(SystemVocabulary.slug == SLUG))).scalar_one()
        db.add(
            SystemWord(
                vocabulary_id=vocabulary.id, term="dog", meaning="뜻", example="An example.",
                example_meaning="예문", order_index=3, source="admin",
            )
        )
        await db.commit()

    await seed(_simple_seed(tmp_path, words=[_word("apple"), _word("book"), _word("cat"), _word("dog")]))

    assert (await words())["dog"][2] == "seed"
