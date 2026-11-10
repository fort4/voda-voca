# 2026-11-05 - voda-voca - 표준 단어장 시드 로더 테스트: 파일 검증, 해시, 멱등 적재, 동시 실행, 실제 시드 1,000단어
# 파일 위치: src/backend/tests/test_system_seed.py

import asyncio
import json
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import delete, func, select

from backend.db.session import get_session_factory
from backend.models import SystemVocabulary, SystemWord
from backend.services import system_seed
from backend.services.system_seed import (
    SEED_DIR,
    SeedValidationError,
    compute_content_hash,
    load_seed_vocabularies,
    seed_system_vocabularies,
)

PREFIX = "tvoda-"
REAL_SLUGS = ["beginner-200", "intermediate-200", "advanced-200", "exam-core-200", "business-practical-200"]
NEW_SLUGS = ["exam-core-200", "business-practical-200"]


# ---------------------------------------------------------------------------
# 도우미
# ---------------------------------------------------------------------------


def _word(term: str, meaning: str = "뜻", example: str | None = "An example.", example_meaning: str | None = "예문") -> dict:
    return {"term": term, "meaning": meaning, "example": example, "example_meaning": example_meaning}


def _write_seed(root: Path, vocabularies: list[dict], words: dict[str, list[dict]]) -> Path:
    """tmp 시드 디렉터리를 만든다. vocabularies.json 과 words/<slug>.json 구조다."""
    (root / "words").mkdir(parents=True, exist_ok=True)
    (root / "vocabularies.json").write_text(json.dumps(vocabularies, ensure_ascii=False), encoding="utf-8")
    for slug, items in words.items():
        (root / "words" / f"{slug}.json").write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
    return root


def _meta(slug: str, **overrides: object) -> dict:
    meta: dict[str, object] = {
        "slug": slug,
        "title": "테스트 단어장",
        "category": "ELEMENTARY",
        "level": 1,
        "description": "설명",
        "sort_order": 1,
    }
    meta.update(overrides)
    return meta


def _simple_seed(root: Path, slug: str = f"{PREFIX}a", words: list[dict] | None = None, **meta: object) -> Path:
    words = words if words is not None else [_word("apple", "사과"), _word("book", "책"), _word("cat", "고양이")]
    return _write_seed(root, [_meta(slug, **meta)], {slug: words})


# ---------------------------------------------------------------------------
# 1. 파일 로드와 검증 (DB 없음)
# ---------------------------------------------------------------------------


def test_load_reads_vocabularies_and_words_in_file_order(tmp_path: Path) -> None:
    _simple_seed(tmp_path)
    (vocabulary,) = load_seed_vocabularies(tmp_path)
    assert vocabulary.slug == f"{PREFIX}a"
    assert [w.term for w in vocabulary.words] == ["apple", "book", "cat"]
    assert [w.order_index for w in vocabulary.words] == [0, 1, 2]


def test_load_trims_values_and_drops_example_meaning_without_example(tmp_path: Path) -> None:
    _simple_seed(tmp_path, words=[_word("  apple ", " 사과 ", example="  ", example_meaning="예문 뜻")])
    (vocabulary,) = load_seed_vocabularies(tmp_path)
    (word,) = vocabulary.words
    assert (word.term, word.meaning) == ("apple", "사과")
    assert word.example is None and word.example_meaning is None


def test_load_accepts_a_new_category_without_code_change(tmp_path: Path) -> None:
    _simple_seed(tmp_path, category="BUSINESS")
    (vocabulary,) = load_seed_vocabularies(tmp_path)
    assert vocabulary.category == "BUSINESS"


@pytest.mark.parametrize(
    ("meta_overrides", "words", "message"),
    [
        ({"slug": ""}, None, "slug"),
        ({"category": "  "}, None, "category"),
        ({"category": "X" * 51}, None, "category"),
        ({"level": 0}, None, "level"),
        ({"level": 6}, None, "level"),
        ({"title": "T" * 101}, None, "title"),
        (None, [], "words"),
        (None, [_word("")], "term"),
        (None, [_word("a", meaning="")], "meaning"),
        (None, [_word("a" * 101)], "term"),
        (None, [_word("a", meaning="m" * 201)], "meaning"),
        (None, [_word("a", example="e" * 501)], "example"),
        (None, [_word("Apple"), _word("apple")], "중복"),
        (None, [_word("résumé"), _word("resume")], "중복"),
    ],
)
def test_invalid_seed_is_rejected(tmp_path: Path, meta_overrides, words, message: str) -> None:
    _simple_seed(tmp_path, words=words, **(meta_overrides or {}))
    with pytest.raises(SeedValidationError, match=message):
        load_seed_vocabularies(tmp_path)


def test_duplicate_slug_is_rejected(tmp_path: Path) -> None:
    _write_seed(
        tmp_path,
        [_meta(f"{PREFIX}a"), _meta(f"{PREFIX}a", title="다른")],
        {f"{PREFIX}a": [_word("apple")]},
    )
    with pytest.raises(SeedValidationError, match="slug"):
        load_seed_vocabularies(tmp_path)


