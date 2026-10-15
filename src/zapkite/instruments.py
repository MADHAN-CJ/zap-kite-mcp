"""Kite's daily instruments dump, cached in SQLite, and symbol resolution on top of it."""

from __future__ import annotations

import contextlib
import csv
import io
import os
import sqlite3
import threading
from typing import Any

from . import client
from .config import settings, today_ist
from .errors import InstrumentNotFound
from .markets import DERIVATIVE_EXCHANGES

Row = dict[str, Any]

INDEX_SPOT_KEYS: dict[str, str] = {
    "NIFTY": "NSE:NIFTY 50",
    "NIFTY50": "NSE:NIFTY 50",
    "BANKNIFTY": "NSE:NIFTY BANK",
    "FINNIFTY": "NSE:NIFTY FIN SERVICE",
    "MIDCPNIFTY": "NSE:NIFTY MID SELECT",
    "NIFTYNXT50": "NSE:NIFTY NEXT 50",
    "VIX": "NSE:INDIA VIX",
    "INDIAVIX": "NSE:INDIA VIX",
    "SENSEX": "BSE:SENSEX",
    "BANKEX": "BSE:BANKEX",
    "SENSEX50": "BSE:SENSEX50",
}

_FUTURE_EXCHANGE_ORDER = ("MCX", "CDS", "BCD", "NFO", "BFO")
_OPTION_EXCHANGE_ORDER = ("NFO", "BFO", "MCX", "CDS", "BCD")

_COLUMNS = (
    "instrument_token",
    "exchange_token",
    "tradingsymbol",
    "name",
    "last_price",
    "expiry",
    "strike",
    "tick_size",
    "lot_size",
    "instrument_type",
    "segment",
    "exchange",
)

_SCHEMA = """
CREATE TABLE instruments (
  instrument_token INTEGER NOT NULL,
  exchange_token INTEGER,
  tradingsymbol TEXT NOT NULL,
  name TEXT NOT NULL,
  last_price REAL,
  expiry TEXT NOT NULL,
  strike REAL NOT NULL,
  tick_size REAL,
  lot_size INTEGER,
  instrument_type TEXT NOT NULL,
  segment TEXT NOT NULL,
  exchange TEXT NOT NULL
);
CREATE INDEX idx_key ON instruments (exchange, tradingsymbol);
CREATE INDEX idx_name ON instruments (name, exchange, instrument_type, expiry);
CREATE INDEX idx_symbol ON instruments (tradingsymbol);
CREATE INDEX idx_token ON instruments (instrument_token);
"""

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None
_conn_day: str = ""


def _int(v: str) -> int:
    try:
        return int(float(v))
    except ValueError:
        return 0


def _float(v: str) -> float:
    try:
        return float(v)
    except ValueError:
        return 0.0


def _parse(csv_text: str) -> list[tuple[Any, ...]]:
    reader = csv.DictReader(io.StringIO(csv_text))
    rows: list[tuple[Any, ...]] = []
    for r in reader:
        if not r.get("tradingsymbol") or not r.get("exchange"):
            continue
        rows.append(
            (
                _int(r.get("instrument_token") or "0"),
                _int(r.get("exchange_token") or "0"),
                r["tradingsymbol"].strip(),
                (r.get("name") or "").strip(),
                _float(r.get("last_price") or "0"),
                (r.get("expiry") or "").strip(),
                _float(r.get("strike") or "0"),
                _float(r.get("tick_size") or "0"),
                _int(r.get("lot_size") or "0"),
                (r.get("instrument_type") or "").strip(),
                (r.get("segment") or "").strip(),
                r["exchange"].strip(),
            )
        )
    return rows


def _build(path: str) -> None:
    tmp = f"{path}.{os.getpid()}.tmp"
    rows = _parse(client.instruments_csv())
    if os.path.exists(tmp):
        os.remove(tmp)
    con = sqlite3.connect(tmp)
    try:
        con.executescript(_SCHEMA)
        con.executemany(f"INSERT INTO instruments VALUES ({','.join('?' * len(_COLUMNS))})", rows)
        con.commit()
    finally:
        con.close()
    os.replace(tmp, path)


def _prune(cache_dir: str, keep: str) -> None:
    for name in os.listdir(cache_dir):
        if name.startswith("instruments-") and name.endswith(".sqlite3") and name != keep:
            with contextlib.suppress(OSError):
                os.remove(os.path.join(cache_dir, name))


def db() -> sqlite3.Connection:
    """Open today's instruments cache, downloading and indexing the dump on first use."""
    global _conn, _conn_day
    day = today_ist().isoformat()
    with _lock:
        if _conn is not None and _conn_day == day:
            return _conn
        cache_dir = str(settings().cache_dir)
        os.makedirs(cache_dir, exist_ok=True)
        filename = f"instruments-{day}.sqlite3"
        path = os.path.join(cache_dir, filename)
        if not os.path.exists(path):
            _build(path)
            _prune(cache_dir, filename)
        if _conn is not None:
            _conn.close()
        _conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn_day = day
        return _conn


def reset() -> None:
    global _conn, _conn_day
    with _lock:
        if _conn is not None:
            _conn.close()
        _conn, _conn_day = None, ""


