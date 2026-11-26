# 2026-11-05 - voda-voca - 학습 지표 API 스키마: 통계, 오답 단어 목록, 학습 이력 (REQ-016). 세션 러너 스키마는 learning_session.py
# 파일 위치: src/backend/schemas/study.py

from datetime import date as DateType
from datetime import datetime

from pydantic import BaseModel, Field, field_serializer

from backend.schemas.common import to_utc_iso

QUIZ_CHOICE_COUNT = 4
STUDY_LOG_LIMIT = 100
FREQUENT_WRONG_DEFAULT = 10  # 자주 틀리는 단어 기본 개수 (VOCA-FR-033)
FREQUENT_WRONG_MAX = 50
TREND_SESSIONS_DEFAULT = 20  # 성적 추이: 최근 시험 회차 수 (VOCA-FR-032)
TREND_SESSIONS_MAX = 100
TREND_DAYS_DEFAULT = 30  # 성적 추이: 날짜별 정답률을 거슬러 볼 일수
TREND_DAYS_MAX = 90


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


class DayProgressOut(BaseModel):
    """학습 중인 단어장의 일차 진도 (REQ-165)."""

    vocabulary_id: int
    day: int = Field(description="지금 일차. 학습량을 채우고 날짜가 바뀌면 다음 일차다")
    words: int = Field(description="이 일차에 학습한 서로 다른 단어 수")


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
    due_review_count: int = Field(default=0, description="오늘 복습할 단어 수 (SRS 복습 예정 시각이 지금 이전인 단어)")
    day_progress: DayProgressOut | None = Field(default=None, description="학습 중인 단어장의 일차 진도. 고른 단어장이 없으면 null")


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
    pos: str | None = None
    phonetic: str | None = None
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


# --- 자주 틀리는 단어 상위 N (VOCA-FR-033) ---


class FrequentWrongOut(BaseModel):
    """오답 횟수가 많은 단어 한 건. 횟수는 study_logs 의 오답 행 수라 한 번 맞혀도 줄지 않는다."""

    word_id: int
    vocabulary_id: int
    vocabulary_title: str
    term: str
    meaning: str
    wrong_count: int = Field(description="누적 오답 횟수 (1 이상)")
    answered_count: int = Field(description="그 단어를 푼 누적 횟수 (정답 포함)")
    last_wrong_at: datetime = Field(description="가장 최근에 틀린 시각 (UTC)")

    @field_serializer("last_wrong_at")
    def _serialize_utc(self, value: datetime) -> str:
        return to_utc_iso(value)


class FrequentWrongList(BaseModel):
    items: list[FrequentWrongOut]


# --- 시험 성적 추이 (VOCA-FR-032) ---


class SessionScoreOut(BaseModel):
    """끝까지 푼 퀴즈 1회의 성적."""

    round: int = Field(description="회차. 푼 순서대로 1부터, 최근 N회만 보여 줘도 전체 기준 번호를 유지한다")
    session_id: int
    taken_at: datetime = Field(description="출제 시각 (UTC)")
    total: int
    correct: int
    accuracy: float = Field(description="정답률 (0~100, 소수 첫째 자리)")

    @field_serializer("taken_at")
    def _serialize_utc(self, value: datetime) -> str:
        return to_utc_iso(value)


class DailyScoreOut(BaseModel):
    """한국 날짜별 퀴즈 정답률. 플래시카드는 시험이 아니므로 뺀다."""

    date: DateType
    answered: int
    correct: int
    accuracy: float = Field(description="정답률 (0~100, 소수 첫째 자리)")


class ScoreTrendOut(BaseModel):
    sessions: list[SessionScoreOut] = Field(description="회차별, 오래된 회차부터")
    daily: list[DailyScoreOut] = Field(description="날짜별, 오래된 날부터. 기록이 있는 날만")
