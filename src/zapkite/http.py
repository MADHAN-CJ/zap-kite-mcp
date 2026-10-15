from __future__ import annotations

import threading
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from .config import Settings, settings
from .errors import CallBudgetExceeded, GatewayError, KiteError, RateLimited, classify
from .ratelimit import RateLimiter, kind_for

Params = Sequence[tuple[str, str]]

INSTRUMENTS_TIMEOUT_S = 120.0
HISTORICAL_TIMEOUT_S = 30.0


@dataclass(frozen=True)
class Response:
    status: int
    content: bytes
    content_type: str

    def json(self) -> Any:
        import json

        try:
            return json.loads(self.content.decode("utf-8"))
        except ValueError:
            return None

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", errors="replace")


class Transport(Protocol):
    def get(self, path: str, params: Params, timeout_s: float) -> Response: ...


def _timeout_for(path: str, default: float) -> float:
    p = path.lstrip("/")
    if p.startswith("instruments/historical"):
        return HISTORICAL_TIMEOUT_S
    if p.startswith("instruments") or p.startswith("mf/instruments"):
        return INSTRUMENTS_TIMEOUT_S
    return default


class DirectTransport:
    """Talks to api.kite.trade with the app key and one user's access token, rate limited."""

    def __init__(
        self,
        api_key: str,
        access_token: str,
        base_url: str,
        limiter: RateLimiter | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        if not api_key or not access_token:
            raise GatewayError(
                "KITE_API_KEY and KITE_ACCESS_TOKEN are required for direct Kite access"
            )
        self.base_url = base_url.rstrip("/")
        self.limiter = limiter or RateLimiter()
        self._headers = {
            "X-Kite-Version": "3",
            "Authorization": f"token {api_key}:{access_token}",
        }
        self._client = client or httpx.Client()

    def get(self, path: str, params: Params, timeout_s: float) -> Response:
        self.limiter.acquire(kind_for(path))
        r = self._client.get(
            f"{self.base_url}/{path.lstrip('/')}",
            params=list(params),
            headers=self._headers,
            timeout=timeout_s,
        )
        if r.status_code == 429:
            self.limiter.hold()
        return Response(r.status_code, r.content, r.headers.get("content-type", ""))


class GatewayTransport:
    """Talks to the local zap-kite-mcp gateway, which holds the Kite token and the limiter."""

    def __init__(
        self, gateway_url: str, run_token: str, client: httpx.Client | None = None
    ) -> None:
        if not gateway_url or not run_token:
            raise GatewayError("ZAPKITE_GATEWAY_URL and ZAPKITE_RUN_TOKEN are required")
        self.base_url = gateway_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {run_token}"}
        self._client = client or httpx.Client()

    def get(self, path: str, params: Params, timeout_s: float) -> Response:
        r = self._client.get(
            f"{self.base_url}/kite/{path.lstrip('/')}",
            params=list(params),
            headers=self._headers,
            timeout=timeout_s + 5.0,
        )
        return Response(r.status_code, r.content, r.headers.get("content-type", ""))


class Session:
    """One script's view of Kite: a transport plus the per-script call budget."""

    def __init__(self, transport: Transport, cfg: Settings) -> None:
        self.transport = transport
        self.cfg = cfg
        self.calls = 0
        self._lock = threading.Lock()

    def _spend(self) -> None:
        with self._lock:
            if self.calls >= self.cfg.call_budget:
                raise CallBudgetExceeded(
                    f"This script already made {self.calls} Kite requests (budget "
                    f"{self.cfg.call_budget}). Batch quote keys, fetch fewer strikes or wider "
                    "candle intervals, or split the work across scripts."
                )
            self.calls += 1

    def get(self, path: str, params: Params = ()) -> Response:
        self._spend()
        timeout = _timeout_for(path, self.cfg.timeout_s)
        try:
            return self.transport.get(path, params, timeout)
        except httpx.HTTPError as e:
            raise KiteError(f"Kite request failed: {e}", 0) from e

    def get_json(self, path: str, params: Params = ()) -> Any:
        r = self.get(path, params)
        payload = r.json()
        if r.status >= 400 or (isinstance(payload, dict) and payload.get("status") == "error"):
            raise classify(r.status, payload, f"HTTP {r.status} on {path}")
        if isinstance(payload, dict) and "data" in payload:
            return payload["data"]
        return payload

    def get_text(self, path: str, params: Params = ()) -> str:
        r = self.get(path, params)
        if r.status >= 400:
            raise classify(r.status, r.json(), f"HTTP {r.status} on {path}")
        return r.text


_session: Session | None = None
_session_lock = threading.Lock()


def _build_transport(cfg: Settings) -> Transport:
    if cfg.uses_gateway:
        return GatewayTransport(cfg.gateway_url, cfg.run_token)
    return DirectTransport(cfg.api_key, cfg.access_token, cfg.base_url)


def session() -> Session:
    global _session
    with _session_lock:
        if _session is None:
            cfg = settings()
            _session = Session(_build_transport(cfg), cfg)
        return _session


def configure(transport: Transport | None = None, cfg: Settings | None = None) -> Session:
    """Install an explicit transport (tests, the gateway process) and reset the call budget."""
    global _session
    with _session_lock:
        c = cfg or settings()
        _session = Session(transport or _build_transport(c), c)
        return _session


def reset() -> None:
    global _session
    with _session_lock:
        _session = None


__all__ = [
    "DirectTransport",
    "GatewayTransport",
    "RateLimited",
    "Response",
    "Session",
    "Transport",
    "configure",
    "reset",
    "session",
]