def _row(r: sqlite3.Row | None) -> Row | None:
    if r is None:
        return None
    d: Row = dict(r)
    d["key"] = f"{d['exchange']}:{d['tradingsymbol']}"
    d["kind"] = kind_of(d)
    return d


def _rows(cur: sqlite3.Cursor) -> list[Row]:
    out: list[Row] = []
    for r in cur.fetchall():
        row = _row(r)
        if row is not None:
            out.append(row)
    return out


def kind_of(row: Row) -> str:
    seg, ex, typ = row.get("segment", ""), row.get("exchange", ""), row.get("instrument_type", "")
    if seg == "INDICES":
        return "index"
    if ex == "MCX":
        return "commodity_future" if typ == "FUT" else "commodity_option"
    if ex in ("CDS", "BCD"):
        return "currency_future" if typ == "FUT" else "currency_option"
    if typ == "FUT":
        return "future"
    if typ in ("CE", "PE"):
        return "option"
    return "stock"


def is_derivative(row: Row) -> bool:
    return row.get("exchange") in DERIVATIVE_EXCHANGES


def by_key(key: str) -> Row | None:
    ex, _, ts = key.strip().upper().partition(":")
    if not ts:
        return None
    cur = db().execute(
        "SELECT * FROM instruments WHERE exchange = ? AND tradingsymbol = ? LIMIT 1", (ex, ts)
    )
    return _row(cur.fetchone())


def by_token(token: int) -> Row | None:
    cur = db().execute(
        "SELECT * FROM instruments WHERE instrument_token = ? LIMIT 1", (int(token),)
    )
    return _row(cur.fetchone())


def _live_clause(include_expired: bool) -> tuple[str, tuple[Any, ...]]:
    if include_expired:
        return "", ()
    return " AND (expiry = '' OR expiry >= ?)", (today_ist().isoformat(),)


def _first_future(name: str, exchange: str) -> Row | None:
    live, args = _live_clause(False)
    cur = db().execute(
        "SELECT * FROM instruments WHERE name = ? AND exchange = ? AND instrument_type = 'FUT'"
        f"{live} ORDER BY expiry LIMIT 1",
        (name, exchange, *args),
    )
    return _row(cur.fetchone())


def _equity(symbol: str, exchange: str) -> Row | None:
    cur = db().execute(
        "SELECT * FROM instruments WHERE exchange = ? AND tradingsymbol = ? "
        "AND instrument_type = 'EQ' AND segment != 'INDICES' LIMIT 1",
        (exchange, symbol),
    )
    return _row(cur.fetchone())


def _index_row(symbol: str) -> Row | None:
    cur = db().execute(
        "SELECT * FROM instruments WHERE segment = 'INDICES' AND tradingsymbol = ? "
        "ORDER BY CASE exchange WHEN 'NSE' THEN 0 ELSE 1 END LIMIT 1",
        (symbol,),
    )
    return _row(cur.fetchone())


def resolve_symbol(symbol: str, exchange: str | None = None) -> Row | None:
    """Map a human symbol to one tradable instrument row, or None."""
    sym = symbol.strip().upper()
    if not sym:
        return None
    if ":" in sym:
        return by_key(sym)
    if exchange:
        ex = exchange.upper()
        row = by_key(f"{ex}:{sym}")
        if row is not None:
            return row
        if ex in DERIVATIVE_EXCHANGES:
            return _first_future(sym, ex)
        return None
    alias = INDEX_SPOT_KEYS.get(sym.replace(" ", ""))
    if alias:
        row = by_key(alias)
        if row is not None:
            return row
    for ex in ("NSE", "BSE"):
        row = _equity(sym, ex)
        if row is not None:
            return row
    row = _index_row(sym)
    if row is not None:
        return row
    for ex in _FUTURE_EXCHANGE_ORDER:
        row = _first_future(sym, ex)
        if row is not None:
            return row
    return None


def lookup(ref: str | int) -> Row:
    """Resolve a key ('NSE:INFY'), an instrument_token or a plain symbol; raise if none match."""
    row: Row | None
    if isinstance(ref, int) or (isinstance(ref, str) and ref.strip().isdigit()):
        row = by_token(int(ref))
    else:
        row = resolve_symbol(str(ref))
    if row is None:
        raise InstrumentNotFound(
            f"No instrument matches {ref!r}. Try search_instruments({str(ref)!r}) or an "
            "exchange-qualified key like 'NSE:INFY' / 'MCX:GOLD25DECFUT'."
        )
    return row


def search_instruments(
    query: str,
    exchange: str | None = None,
    instrument_type: str | None = None,
    limit: int = 20,
    include_expired: bool = False,
) -> list[Row]:
    """Substring search over tradingsymbol and name; live contracts first, nearest expiry first."""
    q = f"%{query.strip().upper()}%"
    live, args = _live_clause(include_expired)
    sql = "SELECT * FROM instruments WHERE (tradingsymbol LIKE ? OR name LIKE ?)" + live
    params: list[Any] = [q, q, *args]
    if exchange:
        sql += " AND exchange = ?"
        params.append(exchange.upper())
    if instrument_type:
        sql += " AND instrument_type = ?"
        params.append(instrument_type.upper())
    sql += " ORDER BY CASE WHEN expiry = '' THEN 0 ELSE 1 END, expiry, tradingsymbol LIMIT ?"
    params.append(max(1, min(int(limit), 500)))
    return _rows(db().execute(sql, params))


