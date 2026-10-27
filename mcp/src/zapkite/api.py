"""The functions the model's scripts call. Signatures and first doc lines are the schema."""

from __future__ import annotations

import json
import math
from collections.abc import Iterable, Sequence
from datetime import date, timedelta
from typing import Any

from . import client, instruments
from .config import IST, now_ist, settings, today_ist
from .errors import (
    CallBudgetExceeded,
    DataPlanMissing,
    InstrumentNotFound,
    KiteError,
    RateLimited,
    TokenExpired,
    ZapKiteError,
)
from .http import session
from .indicators import atr, bollinger, closes, ema, macd, pct_change, rsi, sma, vwap
from .instruments import (
    INDEX_SPOT_KEYS,
    find_option_contracts,
    list_underlyings,
    lookup,
    resolve_symbol,
    search_instruments,
)
from .markets import days_ago, market_status, to_ist, today, ymd
from .options_math import OptionType, max_pain, option_greeks, years_to_expiry

Row = dict[str, Any]

_INTERVALS: dict[str, str] = {
    "1": "minute",
    "minute": "minute",
    "1minute": "minute",
    "1m": "minute",
    "3": "3minute",
    "3minute": "3minute",
    "3m": "3minute",
    "5": "5minute",
    "5minute": "5minute",
    "5m": "5minute",
    "10": "10minute",
    "10minute": "10minute",
    "10m": "10minute",
    "15": "15minute",
    "15minute": "15minute",
    "15m": "15minute",
    "30": "30minute",
    "30minute": "30minute",
    "30m": "30minute",
    "60": "60minute",
    "60minute": "60minute",
    "60m": "60minute",
    "1h": "60minute",
    "hour": "60minute",
    "day": "day",
    "1d": "day",
    "d": "day",
    "daily": "day",
}

_MAX_DAYS: dict[str, int] = {
    "minute": 60,
    "3minute": 100,
    "5minute": 100,
    "10minute": 100,
    "15minute": 200,
    "30minute": 200,
    "60minute": 400,
    "day": 2000,
}

MAX_CHAIN_STRIKES_AROUND = 60


# ---------------------------------------------------------------- account


def profile() -> Row:
    """Zerodha profile of the connected user (user_id, user_name, email, exchanges, products)."""
    return client.profile()


def positions(day: bool = False) -> list[Row]:
    """Open positions: net positions by default, today's intraday legs with day=True.

    Rows carry tradingsymbol, exchange, instrument_token, product (CNC/MIS/NRML), quantity
    (negative = short), average_price, last_price, pnl, m2m, unrealised, realised, buy_/sell_
    quantities and values. Quantity 0 rows are closed positions still shown by Kite today.
    """
    p = client.positions()
    return p["day"] if day else p["net"]


def holdings() -> list[Row]:
    """Demat holdings with quantity, average_price, last_price, pnl, day_change, isin, product."""
    return client.holdings()


def funds() -> Row:
    """Margins: {equity: {net, available: {live_balance, cash, collateral}, utilised}, commodity}"""
    return client.margins()


def orders() -> list[Row]:
    """Today's order book (status COMPLETE/OPEN/REJECTED/CANCELLED, filled_quantity, avg price)."""
    return client.orders()


def trades() -> list[Row]:
    """Today's executed trades (tradingsymbol, quantity, average_price, fill_timestamp)."""
    return client.trades()


def order_history(order_id: str) -> list[Row]:
    """Status transitions of one order, oldest first."""
    return client.order_history(order_id)


def position_for(tradingsymbol: str, exchange: str | None = None) -> Row | None:
    """The net position row for one tradingsymbol (optionally on one exchange), or None."""
    ts = tradingsymbol.strip().upper()
    ex = exchange.strip().upper() if exchange else None
    for p in positions():
        if str(p.get("tradingsymbol", "")).upper() == ts and (
            ex is None or p.get("exchange") == ex
        ):
            return p
    return None


def mf_holdings() -> list[Row]:
    """Mutual-fund holdings (fund, folio, quantity, average_price, last_price, pnl)."""
    return client.mf_holdings()


def mf_orders() -> list[Row]:
    """Mutual-fund orders placed through Kite."""
    return client.mf_orders()


def mf_sips() -> list[Row]:
    """Active mutual-fund SIPs."""
    return client.mf_sips()


def gtt_triggers() -> list[Row]:
    """Good-till-triggered orders the user has set up in Kite (read-only view)."""
    return client.gtt_triggers()


# ---------------------------------------------------------------- quotes


def _key_of(ref: str | int) -> str:
    if isinstance(ref, str) and ":" in ref:
        return ref.strip().upper()
    return str(lookup(ref)["key"])


