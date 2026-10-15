from __future__ import annotations

import math
from types import ModuleType

import pytest

from zapkite.errors import InstrumentNotFound
from zapkite.options_math import black76_price
from zapkite.schema import reference

from .fake_kite import OPTION_IV, FakeKite


def _instrument_calls(fake: FakeKite) -> int:
    return sum(1 for r in fake.calls if r.url.path == "/instruments")


def test_account_reads(z: ModuleType) -> None:
    assert len(z.positions()) == 2
    assert z.positions(day=True)[0]["tradingsymbol"] == "INFY"
    assert z.position_for("nifty25oct24700ce")["quantity"] == 75
    assert z.position_for("INFY", "BSE") is None
    assert z.holdings()[0]["pnl"] == 3000.0
    assert z.funds()["equity"]["available"]["live_balance"] == 50000.0
    assert z.orders()[0]["status"] == "COMPLETE"
    assert z.order_history("1")[-1]["status"] == "COMPLETE"
    assert z.trades()[0]["trade_id"] == "t1"
    assert z.mf_holdings()[0]["quantity"] == 10.5
    assert z.mf_orders() == []
    assert z.mf_sips()[0]["sip_id"] == "s1"
    assert z.gtt_triggers()[0]["status"] == "active"


def test_ltp_accepts_keys_tokens_and_symbols(z: ModuleType, fake: FakeKite) -> None:
    prices = z.ltp(["NSE:INFY", "TCS", 256265, "NIFTY"])
    assert prices == {"NSE:INFY": 1520.5, "NSE:TCS": 3500.0, "NSE:NIFTY 50": 24712.5}
    assert z.ltp_of("GOLD") == 78000.0
    with pytest.raises(InstrumentNotFound):
        z.ltp_of("NSE:UNKNOWN")
    assert _instrument_calls(fake) == 1


def test_quote_calls_are_batched(z: ModuleType, fake: FakeKite) -> None:
    keys = [f"NSE:K{i}" for i in range(1500)]
    assert z.ltp(keys) == {}
    z.quote(keys[:700])
    sizes = [len(c) for c in fake.quote_calls()]
    assert sizes == [1000, 500, 500, 200]
    q = z.quote(["NSE:INFY"])["NSE:INFY"]
    assert q["depth"]["buy"][0]["price"] == 1520.45


def test_symbol_resolution(z: ModuleType, fake: FakeKite) -> None:
    assert z.resolve_symbol("tcs")["key"] == "NSE:TCS"
    assert z.resolve_symbol("TCS")["kind"] == "stock"
    assert z.resolve_symbol("TCS", exchange="BSE")["key"] == "BSE:TCS"
    assert z.resolve_symbol("NIFTY")["key"] == "NSE:NIFTY 50"
    assert z.resolve_symbol("NIFTY")["kind"] == "index"
    assert z.resolve_symbol("NIFTY 50")["instrument_token"] == 256265
    assert z.resolve_symbol("INDIA VIX")["kind"] == "index"
    assert z.resolve_symbol("GOLD")["key"] == "MCX:GOLD25DECFUT"
    assert z.resolve_symbol("GOLD")["kind"] == "commodity_future"
    assert z.resolve_symbol("USDINR")["kind"] == "currency_future"
    assert z.resolve_symbol("GOLDBEES")["kind"] == "stock"
    assert z.resolve_symbol("NIFTY", exchange="NFO")["tradingsymbol"] == "NIFTY25OCTFUT"
    assert z.resolve_symbol("NFO:NIFTY25NOVFUT")["kind"] == "future"
    assert z.resolve_symbol("NOPE") is None
    assert z.instrument(738561)["tradingsymbol"] == "RELIANCE"
    with pytest.raises(InstrumentNotFound):
        z.instrument("NOPE")
    assert _instrument_calls(fake) == 1


def test_search_hides_expired_by_default(z: ModuleType) -> None:
    live = z.search_instruments("NIFTY25O13")
    assert live == []
    expired = z.search_instruments("NIFTY25O13", include_expired=True)
    assert expired[0]["expiry"] == "2026-10-13"
    futs = z.search_instruments("NIFTY", exchange="NFO", instrument_type="FUT")
    assert [f["expiry"] for f in futs] == ["2026-10-27", "2026-11-24"]


