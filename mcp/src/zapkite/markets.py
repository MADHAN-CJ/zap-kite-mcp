from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any

from .config import IST, now_ist

DERIVATIVE_EXCHANGES = frozenset({"NFO", "BFO", "MCX", "CDS", "BCD"})
EQUITY_EXCHANGES = frozenset({"NSE", "BSE"})

HOURS: dict[str, tuple[time, time]] = {
    "NSE": (time(9, 15), time(15, 30)),
    "BSE": (time(9, 15), time(15, 30)),
    "NFO": (time(9, 15), time(15, 30)),
    "BFO": (time(9, 15), time(15, 30)),
    "CDS": (time(9, 0), time(17, 0)),
    "BCD": (time(9, 0), time(17, 0)),
    "MCX": (time(9, 0), time(23, 30)),
}


def hours_for(exchange: str) -> tuple[time, time]:
    return HOURS.get(exchange.upper(), HOURS["NSE"])


def is_open(exchange: str, at: datetime | None = None) -> bool:
    now = (at or now_ist()).astimezone(IST)
    if now.weekday() >= 5:
        return False
    start, end = hours_for(exchange)
    return start <= now.time() <= end


def market_status(at: str | None = None) -> dict[str, Any]:
    """Open/closed per exchange (NSE, BSE, NFO, BFO, CDS, BCD, MCX) now or at an IST time."""
    now = datetime.fromisoformat(at).replace(tzinfo=IST) if at else now_ist()
    now = now.astimezone(IST)
    markets = {
        ex: {
            "open": is_open(ex, now),
            "hours": f"{s.strftime('%H:%M')}-{e.strftime('%H:%M')} IST Mon-Fri",
        }
        for ex, (s, e) in HOURS.items()
    }
    return {
        "now_ist": now.strftime("%Y-%m-%d %H:%M:%S"),
        "weekday": now.strftime("%A"),
        "markets": markets,
        "holiday_aware": False,
    }


def today() -> str:
    """Today's date in IST as YYYY-MM-DD."""
    return now_ist().date().isoformat()


def days_ago(n: int) -> str:
    """The date n days before today (IST) as YYYY-MM-DD."""
    return (now_ist().date() - timedelta(days=n)).isoformat()


def ymd(d: date | datetime) -> str:
    """Format a date or datetime as YYYY-MM-DD."""
    return d.strftime("%Y-%m-%d")


def to_ist(ts: str) -> datetime:
    """Parse a Kite timestamp ('2026-10-15T09:15:00+0530' or '+05:30') into an aware IST time."""
    s = ts.strip()
    if len(s) >= 5 and s[-5] in "+-" and s[-3] != ":":
        s = f"{s[:-2]}:{s[-2:]}"
    parsed = datetime.fromisoformat(s)
    return (parsed if parsed.tzinfo else parsed.replace(tzinfo=IST)).astimezone(IST)
