# 2026-11-05 - voda-voca - 학습 지표 API 스키마: 통계, 오답 단어 목록, 학습 이력 (REQ-016). 세션 러너 스키마는 learning_session.py
# 파일 위치: src/backend/schemas/study.py

from datetime import date as DateType
from datetime import datetime

from pydantic import BaseModel, Field, field_serializer

from backend.schemas.common import to_utc_iso

QUIZ_CHOICE_COUNT = 4
STUDY_LOG_LIMIT = 100


# --- 학습 통계 (이슈 #3) ---


class DayActivityOut(BaseModel):
    date: DateType = Field(description="한국 날짜")
    label: str = Field(description="요일 (월~일)")
    count: int = Field(description="그날 푼 단어 수. 같은 단어를 여러 번 풀어도 1")
    is_today: bool


class VocabularyProgressOut(BaseModel):
    vocabulary_id: int
    word_count: int
    learned_words: int = Field(description="한 번이라도 맞힌 단어 수")
    percent: int = Field(description="learned_words / word_count (0~100, 반올림)")


class StudyStatsOut(BaseModel):
    """학습 지표 전체. 모두 전체 이력 기준이며 최근 N건 제한이 없다."""

    answered: int = Field(description="누적 푼 문항 수")
    correct: int = Field(description="그중 정답 수")
    accuracy: float | None = Field(description="누적 정답률 (0~100, 소수 첫째 자리). 푼 문항이 없으면 null")
    streak_days: int = Field(description="연속 학습일 (한국 날짜). 오늘 아직 안 풀었으면 어제부터 센다")
    weekly: list[DayActivityOut] = Field(description="오늘을 포함한 최근 7일, 오래된 날부터")
    total_words: int = Field(description="모든 표준 단어장의 단어 수 합계")
    vocabulary_progress: list[VocabularyProgressOut]
    wrong_word_count: int = Field(description="오답 복습 대상 단어 수 (단어별 마지막 결과가 오답)")


# --- 학습 이력 (REQ-016) ---


class StudyLogOut(BaseModel):
    word_id: int
    vocabulary_id: int = Field(description="단어가 속한 표준 단어장 ID (진행률 계산용)")
    term: str
    is_correct: bool
    created_at: datetime

    @field_serializer("created_at")
    def _serialize_utc(self, value: datetime) -> str:
        return to_utc_iso(value)


class WrongWordOut(BaseModel):
    """오답 복습 대상 단어 한 건. 단어와 속한 표준 단어장 정보, 가장 최근에 틀린 시각을 담는다."""

    word_id: int
    vocabulary_id: int
    vocabulary_title: str
    term: str
    meaning: str
    example: str | None
    example_meaning: str | None
    bookmarked: bool
    wrong_at: datetime = Field(description="가장 최근에 틀린 시각 (UTC)")

    @field_serializer("wrong_at")
    def _serialize_utc(self, value: datetime) -> str:
        return to_utc_iso(value)


class WrongWordPage(BaseModel):
    items: list[WrongWordOut]
    total: int
    page: int
    size: int


class StudyLogList(BaseModel):
    items: list[StudyLogOut]
