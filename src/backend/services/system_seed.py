# 2026-11-05 - voda-voca - 표준 단어장 시드 로더: 시드 파일 검증, content_hash 비교, 멱등 적재 (중앙 제공형 단어장 B-2)
# 파일 위치: src/backend/services/system_seed.py

import hashlib
import json
import logging
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_session_factory
from backend.models import SystemVocabulary, SystemWord

logger = logging.getLogger(__name__)

SEED_DIR = Path(__file__).resolve().parents[1] / "data" / "seeds"

# DB 컬럼 길이와 같은 한도. 시드 파일 검증과 모델 정의가 어긋나지 않게 이름으로 모아 둔다.
SLUG_MAX = 50
TITLE_MAX = 100
CATEGORY_MAX = 50
DESCRIPTION_MAX = 255
TERM_MAX = 100
MEANING_MAX = 200
EXAMPLE_MAX = 500
EXAMPLE_MEANING_MAX = 500
LEVEL_RANGE = (1, 5)


class SeedValidationError(ValueError):
    """시드 파일이 규칙을 어겼다. 이 오류가 나면 DB 에는 아무것도 쓰지 않는다."""


@dataclass(frozen=True)
class SeedWordData:
    term: str
    meaning: str
    example: str | None
    example_meaning: str | None
    order_index: int


@dataclass(frozen=True)
class SeedVocabularyData:
    slug: str
    title: str
    category: str
    level: int
    description: str | None
    sort_order: int
    words: tuple[SeedWordData, ...]


@dataclass
class SeedItemReport:
    slug: str
    status: str  # 'created' | 'updated' | 'unchanged'
    words_inserted: int = 0
    words_updated: int = 0
    total_words: int = 0


@dataclass
class SeedReport:
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    words_inserted: int = 0
    words_updated: int = 0
    warnings: list[str] = field(default_factory=list)
    items: list[SeedItemReport] = field(default_factory=list)


# ---------------------------------------------------------------------------
# 파일 로드·검증
# ---------------------------------------------------------------------------


def _term_key(term: str) -> str:
    """DB 콜레이션(utf8mb4_0900_ai_ci)처럼 대소문자와 악센트를 무시한 비교 키다."""
    decomposed = unicodedata.normalize("NFKD", term.casefold())
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def _text(value: object, name: str, where: str, max_length: int, *, required: bool) -> str | None:
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise SeedValidationError(f"{where}: {name} 는 문자열이어야 합니다")
    cleaned = value.strip()
    if not cleaned:
        if required:
            raise SeedValidationError(f"{where}: {name} 가 비어 있습니다")
        return None
    if len(cleaned) > max_length:
        raise SeedValidationError(f"{where}: {name} 는 {max_length}자 이하여야 합니다 ({len(cleaned)}자)")
    return cleaned


def _read_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SeedValidationError(f"{path.name}: 읽을 수 없습니다 ({exc})") from exc


def _parse_words(slug: str, raw: object) -> tuple[SeedWordData, ...]:
    if not isinstance(raw, list) or not raw:
        raise SeedValidationError(f"{slug}: words 가 비어 있거나 배열이 아닙니다")
    words: list[SeedWordData] = []
    seen: dict[str, str] = {}
    for index, item in enumerate(raw):
        where = f"{slug} words[{index}]"
        if not isinstance(item, dict):
            raise SeedValidationError(f"{where}: 객체여야 합니다")
        term = _text(item.get("term"), "term", where, TERM_MAX, required=True)
        meaning = _text(item.get("meaning"), "meaning", where, MEANING_MAX, required=True)
        example = _text(item.get("example"), "example", where, EXAMPLE_MAX, required=False)
        example_meaning = _text(item.get("example_meaning"), "example_meaning", where, EXAMPLE_MEANING_MAX, required=False)
        if example is None:
            example_meaning = None  # 예문이 없으면 예문 뜻도 두지 않는다 (기존 words 규칙)
        key = _term_key(term)
        if key in seen:
            raise SeedValidationError(f"{where}: term 중복 ('{term}' 는 '{seen[key]}' 와 같은 단어로 취급됩니다)")
        seen[key] = term
        words.append(SeedWordData(term, meaning, example, example_meaning, index))
    return tuple(words)


