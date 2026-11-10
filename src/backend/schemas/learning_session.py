# 2026-11-05 - voda-voca - 학습 세션 API 스키마: 세션 생성(퀴즈/플래시카드), 문항별 답 기록
# 파일 위치: src/backend/schemas/learning_session.py

from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, Field, field_serializer, model_validator

from backend.schemas.common import to_utc_iso

SESSION_COUNT_DEFAULT = 15
SESSION_COUNT_MAX = 30
CHOICE_MAX_INDEX = 3  # 4지선다의 마지막 선지 번호


class SessionCreate(BaseModel):
    mode: Literal["quiz", "flashcard"] = Field(default="quiz", description="quiz: 4지선다, flashcard: 알아요/헷갈려요")
    count: int = Field(default=SESSION_COUNT_DEFAULT, ge=1, le=SESSION_COUNT_MAX, description="요청 문항 수. 단어가 적으면 줄어든다")
    include_memorized: bool = Field(default=False, description="true 면 숙련한 단어도 출제 대상에 넣는다 (source 가 all 일 때만 적용)")
    source: Literal["all", "bookmarks", "wrong"] = Field(
        default="all",
        description="all: 활성 단어장 워터폴 출제, bookmarks: 내 북마크 복습, wrong: 단어별 마지막 결과가 오답인 단어 복습",
    )


class SessionItemOut(BaseModel):
    """출제된 문항. 퀴즈 문항에는 정답과 뜻, 발음기호를 싣지 않는다 (답 기록 응답에서 공개). 플래시카드는 뒷면(뜻)과 앞면 발음기호를 함께 준다. 품사는 둘 다 싣는다."""

    question_id: int
    word_id: int
    term: str
    context: str | None = Field(description="문맥으로 보여 줄 예문. 없는 단어는 null")
    options: list[str] | None = Field(default=None, description="퀴즈의 4지선다 뜻. 플래시카드는 null")
    meaning: str | None = Field(default=None, description="플래시카드 뒷면의 뜻. 퀴즈는 null")
    example_meaning: str | None = Field(default=None, description="플래시카드 뒷면의 예문 뜻. 퀴즈는 null")
    phonetic: str | None = Field(default=None, description="플래시카드 앞면의 발음기호(IPA). 퀴즈는 항상 null (채점 응답에서 공개)")
    pos: str | None = Field(default=None, description="품사(영문 소문자, 예: noun). 퀴즈·플래시카드 모두 싣는다. 없는 단어나 옛 세션은 null")


class CompositionOut(BaseModel):
    wrong: int
    review: int
    unseen: int


class SessionOut(BaseModel):
    session_id: int
    mode: str
    vocabulary_id: int | None = Field(description="활성 단어장 세션만 값이 있다. 북마크·오답 복습은 null")
    vocabulary_title: str
    total_questions: int
    expires_at: datetime = Field(description="이 시각 이후에는 새 답을 기록할 수 없다 (UTC). 답을 기록할 때마다 30분씩 밀린다")
    composition: CompositionOut
    items: list[SessionItemOut]

    @field_serializer("expires_at")
    def _serialize_utc(self, value: datetime) -> str:
        return to_utc_iso(value)


class SessionAnswerIn(BaseModel):
    """퀴즈 세션은 choice_index, 플래시카드 세션은 known 으로 답한다. 둘 중 정확히 하나만 보낸다."""

    question_id: int = Field(ge=0)
    choice_index: int | None = Field(default=None, ge=0, le=CHOICE_MAX_INDEX)
    known: bool | None = Field(default=None, description="플래시카드: true=알아요, false=헷갈려요")

    @model_validator(mode="after")
    def _exactly_one_answer(self) -> Self:
        if (self.choice_index is None) == (self.known is None):
            raise ValueError("choice_index 와 known 중 하나만 보내야 합니다.")
        return self


class ProgressOut(BaseModel):
    correct_count: int
    wrong_count: int
    consecutive_correct_count: int
    is_memorized: bool


class SessionAnswerOut(BaseModel):
    """답 1건의 채점 결과와 해설, 갱신된 단어 진행도. 같은 답을 다시 보내면 같은 응답을 돌려준다 (멱등)."""

    question_id: int
    is_correct: bool
    correct_index: int | None = Field(description="퀴즈의 정답 선지 번호. 플래시카드는 null")
    selected_index: int | None
    known: bool | None = Field(description="플래시카드의 응답. 퀴즈는 null")
    term: str
    meaning: str
    example: str | None
    example_meaning: str | None
    phonetic: str | None = Field(default=None, description="발음기호(IPA, 슬래시 없음). 없는 단어나 옛 세션은 null")
    pos: str | None = Field(default=None, description="품사(영문 소문자). 없는 단어나 옛 세션은 null")
    progress: ProgressOut
    answered: int = Field(description="지금까지 답한 문항 수")
    total: int
    is_finished: bool = Field(description="모든 문항에 답해 세션이 끝났는지")
    expires_at: datetime

    @field_serializer("expires_at")
    def _serialize_utc(self, value: datetime) -> str:
        return to_utc_iso(value)
