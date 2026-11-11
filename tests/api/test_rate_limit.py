import pytest
from starlette.requests import Request

from app.api import rate_limit
from app.api.errors import ApiFailure
from app.api.rate_limit import RateLimit


def _request(host: str) -> Request:
    return Request({"type": "http", "client": (host, 1), "headers": []})


def test_each_address_has_its_own_bucket() -> None:
    limit = RateLimit(rate=1, burst=1, clock=lambda: 0.0)
    limit.check(_request("a"))
    limit.check(_request("b"))
    try:
        limit.check(_request("a"))
    except ApiFailure as failure:
        assert failure.status == 429
        assert failure.headers == {"Retry-After": "1"}
    else:
        raise AssertionError("second request from a should be limited")


def test_full_buckets_are_forgotten_past_the_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rate_limit, "MAX_CLIENTS", 2)
    now = [0.0]
    limit = RateLimit(rate=1, burst=1, clock=lambda: now[0])
    for host in ("a", "b"):
        limit.check(_request(host))
    now[0] = 5.0  # a and b are full again
    limit.check(_request("c"))
    assert set(limit._buckets) == {"c"}
