from app.core.rate_limit import RateLimiter


def test_rate_limiter_expires_old_hits_and_returns_retry_after() -> None:
    limiter = RateLimiter(requests=2, window_s=10)
    assert limiter.allow("client", now=0) == (True, 0)
    assert limiter.allow("client", now=1) == (True, 0)
    allowed, retry_after = limiter.allow("client", now=2)
    assert not allowed
    assert retry_after == 8
    assert limiter.allow("client", now=10) == (True, 0)


def test_rate_limiters_are_isolated_by_client_identity() -> None:
    limiter = RateLimiter(requests=1, window_s=60)
    assert limiter.allow("one", now=5)[0]
    assert limiter.allow("two", now=5)[0]