def derivative_exchange(name: str) -> str | None:
    """Exchange that lists derivatives for an underlying name (NFO before BFO, MCX, CDS, BCD)."""
    n = name.strip().upper()
    live, args = _live_clause(False)
    for ex in _OPTION_EXCHANGE_ORDER:
        cur = db().execute(
            "SELECT 1 FROM instruments WHERE name = ? AND exchange = ? AND instrument_type IN "
            f"('CE','PE','FUT'){live} LIMIT 1",
            (n, ex, *args),
        )
        if cur.fetchone() is not None:
            return ex
    return None


def option_expiries(name: str, exchange: str | None = None) -> list[str]:
    """Live option expiries (today or later) for an underlying, nearest first."""
    n = name.strip().upper()
    ex = (exchange or derivative_exchange(n) or "").upper()
    if not ex:
        return []
    cur = db().execute(
        "SELECT DISTINCT expiry FROM instruments WHERE name = ? AND exchange = ? AND "
        "instrument_type IN ('CE','PE') AND expiry >= ? ORDER BY expiry",
        (n, ex, today_ist().isoformat()),
    )
    return [str(r[0]) for r in cur.fetchall()]


def option_contracts(name: str, expiry: str, exchange: str | None = None) -> list[Row]:
    n = name.strip().upper()
    ex = (exchange or derivative_exchange(n) or "").upper()
    cur = db().execute(
        "SELECT * FROM instruments WHERE name = ? AND exchange = ? AND expiry = ? AND "
        "instrument_type IN ('CE','PE') ORDER BY strike, instrument_type",
        (n, ex, expiry),
    )
    return _rows(cur)


def find_option_contracts(
    underlying: str,
    expiry: str | None = None,
    option_type: str | None = None,
    strike: float | None = None,
    exchange: str | None = None,
    limit: int = 50,
) -> list[Row]:
    """Option contracts of an underlying filtered by expiry, CE/PE and strike (live only)."""
    n = underlying.strip().upper()
    ex = (exchange or derivative_exchange(n) or "").upper()
    if not ex:
        return []
    sql = (
        "SELECT * FROM instruments WHERE name = ? AND exchange = ? "
        "AND instrument_type IN ('CE','PE') AND expiry >= ?"
    )
    params: list[Any] = [n, ex, today_ist().isoformat()]
    if expiry:
        sql += " AND expiry = ?"
        params.append(expiry)
    if option_type:
        sql += " AND instrument_type = ?"
        params.append(option_type.upper())
    if strike is not None:
        sql += " AND strike = ?"
        params.append(float(strike))
    sql += " ORDER BY expiry, strike, instrument_type LIMIT ?"
    params.append(max(1, min(int(limit), 1000)))
    return _rows(db().execute(sql, params))


def futures_contracts(
    name: str, exchange: str | None = None, include_expired: bool = False
) -> list[Row]:
    """Futures contracts of an underlying, nearest expiry first."""
    n = name.strip().upper()
    ex = (exchange or derivative_exchange(n) or "").upper()
    if not ex:
        return []
    live, args = _live_clause(include_expired)
    cur = db().execute(
        "SELECT * FROM instruments WHERE name = ? AND exchange = ? AND instrument_type = 'FUT'"
        f"{live} ORDER BY expiry",
        (n, ex, *args),
    )
    return _rows(cur)


def spot_key(name: str) -> str | None:
    """Quote key for an underlying's spot: index alias, else its NSE/BSE share; None for MCX/CDS."""
    n = name.strip().upper()
    alias = INDEX_SPOT_KEYS.get(n)
    if alias:
        return alias
    for ex in ("NSE", "BSE"):
        row = _equity(n, ex)
        if row is not None:
            return str(row["key"])
    return None


def list_underlyings(kind: str = "all") -> list[str]:
    """Underlying names with live options: kind = all | index | stock | commodity | currency."""
    exchanges = {
        "all": tuple(_OPTION_EXCHANGE_ORDER),
        "index": ("NFO", "BFO"),
        "stock": ("NFO", "BFO"),
        "commodity": ("MCX",),
        "currency": ("CDS", "BCD"),
    }.get(kind, tuple(_OPTION_EXCHANGE_ORDER))
    cur = db().execute(
        "SELECT DISTINCT name FROM instruments WHERE instrument_type IN ('CE','PE') "
        "AND expiry >= ? "
        f"AND exchange IN ({','.join('?' * len(exchanges))}) ORDER BY name",
        (today_ist().isoformat(), *exchanges),
    )
    names = [str(r[0]) for r in cur.fetchall()]
    if kind == "index":
        return [n for n in names if n in INDEX_SPOT_KEYS]
    if kind == "stock":
        return [n for n in names if n not in INDEX_SPOT_KEYS]
    return names
