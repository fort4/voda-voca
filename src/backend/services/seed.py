# 2026-11-02 - voda-voca - 시드 로더: 기본 단어장(JSON)과 추천 프리셋(CSV 3열 또는 4열)을 읽어 단어장 생성용 목록으로 제공 (v2 Phase 1 예문 한글 뜻 포함)
# 파일 위치: src/backend/services/seed.py

import csv
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

SEED_DIR = Path(__file__).resolve().parents[1] / "data" / "seeds"


@dataclass(frozen=True)
class SeedWord:
    term: str
    meaning: str
    example: str
    example_meaning: str | None = None  # 예문의 한글 뜻. 없으면 None


@dataclass(frozen=True)
class SeedWordbook:
    name: str
    words: tuple[SeedWord, ...]


# (파일 이름, 단어장 이름) 순서가 곧 가입 시 생성 순서다.
DEFAULT_WORDBOOKS: tuple[tuple[str, str], ...] = (
    ("beginner_200.json", "초급 필수 영단어 200"),
    ("intermediate_200.json", "중급 핵심 영단어 200"),
    ("advanced_200.json", "고급 심화 영단어 200"),
)


class SeedDataMissingError(Exception):
    """추천 단어장 데이터 파일이 아직 없다. 라우터는 503 으로 알린다."""


# 추천 프리셋: 키 -> (파일 이름, 생성될 단어장 이름). 파일은 요청마다 읽는다 (데이터 교체가 재시작 없이 반영되도록).
PRESET_WORDBOOKS: dict[str, tuple[str, str]] = {
    "intermediate-1000": ("intermediate_1000.csv", "중급 필수 영단어 1,000"),
}

# CSV 헤더는 두 형식 중 하나여야 한다. 3열은 구형, 4열은 예문 뜻을 포함한 신형이다.
PRESET_COLUMNS = ("term", "meaning", "example")
PRESET_COLUMNS_WITH_TRANSLATION = ("term", "meaning", "example", "example_meaning")


def _seed_word(term: str, meaning: str, example: str | None, example_meaning: str | None) -> SeedWord:
    """값을 다듬는다. 예문이 없으면 예문 뜻도 버린다 (서버의 단어 저장 규칙과 같다)."""
    clean_example = (example or "").strip()
    clean_translation = (example_meaning or "").strip() if clean_example else ""
    return SeedWord(
        term=term.strip(),
        meaning=meaning.strip(),
        example=clean_example,
        example_meaning=clean_translation or None,
    )


def _read_csv_words(path: Path) -> tuple[SeedWord, ...]:
    """term,meaning,example 또는 term,meaning,example,example_meaning 헤더의 CSV 를 읽는다. BOM 이 있어도 허용한다."""
    with path.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        fields = tuple(reader.fieldnames or ())
        if fields not in (PRESET_COLUMNS, PRESET_COLUMNS_WITH_TRANSLATION):
            expected = " 또는 ".join(",".join(cols) for cols in (PRESET_COLUMNS, PRESET_COLUMNS_WITH_TRANSLATION))
            raise ValueError(f"{path.name}: 헤더는 {expected} 이어야 합니다")
        return tuple(
            _seed_word(row["term"], row["meaning"], row["example"], row.get("example_meaning"))
            for row in reader
        )


def _read_json_words(path: Path) -> tuple[SeedWord, ...]:
    """JSON 배열을 읽는다. example_meaning 키는 없어도 된다."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    return tuple(
        _seed_word(item["term"], item["meaning"], item["example"], item.get("example_meaning"))
        for item in raw
    )


def load_preset(key: str) -> tuple[str, tuple[SeedWord, ...]]:
    """프리셋 단어장의 (이름, 단어 목록)을 읽는다. 파일이 없으면 SeedDataMissingError."""
    file_name, name = PRESET_WORDBOOKS[key]
    path = SEED_DIR / file_name
    if not path.is_file():
        raise SeedDataMissingError(file_name)
    return name, _read_csv_words(path)


@lru_cache(maxsize=1)
def default_wordbooks() -> tuple[SeedWordbook, ...]:
    """기본 단어장 3종을 읽어 돌려준다. 파일은 한 번만 읽는다."""
    return tuple(
        SeedWordbook(name=name, words=_read_json_words(SEED_DIR / file_name))
        for file_name, name in DEFAULT_WORDBOOKS
    )