def test_missing_words_file_is_rejected(tmp_path: Path) -> None:
    _write_seed(tmp_path, [_meta(f"{PREFIX}a")], {})
    with pytest.raises(SeedValidationError, match="words"):
        load_seed_vocabularies(tmp_path)


def test_content_hash_is_stable_and_sensitive_to_changes(tmp_path: Path) -> None:
    _simple_seed(tmp_path / "one")
    _simple_seed(tmp_path / "two")
    (a,) = load_seed_vocabularies(tmp_path / "one")
    (b,) = load_seed_vocabularies(tmp_path / "two")
    assert compute_content_hash(a) == compute_content_hash(b)
    assert len(compute_content_hash(a)) == 64

    _simple_seed(tmp_path / "meaning", words=[_word("apple", "능금"), _word("book", "책"), _word("cat", "고양이")])
    _simple_seed(tmp_path / "title", title="다른 제목")
    _simple_seed(tmp_path / "order", words=[_word("book", "책"), _word("apple", "사과"), _word("cat", "고양이")])
    for name in ("meaning", "title", "order"):
        (changed,) = load_seed_vocabularies(tmp_path / name)
        assert compute_content_hash(changed) != compute_content_hash(a), name


# ---------------------------------------------------------------------------
# 2. 실제 시드 파일: 초급·중급·고급 각 200단어, 총 600단어
# ---------------------------------------------------------------------------


def test_real_seed_has_exactly_five_vocabularies_of_200_words() -> None:
    vocabularies = load_seed_vocabularies(SEED_DIR)
    assert [(v.slug, v.category, v.level, v.sort_order, len(v.words)) for v in vocabularies] == [
        ("beginner-200", "ELEMENTARY", 1, 1, 200),
        ("intermediate-200", "SECONDARY", 2, 2, 200),
        ("advanced-200", "CSAT", 3, 3, 200),
        ("exam-core-200", "EXAM", 3, 4, 200),
        ("business-practical-200", "BUSINESS", 3, 5, 200),
    ]
    assert sum(len(v.words) for v in vocabularies) == 1000


def test_real_seed_excludes_the_1000_word_preset() -> None:
    slugs = {v.slug for v in load_seed_vocabularies(SEED_DIR)}
    assert not any("1000" in slug for slug in slugs)
    assert not (SEED_DIR / "words").joinpath("intermediate-1000.json").exists()


def test_real_seed_words_have_examples_and_translations() -> None:
    for vocabulary in load_seed_vocabularies(SEED_DIR):
        for word in vocabulary.words:
            assert word.example and word.example_meaning, (vocabulary.slug, word.term)


# ---------------------------------------------------------------------------
# 3. DB 적재와 멱등성 (tmp 시드 + tvoda- 슬러그로 격리)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(autouse=True)
async def _cleanup() -> AsyncIterator[None]:
    await _delete_test_vocabularies()
    yield
    await _delete_test_vocabularies()


async def _delete_test_vocabularies() -> None:
    async with get_session_factory()() as session:
        await session.execute(delete(SystemVocabulary).where(SystemVocabulary.slug.like(f"{PREFIX}%")))
        await session.commit()


async def _run(root: Path):
    async with get_session_factory()() as session:
        return await seed_system_vocabularies(session, root)


async def _vocabulary(slug: str) -> SystemVocabulary:
    async with get_session_factory()() as session:
        return (await session.execute(select(SystemVocabulary).where(SystemVocabulary.slug == slug))).scalar_one()


async def _words(slug: str) -> dict[str, SystemWord]:
    async with get_session_factory()() as session:
        rows = await session.execute(
            select(SystemWord).join(SystemVocabulary).where(SystemVocabulary.slug == slug).order_by(SystemWord.order_index)
        )
        return {w.term: w for w in rows.scalars()}


@pytest.mark.asyncio
async def test_first_run_creates_vocabulary_words_and_total(tmp_path: Path) -> None:
    _simple_seed(tmp_path)
    report = await _run(tmp_path)

    assert (report.created, report.updated, report.unchanged) == (1, 0, 0)
    assert report.words_inserted == 3
    vocabulary = await _vocabulary(f"{PREFIX}a")
    assert vocabulary.total_words == 3
    assert vocabulary.content_hash is not None and len(vocabulary.content_hash) == 64
    assert vocabulary.category == "ELEMENTARY" and vocabulary.level == 1
    words = await _words(f"{PREFIX}a")
    assert list(words) == ["apple", "book", "cat"]
    assert words["apple"].meaning == "사과" and words["apple"].example == "An example."


@pytest.mark.asyncio
async def test_second_run_with_same_seed_changes_nothing(tmp_path: Path) -> None:
    _simple_seed(tmp_path)
    await _run(tmp_path)
    before_vocab = await _vocabulary(f"{PREFIX}a")
    before_words = await _words(f"{PREFIX}a")

    report = await _run(tmp_path)

    assert (report.created, report.updated, report.unchanged) == (0, 0, 1)
    assert report.words_inserted == 0 and report.words_updated == 0
    after_vocab = await _vocabulary(f"{PREFIX}a")
    assert after_vocab.updated_at == before_vocab.updated_at  # DB 쓰기가 없었다
    assert after_vocab.content_hash == before_vocab.content_hash
    after_words = await _words(f"{PREFIX}a")
    assert {t: w.id for t, w in after_words.items()} == {t: w.id for t, w in before_words.items()}