def ltp(instruments_: Iterable[str | int]) -> dict[str, float]:
    """Last traded price for many instruments → {"NSE:INFY": 1520.5, …}. ≤1000 per Kite call.

    Accepts quote keys ("NSE:INFY", "NFO:NIFTY25OCT24700CE"), instrument tokens or plain
    symbols (resolved via resolve_symbol). Missing keys are omitted by Kite.
    """
    keys = [_key_of(r) for r in instruments_]
    data = client.ltp(keys)
    return {k: float(v.get("last_price") or 0) for k, v in data.items() if isinstance(v, dict)}


def ltp_of(instrument: str | int) -> float:
    """Last traded price of one instrument (raises InstrumentNotFound if Kite returns nothing)."""
    key = _key_of(instrument)
    prices = ltp([key])
    if key not in prices:
        raise InstrumentNotFound(f"Kite returned no price for {key}")
    return prices[key]


def ohlc(instruments_: Iterable[str | int]) -> dict[str, Row]:
    """Day OHLC + last_price per instrument → {key: {instrument_token, last_price, ohlc}}."""
    keys = [_key_of(r) for r in instruments_]
    return {k: v for k, v in client.ohlc(keys).items() if isinstance(v, dict)}


def quote(instruments_: Iterable[str | int]) -> dict[str, Row]:
    """Full quotes: last_price, volume, average_price, oi, oi_day_high/low, net_change, circuits,

    buy_/sell_quantity, ohlc and 5-level depth {buy:[{price,quantity,orders}], sell:[…]}.
    ≤500 keys per Kite call; the quote endpoint allows 1 request per second app-wide.
    """
    keys = [_key_of(r) for r in instruments_]
    return {k: v for k, v in client.quote(keys).items() if isinstance(v, dict)}


# ---------------------------------------------------------------- candles


def _interval(interval: str | int) -> str:
    key = str(interval).strip().lower()
    try:
        return _INTERVALS[key]
    except KeyError:
        raise ValueError(
            f"Unknown interval {interval!r}. Use 1, 3, 5, 10, 15, 30, 60 (minutes) or 'day'."
        ) from None


def _candle_rows(raw: Sequence[Sequence[Any]]) -> list[Row]:
    out: list[Row] = []
    for c in raw:
        if len(c) < 6:
            continue
        row: Row = {
            "time": to_ist(str(c[0])).isoformat(),
            "open": float(c[1]),
            "high": float(c[2]),
            "low": float(c[3]),
            "close": float(c[4]),
            "volume": int(c[5] or 0),
        }
        if len(c) > 6:
            row["oi"] = int(c[6] or 0)
        out.append(row)
    return out


def _fetch_candles(
    token: int,
    interval: str,
    start: date,
    end: date,
    oi: bool,
    continuous: bool = False,
) -> list[Row]:
    step = _MAX_DAYS[interval]
    out: list[Row] = []
    seen: set[str] = set()
    cursor = start
    while cursor <= end:
        chunk_end = min(cursor + timedelta(days=step - 1), end)
        raw = client.historical(
            token,
            interval,
            f"{cursor.isoformat()} 00:00:00",
            f"{chunk_end.isoformat()} 23:59:59",
            continuous=continuous,
            oi=oi,
        )
        for row in _candle_rows(raw):
            if row["time"] not in seen:
                seen.add(row["time"])
                out.append(row)
        cursor = chunk_end + timedelta(days=1)
    out.sort(key=lambda r: str(r["time"]))
    return out


def _window(days_back: int, from_date: str | None, to_date: str | None) -> tuple[date, date]:
    end = date.fromisoformat(to_date) if to_date else today_ist()
    start = (
        date.fromisoformat(from_date) if from_date else end - timedelta(days=max(0, int(days_back)))
    )
    if start > end:
        raise ValueError("from_date must not be after to_date")
    return start, end


def intraday_candles(
    instrument: str | int,
    interval: str | int = 15,
    days_back: int = 5,
    from_date: str | None = None,
    to_date: str | None = None,
    oi: bool | None = None,
) -> list[Row]:
    """Intraday candles [{time (IST ISO), open, high, low, close, volume, oi?}] oldest first.

    interval: 1, 3, 5, 10, 15, 30 or 60 minutes. Kite caps one request at 60 days (1-min) to
    400 days (60-min); longer windows are fetched in chunks automatically (each chunk is one
    Kite call against the script budget). oi defaults to True for derivatives.
    """
    row = lookup(instrument)
    iv = _interval(interval)
    if iv == "day":
        raise ValueError("Use daily_candles() for the day interval")
    start, end = _window(days_back, from_date, to_date)
    use_oi = instruments.is_derivative(row) if oi is None else oi
    return _fetch_candles(int(row["instrument_token"]), iv, start, end, use_oi)


