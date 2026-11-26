# 2026-11-05 - voda-voca - 세션 출제 순수 함수: 오답 30% 상한, 복습 10% 선확보, 미학습 충원, 풀 부족 시 전수 반환, 퀴즈 가중 무작위
# 파일 위치: src/backend/services/session_picker.py
"""DB 와 무관한 순수 로직이다. 서비스가 단어 후보를 읽어 split_pools 로 나누고, select_session_words 로 고른다.

배분 규칙 (문항 수 N):
  W  = min(오답 풀, floor(0.3 N))               오답 복습 (상한 30%)
  R0 = min(복습 풀, floor(0.1 N))               복습 10% 선확보
  U  = min(미학습 풀, N - (W + R0))             미학습 충원
  R  = min(복습 풀, N - W - U)                  미학습이 모자라면 복습이 잔여를 채움 (R >= R0)
  마지막으로 슬롯이 남으면 상한에 걸려 못 쓴 오답이 채운다 (풀 전체가 N 이상이면 항상 N개).
풀 전체가 N 미만이면 전부 돌려준다. 배분 계산은 정수 연산을 써서 부동소수점 오차가 없다.

각 풀에서 어느 단어를 뽑는지는 weights 로 갈린다 (REQ-168).
  없음(플래시카드): 풀의 앞에서부터 (오답은 최근 순, 미학습은 order_index 순, 복습은 기한 지난 것부터이고 나머지는 균등 무작위)
  있음(퀴즈): 풀 안을 가중 무작위 순서로 바꾼 뒤 앞에서부터. 복습 풀의 "기한 지난 것 먼저"(REQ-150)는 유지한다.
"""

import math
import random
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime

from backend.services.progress import WRONG, ProgressState

WRONG_RATIO_PERCENT = 30
REVIEW_RATIO_PERCENT = 10

# 가중치 = (1 + 오답 횟수) x (10 + 안 본 일수). 상한을 두어 한 단어가 계속 나오지 않게 한다 (10~240).
WEIGHT_WRONG_CAP = 5
WEIGHT_AGE_BASE = 10
WEIGHT_AGE_CAP_DAYS = 30
UNSEEN_WEIGHT = 1  # 미학습끼리는 모두 같으면 되고, 다른 풀의 가중치와는 섞이지 않는다


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


def study_weight(progress: ProgressState | None, now: datetime) -> int:
    """퀴즈에서 이 단어가 뽑힐 상대 가중치. 많이 틀렸고 오래 안 볼수록 크다.

    학습 시각이 없는 옛 기록은 가장 오래된 것으로 본다. 일수는 24시간 단위이며 음수는 0 이다.
    """
    if progress is None:
        return UNSEEN_WEIGHT
    if progress.last_studied_at is None:
        days = WEIGHT_AGE_CAP_DAYS
    else:
        days = min(max((now - progress.last_studied_at).days, 0), WEIGHT_AGE_CAP_DAYS)
    return (1 + min(progress.wrong_count, WEIGHT_WRONG_CAP)) * (WEIGHT_AGE_BASE + days)


def weighted_order(ids: Sequence[int], weights: Mapping[int, int], rng: random.Random) -> list[int]:
    """가중 비복원 추출 순서. 앞에서부터 k개를 자르면 가중치에 비례해 중복 없이 k개를 뽑은 것과 같다.

    Efraimidis-Spirakis: log(u) / w 가 큰 순. u 는 (0, 1] 이라 log 가 항상 정의된다. weights 에 없는 id 는 1 이다.
    """
    keys = {i: math.log(1.0 - rng.random()) / weights.get(i, 1) for i in ids}
    return sorted(ids, key=keys.__getitem__, reverse=True)


