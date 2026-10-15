from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

KITE_429_HOLD_S = 10.0
_EPS = 1e-9
_MIN_WAIT_S = 0.001

LIMITS: dict[str, tuple[int, float]] = {
    "quote": (1, 1.0),
    "historical": (3, 3.0),
    "general": (10, 10.0),
}


def kind_for(path: str) -> str:
    p = path.lstrip("/")
    if p.startswith("quote"):
        return "quote"
    if p.startswith("instruments/historical"):
        return "historical"
    return "general"


@dataclass
class _Bucket:
    capacity: int
    refill_per_s: float
    tokens: float
    last: float


class RateLimiter:
    """Token buckets per Kite endpoint class, shared by every caller on one api_key.

    Kite applies its limits per api_key, so a single limiter instance must front all
    traffic of a process. A 429 parks every bucket for Kite's sliding cooldown.
    """

    def __init__(
        self,
        limits: dict[str, tuple[int, float]] | None = None,
        now: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._now = now
        self._sleep = sleep
        self._lock = threading.Lock()
        self._hold_until = 0.0
        src = limits or LIMITS
        t = now()
        self._buckets = {
            k: _Bucket(capacity=c, refill_per_s=r, tokens=float(c), last=t)
            for k, (c, r) in src.items()
        }

    def hold(self, seconds: float = KITE_429_HOLD_S) -> None:
        with self._lock:
            self._hold_until = max(self._hold_until, self._now() + seconds)

    def holding_for(self) -> float:
        with self._lock:
            return max(0.0, self._hold_until - self._now())

    def acquire(self, kind: str) -> float:
        waited = 0.0
        while True:
            with self._lock:
                t = self._now()
                hold = self._hold_until - t
                if hold > 0:
                    wait = hold
                else:
                    b = self._buckets.get(kind) or self._buckets["general"]
                    b.tokens = min(float(b.capacity), b.tokens + (t - b.last) * b.refill_per_s)
                    b.last = t
                    if b.tokens >= 1.0 - _EPS:
                        b.tokens -= 1.0
                        return waited
                    wait = max((1.0 - b.tokens) / b.refill_per_s, _MIN_WAIT_S)
            self._sleep(wait)
            waited += wait