def load_seed_vocabularies(seed_dir: Path = SEED_DIR) -> list[SeedVocabularyData]:
    """vocabularies.json 과 words/<slug>.json 을 읽어 검증한다. 하나라도 틀리면 SeedValidationError."""
    metas = _read_json(seed_dir / "vocabularies.json")
    if not isinstance(metas, list) or not metas:
        raise SeedValidationError("vocabularies.json: 비어 있거나 배열이 아닙니다")

    vocabularies: list[SeedVocabularyData] = []
    slugs: set[str] = set()
    for index, meta in enumerate(metas):
        where = f"vocabularies[{index}]"
        if not isinstance(meta, dict):
            raise SeedValidationError(f"{where}: 객체여야 합니다")
        slug = _text(meta.get("slug"), "slug", where, SLUG_MAX, required=True)
        assert slug is not None
        if slug in slugs:
            raise SeedValidationError(f"{where}: slug 중복 ('{slug}')")
        slugs.add(slug)
        title = _text(meta.get("title"), "title", slug, TITLE_MAX, required=True)
        category = _text(meta.get("category"), "category", slug, CATEGORY_MAX, required=True)
        description = _text(meta.get("description"), "description", slug, DESCRIPTION_MAX, required=False)
        level = meta.get("level", 1)
        if isinstance(level, bool) or not isinstance(level, int) or not LEVEL_RANGE[0] <= level <= LEVEL_RANGE[1]:
            raise SeedValidationError(f"{slug}: level 은 {LEVEL_RANGE[0]}~{LEVEL_RANGE[1]} 정수여야 합니다")
        sort_order = meta.get("sort_order", 0)
        if isinstance(sort_order, bool) or not isinstance(sort_order, int):
            raise SeedValidationError(f"{slug}: sort_order 는 정수여야 합니다")

        words_path = seed_dir / "words" / f"{slug}.json"
        if not words_path.is_file():
            raise SeedValidationError(f"{slug}: words 파일이 없습니다 ({words_path.name})")
        words = _parse_words(slug, _read_json(words_path))
        assert title is not None and category is not None
        vocabularies.append(SeedVocabularyData(slug, title, category, level, description, sort_order, words))
    return vocabularies


