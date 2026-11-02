# 2026-11-02 - voda-voca - 학습 API 요청/응답 스키마: 플래시카드, 퀴즈 출제·제출, 학습 이력 (REQ-012~016, REQ-019)
# 파일 위치: src/backend/schemas/study.py

from datetime import datetime
from typing import Self

from pydantic import BaseModel, Field, field_serializer, model_validator

from backend.schemas.common import to_utc_iso

QUIZ_CHOICE_COUNT = 4
QUIZ_COUNT_DEFAULT = 10
QUIZ_COUNT_MAX = 50
FLASHCARD_LIMIT_DEFAULT = 100
FLASHCARD_LIMIT_MAX = 500
STUDY_LOG_LIMIT = 100


# --- 플래시카드 (REQ-012, 013, 019) ---


class FlashcardOut(BaseModel):
    """카드 한 장. 앞면은 term, 뒷면은 meaning/example 이다 (앞·뒤 전환은 클라이언트가 한다)."""

    word_id: int
    wordbook_id: int
    term: str
    meaning: str
    example: str | None
    bookmarked: bool


class FlashcardPage(BaseModel):
    items: list[FlashcardOut]
    total: int = Field(description="조건에 맞는 전체 카드 수 (limit 과 무관)")


# --- 퀴즈 출제 (REQ-014, 019) ---


class QuizCreate(BaseModel):
    """출제 원천은 단어장, 북마크, 오답 복습 중 정확히 하나여야 한다."""

    wordbook_id: int | None = Field(default=None, description="출제할 단어장 ID (wordbook_id 가 있으면 단어장 퀴즈)")
    bookmarks: bool = Field(default=False, description="true 면 본인 북마크 단어로 출제")
    wrong_only: bool = Field(default=False, description="true 면 최근 학습 기록(100건)에서 틀린 단어로 출제 (오답 복습)")
    count: int = Field(
        default=QUIZ_COUNT_DEFAULT,
        ge=1,
        le=QUIZ_COUNT_MAX,
        description="요청 문항 수. 가용 단어가 적으면 가용 단어 수로 줄어든다.",
    )

    @model_validator(mode="after")
    def _exactly_one_source(self) -> Self:
        chosen = [self.wordbook_id is not None, self.bookmarks, self.wrong_only]
        if sum(chosen) != 1:
            raise ValueError("wordbook_id, bookmarks=true, wrong_only=true 중 하나만 지정해야 합니다.")
        return self


class QuizQuestionOut(BaseModel):
    """문항. 정답 인덱스와 해설용 예문을 포함한다 (즉각 피드백, 요구사항 2026-11-02).

    정답을 미리 알려 주므로 이 응답만으로 채점 결과를 숨길 수는 없다. 제출 API 는 기록을 남기는 역할을 계속 맡는다.
    """

    question_id: int
    term: str = Field(description="문제로 보여 줄 표제어")
    choices: list[str] = Field(min_length=QUIZ_CHOICE_COUNT, max_length=QUIZ_CHOICE_COUNT)
    correct_index: int = Field(ge=0, lt=QUIZ_CHOICE_COUNT, description="정답 선지 번호 (0~3)")
    example: str | None = Field(default=None, description="해설용 예문 (없으면 null)")


class QuizSessionOut(BaseModel):
    session_id: int
    expires_at: datetime = Field(description="이 시각 이후에는 제출할 수 없다 (UTC)")
    questions: list[QuizQuestionOut]

    @field_serializer("expires_at")
    def _serialize_utc(self, value: datetime) -> str:
        return to_utc_iso(value)


# --- 퀴즈 제출 (REQ-015, 016, 106) ---


class QuizAnswer(BaseModel):
    question_id: int = Field(ge=0)
    choice_index: int = Field(ge=0, lt=QUIZ_CHOICE_COUNT)


class QuizSubmit(BaseModel):
    answers: list[QuizAnswer] = Field(min_length=1)


class WrongItem(BaseModel):
    word_id: int
    term: str
    correct_meaning: str
    selected_meaning: str


class QuizResultOut(BaseModel):
    session_id: int
    total: int
    correct_count: int
    accuracy: float = Field(description="정답률 (0~100, 소수 첫째 자리까지)")
    wrong_items: list[WrongItem]


# --- 학습 이력 (REQ-016) ---


class StudyLogOut(BaseModel):
    word_id: int
    term: str
    is_correct: bool
    created_at: datetime

    @field_serializer("created_at")
    def _serialize_utc(self, value: datetime) -> str:
        return to_utc_iso(value)


class StudyLogList(BaseModel):
    items: list[StudyLogOut]
