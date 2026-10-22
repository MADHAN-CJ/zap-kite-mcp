from __future__ import annotations

from typing import Any


class ZapKiteError(Exception):
    """Base class for every error raised by zapkite."""


class KiteError(ZapKiteError):
    """Kite Connect answered with an error."""

    def __init__(self, message: str, status: int, error_type: str = "", body: Any = None) -> None:
        super().__init__(message)
        self.status = status
        self.error_type = error_type
        self.body = body


class TokenExpired(KiteError):
    """The Kite access token is invalid or has expired (Kite tokens die every morning)."""


class DataPlanMissing(KiteError):
    """The Kite Connect app has no market-data subscription for this endpoint."""


class RateLimited(KiteError):
    """Kite returned 429; all calls on this api_key pause for a few seconds."""


class CallBudgetExceeded(ZapKiteError):
    """A single script made more Kite requests than its budget allows."""


class InstrumentNotFound(ZapKiteError):
    """No instrument matched the given symbol, key or token."""


class GatewayError(ZapKiteError):
    """The local Kite gateway rejected the request before it reached Kite."""


def classify(status: int, payload: Any, fallback: str) -> KiteError:
    message = fallback
    error_type = ""
    if isinstance(payload, dict):
        message = str(payload.get("message") or fallback)
        error_type = str(payload.get("error_type") or "")
    if status == 429 or (error_type == "NetworkException" and "many" in message.lower()):
        return RateLimited(f"Kite rate limit hit: {message}", status, error_type, payload)
    if error_type == "TokenException" or (status in (401, 403) and not error_type):
        return TokenExpired(
            "Kite access token is invalid or expired. The user must log in to Zerodha again "
            "from the /markets web app; nothing in this script can refresh it.",
            status,
            error_type,
            payload,
        )
    if error_type == "PermissionException":
        return DataPlanMissing(
            f"Kite refused the call: {message}. This usually means the Kite Connect app has no "
            "market-data (historical/quote) subscription.",
            status,
            error_type,
            payload,
        )
    return KiteError(
        f"Kite error {status} {error_type}: {message}".strip(), status, error_type, payload
    )
