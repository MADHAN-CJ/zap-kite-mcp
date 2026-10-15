from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import pytest

import zapkite
from zapkite import http, instruments
from zapkite.config import settings
from zapkite.ratelimit import RateLimiter

from .fake_kite import ACCESS_TOKEN, API_KEY, TODAY, FakeKite


class FakeClock:
    def __init__(self) -> None:
        self.t = 1000.0
        self.slept: list[float] = []

    def now(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.t += seconds


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def fake() -> FakeKite:
    return FakeKite()


@pytest.fixture
def kite_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KITE_API_KEY", API_KEY)
    monkeypatch.setenv("KITE_ACCESS_TOKEN", ACCESS_TOKEN)
    monkeypatch.setenv("KITE_BASE_URL", "https://fake.kite.test")
    monkeypatch.setenv("ZAPKITE_TODAY", TODAY.isoformat())
    monkeypatch.setenv("ZAPKITE_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("ZAPKITE_CALL_BUDGET", "40")
    monkeypatch.delenv("ZAPKITE_GATEWAY_URL", raising=False)
    monkeypatch.delenv("ZAPKITE_RUN_TOKEN", raising=False)


@pytest.fixture
def z(kite_env: None, fake: FakeKite, clock: FakeClock) -> Iterator[ModuleType]:
    limiter = RateLimiter(now=clock.now, sleep=clock.sleep)
    transport = http.DirectTransport(
        API_KEY, ACCESS_TOKEN, settings().base_url, limiter, fake.client()
    )
    http.configure(transport)
    instruments.reset()
    yield zapkite
    instruments.reset()
    http.reset()
