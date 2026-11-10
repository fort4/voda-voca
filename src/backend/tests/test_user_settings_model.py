# 2026-11-10 - voda-voca - 학습 개수 사용자 설정 모델·스키마 테스트: users 컬럼 3종 기본값, CHECK, 허용 값 검증 (REQ-147, S1)
# 파일 위치: src/backend/tests/test_user_settings_model.py

import uuid

import pytest
from pydantic import ValidationError
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from backend.db.session import get_session_factory
from backend.models import User
from backend.schemas.user_settings import (
    SETTING_DEFAULT,
    SETTING_OPTIONS,
    UserSettingsOut,
    UserSettingsPatch,
)

COLUMNS = ("quiz_count", "flashcard_count", "daily_goal")


def _new_user() -> User:
    return User(nickname=f"tvoda-{uuid.uuid4().hex[:12]}", password_hash="x")


def test_options_and_default_are_defined_in_one_place() -> None:
    assert SETTING_OPTIONS == (10, 20, 30)
    assert SETTING_DEFAULT == 10
    assert SETTING_DEFAULT in SETTING_OPTIONS


def test_user_model_declares_the_three_setting_columns() -> None:
    for name in COLUMNS:
        column = User.__table__.c[name]
        assert column.nullable is False
        assert str(column.server_default.arg) == "10"


@pytest.mark.parametrize("value", SETTING_OPTIONS)
def test_patch_accepts_each_option(value: int) -> None:
    assert UserSettingsPatch(daily_goal=value).model_dump(exclude_unset=True) == {"daily_goal": value}


@pytest.mark.parametrize("value", [0, 5, 15, 31, 100, -10, "abc", None])
@pytest.mark.parametrize("field", COLUMNS)
def test_patch_rejects_values_outside_the_options(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        UserSettingsPatch(**{field: value})


def test_patch_allows_partial_and_empty_bodies() -> None:
    assert UserSettingsPatch().model_dump(exclude_unset=True) == {}
    assert UserSettingsPatch(quiz_count=20, daily_goal=30).model_dump(exclude_unset=True) == {"quiz_count": 20, "daily_goal": 30}


def test_out_schema_carries_the_options() -> None:
    out = UserSettingsOut(quiz_count=10, flashcard_count=20, daily_goal=30)
    assert out.model_dump() == {"quiz_count": 10, "flashcard_count": 20, "daily_goal": 30, "options": [10, 20, 30]}


@pytest.mark.asyncio
async def test_new_user_gets_default_10_for_every_setting() -> None:
    async with get_session_factory()() as db:
        user = _new_user()
        db.add(user)
        await db.commit()
        row = (await db.execute(select(User).where(User.id == user.id))).scalar_one()
        assert [getattr(row, name) for name in COLUMNS] == [10, 10, 10]


@pytest.mark.asyncio
@pytest.mark.parametrize("column", COLUMNS)
async def test_database_rejects_zero(column: str) -> None:
    async with get_session_factory()() as db:
        user = _new_user()
        db.add(user)
        await db.commit()
        with pytest.raises(DBAPIError) as exc:
            await db.execute(text(f"UPDATE users SET {column} = 0 WHERE id = :id"), {"id": user.id})
        # "컬럼 없음" 같은 다른 오류로 통과하지 않도록 CHECK 위반인지 확인한다
        assert f"ck_users_{column}_positive" in str(exc.value)