def daily_candles(
    instrument: str | int,
    days_back: int = 365,
    from_date: str | None = None,
    to_date: str | None = None,
    oi: bool | None = None,
) -> list[Row]:
    """Daily candles [{time, open, high, low, close, volume, oi?}] oldest first."""
    row = lookup(instrument)
    start, end = _window(days_back, from_date, to_date)
    use_oi = instruments.is_derivative(row) if oi is None else oi
    return _fetch_candles(int(row["instrument_token"]), "day", start, end, use_oi)


def continuous_futures(
    underlying: str,
    days_back: int = 365,
    exchange: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
) -> list[Row]:
    """Daily candles of the rolling front-month future (Kite continuous=1), useful across expiries.

    Kite serves this only for futures and only at the day interval; history is roughly one year.
    """
    futs = instruments.futures_contracts(underlying, exchange)
    if not futs:
        raise InstrumentNotFound(f"No live futures found for {underlying!r}")
    start, end = _window(days_back, from_date, to_date)
    return _fetch_candles(
        int(futs[0]["instrument_token"]), "day", start, end, oi=True, continuous=True
    )


# ---------------------------------------------------------------- options


def expiry_list(underlying: str, exchange: str | None = None) -> list[str]:
    """Live option expiries (YYYY-MM-DD) of an underlying (NIFTY, SENSEX, RELIANCE, GOLD, USDINR)"""
    return instruments.option_expiries(underlying, exchange)


def nearest_expiry(underlying: str, exchange: str | None = None) -> str:
    """The closest live option expiry of an underlying."""
    expiries = expiry_list(underlying, exchange)
    if not expiries:
        raise InstrumentNotFound(f"No live option expiries for {underlying!r}")
    return expiries[0]


def futures_list(underlying: str, exchange: str | None = None) -> list[Row]:
    """Live futures of an underlying, nearest expiry first (tradingsymbol, expiry, lot_size)."""
    return instruments.futures_contracts(underlying, exchange)


def _depth_price(q: Row, side: str) -> float | None:
    depth = q.get("depth")
    if not isinstance(depth, dict):
        return None
    levels = depth.get(side)
    if not isinstance(levels, list) or not levels or not isinstance(levels[0], dict):
        return None
    price = levels[0].get("price")
    return float(price) if price else None


def _spot_for(name: str, exchange: str) -> tuple[float, str, float | None]:
    key = instruments.spot_key(name)
    if key:
        return ltp_of(key), "spot", None
    futs = instruments.futures_contracts(name, exchange)
    if not futs:
        raise InstrumentNotFound(f"No spot or futures price available for {name!r}")
    price = ltp_of(str(futs[0]["key"]))
    return price, f"future:{futs[0]['tradingsymbol']}", price


def option_chain(
    underlying: str,
    expiry: str | None = None,
    strikes_around: int = 10,
    exchange: str | None = None,
) -> Row:
    """Option chain around the money with quotes and computed greeks, in ONE quote call.

    Returns {underlying, exchange, expiry, spot, spot_source, lot_size, strikes: [{strike, ce, pe}],
    pcr, max_pain, rate}. Each side has tradingsymbol, instrument_token, last_price, oi, volume,
    bid, ask, change, iv, delta, gamma, theta (per day), vega (per vol point), intrinsic,
    time_value. Kite has no chain API, so this is derived from the instruments dump plus a
    batched quote; greeks are Black-76 on the forward (indicative). Keep strikes_around ≤ 60.
    """
    name = underlying.strip().upper()
    ex = (exchange or instruments.derivative_exchange(name) or "").upper()
    if not ex:
        raise InstrumentNotFound(f"{name!r} has no listed options on Kite")
    exp = expiry or nearest_expiry(name, ex)
    contracts = instruments.option_contracts(name, exp, ex)
    if not contracts:
        raise InstrumentNotFound(f"No option contracts for {name} expiring {exp} on {ex}")
    n = max(0, min(int(strikes_around), MAX_CHAIN_STRIKES_AROUND))
    spot, spot_source, forward = _spot_for(name, ex)
    strikes = sorted({float(c["strike"]) for c in contracts})
    atm_index = min(range(len(strikes)), key=lambda i: abs(strikes[i] - spot))
    window = strikes[max(0, atm_index - n) : atm_index + n + 1]
    chosen = [c for c in contracts if float(c["strike"]) in set(window)]
    quotes = client.quote([str(c["key"]) for c in chosen])
    rate = settings().risk_free_rate
    t = years_to_expiry(exp)
    by_strike: dict[float, Row] = {s: {"strike": s, "ce": None, "pe": None} for s in window}
    for c in chosen:
        q = quotes.get(str(c["key"]))
        if not isinstance(q, dict):
            continue
        kind: OptionType = "CE" if c["instrument_type"] == "CE" else "PE"
        premium = float(q.get("last_price") or 0)
        g = option_greeks(kind, premium, spot, float(c["strike"]), t, rate, forward)
        side: Row = {
            "tradingsymbol": c["tradingsymbol"],
            "instrument_token": c["instrument_token"],
            "key": c["key"],
            "last_price": premium,
            "oi": int(q.get("oi") or 0),
            "volume": int(q.get("volume") or 0),
            "bid": _depth_price(q, "buy"),
            "ask": _depth_price(q, "sell"),
            "change": q.get("net_change"),
        }
        side.update(g.as_dict())
        by_strike[float(c["strike"])][kind.lower()] = side
    rows = [by_strike[s] for s in window]
    ce_oi = sum(int(r["ce"]["oi"]) for r in rows if r["ce"])
    pe_oi = sum(int(r["pe"]["oi"]) for r in rows if r["pe"])
    pain_rows = [
        (
            float(r["strike"]),
            float(r["ce"]["oi"] if r["ce"] else 0),
            float(r["pe"]["oi"] if r["pe"] else 0),
        )
        for r in rows
    ]
    return {
        "underlying": name,
        "exchange": ex,
        "expiry": exp,
        "spot": spot,
        "spot_source": spot_source,
        "lot_size": int(chosen[0]["lot_size"]) if chosen else None,
        "strikes": rows,
        "pcr": round(pe_oi / ce_oi, 2) if ce_oi else None,
        "max_pain": max_pain(pain_rows),
        "rate": rate,
    }


