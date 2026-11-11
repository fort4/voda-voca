# 2026-11-11 - voda-voca - SRS(간격 반복) 순수 함수: 정답/오답에 따른 복습 단계와 다음 복습 시각 계산 (이슈 #25)
# 파일 위치: src/backend/services/srs.py
"""DB 와 무관한 순수 로직이다. 에빙하우스 망각곡선을 단순화한 단계표를 쓴다.

정답이면 한 단계 올라 더 먼 시점에 복습하고, 오답이면 WRONG_STEP_PENALTY 단계 내려간다 (완전 리셋이 아닌 부분 감쇠:
이미 오래 기억한 단어를 한 번 틀렸다고 처음부터 다시 외우게 하지 않기 위함이다).
"""

from datetime import datetime, timedelta

INTERVAL_DAYS = (0, 1, 3, 7, 14, 30)  # 단계별 다음 복습까지의 간격(일)
MAX_STEP = len(INTERVAL_DAYS) - 1
WRONG_STEP_PENALTY = 2


def schedule_next(step: int, is_correct: bool, now: datetime) -> tuple[int, datetime]:
    """답 하나를 반영한 (새 단계, 다음 복습 시각)을 돌려준다."""
    if not 0 <= step <= MAX_STEP:
        raise ValueError(f"step 은 0~{MAX_STEP} 이어야 합니다: {step}")
    new_step = min(step + 1, MAX_STEP) if is_correct else max(step - WRONG_STEP_PENALTY, 0)
    return new_step, now + timedelta(days=INTERVAL_DAYS[new_step])
