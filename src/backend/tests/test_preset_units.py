# 2026-11-02 - voda-voca - 추천 프리셋 서비스 단위 테스트: 파일 없음, 이름 중복과 다른 무결성 오류의 분기 (DB 없이 가짜 세션)
# 파일 위치: src/backend/tests/test_preset_units.py

import pytest
from sqlalchemy.exc import IntegrityError

from backend.services import seed, wordbook as wordbook_service
from backend.services.seed import SeedDataMissingError, load_preset


class _FakeSession:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.rolled_back = False

    def add(self, _obj: object) -> None:
        pass

    async def flush(self) -> None:
        if self.error is not None:
            raise self.error

    async def execute(self, *_args: object, **_kwargs: object) -> None:
        pass

    async def commit(self) -> None:
        pass

    async def rollback(self) -> None:
        self.rolled_back = True


def test_load_preset_raises_when_the_file_is_missing(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(seed, "SEED_DIR", tmp_path)
    with pytest.raises(SeedDataMissingError):
        load_preset("intermediate-1000")


def test_load_preset_reads_terms_meanings_and_examples(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "intermediate_1000.csv").write_text("term,meaning,example\na,가,a!\n", encoding="utf-8")
    monkeypatch.setattr(seed, "SEED_DIR", tmp_path)
    name, words = load_preset("intermediate-1000")
    assert name == "중급 필수 영단어 1,000"
    assert words[0].term == "a" and words[0].meaning == "가" and words[0].example == "a!"


@pytest.mark.asyncio
async def test_preset_name_conflict_becomes_name_taken(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "intermediate_1000.csv").write_text("term,meaning,example\na,가,a\n", encoding="utf-8")
    monkeypatch.setattr(seed, "SEED_DIR", tmp_path)
    db = _FakeSession(IntegrityError("INSERT", {}, Exception("Duplicate entry for key 'uk_wordbooks_user_name'")))
    with pytest.raises(wordbook_service.WordbookNameTakenError):
        await wordbook_service.create_preset_wordbook(db, 1, "intermediate-1000")  # type: ignore[arg-type]
    assert db.rolled_back is True


@pytest.mark.asyncio
async def test_other_integrity_errors_are_propagated_unchanged(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "intermediate_1000.csv").write_text("term,meaning,example\na,가,a\n", encoding="utf-8")
    monkeypatch.setattr(seed, "SEED_DIR", tmp_path)
    db = _FakeSession(IntegrityError("INSERT", {}, Exception("uk_words_wordbook_term")))
    with pytest.raises(IntegrityError):
        await wordbook_service.create_preset_wordbook(db, 1, "intermediate-1000")  # type: ignore[arg-type]
    assert db.rolled_back is True


@pytest.mark.asyncio
async def test_missing_seed_file_fails_before_touching_the_database(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(seed, "SEED_DIR", tmp_path)
    db = _FakeSession()
    with pytest.raises(SeedDataMissingError):
        await wordbook_service.create_preset_wordbook(db, 1, "intermediate-1000")  # type: ignore[arg-type]
    assert db.rolled_back is False
