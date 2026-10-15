"""In-process stand-in for api.kite.trade, served through httpx.MockTransport."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx

from zapkite.config import IST
from zapkite.options_math import black76_price

API_KEY = "key"
API_SECRET = "secret"
ACCESS_TOKEN = "tok"
REQUEST_TOKEN = "rt-good"
TODAY = date(2026, 10, 15)
OPTION_IV = 0.15
RATE = 0.07

SPOT_KEYS = {
    "NIFTY": "NSE:NIFTY 50",
    "BANKNIFTY": "NSE:NIFTY BANK",
    "RELIANCE": "NSE:RELIANCE",
    "SENSEX": "BSE:SENSEX",
}

PRICES: dict[str, float] = {
    "NSE:NIFTY 50": 24712.5,
    "NSE:NIFTY BANK": 55000.0,
    "NSE:INDIA VIX": 12.3,
    "NSE:TCS": 3500.0,
    "NSE:INFY": 1520.5,
    "NSE:RELIANCE": 1410.0,
    "NSE:GOLDBEES": 70.0,
    "BSE:SENSEX": 81000.0,
    "BSE:TCS": 3501.0,
    "MCX:GOLD25DECFUT": 78000.0,
    "MCX:GOLD26FEBFUT": 78500.0,
    "MCX:CRUDEOIL25OCTFUT": 5600.0,
    "CDS:USDINR25OCTFUT": 84.1,
    "NFO:NIFTY25OCTFUT": 24750.0,
    "NFO:NIFTY25NOVFUT": 24800.0,
    "NFO:RELIANCE25OCTFUT": 1415.0,
}


@dataclass
class Instrument:
    token: int
    tradingsymbol: str
    name: str
    exchange: str
    segment: str
    instrument_type: str
    expiry: str = ""
    strike: float = 0.0
    lot_size: int = 1

    @property
    def key(self) -> str:
        return f"{self.exchange}:{self.tradingsymbol}"


def _options(
    start_token: int,
    name: str,
    exchange: str,
    expiry: str,
    strikes: list[float],
    lot: int,
    code: str,
) -> list[Instrument]:
    out: list[Instrument] = []
    tok = start_token
    for s in strikes:
        for typ in ("CE", "PE"):
            label = f"{s:g}".replace(".", "_")
            out.append(
                Instrument(
                    tok,
                    f"{name}{code}{label}{typ}",
                    name,
                    exchange,
                    f"{exchange}-OPT",
                    typ,
                    expiry,
                    s,
                    lot,
                )
            )
            tok += 1
    return out


def build_instruments() -> list[Instrument]:
    rows: list[Instrument] = [
        Instrument(2953217, "TCS", "TATA CONSULTANCY SERV LT", "NSE", "NSE", "EQ"),
        Instrument(408065, "INFY", "INFOSYS", "NSE", "NSE", "EQ"),
        Instrument(738561, "RELIANCE", "RELIANCE INDUSTRIES", "NSE", "NSE", "EQ"),
        Instrument(1234, "GOLDBEES", "NIPPON INDIA ETF GOLD BEES", "NSE", "NSE", "EQ"),
        Instrument(532540, "TCS", "TATA CONSULTANCY SERV LT", "BSE", "BSE", "EQ"),
        Instrument(256265, "NIFTY 50", "NIFTY 50", "NSE", "INDICES", "EQ"),
        Instrument(260105, "NIFTY BANK", "NIFTY BANK", "NSE", "INDICES", "EQ"),
        Instrument(264969, "INDIA VIX", "INDIA VIX", "NSE", "INDICES", "EQ"),
        Instrument(265, "SENSEX", "SENSEX", "BSE", "INDICES", "EQ"),
        Instrument(9001, "NIFTY25OCTFUT", "NIFTY", "NFO", "NFO-FUT", "FUT", "2026-10-27", 0, 75),
        Instrument(9002, "NIFTY25NOVFUT", "NIFTY", "NFO", "NFO-FUT", "FUT", "2026-11-24", 0, 75),
        Instrument(
            9003, "RELIANCE25OCTFUT", "RELIANCE", "NFO", "NFO-FUT", "FUT", "2026-10-27", 0, 500
        ),
        Instrument(9101, "GOLD25DECFUT", "GOLD", "MCX", "MCX-FUT", "FUT", "2026-12-04", 0, 100),
        Instrument(9102, "GOLD26FEBFUT", "GOLD", "MCX", "MCX-FUT", "FUT", "2027-02-05", 0, 100),
        Instrument(
            9103, "CRUDEOIL25OCTFUT", "CRUDEOIL", "MCX", "MCX-FUT", "FUT", "2026-10-19", 0, 100
        ),
        Instrument(
            9201, "USDINR25OCTFUT", "USDINR", "CDS", "CDS-FUT", "FUT", "2026-10-28", 0, 1000
        ),
        Instrument(
            9301, "NIFTY25O1324000CE", "NIFTY", "NFO", "NFO-OPT", "CE", "2026-10-13", 24000, 75
        ),
    ]
    nifty_strikes = [24000.0 + 100 * i for i in range(15)]
    rows += _options(10000, "NIFTY", "NFO", "2026-10-20", nifty_strikes, 75, "25O20")
    rows += _options(11000, "NIFTY", "NFO", "2026-10-27", nifty_strikes, 75, "25OCT")
    rows += _options(12000, "NIFTY", "NFO", "2026-11-24", nifty_strikes, 75, "25NOV")
    rows += _options(
        13000, "RELIANCE", "NFO", "2026-10-27", [1300.0 + 20 * i for i in range(11)], 500, "25OCT"
    )
    rows += _options(
        14000, "SENSEX", "BFO", "2026-10-16", [80000.0 + 100 * i for i in range(21)], 20, "25O16"
    )
    rows += _options(
        15000, "GOLD", "MCX", "2026-11-26", [76000.0 + 500 * i for i in range(9)], 100, "25NOV"
    )
    rows += _options(
        16000, "USDINR", "CDS", "2026-10-28", [83.0 + 0.25 * i for i in range(9)], 1000, "25OCT"
    )
    return rows


def instruments_csv(rows: list[Instrument]) -> str:
    head = (
        "instrument_token,exchange_token,tradingsymbol,name,last_price,expiry,strike,"
        "tick_size,lot_size,instrument_type,segment,exchange"
    )
    lines = [head]
    for r in rows:
        lines.append(
            f"{r.token},{r.token // 256},{r.tradingsymbol},{r.name},0,{r.expiry},{r.strike},0.05,"
            f"{r.lot_size},{r.instrument_type},{r.segment},{r.exchange}"
        )
    return "\n".join(lines) + "\n"


def _years(expiry: str) -> float:
    close = datetime.combine(date.fromisoformat(expiry), time(15, 30), IST)
    now = datetime.combine(TODAY, time(12, 0), IST)
    return max((close - now).total_seconds() / (365 * 86400), 0.0)


@dataclass
class FakeKite:
    rows: list[Instrument] = field(default_factory=build_instruments)
    calls: list[httpx.Request] = field(default_factory=list)
    token_valid: bool = True
    data_plan: bool = True
    rate_limit_next: bool = False
    prices: dict[str, float] = field(default_factory=lambda: dict(PRICES))

    def __post_init__(self) -> None:
        self.by_key = {r.key: r for r in self.rows}

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handler)

    def client(self) -> httpx.Client:
        return httpx.Client(transport=self.transport())

    def historical_calls(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for r in self.calls:
            if r.url.path.startswith("/instruments/historical/"):
                q = parse_qs(r.url.query.decode())
                _, _, _, token, interval = r.url.path.split("/")
                out.append(
                    {
                        "token": int(token),
                        "interval": interval,
                        "from": q["from"][0],
                        "to": q["to"][0],
                        "continuous": q.get("continuous", ["0"])[0],
                        "oi": q.get("oi", ["0"])[0],
                    }
                )
        return out

    def quote_calls(self) -> list[list[str]]:
        return [
            parse_qs(r.url.query.decode()).get("i", [])
            for r in self.calls
            if r.url.path.startswith("/quote")
        ]

    def price_of(self, key: str) -> float | None:
        if key in self.prices:
            return self.prices[key]
        inst = self.by_key.get(key)
        if inst is None or inst.instrument_type not in ("CE", "PE"):
            return None
        spot_key = SPOT_KEYS.get(inst.name)
        if spot_key:
            spot = self.prices[spot_key]
            t = _years(inst.expiry)
            forward = spot * math.exp(RATE * t)
        else:
            futs = sorted(
                (r for r in self.rows if r.name == inst.name and r.instrument_type == "FUT"),
                key=lambda r: r.expiry,
            )
            forward = self.prices[futs[0].key]
            t = _years(inst.expiry)
        price = black76_price(inst.instrument_type, forward, inst.strike, t, RATE, OPTION_IV)  # type: ignore[arg-type]
        return max(round(price, 2), 0.05)

    def _quote(self, key: str, full: bool) -> dict[str, Any] | None:
        lp = self.price_of(key)
        inst = self.by_key.get(key)
        if lp is None or inst is None:
            return None
        base: dict[str, Any] = {"instrument_token": inst.token, "last_price": lp}
        if not full:
            return base
        tick = 0.05
        base.update(
            {
                "volume": 1000 + inst.token % 97,
                "average_price": lp,
                "oi": (inst.token % 13 + 1) * 1000
                if inst.instrument_type in ("CE", "PE", "FUT")
                else 0,
                "net_change": 1.5,
                "ohlc": {"open": lp, "high": lp * 1.01, "low": lp * 0.99, "close": lp},
                "depth": {
                    "buy": [{"price": round(lp - tick, 2), "quantity": 50, "orders": 2}],
                    "sell": [{"price": round(lp + tick, 2), "quantity": 50, "orders": 2}],
                },
            }
        )
        return base

    def _candles(self, start: date, end: date, interval: str, oi: bool) -> list[list[Any]]:
        out: list[list[Any]] = []
        day = start
        while day <= end:
            if day.weekday() < 5:
                times = (
                    [time(9, 15)] if interval == "day" else [time(9, 15), time(9, 30), time(9, 45)]
                )
                for i, t in enumerate(times):
                    ts = datetime.combine(day, t).strftime("%Y-%m-%dT%H:%M:%S+0530")
                    row: list[Any] = [ts, 100 + i, 101 + i, 99 + i, 100.5 + i, 1000 + i]
                    if oi:
                        row.append(5000 + i)
                    out.append(row)
            day += timedelta(days=1)
        return out

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        if request.headers.get("X-Kite-Version") != "3":
            return self._error(400, "InputException", "Missing X-Kite-Version")
        if request.url.path == "/session/token":
            return self._session(request)
        if (
            request.headers.get("Authorization") != f"token {API_KEY}:{ACCESS_TOKEN}"
            or not self.token_valid
        ):
            return self._error(403, "TokenException", "Incorrect `api_key` or `access_token`.")
        if self.rate_limit_next:
            self.rate_limit_next = False
            return self._error(429, "NetworkException", "Too many requests")
        path = urlparse(str(request.url)).path
        q = parse_qs(request.url.query.decode())
        if path == "/user/profile":
            return self._ok(
                {"user_id": "AB1234", "user_name": "Test User", "email": "t@example.com"}
            )
        if path == "/user/margins":
            return self._ok(
                {
                    "equity": {
                        "net": 50000.0,
                        "available": {"live_balance": 50000.0, "cash": 60000.0},
                    },
                    "commodity": {"net": 0.0},
                }
            )
        if path == "/portfolio/holdings":
            return self._ok(
                [
                    {
                        "tradingsymbol": "TCS",
                        "exchange": "NSE",
                        "quantity": 10,
                        "average_price": 3200.0,
                        "last_price": 3500.0,
                        "pnl": 3000.0,
                    }
                ]
            )
        if path == "/portfolio/positions":
            return self._ok(
                {
                    "net": [
                        {
                            "tradingsymbol": "NIFTY25OCT24700CE",
                            "exchange": "NFO",
                            "product": "NRML",
                            "quantity": 75,
                            "average_price": 120.0,
                            "last_price": 130.0,
                            "pnl": 750.0,
                        },
                        {
                            "tradingsymbol": "INFY",
                            "exchange": "NSE",
                            "product": "MIS",
                            "quantity": 0,
                            "average_price": 0.0,
                            "last_price": 1520.5,
                            "pnl": 40.0,
                        },
                    ],
                    "day": [
                        {
                            "tradingsymbol": "INFY",
                            "exchange": "NSE",
                            "product": "MIS",
                            "quantity": 0,
                        }
                    ],
                }
            )
        if path == "/orders":
            return self._ok([{"order_id": "1", "status": "COMPLETE", "tradingsymbol": "INFY"}])
        if path.startswith("/orders/"):
            return self._ok(
                [{"order_id": path.rsplit("/", 1)[1], "status": "OPEN"}, {"status": "COMPLETE"}]
            )
        if path == "/trades":
            return self._ok([{"trade_id": "t1", "tradingsymbol": "INFY", "quantity": 1}])
        if path == "/mf/holdings":
            return self._ok([{"fund": "Some Fund", "quantity": 10.5}])
        if path == "/mf/orders":
            return self._ok([])
        if path == "/mf/sips":
            return self._ok([{"sip_id": "s1"}])
        if path == "/gtt/triggers":
            return self._ok([{"id": 1, "status": "active"}])
        if path == "/instruments":
            return httpx.Response(
                200, text=instruments_csv(self.rows), headers={"content-type": "text/csv"}
            )
        if path in ("/quote", "/quote/ltp", "/quote/ohlc"):
            keys = q.get("i", [])
            limit = 500 if path == "/quote" else 1000
            if len(keys) > limit:
                return self._error(400, "InputException", "Too many instruments")
            data: dict[str, Any] = {}
            for k in keys:
                item = self._quote(k, full=(path == "/quote"))
                if item is not None:
                    if path == "/quote/ohlc":
                        item = {
                            "instrument_token": item["instrument_token"],
                            "last_price": item["last_price"],
                            "ohlc": {},
                        }
                    data[k] = item
            return self._ok(data)
        if path.startswith("/instruments/historical/"):
            if not self.data_plan:
                return self._error(
                    403, "PermissionException", "Insufficient permission for that call."
                )
            interval = path.rsplit("/", 1)[1]
            start = datetime.strptime(q["from"][0], "%Y-%m-%d %H:%M:%S").date()
            end = datetime.strptime(q["to"][0], "%Y-%m-%d %H:%M:%S").date()
            return self._ok(
                {"candles": self._candles(start, end, interval, q.get("oi", ["0"])[0] == "1")}
            )
        return self._error(404, "GeneralException", f"Route not found: {path}")

    def _session(self, request: httpx.Request) -> httpx.Response:
        if request.method == "DELETE":
            return self._ok(True)
        form = parse_qs(request.content.decode())
        rt = form.get("request_token", [""])[0]
        checksum = hashlib.sha256(f"{API_KEY}{rt}{API_SECRET}".encode()).hexdigest()
        if rt != REQUEST_TOKEN or form.get("checksum", [""])[0] != checksum:
            return self._error(403, "TokenException", "Invalid `request_token`.")
        return self._ok(
            {
                "user_id": "AB1234",
                "user_name": "Test User",
                "access_token": ACCESS_TOKEN,
                "login_time": "2026-10-15 09:00:00",
            }
        )

    @staticmethod
    def _ok(data: Any) -> httpx.Response:
        return httpx.Response(200, json={"status": "success", "data": data})

    @staticmethod
    def _error(status: int, error_type: str, message: str) -> httpx.Response:
        return httpx.Response(
            status,
            content=json.dumps(
                {"status": "error", "message": message, "error_type": error_type, "data": None}
            ).encode(),
            headers={"content-type": "application/json"},
        )
