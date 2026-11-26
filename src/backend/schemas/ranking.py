# 2026-11-26 - voda-voca - 학습 순위 스키마: 순위 항목, 본인 지표, 공개 설정 (REQ-172, REQ-173)
# 파일 위치: src/backend/schemas/ranking.py

from typing import Literal

from pydantic import BaseModel, ConfigDict, StrictBool

RankingMetric = Literal["learned_words", "week_words", "week_days"]


class RankingMetricsOut(BaseModel):
    learned_words: int
    week_words: int
    week_days: int


class RankingEntryOut(RankingMetricsOut):
    """남에게 보이는 항목의 전부다. 사용자 ID, 단어장, 단어, 정답률은 싣지 않는다 (REQ-172 ⑤)."""

    rank: int
    nickname: str
    is_me: bool


class RankingMeOut(RankingMetricsOut):
    """본인 지표. 비공개면 순위가 없다."""

    public: bool
    rank: int | None


class RankingOut(BaseModel):
    metric: RankingMetric
    items: list[RankingEntryOut]
    total_public: int
    me: RankingMeOut


class RankingVisibility(BaseModel):
    """공개 설정의 입력과 응답. StrictBool: 1 이나 "true" 가 조용히 공개로 바뀌지 않게 한다."""

    model_config = ConfigDict(extra="forbid")

    public: StrictBool
