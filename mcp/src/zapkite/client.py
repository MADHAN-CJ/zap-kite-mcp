"""Thin, typed wrappers over the Kite Connect read endpoints. Returns Kite's `data` as-is."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .http import session

LTP_BATCH = 1000
OHLC_BATCH = 1000
QUOTE_BATCH = 500


def _keys(keys: Iterable[str]) -> list[str]:
    seen: dict[str, None] = {}
    for k in keys:
        k = k.strip()
        if k:
            seen.setdefault(k, None)
    return list(seen)


def _batched(path: str, keys: Iterable[str], size: int) -> dict[str, Any]:
    out: dict[str, Any] = {}
    uniq = _keys(keys)
    for i in range(0, len(uniq), size):
        chunk = uniq[i : i + size]
        data = session().get_json(path, [("i", k) for k in chunk])
        if isinstance(data, dict):
            out.update(data)
    return out


def profile() -> dict[str, Any]:
    data = session().get_json("/user/profile")
    return data if isinstance(data, dict) else {}


def margins() -> dict[str, Any]:
    data = session().get_json("/user/margins")
    return data if isinstance(data, dict) else {}


def holdings() -> list[dict[str, Any]]:
    data = session().get_json("/portfolio/holdings")
    return list(data) if isinstance(data, list) else []


def positions() -> dict[str, list[dict[str, Any]]]:
    data = session().get_json("/portfolio/positions")
    if not isinstance(data, dict):
        return {"net": [], "day": []}
    return {"net": list(data.get("net") or []), "day": list(data.get("day") or [])}


def orders() -> list[dict[str, Any]]:
    data = session().get_json("/orders")
    return list(data) if isinstance(data, list) else []


def order_history(order_id: str) -> list[dict[str, Any]]:
    data = session().get_json(f"/orders/{order_id}")
    return list(data) if isinstance(data, list) else []


def trades() -> list[dict[str, Any]]:
    data = session().get_json("/trades")
    return list(data) if isinstance(data, list) else []


def ltp(keys: Iterable[str]) -> dict[str, Any]:
    return _batched("/quote/ltp", keys, LTP_BATCH)


def ohlc(keys: Iterable[str]) -> dict[str, Any]:
    return _batched("/quote/ohlc", keys, OHLC_BATCH)


def quote(keys: Iterable[str]) -> dict[str, Any]:
    return _batched("/quote", keys, QUOTE_BATCH)


def historical(
    instrument_token: int,
    interval: str,
    from_ts: str,
    to_ts: str,
    continuous: bool = False,
    oi: bool = False,
) -> list[list[Any]]:
    params = [
        ("from", from_ts),
        ("to", to_ts),
        ("continuous", "1" if continuous else "0"),
        ("oi", "1" if oi else "0"),
    ]
    data = session().get_json(f"/instruments/historical/{instrument_token}/{interval}", params)
    if isinstance(data, dict):
        return list(data.get("candles") or [])
    return []


def instruments_csv(exchange: str | None = None) -> str:
    path = f"/instruments/{exchange}" if exchange else "/instruments"
    return session().get_text(path)


def mf_holdings() -> list[dict[str, Any]]:
    data = session().get_json("/mf/holdings")
    return list(data) if isinstance(data, list) else []


def mf_orders() -> list[dict[str, Any]]:
    data = session().get_json("/mf/orders")
    return list(data) if isinstance(data, list) else []


def mf_sips() -> list[dict[str, Any]]:
    data = session().get_json("/mf/sips")
    return list(data) if isinstance(data, list) else []


def gtt_triggers() -> list[dict[str, Any]]:
    data = session().get_json("/gtt/triggers")
    return list(data) if isinstance(data, list) else []