def test_option_lookups(z: ModuleType) -> None:
    assert z.expiry_list("NIFTY") == ["2026-10-20", "2026-10-27", "2026-11-24"]
    assert z.nearest_expiry("nifty") == "2026-10-20"
    assert z.expiry_list("GOLD") == ["2026-11-26"]
    assert z.expiry_list("SENSEX") == ["2026-10-16"]
    assert z.expiry_list("TCS") == []
    with pytest.raises(InstrumentNotFound):
        z.nearest_expiry("TCS")
    rows = z.find_option_contracts("NIFTY", expiry="2026-10-20", option_type="CE", strike=24700)
    assert len(rows) == 1 and rows[0]["kind"] == "option"
    assert [f["tradingsymbol"] for f in z.futures_list("GOLD")] == ["GOLD25DECFUT", "GOLD26FEBFUT"]
    assert z.list_underlyings("index") == ["NIFTY", "SENSEX"]
    assert z.list_underlyings("stock") == ["RELIANCE"]
    assert z.list_underlyings("commodity") == ["GOLD"]
    assert z.list_underlyings("currency") == ["USDINR"]


def test_option_chain_is_derived_in_one_quote_call(z: ModuleType, fake: FakeKite) -> None:
    chain = z.option_chain("NIFTY", strikes_around=3)
    assert chain["expiry"] == "2026-10-20"
    assert chain["spot"] == 24712.5
    assert chain["spot_source"] == "spot"
    assert chain["lot_size"] == 75
    strikes = [r["strike"] for r in chain["strikes"]]
    assert strikes == [24400.0, 24500.0, 24600.0, 24700.0, 24800.0, 24900.0, 25000.0]
    quote_calls = fake.quote_calls()
    assert len(quote_calls) == 2
    assert len(quote_calls[1]) == 14
    atm = chain["strikes"][3]
    ce, pe = atm["ce"], atm["pe"]
    assert abs(ce["iv"] - OPTION_IV) < 0.01 and abs(pe["iv"] - OPTION_IV) < 0.01
    assert 0 < ce["delta"] < 1 and -1 < pe["delta"] < 0
    assert abs((ce["delta"] - pe["delta"]) - 1) < 0.02
    assert ce["theta"] < 0 and ce["vega"] > 0 and ce["gamma"] > 0
    assert ce["bid"] < ce["last_price"] < ce["ask"]
    assert ce["intrinsic"] == 12.5 and pe["intrinsic"] == 0.0
    assert chain["pcr"] is not None and chain["max_pain"] in strikes
    assert chain["rate"] == 0.07


def test_option_chain_uses_front_future_when_no_spot(z: ModuleType) -> None:
    chain = z.option_chain("GOLD", strikes_around=2)
    assert chain["spot"] == 78000.0
    assert chain["spot_source"] == "future:GOLD25DECFUT"
    assert [r["strike"] for r in chain["strikes"]] == [77000.0, 77500.0, 78000.0, 78500.0, 79000.0]
    chain = z.option_chain("USDINR", expiry="2026-10-28", strikes_around=1)
    assert chain["exchange"] == "CDS"
    with pytest.raises(InstrumentNotFound):
        z.option_chain("TCS")


def test_greeks_round_trip_price(z: ModuleType) -> None:
    f, k, t, r = 24712.5 * math.exp(0.07 * 0.02), 24700.0, 0.02, 0.07
    price = black76_price("CE", f, k, t, r, 0.2)
    from zapkite.options_math import implied_vol

    iv = implied_vol("CE", price, f, k, t, r)
    assert iv is not None and abs(iv - 0.2) < 1e-4


