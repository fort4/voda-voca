# 2026-11-10 - voda-voca - 학습 개수 사용자 설정 스키마: 퀴즈·플래시카드 문항 수와 오늘의 목표 (REQ-147)
# 파일 위치: src/backend/schemas/user_settings.py

from typing import Annotated, Any

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StrictInt, model_validator

# 선택 가능한 값과 기본값은 여기 한 곳에서만 정한다. 응답에 싣어 프론트가 하드코딩하지 않게 한다.
# DB 는 값이 0 보다 큰지만 검사하므로, 옵션을 늘릴 때 마이그레이션이 필요 없다.
SETTING_OPTIONS: tuple[int, ...] = (10, 20, 30)
SETTING_DEFAULT = 10


def _check_option(value: int) -> int:
    if value not in SETTING_OPTIONS:
        raise ValueError(f"{', '.join(map(str, SETTING_OPTIONS))} 중 하나여야 합니다.")
    return value


# StrictInt: "20" 이나 true 같은 값이 조용히 정수로 바뀌지 않게 한다.
SettingValue = Annotated[StrictInt, AfterValidator(_check_option)]


class UserSettingsPatch(BaseModel):
    """부분 수정 입력. 보낸 필드만 바꾼다. null 은 허용하지 않는다."""

    model_config = ConfigDict(extra="forbid")

    quiz_count: SettingValue | None = Field(default=None, description="퀴즈 1회 문항 수")
    flashcard_count: SettingValue | None = Field(default=None, description="플래시카드 1회 문항 수")
    daily_goal: SettingValue | None = Field(default=None, description="오늘의 목표 문항 수")

    @model_validator(mode="before")
    @classmethod
    def _reject_explicit_null(cls, data: Any) -> Any:
        # 필드를 생략하는 것은 "바꾸지 않음"이고, null 을 보내는 것은 잘못된 입력이다.
        if isinstance(data, dict):
            for key, value in data.items():
                if value is None and key in cls.model_fields:
                    raise ValueError(f"{key} 는 null 일 수 없습니다.")
        return data


class UserSettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    quiz_count: int
    flashcard_count: int
    daily_goal: int
    options: list[int] = Field(default_factory=lambda: list(SETTING_OPTIONS), description="선택 가능한 값 목록")
