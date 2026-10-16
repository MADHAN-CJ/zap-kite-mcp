from __future__ import annotations

from types import ModuleType

import httpx
import pytest

from zapkite import http
from zapkite.config import settings
from zapkite.errors import (
    CallBudgetExceeded,
    DataPlanMissing,
    KiteError,
    RateLimited,
    TokenExpired,
)
from zapkite.ratelimit import RateLimiter

from .conftest import FakeClock
from .fake_kite import ACCESS_TOKEN, API_KEY, FakeKite


def test_direct_transport_sends_kite_headers(z: ModuleType, fake: FakeKite) -> None:
    assert z.profile()["user_id"] == "AB1234"
    req = fake.calls[0]
    assert req.headers["X-Kite-Version"] == "3"
    assert req.headers["Authorization"] == f"token {API_KEY}:{ACCESS_TOKEN}"
    assert req.url.host == "fake.kite.test"


def test_token_exception_becomes_token_expired(z: ModuleType, fake: FakeKite) -> None:
    fake.token_valid = False
    with pytest.raises(TokenExpired) as e:
        z.holdings()
    assert e.value.status == 403
    assert "log in to Zerodha again" in str(e.value)


def test_permission_exception_becomes_data_plan_missing(z: ModuleType, fake: FakeKite) -> None:
    fake.data_plan = False
    with pytest.raises(DataPlanMissing):
        z.daily_candles("TCS", days_back=5)


def test_429_raises_and_parks_the_limiter(z: ModuleType, fake: FakeKite) -> None:
    fake.rate_limit_next = True
    with pytest.raises(RateLimited):
        z.funds()
    limiter = http.session().transport.limiter  # type: ignore[attr-defined]
    assert limiter.holding_for() >= 9.9


def test_other_kite_errors_keep_status_and_type(z: ModuleType) -> None:
    with pytest.raises(KiteError) as e:
        z.kite_get("/nope")
    assert e.value.status == 404
    assert e.value.error_type == "GeneralException"


def test_call_budget_is_enforced(
    kite_env: None, fake: FakeKite, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ZAPKITE_CALL_BUDGET", "2")
    transport = http.DirectTransport(
        API_KEY, ACCESS_TOKEN, settings().base_url, RateLimiter(), fake.client()
    )
    http.configure(transport)
    try:
        import zapkite

        zapkite.funds()
        zapkite.funds()
        with pytest.raises(CallBudgetExceeded):
            zapkite.funds()
    finally:
        http.reset()


def test_rate_limiter_buckets_and_hold(clock: FakeClock) -> None:
    limiter = RateLimiter(now=clock.now, sleep=clock.sleep)
    assert limiter.acquire("quote") == 0.0
    limiter.acquire("quote")
    limiter.acquire("quote")
    assert [round(s, 3) for s in clock.slept] == [1.0, 1.0]
    for _ in range(3):
        assert limiter.acquire("historical") == 0.0
    assert round(limiter.acquire("historical"), 3) == round(1 / 3, 3)
    limiter.hold(10)
    waited = limiter.acquire("general")
    assert waited >= 10.0
    assert limiter.holding_for() == 0.0


def test_gateway_transport_forwards_through_the_local_gateway() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path.endswith("/kite/user/profile"):
            return httpx.Response(200, json={"status": "success", "data": {"user_id": "X"}})
        return httpx.Response(
            403,
            json={"status": "error", "error_type": "TokenException", "message": "expired"},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    transport = http.GatewayTransport("http://127.0.0.1:9", "run-token", client)
    session = http.Session(transport, settings())
    assert session.get_json("/user/profile", [("a", "1")]) == {"user_id": "X"}
    assert seen[0].headers["Authorization"] == "Bearer run-token"
    assert seen[0].url.path == "/kite/user/profile"
    assert seen[0].url.params["a"] == "1"
    with pytest.raises(TokenExpired):
        session.get_json("/portfolio/holdings")
