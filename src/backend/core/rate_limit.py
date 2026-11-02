# 2026-11-02 - voda-voca - 로그인 무차별 대입 방어: IP·계정 기준 1분 5회 실패 시 차단, 인메모리 슬라이딩 윈도우 (REQ-121)
# 파일 위치: src/backend/core/rate_limit.py

import math
import time
from collections import deque
from collections.abc import Callable, Iterable

WINDOW_SECONDS = 60
MAX_FAILURES = 5


class LoginRateLimiter:
    """키(IP 또는 계정)별 로그인 실패 시각을 슬라이딩 윈도우로 집계한다.

    - 차단 판정은 로그인 시도 전에 한다. 차단 중이면 비밀번호와 무관하게 거부한다.
    - 차단된 요청은 실패로 집계하지 않는다. 그래서 차단은 마지막 실패로부터 window 초 뒤에 풀린다.
    - 외부 저장소를 쓰지 않으므로 프로세스 단위로 상태가 나뉜다. 워커를 여러 개 띄우면 한도가 워커마다 따로 적용된다.
    - clock 은 테스트에서 시간을 조작하기 위해 주입한다.
    """

    def __init__(
        self,
        window_seconds: float = WINDOW_SECONDS,
        max_failures: int = MAX_FAILURES,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._window = window_seconds
        self._max = max_failures
        self._clock = clock
        self._failures: dict[str, deque[float]] = {}

    def _recent(self, key: str, now: float) -> deque[float]:
        """윈도우 밖의 실패 기록을 버리고 남은 기록을 돌려준다. 기록이 없으면 키도 지운다."""
        recent = self._failures.get(key)
        if recent is None:
            return deque()
        while recent and now - recent[0] >= self._window:
            recent.popleft()
        if not recent:
            del self._failures[key]
        return recent

    def retry_after(self, keys: Iterable[str]) -> int | None:
        """키 중 하나라도 한도에 도달했으면 풀릴 때까지 남은 초(올림, 1 이상)를 준다. 허용이면 None."""
        now = self._clock()
        waits = []
        for key in keys:
            recent = self._recent(key, now)
            if len(recent) >= self._max:
                waits.append(recent[0] + self._window - now)
        if not waits:
            return None
        return max(1, math.ceil(max(waits)))

    def record_failure(self, keys: Iterable[str]) -> None:
        now = self._clock()
        for key in keys:
            self._recent(key, now)  # 오래된 기록을 먼저 버린다
            self._failures.setdefault(key, deque()).append(now)

    def reset(self, key: str) -> None:
        """성공한 로그인의 계정 키 실패 기록을 지운다."""
        self._failures.pop(key, None)

    def clear(self) -> None:
        """모든 집계를 지운다. 테스트 격리용."""
        self._failures.clear()


login_rate_limiter = LoginRateLimiter()
