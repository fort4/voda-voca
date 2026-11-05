# 2026-11-05 - voda-voca - 세션 출제 순수 함수: 오답 30% 상한, 복습 10% 선확보, 미학습 충원, 풀 부족 시 전수 반환
# 파일 위치: src/backend/services/session_picker.py
"""DB 와 무관한 순수 로직이다. 서비스가 단어 후보를 읽어 split_pools 로 나누고, select_session_words 로 고른다.

배분 규칙 (문항 수 N):
  W  = min(오답 풀, floor(0.3 N))               오답 복습 (상한 30%)
  R0 = min(복습 풀, floor(0.1 N))               복습 10% 선확보
  U  = min(미학습 풀, N - (W + R0))             미학습 충원
  R  = min(복습 풀, N - W - U)                  미학습이 모자라면 복습이 잔여를 채움 (R >= R0)
  마지막으로 슬롯이 남으면 상한에 걸려 못 쓴 오답이 채운다 (풀 전체가 N 이상이면 항상 N개).
풀 전체가 N 미만이면 전부 돌려준다. 정수 연산을 써서 부동소수점 오차가 없다.
"""

import random
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime

from backend.services.progress import WRONG, ProgressState

WRONG_RATIO_PERCENT = 30
REVIEW_RATIO_PERCENT = 10


def wrong_cap(n: int) -> int:
    """오답 복습 상한 floor(0.3 N)."""
    return (n * WRONG_RATIO_PERCENT) // 100


def review_reserve(n: int) -> int:
    """복습 선확보 floor(0.1 N)."""
    return (n * REVIEW_RATIO_PERCENT) // 100


@dataclass(frozen=True)
class PickResult:
    ids: list[int]  # 섞인 출제 순서
    wrong_count: int
    unseen_count: int
    review_count: int


def _unique(ids: Iterable[int]) -> list[int]:
    """순서를 지키며 중복을 없앤다."""
    return list(dict.fromkeys(ids))


def select_session_words(
    wrong_ids: Sequence[int],
    unseen_ids: Sequence[int],
    review_ids: Sequence[int],
    n: int,
    rng: random.Random | None = None,
) -> PickResult:
    """풀 세 개에서 최대 n개를 고른다.

    - wrong_ids: 우선순위 순서 (앞이 먼저 뽑힌다). unseen_ids: 출제 순서. review_ids: 순서 무관 (무작위로 뽑는다).
    - 같은 id 가 여러 풀에 있으면 오답 > 미학습 > 복습 순으로 한 곳에만 센다.
    - 입력 시퀀스는 바꾸지 않는다. rng 를 주면 결과가 결정적이다.
    """
    if n < 1:
        raise ValueError("n 은 1 이상이어야 합니다")
    rng = rng or random.Random()

    wrong = _unique(wrong_ids)
    wrong_set = set(wrong)
    unseen = [i for i in _unique(unseen_ids) if i not in wrong_set]
    taken = wrong_set | set(unseen)
    review = [i for i in _unique(review_ids) if i not in taken]

    wrong_take = min(len(wrong), wrong_cap(n))
    reserved_review = min(len(review), review_reserve(n))
    unseen_take = min(len(unseen), n - (wrong_take + reserved_review))
    review_take = min(len(review), n - wrong_take - unseen_take)

    picked_wrong = wrong[:wrong_take]
    picked_unseen = unseen[:unseen_take]
    picked_review = rng.sample(review, review_take) if review_take else []

    leftover = n - (len(picked_wrong) + len(picked_unseen) + len(picked_review))
    if leftover > 0:
        extra = wrong[wrong_take : wrong_take + leftover]
        picked_wrong = picked_wrong + extra

    ids = picked_wrong + picked_unseen + picked_review
    rng.shuffle(ids)
    return PickResult(
        ids=ids,
        wrong_count=len(picked_wrong),
        unseen_count=len(picked_unseen),
        review_count=len(picked_review),
    )


@dataclass(frozen=True)
class WordCandidate:
    """활성 단어장의 단어 하나. progress 가 None 이면 한 번도 학습하지 않은 단어다."""

    word_id: int
    order_index: int
    progress: ProgressState | None


@dataclass
class Pools:
    wrong: list[int] = field(default_factory=list)
    unseen: list[int] = field(default_factory=list)
    review: list[int] = field(default_factory=list)


def split_pools(candidates: Iterable[WordCandidate], include_memorized: bool = False) -> Pools:
    """후보를 오답/미학습/복습 풀로 나눈다. 기본은 숙련 단어를 모두 제외한다 (#15).

    오답은 최근에 틀린 것이 먼저, 미학습은 order_index 순이다.
    """
    wrong: list[tuple[WordCandidate, ProgressState]] = []
    unseen: list[WordCandidate] = []
    review: list[WordCandidate] = []
    for candidate in candidates:
        progress = candidate.progress
        if progress is None:
            unseen.append(candidate)
            continue
        if progress.is_memorized and not include_memorized:
            continue
        if progress.last_result == WRONG:
            wrong.append((candidate, progress))
        else:
            review.append(candidate)

    def _recency_key(item: tuple[WordCandidate, ProgressState]) -> tuple[int, float, int]:
        candidate, progress = item
        stamp: datetime | None = progress.last_studied_at
        # 시각이 없는 오답은 뒤로, 있으면 최근 순 (시각 큰 것이 앞)
        return (stamp is None, -stamp.timestamp() if stamp else 0.0, candidate.word_id)

    wrong.sort(key=_recency_key)
    unseen.sort(key=lambda c: (c.order_index, c.word_id))
    return Pools(
        wrong=[c.word_id for c, _ in wrong],
        unseen=[c.word_id for c in unseen],
        review=[c.word_id for c in review],
    )