def test_candles_normalise_and_chunk(z: ModuleType, fake: FakeKite) -> None:
    bars = z.intraday_candles("INFY", 15, days_back=3)
    assert bars[0]["time"].endswith("+05:30")
    assert set(bars[0]) == {"time", "open", "high", "low", "close", "volume"}
    assert [c["time"] for c in bars] == sorted(c["time"] for c in bars)
    calls = fake.historical_calls()
    assert calls[-1]["interval"] == "15minute" and calls[-1]["oi"] == "0"
    assert calls[-1]["token"] == 408065

    fake.calls.clear()
    bars = z.intraday_candles("NFO:NIFTY25OCTFUT", "5m", days_back=250)
    calls = fake.historical_calls()
    assert len(calls) == 3
    assert all(c["oi"] == "1" and c["interval"] == "5minute" for c in calls)
    assert calls[0]["from"] == "2026-02-07 00:00:00" and calls[-1]["to"] == "2026-10-15 23:59:59"
    assert "oi" in bars[0]
    assert len({b["time"] for b in bars}) == len(bars)

    fake.calls.clear()
    z.daily_candles("TCS", days_back=10, oi=True)
    assert fake.historical_calls()[0]["interval"] == "day"
    assert fake.historical_calls()[0]["oi"] == "1"

    fake.calls.clear()
    z.continuous_futures("GOLD", days_back=30)
    call = fake.historical_calls()[0]
    assert call["token"] == 9101 and call["continuous"] == "1" and call["interval"] == "day"

    token = z.find_option_contracts("NIFTY", expiry="2026-10-20", strike=24700)[0][
        "instrument_token"
    ]
    fake.calls.clear()
    z.option_candles(token, 15, days_back=2)
    assert fake.historical_calls()[0]["token"] == token

    with pytest.raises(ValueError):
        z.intraday_candles("INFY", "2m")
    with pytest.raises(ValueError):
        z.intraday_candles("INFY", "day")
    with pytest.raises(ValueError):
        z.daily_candles("INFY", from_date="2026-10-10", to_date="2026-10-01")


def test_market_status(z: ModuleType) -> None:
    s = z.market_status("2026-10-15 10:00:00")
    assert (
        s["markets"]["NSE"]["open"] and s["markets"]["MCX"]["open"] and s["markets"]["CDS"]["open"]
    )
    s = z.market_status("2026-10-15 16:00:00")
    assert (
        not s["markets"]["NSE"]["open"]
        and s["markets"]["CDS"]["open"]
        and s["markets"]["MCX"]["open"]
    )
    s = z.market_status("2026-10-18 10:00:00")
    assert not any(m["open"] for m in s["markets"].values())
    assert z.today() == "2026-10-15" and z.days_ago(5) == "2026-10-10"
    assert z.to_ist("2026-10-15T09:15:00+0530").hour == 9


def test_indicators(z: ModuleType) -> None:
    assert z.sma([1, 2, 3, 4], 2) == [None, 1.5, 2.5, 3.5]
    e = z.ema([1, 2, 3, 4, 5], 3)
    assert e[:2] == [None, None] and e[2] == 2.0 and e[-1] is not None
    assert z.rsi(list(range(1, 20)), 14)[-1] == 100.0
    m = z.macd([float(i) for i in range(60)])
    assert set(m) == {"macd", "signal", "histogram"} and m["histogram"][-1] is not None
    b = z.bollinger([1.0, 2.0, 3.0, 4.0], 2)
    assert b["middle"] == z.sma([1.0, 2.0, 3.0, 4.0], 2)
    candles = [{"high": 10 + i, "low": 9 + i, "close": 9.5 + i, "volume": 100} for i in range(20)]
    assert z.atr(candles, 14)[-1] is not None
    assert z.vwap(candles)[0] == pytest.approx(9.5)
    assert z.pct_change([100.0, 110.0]) == [None, pytest.approx(10.0)]
    assert z.closes(candles)[0] == 9.5
    assert z.is_nan(None) and not z.is_nan(1.0)


def test_schema_covers_every_function(z: ModuleType) -> None:
    text = reference(brief=True)
    for name in z.__all__:
        obj = getattr(z, name)
        if callable(obj) and not isinstance(obj, type):
            assert f"- {name}(" in text, name
    assert "Row" not in text
    assert len(text) < 8000
    assert "option_chain(" in z.help_api()


def test_pp_truncates(z: ModuleType, capsys: pytest.CaptureFixture[str]) -> None:
    z.pp({"a": "x" * 50}, limit=20)
    out = capsys.readouterr().out
    assert "more chars" in out and len(out) < 80
