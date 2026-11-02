# 2026-11-02 - voda-voca - 기본 단어장 시드 로더: 초/중/고 200제 JSON 을 읽어 가입 시 복제할 목록으로 제공 (기본 단어장 자동 제공)
# 파일 위치: src/backend/services/seed.py

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


@lru_cache(maxsize=1)
def default_wordbooks() -> tuple[SeedWordbook, ...]:
    """기본 단어장 3종을 읽어 돌려준다. 파일은 한 번만 읽는다."""
    out: list[SeedWordbook] = []
    for file_name, name in DEFAULT_WORDBOOKS:
        raw = json.loads((SEED_DIR / file_name).read_text(encoding="utf-8"))
        words = tuple(SeedWord(term=item["term"], meaning=item["meaning"], example=item["example"]) for item in raw)
        out.append(SeedWordbook(name=name, words=words))
    return tuple(out)