@pytest.mark.asyncio
async def test_repeated_runs_never_duplicate_rows(tmp_path: Path) -> None:
    _simple_seed(tmp_path)
    for _ in range(3):
        await _run(tmp_path)
    async with get_session_factory()() as session:
        vocab_count = await session.scalar(
            select(func.count()).select_from(SystemVocabulary).where(SystemVocabulary.slug == f"{PREFIX}a")
        )
        word_count = await session.scalar(
            select(func.count()).select_from(SystemWord).join(SystemVocabulary).where(SystemVocabulary.slug == f"{PREFIX}a")
        )
    assert (vocab_count, word_count) == (1, 3)


@pytest.mark.asyncio
async def test_changed_meaning_updates_in_place_and_keeps_word_id(tmp_path: Path) -> None:
    _simple_seed(tmp_path)
    await _run(tmp_path)
    before = (await _words(f"{PREFIX}a"))["apple"].id
    old_hash = (await _vocabulary(f"{PREFIX}a")).content_hash

    _simple_seed(tmp_path, words=[_word("apple", "능금"), _word("book", "책"), _word("cat", "고양이")])
    report = await _run(tmp_path)

    assert (report.created, report.updated, report.unchanged) == (0, 1, 0)
    assert report.words_updated == 1 and report.words_inserted == 0
    words = await _words(f"{PREFIX}a")
    assert words["apple"].meaning == "능금"
    assert words["apple"].id == before  # 삭제 후 재삽입이 아니다 (학습 이력 FK 보호)
    assert (await _vocabulary(f"{PREFIX}a")).content_hash != old_hash


@pytest.mark.asyncio
async def test_added_word_is_inserted_and_total_updated(tmp_path: Path) -> None:
    _simple_seed(tmp_path)
    await _run(tmp_path)
    _simple_seed(tmp_path, words=[_word("apple", "사과"), _word("book", "책"), _word("cat", "고양이"), _word("dog", "개")])
    report = await _run(tmp_path)
    assert report.words_inserted == 1
    assert (await _vocabulary(f"{PREFIX}a")).total_words == 4


@pytest.mark.asyncio
async def test_word_removed_from_seed_is_kept_with_a_warning(tmp_path: Path) -> None:
    _simple_seed(tmp_path)
    await _run(tmp_path)
    _simple_seed(tmp_path, words=[_word("apple", "사과"), _word("book", "책")])
    report = await _run(tmp_path)

    assert "cat" in await _words(f"{PREFIX}a")  # 지우지 않는다
    assert any("cat" in warning for warning in report.warnings)
    assert (await _vocabulary(f"{PREFIX}a")).total_words == 3  # 실제 행 수


@pytest.mark.asyncio
async def test_removed_word_does_not_cause_endless_updates(tmp_path: Path) -> None:
    _simple_seed(tmp_path)
    await _run(tmp_path)
    _simple_seed(tmp_path, words=[_word("apple", "사과"), _word("book", "책")])
    await _run(tmp_path)
    report = await _run(tmp_path)
    assert (report.updated, report.unchanged) == (0, 1)


@pytest.mark.asyncio
async def test_metadata_change_updates_the_vocabulary(tmp_path: Path) -> None:
    _simple_seed(tmp_path)
    await _run(tmp_path)
    _simple_seed(tmp_path, title="새 제목", category="CONVERSATION", level=3)
    report = await _run(tmp_path)
    assert report.updated == 1
    vocabulary = await _vocabulary(f"{PREFIX}a")
    assert (vocabulary.title, vocabulary.category, vocabulary.level) == ("새 제목", "CONVERSATION", 3)


@pytest.mark.asyncio
async def test_two_workers_seeding_at_once_do_not_collide(tmp_path: Path) -> None:
    _simple_seed(tmp_path)
    await asyncio.gather(_run(tmp_path), _run(tmp_path), _run(tmp_path))
    async with get_session_factory()() as session:
        vocab_count = await session.scalar(
            select(func.count()).select_from(SystemVocabulary).where(SystemVocabulary.slug == f"{PREFIX}a")
        )
    assert vocab_count == 1
    assert len(await _words(f"{PREFIX}a")) == 3
    assert (await _vocabulary(f"{PREFIX}a")).total_words == 3


@pytest.mark.asyncio
async def test_invalid_seed_writes_nothing(tmp_path: Path) -> None:
    _write_seed(
        tmp_path,
        [_meta(f"{PREFIX}a"), _meta(f"{PREFIX}b", level=9)],
        {f"{PREFIX}a": [_word("apple")], f"{PREFIX}b": [_word("pear")]},
    )
    with pytest.raises(SeedValidationError):
        await _run(tmp_path)
    async with get_session_factory()() as session:
        count = await session.scalar(
            select(func.count()).select_from(SystemVocabulary).where(SystemVocabulary.slug.like(f"{PREFIX}%"))
        )
    assert count == 0


