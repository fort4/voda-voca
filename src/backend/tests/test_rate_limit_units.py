# 2026-11-02 - voda-voca - 로그인 레이트 리미터 단위 테스트: 윈도우 경계, 키 독립성, 리셋 (가짜 시계, DB 없음, REQ-121)
# 파일 위치: src/backend/tests/test_rate_limit_units.py

from backend.core.rate_limit import LoginRateLimiter


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def make_limiter(clock: FakeClock) -> LoginRateLimiter:
    return LoginRateLimiter(window_seconds=60, max_failures=5, clock=clock)


def test_allows_until_the_limit_is_reached() -> None:
    clock = FakeClock()
    limiter = make_limiter(clock)
    for _ in range(4):
        limiter.record_failure(["ip:a"])
    assert limiter.retry_after(["ip:a"]) is None  # 4회까지는 허용


def test_fifth_failure_blocks_the_key() -> None:
    clock = FakeClock()
    limiter = make_limiter(clock)
    for _ in range(5):
        limiter.record_failure(["ip:a"])
    assert limiter.retry_after(["ip:a"]) == 60


def test_retry_after_counts_down_from_the_oldest_failure() -> None:
    clock = FakeClock()
    limiter = make_limiter(clock)
    limiter.record_failure(["k"])  # t=1000
    clock.now += 20
    for _ in range(4):
        limiter.record_failure(["k"])  # t=1020
    clock.now += 10  # t=1030: 가장 오래된 실패(t=1000) 기준 30초 남음
    assert limiter.retry_after(["k"]) == 30


def test_block_lifts_after_the_window_passes() -> None:
    clock = FakeClock()
    limiter = make_limiter(clock)
    for _ in range(5):
        limiter.record_failure(["k"])
    clock.now += 59  # 59초: 아직 차단
    assert limiter.retry_after(["k"]) is not None
    clock.now += 1  # 정확히 60초: 풀림
    assert limiter.retry_after(["k"]) is None


def test_old_failures_slide_out_of_the_window_one_by_one() -> None:
    clock = FakeClock()
    limiter = make_limiter(clock)
    for _ in range(4):
        limiter.record_failure(["k"])  # t=1000
    clock.now += 30
    limiter.record_failure(["k"])  # t=1030, 이제 5건
    assert limiter.retry_after(["k"]) is not None
    clock.now += 30  # t=1060: t=1000 기록 4건이 빠져 1건만 남는다
    assert limiter.retry_after(["k"]) is None
    limiter.record_failure(["k"])  # 2건
    assert limiter.retry_after(["k"]) is None


def test_keys_are_independent() -> None:
    clock = FakeClock()
    limiter = make_limiter(clock)
    for _ in range(5):
        limiter.record_failure(["ip:a"])
    assert limiter.retry_after(["ip:a"]) is not None
    assert limiter.retry_after(["ip:b"]) is None


def test_any_blocked_key_blocks_the_request() -> None:
    """IP 또는 계정 중 하나라도 한도에 도달하면 차단한다."""
    clock = FakeClock()
    limiter = make_limiter(clock)
    for _ in range(5):
        limiter.record_failure(["acct:x"])
    assert limiter.retry_after(["ip:fresh", "acct:x"]) is not None
    assert limiter.retry_after(["ip:fresh", "acct:other"]) is None


def test_reset_clears_only_the_given_key() -> None:
    clock = FakeClock()
    limiter = make_limiter(clock)
    for _ in range(5):
        limiter.record_failure(["acct:x"])
        limiter.record_failure(["ip:a"])
    limiter.reset("acct:x")
    assert limiter.retry_after(["acct:x"]) is None
    assert limiter.retry_after(["ip:a"]) is not None


def test_clear_removes_everything() -> None:
    clock = FakeClock()
    limiter = make_limiter(clock)
    for _ in range(5):
        limiter.record_failure(["k"])
    limiter.clear()
    assert limiter.retry_after(["k"]) is None


def test_reset_on_unknown_key_is_a_no_op() -> None:
    limiter = make_limiter(FakeClock())
    limiter.reset("never-seen")  # 예외 없이 지나가야 한다
    assert limiter.retry_after(["never-seen"]) is None


def test_failure_after_full_expiry_starts_a_fresh_count() -> None:
    """키가 윈도우 밖으로 완전히 빠졌다가 다시 실패하면 1건부터 센다."""
    clock = FakeClock()
    limiter = make_limiter(clock)
    for _ in range(5):
        limiter.record_failure(["k"])
    clock.now += 61
    limiter.record_failure(["k"])
    assert limiter.retry_after(["k"]) is None
