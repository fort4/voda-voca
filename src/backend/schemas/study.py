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
    example_meaning: str | None = None
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
    example_meaning: str | None = Field(default=None, description="해설 예문의 한글 뜻 (없으면 null)")


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
    """퀴즈 완료 본문. 답은 문항마다 /answers 로 이미 기록되므로 비어 있어도 된다.

    아직 기록되지 않은 답을 함께 보내면 이때 기록한다 (이전 방식의 일괄 제출과 호환). 이미 기록된 문항은 서버 값이 우선한다.
    """

    answers: list[QuizAnswer] = Field(default_factory=list)


class WrongItem(BaseModel):
    word_id: int
    term: str
    correct_meaning: str
    selected_meaning: str


class QuizResultOut(BaseModel):
    session_id: int
    total: int = Field(description="출제된 문항 수")
    answered: int = Field(description="답을 기록한 문항 수 (일부만 풀고 끝낼 수 있다)")
    correct_count: int
    accuracy: float = Field(description="푼 문항 기준 정답률 (0~100, 소수 첫째 자리까지). 푼 문항이 없으면 0")
    wrong_items: list[WrongItem]


# --- 문항별 즉시 기록, 세션 상세 (이슈 #8) ---


class QuizAnswerOut(BaseModel):
    """답 1건을 기록한 결과. 같은 답을 다시 보내면 같은 응답을 돌려준다 (멱등)."""

    question_id: int
    selected_index: int
    correct_index: int
    is_correct: bool
    expires_at: datetime = Field(description="이 시각 이후에는 새 답을 기록할 수 없다 (UTC). 답을 기록할 때마다 30분씩 밀린다")

    @field_serializer("expires_at")
    def _serialize_utc(self, value: datetime) -> str:
        return to_utc_iso(value)


class QuizItemOut(BaseModel):
    """결과 화면의 문항 1개. 아직 풀지 않았으면 selected_index, is_correct 는 null 이다."""

    question_id: int
    word_id: int
    term: str
    choices: list[str]
    correct_index: int
    selected_index: int | None
    is_correct: bool | None
    example: str | None = None
    example_meaning: str | None = None


class QuizSessionDetailOut(BaseModel):
    """세션 상세 = 문항 + 내가 고른 답 + 요약. 결과 화면을 새로고침·다른 탭에서도 다시 만들 수 있다."""

    session_id: int
    source: str
    wordbook_id: int | None
    is_submitted: bool
    expires_at: datetime
    total: int
    answered: int
    correct_count: int
    accuracy: float
    items: list[QuizItemOut]

    @field_serializer("expires_at")
    def _serialize_utc(self, value: datetime) -> str:
        return to_utc_iso(value)


# --- 학습 이력 (REQ-016) ---


class StudyLogOut(BaseModel):
    word_id: int
    wordbook_id: int = Field(description="단어가 속한 단어장 ID (진행률 계산용)")
    term: str
    is_correct: bool
    created_at: datetime

    @field_serializer("created_at")
    def _serialize_utc(self, value: datetime) -> str:
        return to_utc_iso(value)


class StudyLogList(BaseModel):
    items: list[StudyLogOut]