def compute_content_hash(vocabulary: SeedVocabularyData) -> str:
    """메타와 단어 목록(순서 포함)으로 만든 SHA-256. 같으면 DB 를 건드리지 않는다."""
    payload = {
        "title": vocabulary.title,
        "category": vocabulary.category,
        "level": vocabulary.level,
        "description": vocabulary.description,
        "sort_order": vocabulary.sort_order,
        "words": [
            [w.term, w.meaning, w.example, w.example_meaning, w.order_index] for w in vocabulary.words
        ],
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# DB 적재
# ---------------------------------------------------------------------------


async def _seed_one(session: AsyncSession, data: SeedVocabularyData, report: SeedReport) -> None:
    content_hash = compute_content_hash(data)

    # 1) 행이 없으면 만든다. 다른 워커가 먼저 만들었다면 아무 일도 하지 않는다 (slug 유니크 + no-op upsert).
    await session.execute(
        mysql_insert(SystemVocabulary)
        .values(
            slug=data.slug,
            title=data.title,
            category=data.category,
            level=data.level,
            description=data.description,
            sort_order=data.sort_order,
        )
        .on_duplicate_key_update(slug=SystemVocabulary.slug)
    )

    # 2) 단어장 행을 잠가 같은 단어장의 동시 적재를 직렬화한다. 나중 워커는 앞 워커가 끝난 뒤 해시를 본다.
    vocabulary = (
        await session.execute(
            select(SystemVocabulary).where(SystemVocabulary.slug == data.slug).with_for_update()
        )
    ).scalar_one()

    # content_hash 가 NULL 이면 아직 한 번도 적재되지 않은 행이다 (rowcount 는 드라이버의 found-rows 설정 때문에 믿지 않는다).
    created = vocabulary.content_hash is None
    if not created and vocabulary.content_hash == content_hash:
        report.unchanged += 1
        report.items.append(SeedItemReport(data.slug, "unchanged", total_words=vocabulary.total_words))
        await session.commit()
        return

    vocabulary.title = data.title
    vocabulary.category = data.category
    vocabulary.level = data.level
    vocabulary.description = data.description
    vocabulary.sort_order = data.sort_order

    existing = {
        _term_key(w.term): w
        for w in (
            await session.execute(select(SystemWord).where(SystemWord.vocabulary_id == vocabulary.id))
        ).scalars()
    }
    seed_keys = {_term_key(w.term) for w in data.words}

    inserted: list[dict[str, object]] = []
    updated = 0
    for word in data.words:
        row = existing.get(_term_key(word.term))
        if row is None:
            inserted.append(
                {
                    "vocabulary_id": vocabulary.id,
                    "term": word.term,
                    "meaning": word.meaning,
                    "example": word.example,
                    "example_meaning": word.example_meaning,
                    "order_index": word.order_index,
                }
            )
            continue
        new_values = (word.term, word.meaning, word.example, word.example_meaning, word.order_index)
        if (row.term, row.meaning, row.example, row.example_meaning, row.order_index) != new_values:
            row.term, row.meaning, row.example, row.example_meaning, row.order_index = new_values
            updated += 1
    if inserted:
        await session.execute(mysql_insert(SystemWord), inserted)

    # 시드에서 빠진 단어는 지우지 않는다 (학습 이력이 참조할 수 있다). 경고만 남긴다.
    for key, row in existing.items():
        if key not in seed_keys:
            report.warnings.append(f"{data.slug}: 시드에 없는 단어 '{row.term}' 를 DB 에 그대로 둡니다")

    await session.flush()
    total = await session.scalar(
        select(func.count()).select_from(SystemWord).where(SystemWord.vocabulary_id == vocabulary.id)
    )
    vocabulary.total_words = int(total or 0)
    vocabulary.content_hash = content_hash
    await session.commit()

    status = "created" if created else "updated"
    report.created += created
    report.updated += not created
    report.words_inserted += len(inserted)
    report.words_updated += updated
    report.items.append(
        SeedItemReport(data.slug, status, len(inserted), updated, vocabulary.total_words)
    )


async def seed_system_vocabularies(session: AsyncSession, seed_dir: Path = SEED_DIR) -> SeedReport:
    """시드 파일을 DB 에 맞춘다. 같은 시드로 여러 번 실행해도, 여러 워커가 동시에 실행해도 안전하다.

    파일 전체를 먼저 검증하므로 잘못된 시드는 DB 를 하나도 바꾸지 않는다. 단어장 하나를 한 트랜잭션으로 처리한다.
    """
    vocabularies = load_seed_vocabularies(seed_dir)
    report = SeedReport()
    try:
        for data in vocabularies:
            await _seed_one(session, data, report)
    except Exception:
        await session.rollback()
        raise
    return report


async def init_system_seeds() -> SeedReport:
    """앱 시작(lifespan) 시 표준 단어장 시드를 적재한다. 시드가 잘못되면 시작을 막는다."""
    async with get_session_factory()() as session:
        report = await seed_system_vocabularies(session)
    logger.info(
        "표준 단어장 시드: 생성 %d, 갱신 %d, 변경 없음 %d (단어 추가 %d, 수정 %d)",
        report.created,
        report.updated,
        report.unchanged,
        report.words_inserted,
        report.words_updated,
    )
    for warning in report.warnings:
        logger.warning(warning)
    return report
