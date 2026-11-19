# 2026-11-19 - voda-voca - SRS(간격 반복) 순수 함수: 정답/오답에 따른 복습 단계와 다음 복습 시각(한국 날짜 0시) 계산 (이슈 #25, REQ-150)
# 파일 위치: src/backend/services/srs.py
"""DB 와 무관한 순수 로직이다. 에빙하우스 망각곡선을 단순화한 단계표를 쓴다.

정답이면 한 단계 올라 더 먼 시점에 복습하고, 오답이면 WRONG_STEP_PENALTY 단계 내려간다 (완전 리셋이 아닌 부분 감쇠:
이미 오래 기억한 단어를 한 번 틀렸다고 처음부터 다시 외우게 하지 않기 위함이다).
"""

from datetime import datetime, time, timedelta

KST_OFFSET = timedelta(hours=9)  # 학습일 경계는 한국 시각 자정이다 (DB 에는 UTC 로 저장)
INTERVAL_DAYS = (0, 1, 3, 7, 14, 30)  # 단계별 다음 복습까지의 간격(일)
MAX_STEP = len(INTERVAL_DAYS) - 1
WRONG_STEP_PENALTY = 2


def kst_day_start(now: datetime) -> datetime:
    """UTC 로 주어진 시각이 속한 한국 날짜의 0시를 UTC 로 돌려준다 (예: 한국 11-11 23:00 → UTC 11-10 15:00)."""
    return datetime.combine((now + KST_OFFSET).date(), time.min) - KST_OFFSET


def schedule_next(
    step: int, is_correct: bool, now: datetime, current_due: datetime | None = None
) -> tuple[int, datetime]:
    """답 하나를 반영한 (새 단계, 다음 복습 시각)을 돌려준다.

    - 다음 복습 시각은 답한 시각 + 간격이 아니라 **간격일 뒤 한국 날짜의 0시**다. 그래야 그 날 하루 종일 "오늘 복습"에 뜬다
      (밤 11시에 맞힌 단어가 다음 날 오전에 열었을 때 아직 기한 전이 되는 일을 막는다). 단계 0(오답)은 오늘 0시라 즉시 대상이다.
    - 기한(current_due)이 되기 전에 맞힌 정답은 단계와 복습 시각을 그대로 둔다. 같은 날 여러 번 풀어 단계가 부풀지 않게 하기 위함이다.
      오답은 기한과 상관없이 단계를 내린다. current_due 가 없으면(처음 푸는 단어, 옛 데이터) 기한 전이 아니다.
    """
    if not 0 <= step <= MAX_STEP:
        raise ValueError(f"step 은 0~{MAX_STEP} 이어야 합니다: {step}")
    if is_correct and current_due is not None and now < current_due:
        return step, current_due
    new_step = min(step + 1, MAX_STEP) if is_correct else max(step - WRONG_STEP_PENALTY, 0)
    return new_step, kst_day_start(now) + timedelta(days=INTERVAL_DAYS[new_step])
