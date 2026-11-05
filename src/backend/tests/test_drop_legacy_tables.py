# 2026-11-05 - voda-voca - 옛 개인 단어장 테이블(wordbooks, words) 제거 회귀 테스트 (D-2): 모델과 실제 DB 양쪽에서 부재 확인
# 파일 위치: src/backend/tests/test_drop_legacy_tables.py

import importlib

import pytest
from sqlalchemy import text

import backend.models as models
from backend.db.session import get_session_factory
from backend.models import Base

LEGACY_TABLES = {"words", "wordbooks"}


def test_legacy_models_are_not_registered() -> None:
    assert LEGACY_TABLES.isdisjoint(Base.metadata.tables)
    assert not hasattr(models, "Word") and not hasattr(models, "Wordbook")


@pytest.mark.parametrize("module", ["backend.models.word", "backend.models.wordbook"])
def test_legacy_model_modules_are_gone(module: str) -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(module)


@pytest.mark.asyncio
async def test_legacy_tables_do_not_exist_in_database() -> None:
    async with get_session_factory()() as db:
        rows = await db.execute(text("SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE()"))
        tables = {r[0] for r in rows}
    assert LEGACY_TABLES.isdisjoint(tables)
