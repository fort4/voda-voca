# 2026-11-26 - voda-voca - 개인 단어장 요청 스키마: 단어장 생성·수정, 단어 등록·수정, 일괄 등록 결과 (REQ-170, 171)
# 파일 위치: src/backend/schemas/content.py

from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field, StringConstraints, field_validator, model_validator

# 길이 한도는 DB 컬럼, 시드 검증(services/system_seed.py)과 같다.
TITLE_MAX = 100
DESCRIPTION_MAX = 255
CATEGORY_MAX = 50
DEFAULT_CATEGORY = "PERSONAL"  # 분류를 고르지 않은 개인 단어장
TERM_MAX = 100
MEANING_MAX = 200
EXAMPLE_MAX = 500


def _blank_to_none(value: object) -> object:
    """선택 항목은 공백만 있으면 없는 것으로 본다."""
    if isinstance(value, str):
        return value.strip() or None
    return value


def _required(max_length: int):
    return Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=max_length)]


Title = _required(TITLE_MAX)
Category = _required(CATEGORY_MAX)
Term = _required(TERM_MAX)
Meaning = _required(MEANING_MAX)
Description = Annotated[Annotated[str, Field(max_length=DESCRIPTION_MAX)] | None, BeforeValidator(_blank_to_none)]
Example = Annotated[Annotated[str, Field(max_length=EXAMPLE_MAX)] | None, BeforeValidator(_blank_to_none)]


class VocabularyCreate(BaseModel):
    title: Title
    description: Description = None
    category: Category = DEFAULT_CATEGORY
    level: int = Field(default=1, ge=1, le=5)


class VocabularyUpdate(BaseModel):
    """제목과 설명만 바꾼다. 보내지 않은 항목은 그대로 둔다."""

    title: Title | None = None
    description: Description = None

    @field_validator("title")
    @classmethod
    def _title_cannot_be_cleared(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("제목은 비울 수 없습니다.")
        return value


class WordInput(BaseModel):
    """단어 등록·수정 입력. 수정은 네 항목 전체를 바꾼다."""

    term: Term
    meaning: Meaning
    example: Example = None
    example_meaning: Example = None

    @model_validator(mode="after")
    def _translation_needs_an_example(self) -> "WordInput":
        if self.example is None:
            self.example_meaning = None  # 예문이 없으면 예문 뜻도 두지 않는다 (시드와 같은 규칙)
        return self


class WordImportOut(BaseModel):
    """CSV 일괄 등록 결과 (REQ-171)."""

    created: int = Field(description="새로 등록한 단어 수")
    skipped: int = Field(description="이미 있거나 파일 안에서 겹쳐 건너뛴 행 수")
