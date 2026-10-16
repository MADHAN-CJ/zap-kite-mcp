"""Black-76 pricing, implied volatility and greeks. Kite exposes none of these."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import date, datetime, time
from typing import Literal

from .config import IST, now_ist

OptionType = Literal["CE", "PE"]

_SQRT_2PI = math.sqrt(2 * math.pi)


def _pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / _SQRT_2PI


def norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def black76_price(kind: OptionType, f: float, k: float, t: float, r: float, sigma: float) -> float:
    if t <= 0 or sigma <= 0 or f <= 0 or k <= 0:
        intrinsic = max(f - k, 0.0) if kind == "CE" else max(k - f, 0.0)
        return math.exp(-r * max(t, 0.0)) * intrinsic
    st = sigma * math.sqrt(t)
    d1 = (math.log(f / k) + 0.5 * st * st) / st
    d2 = d1 - st
    df = math.exp(-r * t)
    if kind == "CE":
        return df * (f * norm_cdf(d1) - k * norm_cdf(d2))
    return df * (k * norm_cdf(-d2) - f * norm_cdf(-d1))


def implied_vol(
    kind: OptionType, price: float, f: float, k: float, t: float, r: float
) -> float | None:
    if not price > 0 or t <= 0 or f <= 0 or k <= 0:
        return None
    df = math.exp(-r * t)
    intrinsic = df * (max(f - k, 0.0) if kind == "CE" else max(k - f, 0.0))
    if price <= intrinsic + 1e-9:
        return None
    lo, hi = 0.001, 5.0
    if black76_price(kind, f, k, t, r, hi) < price:
        return None
    for _ in range(100):
        mid = 0.5 * (lo + hi)
        p = black76_price(kind, f, k, t, r, mid)
        if abs(p - price) < 1e-6:
            return mid
        if p > price:
            hi = mid
        else:
            lo = mid
    return 0.5 * (lo + hi)


@dataclass(frozen=True)
class Greeks:
    iv: float | None
    delta: float | None
    gamma: float | None
    theta: float | None
    vega: float | None
    intrinsic: float
    time_value: float | None

    def as_dict(self) -> dict[str, float | None]:
        return asdict(self)


def option_greeks(
    kind: OptionType,
    premium: float,
    spot: float,
    strike: float,
    years_to_expiry: float,
    rate: float,
    forward: float | None = None,
) -> Greeks:
    """Greeks for an observed premium. Forward defaults to spot·e^{rT}, or pass a futures price."""
    t = years_to_expiry
    intrinsic = max(spot - strike, 0.0) if kind == "CE" else max(strike - spot, 0.0)
    if not spot > 0 or not strike > 0 or t <= 0:
        return Greeks(None, None, None, None, None, round(intrinsic, 2), None)
    f = forward if forward and forward > 0 else spot * math.exp(rate * t)
    iv = implied_vol(kind, premium, f, strike, t, rate)
    if iv is None:
        tv = round(premium - intrinsic, 2) if premium > 0 else None
        return Greeks(None, None, None, None, None, round(intrinsic, 2), tv)
    st = iv * math.sqrt(t)
    d1 = (math.log(f / strike) + 0.5 * st * st) / st
    d2 = d1 - st
    df = math.exp(-rate * t)
    nd1 = _pdf(d1)
    delta = df * norm_cdf(d1) if kind == "CE" else -df * norm_cdf(-d1)
    gamma = (df * nd1) / (f * st)
    vega = (df * f * nd1 * math.sqrt(t)) / 100.0
    decay = -(df * f * nd1 * iv) / (2.0 * math.sqrt(t))
    if kind == "CE":
        theta_year = decay - rate * strike * df * norm_cdf(d2) + rate * f * df * norm_cdf(d1)
    else:
        theta_year = decay + rate * strike * df * norm_cdf(-d2) - rate * f * df * norm_cdf(-d1)
    return Greeks(
        iv=round(iv, 4),
        delta=round(delta, 4),
        gamma=round(gamma, 6),
        theta=round(theta_year / 365.0, 4),
        vega=round(vega, 4),
        intrinsic=round(intrinsic, 2),
        time_value=round(premium - intrinsic, 2),
    )


def years_to_expiry(
    expiry: str | date, close: time = time(15, 30), now: datetime | None = None
) -> float:
    """Years from now until the expiry day's close (15:30 IST by default)."""
    d = date.fromisoformat(expiry) if isinstance(expiry, str) else expiry
    close_dt = datetime.combine(d, close, IST)
    current = now or now_ist()
    return max((close_dt - current).total_seconds() / (365.0 * 86400.0), 0.0)


def max_pain(rows: list[tuple[float, float, float]]) -> float | None:
    """Strike with the lowest total option-writer payout. rows = (strike, ce_oi, pe_oi)."""
    if not rows:
        return None
    best: tuple[float, float] | None = None
    for s, _, _ in rows:
        pain = 0.0
        for k, ce_oi, pe_oi in rows:
            pain += max(s - k, 0.0) * ce_oi + max(k - s, 0.0) * pe_oi
        if best is None or pain < best[1]:
            best = (s, pain)
    return best[0] if best else None
