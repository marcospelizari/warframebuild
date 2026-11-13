"""Per-IP token bucket for the CPU endpoints (PLAN Q23/S1): 429 + Retry-After when empty.

The client address is what uvicorn reports; behind a proxy it is the forwarded one only
with `--proxy-headers --forwarded-allow-ips=<trusted proxy>` (E6/E7).
"""

import ipaddress
import math
import time
from collections.abc import Callable

from fastapi import Request

from app.api.errors import ApiFailure

RATE = 2.0  # requests per second, sustained
BURST = 20  # requests at once
MAX_CLIENTS = 10_000  # remembered addresses; full buckets are forgotten first


def client_key(host: str) -> str:
    """IPv4: the address. IPv6: its /64, which one connection usually owns whole."""
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return host
    if address.version == 6:
        return str(ipaddress.ip_network(f"{address}/64", strict=False))
    return str(address)


class RateLimit:
    def __init__(
        self,
        rate: float = RATE,
        burst: int = BURST,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.rate, self.burst, self._clock = rate, burst, clock
        self._buckets: dict[str, tuple[float, float]] = {}  # address -> tokens, at

    def check(self, request: Request) -> None:
        address = client_key(request.client.host if request.client else "unknown")
        now = self._clock()
        tokens = self._tokens(address, now)
        if tokens < 1:
            wait = math.ceil((1 - tokens) / self.rate)
            raise ApiFailure(429, "rate_limited", "too many requests", retry_after=wait)
        self._buckets[address] = (tokens - 1, now)
        if len(self._buckets) > MAX_CLIENTS:
            self._forget_full(now)

    def _tokens(self, address: str, now: float) -> float:
        tokens, at = self._buckets.get(address, (float(self.burst), now))
        return min(float(self.burst), tokens + (now - at) * self.rate)

    def _forget_full(self, now: float) -> None:
        full = [a for a in self._buckets if self._tokens(a, now) >= self.burst]
        for a in full:
            del self._buckets[a]
