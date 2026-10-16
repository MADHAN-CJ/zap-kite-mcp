from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

IST = timezone(timedelta(hours=5, minutes=30), "IST")

DEFAULT_BASE_URL = "https://api.kite.trade"
DEFAULT_CALL_BUDGET = 40
DEFAULT_RISK_FREE_RATE = 0.07
DEFAULT_TIMEOUT_S = 15.0


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    try:
        return float(raw) if raw else default
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    base_url: str
    api_key: str
    access_token: str
    gateway_url: str
    run_token: str
    cache_dir: Path
    call_budget: int
    risk_free_rate: float
    timeout_s: float

    @property
    def uses_gateway(self) -> bool:
        return bool(self.gateway_url)


def settings() -> Settings:
    return Settings(
        base_url=os.environ.get("KITE_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
        api_key=os.environ.get("KITE_API_KEY", "").strip(),
        access_token=os.environ.get("KITE_ACCESS_TOKEN", "").strip(),
        gateway_url=os.environ.get("ZAPKITE_GATEWAY_URL", "").strip().rstrip("/"),
        run_token=os.environ.get("ZAPKITE_RUN_TOKEN", "").strip(),
        cache_dir=Path(os.environ.get("ZAPKITE_CACHE_DIR") or "~/.zapkite").expanduser(),
        call_budget=_env_int("ZAPKITE_CALL_BUDGET", DEFAULT_CALL_BUDGET),
        risk_free_rate=_env_float("ZAPKITE_RISK_FREE_RATE", DEFAULT_RISK_FREE_RATE),
        timeout_s=_env_float("ZAPKITE_TIMEOUT_S", DEFAULT_TIMEOUT_S),
    )


def now_ist() -> datetime:
    fixed = os.environ.get("ZAPKITE_NOW", "").strip()
    if fixed:
        parsed = datetime.fromisoformat(fixed)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=IST)
    fixed_day = os.environ.get("ZAPKITE_TODAY", "").strip()
    if fixed_day:
        return datetime.combine(date.fromisoformat(fixed_day), datetime.min.time(), IST).replace(
            hour=12
        )
    return datetime.now(IST)


def today_ist() -> date:
    return now_ist().date()
