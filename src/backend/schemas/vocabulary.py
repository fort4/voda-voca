# 2026-11-05 - voda-voca - 표준 단어장 API 스키마: 카탈로그, 단어 목록, 활성 단어장 변경
# 파일 위치: src/backend/schemas/vocabulary.py

from pydantic import BaseModel, Field


class UserProgressOut(BaseModel):
    """한 표준 단어장에 대한 내 학습 요약 (user_word_progress 기준)."""

    studied_words: int = Field(description="한 번이라도 풀어 본 단어 수")
    memorized_words: int = Field(description="숙련(연속 정답 3회)한 단어 수")
    progress_rate: float = Field(description="studied_words / total_words (0~100, 소수 첫째 자리)")
    is_active: bool = Field(description="지금 학습 중인 단어장인지")


class VocabularyOut(BaseModel):
    id: int
    slug: str
    title: str
    category: str
    level: int
    description: str | None
    total_words: int
    user_progress: UserProgressOut


class VocabularyWordOut(BaseModel):
    """단어장 단어 한 건 (읽기 전용). 확장 필드 중 발음기호(phonetic)와 품사(pos)는 v2.2 부터 내려간다."""

    word_id: int
    term: str
    meaning: str
    example: str | None
    example_meaning: str | None
    phonetic: str | None = Field(default=None, description="미국식 IPA (슬래시 없음). 화면이 /…/ 를 입힌다. 없으면 null")
    pos: str | None = Field(default=None, description="품사(영문 소문자, 예: noun). 화면이 한글 라벨을 입힌다. 없으면 null")
    bookmarked: bool


class VocabularyWordPage(BaseModel):
    vocabulary_id: int
    items: list[VocabularyWordOut]
    total: int
    page: int
    size: int


class ActiveVocabularyIn(BaseModel):
    vocabulary_id: int = Field(gt=0, description="학습할 표준 단어장 ID")