# ---------------------------------------------------------------------------
# 4. 실제 시드 적재 (개발 DB 에 1,000단어가 남는다. 반복해도 같아야 한다)
#    주의: 이 테스트는 개발 DB 에 신규 단어장 2개를 INSERT 한다. 사용자 승인·백업 전에는 --deselect 로 제외하고 돌린다.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_real_seed_loads_1000_words_and_is_idempotent() -> None:
    await _run(SEED_DIR)
    report = await _run(SEED_DIR)
    assert report.created == 0 and report.updated == 0 and report.unchanged == 5
    async with get_session_factory()() as session:
        rows = (
            await session.execute(
                select(SystemVocabulary.slug, SystemVocabulary.total_words, func.count(SystemWord.id))
                .join(SystemWord, SystemWord.vocabulary_id == SystemVocabulary.id)
                .where(SystemVocabulary.slug.in_(REAL_SLUGS))
                .group_by(SystemVocabulary.id)
                .order_by(SystemVocabulary.sort_order)
            )
        ).all()
    assert [tuple(r) for r in rows] == [
        ("beginner-200", 200, 200),
        ("intermediate-200", 200, 200),
        ("advanced-200", 200, 200),
        ("exam-core-200", 200, 200),
        ("business-practical-200", 200, 200),
    ]