def select_session_words(
    wrong_ids: Sequence[int],
    unseen_ids: Sequence[int],
    review_ids: Sequence[int],
    n: int,
    rng: random.Random | None = None,
    due_review_ids: Sequence[int] = (),
    weights: Mapping[int, int] | None = None,
) -> PickResult:
    """풀 세 개에서 최대 n개를 고른다.

    - wrong_ids: 우선순위 순서 (앞이 먼저 뽑힌다). unseen_ids: 출제 순서. review_ids: 순서 무관 (무작위로 뽑는다).
    - 같은 id 가 여러 풀에 있으면 오답 > 미학습 > 복습 순으로 한 곳에만 센다.
    - due_review_ids: 복습 풀 중 SRS 복습 기한이 지난 단어 (앞이 더 오래 밀린 것). 복습 슬롯에서 먼저 뽑고 나머지만 무작위로 채운다 (#25).
    - weights: 주면(퀴즈) 각 풀 안의 우선순위 대신 가중 무작위 순서를 쓴다. 풀별 문항 수와 "기한 지난 복습 먼저"는 같다 (REQ-168).
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
    review_set = set(review)
    due = [i for i in _unique(due_review_ids) if i in review_set]
    if weights is not None:
        wrong = weighted_order(wrong, weights, rng)
        unseen = weighted_order(unseen, weights, rng)
        due = weighted_order(due, weights, rng)

    wrong_take = min(len(wrong), wrong_cap(n))
    reserved_review = min(len(review), review_reserve(n))
    unseen_take = min(len(unseen), n - (wrong_take + reserved_review))
    review_take = min(len(review), n - wrong_take - unseen_take)

    picked_wrong = wrong[:wrong_take]
    picked_unseen = unseen[:unseen_take]
    picked_due = due[:review_take]
    rest = [i for i in review if i not in set(picked_due)]
    fill = review_take - len(picked_due)
    if fill <= 0:
        picked_fill: list[int] = []
    elif weights is None:
        picked_fill = rng.sample(rest, fill)
    else:
        picked_fill = weighted_order(rest, weights, rng)[:fill]
    picked_review = picked_due + picked_fill

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
    due: list[int] = field(default_factory=list)  # review 중 SRS 복습 기한이 지난 단어 (now 를 줬을 때만 채워진다)


def candidate_weights(candidates: Iterable[WordCandidate], now: datetime) -> dict[int, int]:
    """후보마다 study_weight 를 매긴다."""
    return {c.word_id: study_weight(c.progress, now) for c in candidates}


def split_pools(
    candidates: Iterable[WordCandidate], include_memorized: bool = False, now: datetime | None = None
) -> Pools:
    """후보를 오답/미학습/복습 풀로 나눈다. 기본은 숙련 단어를 모두 제외한다 (#15).

    오답은 최근에 틀린 것이 먼저, 미학습은 order_index 순이다.
    now 를 주면 SRS(#25)를 적용한다: 복습 기한이 지난(또는 기한 미정인 미숙련) 단어는 숙련 여부와 무관하게 복습 풀에 들어가
    가장 오래 밀린 순으로 앞에 서고(Pools.due), 기한 전 단어는 그 뒤에 기한이 가까운 순으로 이어진다.
    now 가 없으면 이전 동작 그대로다.
    """
    wrong: list[tuple[WordCandidate, ProgressState]] = []
    unseen: list[WordCandidate] = []
    review: list[WordCandidate] = []
    due_review: list[WordCandidate] = []
    for candidate in candidates:
        progress = candidate.progress
        if progress is None:
            unseen.append(candidate)
            continue
        if now is None:
            is_due = False
        elif progress.next_review_at is None:
            is_due = not progress.is_memorized  # 기한 미정인 숙련 단어는 되살리지 않는다 (옛 데이터 보호)
        else:
            is_due = progress.next_review_at <= now
        if progress.is_memorized and not include_memorized and not is_due:
            continue
        if progress.last_result == WRONG:
            wrong.append((candidate, progress))
        elif is_due:
            due_review.append(candidate)
        else:
            review.append(candidate)

    def _recency_key(item: tuple[WordCandidate, ProgressState]) -> tuple[int, float, int]:
        candidate, progress = item
        stamp: datetime | None = progress.last_studied_at
        # 시각이 없는 오답은 뒤로, 있으면 최근 순 (시각 큰 것이 앞)
        return (stamp is None, -stamp.timestamp() if stamp else 0.0, candidate.word_id)

    wrong.sort(key=_recency_key)
    unseen.sort(key=lambda c: (c.order_index, c.word_id))
    if now is not None:
        oldest = datetime.min

        def due_key(c: WordCandidate) -> tuple[datetime, int]:
            return (c.progress.next_review_at or oldest, c.word_id)  # type: ignore[union-attr]

        due_review.sort(key=due_key)
        review.sort(key=due_key)
    return Pools(
        wrong=[c.word_id for c, _ in wrong],
        unseen=[c.word_id for c in unseen],
        review=[c.word_id for c in due_review + review],
        due=[c.word_id for c in due_review],
    )