def option_candles(
    contract: str | int,
    interval: str | int = 15,
    days_back: int = 5,
    from_date: str | None = None,
    to_date: str | None = None,
) -> list[Row]:
    """Intraday candles (with oi) of one option or futures contract by key or instrument_token."""
    return intraday_candles(contract, interval, days_back, from_date, to_date, oi=True)


# ---------------------------------------------------------------- instruments


def instrument(ref: str | int) -> Row:
    """Instrument row for a key, token or symbol.

    Fields: key, exchange, tradingsymbol, name, instrument_token, kind, expiry, strike, lot_size.
    """
    return lookup(ref)


# ---------------------------------------------------------------- helpers


def now() -> str:
    """Current IST time as 'YYYY-MM-DD HH:MM:SS'."""
    return now_ist().strftime("%Y-%m-%d %H:%M:%S")


def kite_get(path: str, params: dict[str, Any] | None = None) -> Any:
    """Escape hatch: GET any Kite Connect read endpoint (e.g. '/user/margins/equity') → its data."""
    items = [(k, str(v)) for k, v in (params or {}).items()]
    return session().get_json(path, items)


def pp(value: Any, limit: int | None = 4000) -> None:
    """Print a value as compact JSON, truncated to `limit` characters (None = no limit)."""
    text = json.dumps(value, default=str, ensure_ascii=False)
    if limit is not None and len(text) > limit:
        text = text[:limit] + f"… [{len(text) - limit} more chars; print less]"
    print(text)


def help_api() -> str:
    """One line per function: the full zapkite reference."""
    from .schema import reference

    return reference(brief=True)


def is_nan(x: Any) -> bool:
    """True for None or NaN, handy when filtering indicator output."""
    return x is None or (isinstance(x, float) and math.isnan(x))


__all__ = [
    # account
    "profile",
    "positions",
    "holdings",
    "funds",
    "orders",
    "trades",
    "order_history",
    "position_for",
    "mf_holdings",
    "mf_orders",
    "mf_sips",
    "gtt_triggers",
    # quotes and candles
    "ltp",
    "ltp_of",
    "ohlc",
    "quote",
    "intraday_candles",
    "daily_candles",
    "continuous_futures",
    # options and futures
    "expiry_list",
    "nearest_expiry",
    "futures_list",
    "option_chain",
    "option_candles",
    # instruments
    "resolve_symbol",
    "search_instruments",
    "find_option_contracts",
    "instrument",
    "list_underlyings",
    "market_status",
    # indicators
    "closes",
    "sma",
    "ema",
    "rsi",
    "macd",
    "bollinger",
    "atr",
    "vwap",
    "pct_change",
    # time
    "now",
    "today",
    "days_ago",
    "ymd",
    "to_ist",
    "IST",
    "INDEX_SPOT_KEYS",
    # misc
    "kite_get",
    "pp",
    "help_api",
    "is_nan",
    # errors
    "ZapKiteError",
    "KiteError",
    "TokenExpired",
    "DataPlanMissing",
    "RateLimited",
    "CallBudgetExceeded",
    "InstrumentNotFound",
]
