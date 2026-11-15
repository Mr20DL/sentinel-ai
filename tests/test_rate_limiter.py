import pytest

from src.adapters.rate_limiter import SlidingWindowRateLimiter


class _FakeClock:
    def __init__(self, now: float = 0.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


def test_limiter_allows_requests_up_to_limit():
    limiter = SlidingWindowRateLimiter(limit=2, clock=_FakeClock())

    assert limiter.allow("client-a") is True
    assert limiter.allow("client-a") is True
    assert limiter.allow("client-a") is False


def test_limiter_recovers_after_window():
    clock = _FakeClock()
    limiter = SlidingWindowRateLimiter(limit=1, window_seconds=60, clock=clock)

    assert limiter.allow("client-a") is True
    assert limiter.allow("client-a") is False

    clock.now = 61.0

    assert limiter.allow("client-a") is True


def test_limiter_isolates_keys():
    limiter = SlidingWindowRateLimiter(limit=1, clock=_FakeClock())

    assert limiter.allow("client-a") is True
    assert limiter.allow("client-b") is True
    assert limiter.allow("client-a") is False


@pytest.mark.parametrize(
    ("limit", "window_seconds"),
    [(0, 60), (-1, 60), (1, 0), (1, -1)],
    ids=["zero-limit", "negative-limit", "zero-window", "negative-window"],
)
def test_limiter_rejects_invalid_settings(limit: int, window_seconds: float):
    with pytest.raises(ValueError):
        SlidingWindowRateLimiter(limit=limit, window_seconds=window_seconds)
