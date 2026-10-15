from __future__ import annotations

import logging
import secrets
import threading
import time
from collections.abc import Callable
from typing import Any

import anyio
import httpx
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from zapkite.ratelimit import RateLimiter, kind_for

from .broker import Broker, Creds
from .config import Settings

log = logging.getLogger(__name__)

READ_PATHS = (
    "user/profile",
    "user/margins",
    "portfolio/holdings",
    "portfolio/positions",
    "orders",
    "trades",
    "quote",
    "instruments",
    "mf/holdings",
    "mf/orders",
    "mf/sips",
    "mf/instruments",
    "gtt/triggers",
)
RUN_TOKEN_TTL_S = 300
UPSTREAM_TIMEOUT_S = 60.0


class RunTokens:
    """Short-lived bearer tokens handed to one script run; each maps to one user."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._tokens: dict[str, tuple[str, float]] = {}

    def issue(self, user_id: str, ttl_s: int = RUN_TOKEN_TTL_S) -> str:
        token = secrets.token_urlsafe(32)
        with self._lock:
            now = time.monotonic()
            self._tokens = {t: v for t, v in self._tokens.items() if v[1] > now}
            self._tokens[token] = (user_id, now + ttl_s)
        return token

    def resolve(self, token: str) -> str | None:
        with self._lock:
            entry = self._tokens.get(token)
            if entry is None or entry[1] <= time.monotonic():
                return None
            return entry[0]

    def revoke(self, token: str) -> None:
        with self._lock:
            self._tokens.pop(token, None)


def _allowed(path: str) -> bool:
    p = path.strip("/")
    return any(p == base or p.startswith(base + "/") for base in READ_PATHS)


class Gateway:
    """Forwards read-only Kite calls for a run token, adding the user's access token and the

    app-wide rate limiter. The script never sees the Kite token.
    """

    def __init__(
        self,
        settings: Settings,
        broker: Broker,
        tokens: RunTokens,
        on_token_expired: Callable[[str], None],
        transport: httpx.AsyncBaseTransport | None = None,
        limiter: RateLimiter | None = None,
    ) -> None:
        self._settings = settings
        self._broker = broker
        self._tokens = tokens
        self._on_token_expired = on_token_expired
        self._limiter = limiter or RateLimiter()
        self._client = httpx.AsyncClient(transport=transport, timeout=UPSTREAM_TIMEOUT_S)
        self.calls = 0

    @property
    def limiter(self) -> RateLimiter:
        return self._limiter

    async def handle(self, request: Request) -> Response:
        auth = request.headers.get("authorization", "")
        token = auth[7:] if auth.lower().startswith("bearer ") else ""
        user_id = self._tokens.resolve(token) if token else None
        if user_id is None:
            return _kite_error(401, "TokenException", "Run token missing or expired")
        path = request.path_params["path"]
        if request.method != "GET" or not _allowed(path):
            return _kite_error(
                403, "PermissionException", f"{request.method} /{path} is not a read endpoint"
            )
        creds = await anyio.to_thread.run_sync(self._broker.creds, user_id)
        if not isinstance(creds, Creds):
            return _kite_error(403, "TokenException", f"Kite session {creds.replace('_', ' ')}")
        await anyio.to_thread.run_sync(self._limiter.acquire, kind_for(path))
        self.calls += 1
        try:
            upstream = await self._client.get(
                f"{self._settings.kite_base_url}/{path.lstrip('/')}",
                params=list(request.query_params.multi_items()),
                headers={
                    "X-Kite-Version": "3",
                    "Authorization": f"token {self._settings.kite_api_key}:{creds.access_token}",
                },
            )
        except httpx.HTTPError as e:
            return _kite_error(502, "NetworkException", f"Kite unreachable: {e}")
        if upstream.status_code == 429:
            self._limiter.hold()
        if upstream.status_code == 403 and _is_token_error(upstream):
            await anyio.to_thread.run_sync(self._on_token_expired, user_id)
        return Response(
            content=upstream.content,
            status_code=upstream.status_code,
            media_type=upstream.headers.get("content-type", "application/json"),
        )

    async def aclose(self) -> None:
        await self._client.aclose()


def _is_token_error(response: httpx.Response) -> bool:
    try:
        body: Any = response.json()
    except ValueError:
        return False
    return isinstance(body, dict) and body.get("error_type") == "TokenException"


def _kite_error(status: int, error_type: str, message: str) -> JSONResponse:
    return JSONResponse(
        {"status": "error", "error_type": error_type, "message": message, "data": None},
        status_code=status,
    )