# ---------------------------------------------------------------------------
# 5. 앱 시작 연동
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_app_lifespan_runs_seed_on_startup(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.main import app

    calls: list[str] = []

    async def _fake_init() -> None:
        calls.append("seed")

    monkeypatch.setattr("backend.main.init_system_seeds", _fake_init)
    async with app.router.lifespan_context(app):
        assert calls == ["seed"]


def test_module_exposes_init_function() -> None:
    assert callable(system_seed.init_system_seeds)


# ---------------------------------------------------------------------------
# 5. 발음기호(phonetic): 검증, 해시, 멱등 적재 (v2.2). 합성 시드만 쓰므로 실제 단어장은 바뀌지 않는다.
# ---------------------------------------------------------------------------

IPA_APPLE = "ˈæpəl"


def _ph(term: str, meaning: str, phonetic: str | None) -> dict:
    """발음기호가 있는 시드 단어. phonetic 이 None 이면 키 자체를 둔다(명시적 null)."""
    return {**_word(term, meaning), "phonetic": phonetic}


def test_load_reads_phonetic_and_missing_key_means_none(tmp_path: Path) -> None:
    _simple_seed(tmp_path, words=[_ph("apple", "사과", IPA_APPLE), _word("book", "책"), _ph("cat", "고양이", None)])
    (vocabulary,) = load_seed_vocabularies(tmp_path)
    assert [w.phonetic for w in vocabulary.words] == [IPA_APPLE, None, None]


def test_load_trims_phonetic_and_blank_means_none(tmp_path: Path) -> None:
    _simple_seed(tmp_path, words=[_ph("apple", "사과", f"  {IPA_APPLE} "), _ph("book", "책", "   ")])
    (vocabulary,) = load_seed_vocabularies(tmp_path)
    assert [w.phonetic for w in vocabulary.words] == [IPA_APPLE, None]


@pytest.mark.parametrize(
    "phonetic",
    ["ˈæpəl", "ˈhaʊs", "θɪŋk", "ˈɛvri", "ʃʊd", "ðɪs", "dʒʌmp", "ɔːl", "ˌɪntərˈnæʃənəl", "ˈkɑːfi", "t͡ʃɛr", "ˈbʌtər", "wɝld"],
)
def test_typical_ipa_is_accepted(tmp_path: Path, phonetic: str) -> None:
    _simple_seed(tmp_path, words=[_ph("apple", "사과", phonetic)])
    (vocabulary,) = load_seed_vocabularies(tmp_path)
    assert vocabulary.words[0].phonetic == phonetic


@pytest.mark.parametrize(
    "phonetic",
    [
        "애플",  # 한글
        "/ˈæpəl/",  # 슬래시는 저장하지 않는다 (화면이 입힌다)
        "[ˈæpəl]",
        "(ˈæpəl)",
        "ÆPPLE",  # 대문자
        "apple1",  # 숫자
        "ˈæ\x00pəl",  # 제어 문자
        "ˈæp\nəl",  # 줄바꿈
        "ˈæp\təl",  # 탭
        "ˈæpəl, ˈæpl",  # 쉼표(발음 변형은 한 값에 넣지 않는다)
    ],
)
def test_non_ipa_phonetic_is_rejected(tmp_path: Path, phonetic: str) -> None:
    _simple_seed(tmp_path, words=[_ph("apple", "사과", phonetic)])
    with pytest.raises(SeedValidationError, match="phonetic"):
        load_seed_vocabularies(tmp_path)


def test_phonetic_longer_than_column_is_rejected(tmp_path: Path) -> None:
    _simple_seed(tmp_path, words=[_ph("apple", "사과", "a" * 101)])
    with pytest.raises(SeedValidationError, match="phonetic"):
        load_seed_vocabularies(tmp_path)
    _simple_seed(tmp_path / "ok", words=[_ph("apple", "사과", "a" * 100)])
    (vocabulary,) = load_seed_vocabularies(tmp_path / "ok")
    assert len(vocabulary.words[0].phonetic or "") == 100


def test_phonetic_must_be_a_string(tmp_path: Path) -> None:
    _simple_seed(tmp_path, words=[{**_word("apple", "사과"), "phonetic": 123}])
    with pytest.raises(SeedValidationError, match="phonetic"):
        load_seed_vocabularies(tmp_path)


def test_content_hash_reacts_to_phonetic_but_not_to_an_explicit_null(tmp_path: Path) -> None:
    base = [_word("apple", "사과"), _word("book", "책"), _word("cat", "고양이")]
    _simple_seed(tmp_path / "none", words=base)
    _simple_seed(tmp_path / "null", words=[_ph("apple", "사과", None), _word("book", "책"), _word("cat", "고양이")])
    _simple_seed(tmp_path / "with", words=[_ph("apple", "사과", IPA_APPLE), _word("book", "책"), _word("cat", "고양이")])
    _simple_seed(tmp_path / "other", words=[_ph("apple", "사과", "ˈæpl"), _word("book", "책"), _word("cat", "고양이")])
    hashes = {name: compute_content_hash(load_seed_vocabularies(tmp_path / name)[0]) for name in ("none", "null", "with", "other")}
    assert hashes["none"] == hashes["null"], "키가 없는 것과 명시적 null 은 같은 내용이다"
    assert hashes["with"] != hashes["none"], "발음기호를 채우면 해시가 바뀌어야 DB 에 반영된다"
    assert hashes["other"] != hashes["with"]


@pytest.mark.asyncio
async def test_phonetic_is_stored_and_missing_phonetic_is_null(tmp_path: Path) -> None:
    _simple_seed(tmp_path, words=[_ph("apple", "사과", IPA_APPLE), _word("book", "책")])
    await _run(tmp_path)
    words = await _words(f"{PREFIX}a")
    assert words["apple"].phonetic == IPA_APPLE
    assert words["book"].phonetic is None


@pytest.mark.asyncio
async def test_same_seed_with_phonetic_is_idempotent(tmp_path: Path) -> None:
    _simple_seed(tmp_path, words=[_ph("apple", "사과", IPA_APPLE), _ph("book", "책", "bʊk")])
    await _run(tmp_path)
    report = await _run(tmp_path)
    assert (report.created, report.updated, report.unchanged) == (0, 0, 1)
    assert report.words_inserted == 0 and report.words_updated == 0


@pytest.mark.asyncio
async def test_adding_phonetic_later_updates_in_place_and_keeps_word_id(tmp_path: Path) -> None:
    _simple_seed(tmp_path, words=[_word("apple", "사과"), _word("book", "책")])
    await _run(tmp_path)
    before = (await _words(f"{PREFIX}a"))["apple"].id
    old_hash = (await _vocabulary(f"{PREFIX}a")).content_hash

    _simple_seed(tmp_path, words=[_ph("apple", "사과", IPA_APPLE), _word("book", "책")])
    report = await _run(tmp_path)

    assert (report.created, report.updated, report.unchanged) == (0, 1, 0)
    assert (report.words_updated, report.words_inserted) == (1, 0)
    words = await _words(f"{PREFIX}a")
    assert words["apple"].phonetic == IPA_APPLE
    assert words["apple"].id == before  # 학습 이력 FK 보호: 삭제 후 재삽입이 아니다
    assert (await _vocabulary(f"{PREFIX}a")).content_hash != old_hash


@pytest.mark.asyncio
async def test_changing_only_the_phonetic_updates_only_that_word(tmp_path: Path) -> None:
    _simple_seed(tmp_path, words=[_ph("apple", "사과", IPA_APPLE), _ph("book", "책", "bʊk")])
    await _run(tmp_path)
    _simple_seed(tmp_path, words=[_ph("apple", "사과", "ˈæpl"), _ph("book", "책", "bʊk")])
    report = await _run(tmp_path)
    assert report.words_updated == 1
    words = await _words(f"{PREFIX}a")
    assert (words["apple"].phonetic, words["book"].phonetic) == ("ˈæpl", "bʊk")


@pytest.mark.asyncio
async def test_removing_phonetic_from_seed_returns_the_column_to_null(tmp_path: Path) -> None:
    _simple_seed(tmp_path, words=[_ph("apple", "사과", IPA_APPLE), _word("book", "책")])
    await _run(tmp_path)
    _simple_seed(tmp_path, words=[_word("apple", "사과"), _word("book", "책")])
    report = await _run(tmp_path)
    assert report.words_updated == 1
    assert (await _words(f"{PREFIX}a"))["apple"].phonetic is None
    assert (await _run(tmp_path)).unchanged == 1


@pytest.mark.asyncio
async def test_new_word_with_phonetic_is_inserted_with_it(tmp_path: Path) -> None:
    _simple_seed(tmp_path, words=[_word("apple", "사과")])
    await _run(tmp_path)
    _simple_seed(tmp_path, words=[_word("apple", "사과"), _ph("book", "책", "bʊk")])
    report = await _run(tmp_path)
    assert report.words_inserted == 1
    assert (await _words(f"{PREFIX}a"))["book"].phonetic == "bʊk"


# ---------------------------------------------------------------------------
# 6. 실제 시드의 발음기호 완성도 (DB 없음). 600단어 전부에 미국식 IPA 가 있어야 한다 (v2.2 데이터 완성의 관문).
# ---------------------------------------------------------------------------


def _real_words() -> list[tuple[str, system_seed.SeedWordData]]:
    return [(v.slug, w) for v in load_seed_vocabularies(SEED_DIR) for w in v.words]


def test_every_real_seed_word_has_a_phonetic() -> None:
    missing = [f"{slug}:{w.term}" for slug, w in _real_words() if not w.phonetic]
    assert missing == [], f"발음기호가 없는 단어 {len(missing)}개: {missing[:10]}"


def test_real_seed_phonetics_are_plain_ipa_without_slashes_or_brackets() -> None:
    bad = [(w.term, w.phonetic) for _, w in _real_words() if w.phonetic and any(c in w.phonetic for c in "/[]()")]
    assert bad == []


def test_stress_marks_appear_only_in_multi_syllable_words() -> None:
    """단음절 단어는 강세 표시를 하지 않는다 (사전 표기 관례)."""
    vowel = "aeiouæɑɔɛɪʊʌəɚɝ"
    offenders = [
        (w.term, w.phonetic)
        for _, w in _real_words()
        if w.phonetic and "ˈ" in w.phonetic and sum(1 for c in w.phonetic if c in vowel) <= 1
    ]
    # 이중모음(aɪ, aʊ, eɪ, oʊ, ɔɪ)은 모음 문자가 둘이므로 한 음절로 세지 못하는 경우만 남는다: 아래에서 직접 확인한다
    assert [t for t, _ in offenders] == []


def test_each_vocabulary_has_a_phonetic_for_every_word_and_no_duplicated_primary_stress() -> None:
    """한 단어에 1차 강세(ˈ)가 둘 이상이면 변환 오류다 (수기 지정한 outside 등 예외는 2차 강세로 구분)."""
    many = [(w.term, w.phonetic) for _, w in _real_words() if w.phonetic and w.phonetic.count("ˈ") > 1]
    assert many == []


# ---------------------------------------------------------------------------
# 7. 품사(pos) 지원 (v2.2 카탈로그 확충, REQ-145). 합성 시드만 쓰므로 실제 단어장은 바뀌지 않는다.
# ---------------------------------------------------------------------------


def _pos(term: str, meaning: str, pos: str | None) -> dict:
    return {**_word(term, meaning), "pos": pos}


def test_load_reads_pos_and_missing_key_means_none(tmp_path: Path) -> None:
    _simple_seed(tmp_path, words=[_pos("apple", "사과", "noun"), _word("book", "책"), _pos("cat", "고양이", None)])
    words = load_seed_vocabularies(tmp_path)[0].words
    assert [w.pos for w in words] == ["noun", None, None]


def test_load_trims_pos_and_blank_means_none(tmp_path: Path) -> None:
    _simple_seed(tmp_path, words=[_pos("apple", "사과", "  noun "), _pos("book", "책", "   ")])
    assert [w.pos for w in load_seed_vocabularies(tmp_path)[0].words] == ["noun", None]


@pytest.mark.parametrize("pos", ["x" * 21, 3, ["noun"]])
def test_invalid_pos_is_rejected(tmp_path: Path, pos: object) -> None:
    _simple_seed(tmp_path, words=[{**_word("apple", "사과"), "pos": pos}])
    with pytest.raises(SeedValidationError, match="pos"):
        load_seed_vocabularies(tmp_path)


def test_content_hash_reacts_to_pos_but_not_to_an_explicit_null(tmp_path: Path) -> None:
    base = [_word("apple", "사과"), _word("book", "책"), _word("cat", "고양이")]
    _simple_seed(tmp_path / "none", words=base)
    _simple_seed(tmp_path / "null", words=[_pos("apple", "사과", None), _word("book", "책"), _word("cat", "고양이")])
    _simple_seed(tmp_path / "noun", words=[_pos("apple", "사과", "noun"), _word("book", "책"), _word("cat", "고양이")])
    _simple_seed(tmp_path / "verb", words=[_pos("apple", "사과", "verb"), _word("book", "책"), _word("cat", "고양이")])
    hashes = {n: compute_content_hash(load_seed_vocabularies(tmp_path / n)[0]) for n in ("none", "null", "noun", "verb")}
    assert hashes["none"] == hashes["null"], "키가 없는 것과 명시적 null 은 같은 내용이다"
    assert hashes["noun"] != hashes["none"], "품사를 채우면 해시가 바뀌어야 DB 에 반영된다"
    assert hashes["verb"] != hashes["noun"]


# 기존 3개 단어장의 content_hash (품사 채움 후 2026-11-10 측정). 시드 내용이 의도치 않게 바뀌는 것을 막는 고정값이다.
# 주의: 이 단어장의 내용(뜻·예문·발음기호·순서·메타)을 의도적으로 고쳤다면 이 값도 의도적으로 갱신해야 한다.
GOLDEN_HASHES = {
    "beginner-200": "cec63c6f751e6406024c1c83089c625b9aa4229af5963fb7d8eac8a074d07a27",
    "intermediate-200": "8cad787f78ec878335458e2a8b514c54a581a1dcda3090c7f7b7f9a3f6608e46",
    "advanced-200": "162e87b3dcd5d9e47b4309c90088446758ee5712b62b2b2d85d73870f4a677a5",
}


def test_existing_vocabularies_match_their_golden_content_hash() -> None:
    """기존 600단어 시드의 해시가 고정값과 같아야 한다. 내용을 고쳤다면 이 값도 의도적으로 갱신한다."""
    actual = {v.slug: compute_content_hash(v) for v in load_seed_vocabularies(SEED_DIR) if v.slug in GOLDEN_HASHES}
    assert actual == GOLDEN_HASHES


@pytest.mark.asyncio
async def test_pos_is_stored_and_missing_pos_is_null(tmp_path: Path) -> None:
    _simple_seed(tmp_path, words=[_pos("apple", "사과", "noun"), _word("book", "책")])
    await _run(tmp_path)
    words = await _words(f"{PREFIX}a")
    assert words["apple"].pos == "noun"
    assert words["book"].pos is None


@pytest.mark.asyncio
async def test_same_seed_with_pos_is_idempotent(tmp_path: Path) -> None:
    _simple_seed(tmp_path, words=[_pos("apple", "사과", "noun"), _pos("book", "책", "noun")])
    await _run(tmp_path)
    report = await _run(tmp_path)
    assert (report.created, report.updated, report.unchanged) == (0, 0, 1)
    assert report.words_inserted == 0 and report.words_updated == 0


@pytest.mark.asyncio
async def test_adding_pos_later_updates_in_place_and_keeps_word_id(tmp_path: Path) -> None:
    _simple_seed(tmp_path, words=[_word("apple", "사과")])
    await _run(tmp_path)
    before = (await _words(f"{PREFIX}a"))["apple"].id
    _simple_seed(tmp_path, words=[_pos("apple", "사과", "noun")])
    report = await _run(tmp_path)
    after = (await _words(f"{PREFIX}a"))["apple"]
    assert (report.updated, report.words_updated, report.words_inserted) == (1, 1, 0)
    assert after.id == before and after.pos == "noun"


@pytest.mark.asyncio
async def test_removing_pos_from_seed_returns_the_column_to_null(tmp_path: Path) -> None:
    _simple_seed(tmp_path, words=[_pos("apple", "사과", "noun")])
    await _run(tmp_path)
    _simple_seed(tmp_path, words=[_word("apple", "사과")])
    await _run(tmp_path)
    assert (await _words(f"{PREFIX}a"))["apple"].pos is None


# ---------------------------------------------------------------------------
# 8. 신규 2개 단어장 데이터 완성도 관문 (DB 없음). 시험 대비 200 + 실무 비즈니스 200 (v2.2 카탈로그 확충).
#    데이터가 없으면 전부 실패(Red)하고, 400단어가 채워져야 통과(Green)한다.
# ---------------------------------------------------------------------------

ALLOWED_POS = {"noun", "verb", "adjective", "adverb", "preposition", "conjunction"}
_HANGUL = __import__("re").compile(r"[\uAC00-\uD7A3]")

# 예문에 표제어의 불규칙 활용형이 들어가는 경우만 여기에 올린다 ({표제어: 예문 속 형태}). 규칙 활용(s, es, ed, ing, ies, ied, er 등)은 자동 허용한다.
EXAMPLE_FORM_EXCEPTIONS: dict[str, str] = {}
EXAMPLE_FORM_EXCEPTIONS_LIMIT = 25


def _new_words() -> list[tuple[str, system_seed.SeedWordData]]:
    return [(v.slug, w) for v in load_seed_vocabularies(SEED_DIR) if v.slug in NEW_SLUGS for w in v.words]


def _forms(term: str) -> set[str]:
    """표제어의 규칙 활용형. 어미 s/es/ed/ing/er/ly, y→i, 끝 e 탈락, 자음 겹침."""
    t = term.lower()
    forms = {t, t + "s", t + "es", t + "d", t + "ed", t + "ing", t + "er", t + "ers", t + "ly", t + "'s"}
    if t.endswith("e"):
        forms |= {t[:-1] + "ing", t[:-1] + "ed", t[:-1] + "er", t[:-1] + "ers", t + "r", t + "rs"}
    if t.endswith("y"):
        forms |= {t[:-1] + "ies", t[:-1] + "ied", t[:-1] + "ier", t[:-1] + "ily"}
    if len(t) >= 2:
        forms |= {t + t[-1] + "ed", t + t[-1] + "ing", t + t[-1] + "er", t + t[-1] + "ers"}
    return forms


def example_has_headword(term: str, example: str, exceptions: dict[str, str] | None = None) -> bool:
    """예문 안에 표제어 또는 그 활용형이 단어 경계로 들어 있는가."""
    import re

    tokens = set(re.findall(r"[a-z]+(?:'[a-z]+)?", example.lower()))
    extra = (exceptions or {}).get(term.lower())
    return bool(tokens & _forms(term)) or (extra is not None and extra.lower() in tokens)


def test_example_has_headword_checker_itself() -> None:
    assert example_has_headword("invoice", "Please send the invoice by Friday.")
    assert example_has_headword("negotiate", "They negotiated a lower price.")
    assert example_has_headword("apply", "Applies to all staff.")  # y → ies
    assert example_has_headword("apply", "She applies for jobs.")
    assert example_has_headword("stop", "The bus stopped suddenly.")
    assert example_has_headword("buy", "We bought it.") is False
    assert example_has_headword("buy", "We bought it.", {"buy": "bought"})
    assert example_has_headword("cat", "The category is wide.") is False, "단어 경계로만 일치한다"


def test_gate_1_new_vocabularies_have_200_words_each_and_the_total_is_1000() -> None:
    sizes = {v.slug: len(v.words) for v in load_seed_vocabularies(SEED_DIR)}
    assert sizes.get("exam-core-200") == 200 and sizes.get("business-practical-200") == 200
    assert sum(sizes.values()) == 1000


def test_gate_2_every_new_word_has_all_six_fields() -> None:
    missing = [
        f"{slug}:{w.term}"
        for slug, w in _new_words()
        if not (w.term and w.phonetic and w.pos and w.meaning and w.example and w.example_meaning)
    ]
    assert len(_new_words()) == 400, "신규 400단어가 있어야 한다"
    assert missing == [], f"6개 필드가 비어 있는 단어 {len(missing)}개: {missing[:10]}"


def test_gate_3_all_1000_words_have_plain_ipa_with_syllable_rules() -> None:
    words = _real_words()
    assert len(words) == 1000
    assert [w.term for _, w in words if not w.phonetic] == []
    assert [(w.term, w.phonetic) for _, w in words if w.phonetic and any(c in w.phonetic for c in "/[]()")] == []
    vowel = "aeiouæɑɔɛɪʊʌəɚɝ"
    bad_mono = [(w.term, w.phonetic) for _, w in words if w.phonetic and "ˈ" in w.phonetic and sum(c in vowel for c in w.phonetic) <= 1]
    assert bad_mono == [], "단음절 단어에는 강세 표시를 하지 않는다"
    assert [(w.term, w.phonetic) for _, w in words if w.phonetic and w.phonetic.count("ˈ") > 1] == [], "1차 강세는 단어당 1개 이하"


def test_gate_4_pos_is_one_of_the_allowed_english_words() -> None:
    bad = [(w.term, w.pos) for _, w in _new_words() if w.pos not in ALLOWED_POS]
    assert len(_new_words()) == 400 and bad == [], f"허용 집합 밖의 품사: {bad[:10]}"


def test_gate_5_example_contains_the_headword_or_a_listed_inflection() -> None:
    assert len(EXAMPLE_FORM_EXCEPTIONS) <= EXAMPLE_FORM_EXCEPTIONS_LIMIT, "예외표가 커지면 예문을 고쳐라"
    words = _new_words()
    assert len(words) == 400
    bad = [(w.term, w.example) for _, w in words if not example_has_headword(w.term, w.example or "", EXAMPLE_FORM_EXCEPTIONS)]
    assert bad == [], f"예문에 표제어가 없는 단어 {len(bad)}개: {bad[:5]}"


def test_gate_6_no_term_is_shared_across_all_1000_words() -> None:
    from collections import Counter

    counts = Counter(system_seed._term_key(w.term) for _, w in _real_words())
    assert len(_real_words()) == 1000
    assert [t for t, n in counts.items() if n > 1] == []


def test_gate_7_meaning_and_translation_are_korean_and_example_is_english() -> None:
    words = _new_words()
    assert len(words) == 400
    assert [w.term for _, w in words if not _HANGUL.search(w.meaning)] == []
    assert [w.term for _, w in words if not _HANGUL.search(w.example_meaning or "")] == []
    assert [w.term for _, w in words if _HANGUL.search(w.example or "")] == [], "영문 예문에 한글이 섞이면 안 된다"
    assert [w.term for _, w in words if " " in w.term or "-" in w.term] == [], "표제어는 단일 단어만 수록한다"


def test_gate_8_meanings_are_unique_inside_each_new_vocabulary_so_quiz_options_never_tie() -> None:
    vocabularies = [v for v in load_seed_vocabularies(SEED_DIR) if v.slug in NEW_SLUGS]
    assert len(vocabularies) == 2
    for v in vocabularies:
        meanings = [w.meaning for w in v.words]
        assert len(v.words) >= 4
        assert len(set(meanings)) == len(meanings), (v.slug, [m for m in set(meanings) if meanings.count(m) > 1])


# 8. 기존 600단어 품사 채우기 (v2.2 후속). 실제 시드 전체가 대상이다.

_KNOWN_POS = {"noun", "verb", "adjective", "adverb", "preposition", "conjunction", "pronoun", "interjection"}  # 프론트 POS_LABELS 와 같은 8종


def test_every_real_seed_word_has_a_known_pos() -> None:
    bad = [f"{slug}:{w.term}={w.pos}" for slug, w in _real_words() if w.pos not in _KNOWN_POS]
    assert bad == [], f"품사가 없거나 알 수 없는 단어 {len(bad)}개: {bad[:10]}"
