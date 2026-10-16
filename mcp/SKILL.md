---
name: slash-markets-kite-data
description: Query a live Zerodha (Kite Connect) account and Indian market data by writing Python through the Slash Markets Kite connector. Use for anything about the user's positions, holdings, funds, orders, trades, mutual funds or GTTs, and for NSE/BSE stocks and indices, NFO/BFO index and stock F&O, MCX commodities and CDS/BCD currency — prices and depth, intraday and daily candles, indicators (EMA/RSI/MACD/Bollinger/ATR/VWAP), option chains with computed greeks, expiries, continuous futures — and for arming e-mail watchers. Trigger on P&L questions, "what is X trading at", trend/outlook/levels, NIFTY/BANKNIFTY/SENSEX or any F&O stock, option IV/OI/max-pain, GOLD/CRUDEOIL/USDINR, "alert me when…".
---

# Slash Markets Kite data via Python

You have one data tool: **`run_python(code)`**. It executes your Python on Slash Markets'
server, where the user's Kite session is already wired in through a local gateway,
and returns whatever the script printed. The data never enters your context unless
you print it, so for any question that needs more than one number write a script
and **print the conclusion**, not the rows.

Two more tools exist: `auth_status` (who is signed in, whether the Zerodha session
is usable, the web-app link) and the watcher pair `create_watcher` / `list_watchers`.

## Model the question as a function

The user's question is a function specification. Write that function, run it
once, print the answer. Before writing anything, ask: *what would a single
function that answers this whole question look like?* Then write that function,
including every decision you would otherwise make by reading intermediate output.

**The anti-pattern**: using the tool as a remote procedure call.

```python
pp(z.option_chain("NIFTY"))  # 21 strikes into your context, you find ATM…
pp(z.option_candles(11234, 15))  # …then 50 bars more
```

Two round trips, thousands of tokens of rows, and the user asked one sentence.

**Composed**: same question, one call, the data stays on the server.

```python
import json, zapkite as z


def answer():
    ch = z.option_chain("NIFTY", strikes_around=3)
    spot = ch["spot"]
    atm = min(ch["strikes"], key=lambda r: abs(r["strike"] - spot))
    ce = atm["ce"]
    if not ce:
        return f"no CE quote at {atm['strike']:.0f}"
    bars = z.option_candles(ce["key"], 15, days_back=1)
    if not bars:
        return f"{ce['tradingsymbol']}: no bars today (holiday or pre-open)"
    first, last = bars[0]["close"], bars[-1]["close"]
    oi_chg = bars[-1].get("oi", 0) - bars[0].get("oi", 0)
    return (
        f"{ce['tradingsymbol']} ({ch['expiry']}): {first} -> {last} "
        f"({(last / first - 1) * 100:+.1f}%), OI {oi_chg:+,}, IV {ce['iv']:.1%}, "
        f"delta {ce['delta']:.2f}, spot {spot}"
    )


print(answer())
```

```
NIFTY25OCT24700CE (2026-10-27): 194.15 -> 108.0 (-44.4%), OI +9,224,215, IV 15.2%, delta 0.53, spot 24712.5
```

Writing it as `def answer():` is a useful habit: it makes early returns available
for the empty and error branches, and it forces the question to have one shape.

### Decisions go in the script

| The urge | The code |
| --- | --- |
| fetch the chain to find ATM | `min(ch["strikes"], key=lambda r: abs(r["strike"] - ch["spot"]))` |
| fetch the expiry list to pick one | `z.nearest_expiry("NIFTY")`, or `z.expiry_list("NIFTY")[1]` |
| read positions to find the worst | `min(z.positions(), key=lambda p: p["pnl"])` |
| see which strikes matter | `sorted(rows, key=lambda r: -((r["ce"] or {}).get("oi") or 0))[:3]` |
| check there is data before using it | `if not rows: return "nothing open"` |

A dependent lookup is not a reason to split a script. The sandbox reads its own
intermediate values for free; you do not.

### Be defensive, not exploratory

You cannot see the data before you write the code, so handle what might be there:
`try/except z.ZapKiteError` around a fetch that can fail, `.get(key)` for anything
optional, an explicit branch for the empty case. A script that covers the empty
account, the closed position and the missing data plan inline is one call; a
script that discovers them is three.

Loop over instruments inside the script rather than asking about them one at a
time: the whole portfolio in one pass costs the same round trip as one row.

### Print the answer, not the working

Print the conclusion and the few numbers supporting it. Candle lists, chains and
intermediate arrays stay in the sandbox. Output over 64 KB is truncated.

### When a second call is justified

A traceback you need to fix, or a genuine follow-up question from the user. Not
"now let me fetch the next thing."

## Mechanics

- Start every script with `import zapkite as z` (plus `json`, `statistics`, `math`,
  `datetime` as needed). Standard library only; no pandas, no numpy.
- A failing script returns its traceback as an error result. Read it and send a
  corrected script.
- Files persist in the working directory between calls: save big fetched data in
  one script, read it back in the next.
- Scripts are killed after 60 s by default; pass `timeout_seconds` up to 180 for
  long candle pulls.
- Each script has a budget of about 40 Kite requests (`CallBudgetExceeded`
  otherwise). Batch quote keys into one `z.ltp([...])`, keep `strikes_around` small,
  use wider candle intervals.
- Kite rate limits are shared by every Slash Markets user on one app key: quotes 1 request/s,
  candles 3/s. `RateLimited` means wait a few seconds, not retry in a loop.
- `print(z.help_api())` lists every function with its first doc line.
- Everything is read-only. There is no order placement, modification or
  cancellation anywhere. If asked to trade, say so; the user trades in Kite.

## Errors that mean something

| Exception | Meaning | What to tell the user |
| --- | --- | --- |
| `TokenExpired` | The Zerodha session ended (Kite clears every session during its overnight reset, usually 05:30–07:30 IST) or the user disconnected. | Log in to Zerodha again from the Slash Markets web app (`auth_status` gives the link). Nothing in a script can refresh it. |
| `DataPlanMissing` | Kite returned "Insufficient permission" for candles or quotes: the Connect app lacks the market-data plan. | Account reads still work; market data needs the plan. |
| `InstrumentNotFound` | No instrument matched the key, token or symbol. | Try `z.search_instruments(q)`. |
| `RateLimited` / `CallBudgetExceeded` | See Mechanics. | Fetch less, batch more. |

## Instruments: keys, symbols, markets

Kite addresses an instrument by **`EXCHANGE:TRADINGSYMBOL`** (a *key*) or by its
numeric `instrument_token`. Both work everywhere a function takes an instrument,
and so does a plain symbol, which `z.resolve_symbol` maps:

| You write | Resolves to |
| --- | --- |
| `"TCS"`, `"INFY"` | the NSE share (`NSE:TCS`); pass `exchange="BSE"` for the BSE listing |
| `"NIFTY"`, `"BANKNIFTY"`, `"FINNIFTY"`, `"SENSEX"` | the spot index (`NSE:NIFTY 50`, `BSE:SENSEX`); pass `exchange="NFO"` for the front future |
| `"GOLD"`, `"CRUDEOIL"`, `"SILVER"`, `"NATURALGAS"` | the nearest MCX future (`MCX:GOLD25DECFUT`) |
| `"USDINR"`, `"EURINR"` | the nearest CDS currency future |
| `"NFO:NIFTY25OCT24700CE"`, `"MCX:GOLD25DECFUT"` | used as-is |

Exchanges served: `NSE`, `BSE` (stocks, ETFs, indices), `NFO`, `BFO` (index and
stock futures and options), `MCX` (commodities), `CDS`, `BCD` (currency). Option
*underlyings* are plain names (`NIFTY`, `RELIANCE`, `GOLD`, `USDINR`);
`z.list_underlyings("index" | "stock" | "commodity" | "currency")` lists them.

```python
z.resolve_symbol(
    symbol, exchange=None
)  # -> {key, exchange, tradingsymbol, name, instrument_token, kind, expiry, strike, lot_size} or None
z.instrument(ref)  # same row for a key / token / symbol; raises InstrumentNotFound
z.search_instruments(q, exchange=None, instrument_type=None, limit=20, include_expired=False)
z.find_option_contracts(underlying, expiry=None, option_type=None, strike=None, exchange=None)
z.futures_list(
    underlying
)  # live futures, nearest first; z.expiry_list / z.nearest_expiry for options
z.market_status()  # {now_ist, weekday, markets: {NSE: {open, hours}, MCX: …}}
```

Hours (Mon–Fri): NSE/BSE/NFO/BFO 09:15–15:30, CDS/BCD 09:00–17:00, MCX 09:00–23:30
IST. Exchange holidays are not modelled. Off-hours, quotes are the last traded
price. Money is ₹. Trading symbols in positions look like `NIFTY25OCT24700CE`
(monthly) or `NIFTY25O1624700CE` (weekly), `RELIANCE25OCTFUT`, `GOLD25DECFUT`.

## Account

```python
z.profile()               # {user_id, user_name, email, exchanges, products, …}
z.funds()                 # {equity: {net, available: {live_balance, cash, collateral, …}, utilised: {…}}, commodity: {…}}
z.positions(day=False)    # net positions: [{tradingsymbol, exchange, instrument_token, product (CNC|MIS|NRML),
                          #   quantity (negative = short), average_price, last_price, pnl, m2m, unrealised, realised,
                          #   buy_quantity, sell_quantity, …}]  quantity 0 = closed today, still listed
z.position_for("NIFTY25OCT24700CE")       # one net row or None
z.holdings()              # [{tradingsymbol, exchange, isin, quantity, average_price, last_price, pnl, day_change, …}]
z.orders()                # today's order book: [{order_id, status (COMPLETE|OPEN|REJECTED|CANCELLED), tradingsymbol,
                          #   transaction_type, quantity, filled_quantity, average_price, …}]
z.order_history(order_id) # status transitions, oldest first
z.trades()                # today's fills: [{trade_id, order_id, tradingsymbol, quantity, average_price, fill_timestamp}]
z.mf_holdings()  z.mf_orders()  z.mf_sips()  z.gtt_triggers()
z.kite_get("/user/margins/equity")        # escape hatch for any other Kite read endpoint
```

Kite returns its own field names (snake_case); pass them through rather than
renaming. P&L fields are rupees.

## Market data

```python
z.ltp(["NSE:INFY", "TCS", "NIFTY", 256265])   # -> {"NSE:INFY": 1520.5, "NSE:TCS": 3500.0, …}; keys Kite doesn't know are omitted
z.ltp_of("GOLD")                              # one float; raises InstrumentNotFound
z.ohlc([...])                                 # {key: {instrument_token, last_price, ohlc: {open, high, low, close}}}
z.quote([...])                                # {key: {last_price, volume, average_price, oi, oi_day_high, oi_day_low,
                                              #   net_change, lower_circuit_limit, upper_circuit_limit, buy_quantity,
                                              #   sell_quantity, ohlc, depth: {buy: [{price, quantity, orders}×5], sell: […]}}}

z.intraday_candles(instrument, interval=15, days_back=5, from_date=None, to_date=None, oi=None)
# interval: 1, 3, 5, 10, 15, 30, 60 (minutes). Rows oldest→newest:
# {"time": "2026-10-15T09:15:00+05:30" (bar OPEN, IST), "open", "high", "low", "close", "volume", "oi"?}
# oi is included for derivatives by default. Long windows are fetched in chunks (one Kite call each,
# Kite caps 60 days per call at 1-min up to 400 days at 60-min) — keep days_back modest.
z.daily_candles(instrument, days_back=365, …)          # day bars, up to 2000 days per call
z.continuous_futures("GOLD", days_back=365)            # rolling front-month FUTURE, daily bars only, ~1 year back
z.option_candles(contract, interval=15, days_back=5)   # premium candles with oi for one live option/future contract
```

The last intraday bar may still be forming during market hours: for indicators use
`z.closes(rows[:-1])`. Expired option contracts are not available on Kite; for
history across expiries use `continuous_futures`.

## Options

Kite has **no option-chain, expiry or greeks API**. `z.option_chain` builds the
chain from the daily instrument dump, fetches the strikes around the money in
**one** batched quote call, and computes Black-76 IV and greeks on the forward.
Say "indicative" when you quote greeks.

```python
z.expiry_list(
    "NIFTY"
)  # ["2026-10-20", "2026-10-27", …] nearest first; works for GOLD, USDINR, RELIANCE…
z.nearest_expiry("BANKNIFTY")
z.option_chain(underlying, expiry=None, strikes_around=10, exchange=None)
# -> {underlying, exchange (NFO|BFO|MCX|CDS), expiry, spot, spot_source ("spot" or "future:GOLD25DECFUT"),
#     lot_size, rate, pcr (PE OI / CE OI over the window), max_pain,
#     strikes: [{strike, ce: {...} | None, pe: {...} | None}]}
#    each side: {tradingsymbol, instrument_token, key, last_price, oi, volume, bid, ask, change,
#                iv (decimal, 0.15 = 15%), delta, gamma, theta (per day), vega (per vol point), intrinsic, time_value}
#    ONE quote call per chain; keep strikes_around ≤ 20 and at most 2 chains per question.
```

Commodity and currency chains use the front future as the spot (`spot_source`
says so). OI is contracts; multiply by `lot_size` for units.

## Indicators, dates, helpers

All indicator functions take a list of floats (use `z.closes(rows)`) and return a
list aligned to the input with `None` while warming up. Feed CLOSED bars.

```python
z.closes(rows, field="close")
z.sma(values, period)        z.ema(values, period)       z.rsi(values, period=14)
z.macd(values, 12, 26, 9)    # {"macd": [...], "signal": [...], "histogram": [...]}
z.bollinger(values, 20, 2.0) # {"upper", "middle", "lower"}
z.atr(rows, 14)              z.vwap(rows)                z.pct_change(values)
z.now()  z.today()  z.days_ago(n)  z.ymd(d)  z.to_ist(ts)  z.IST
z.pp(value, limit=4000)      z.help_api()                z.is_nan(x)
```

## Watchers

`create_watcher(symbol, label, script, check_every_minutes=1, expires_in_days=30, market="auto")`
arms an e-mail alert. The script runs in this same sandbox on the schedule during
that market's hours (auto-detected: MCX for commodities, CDS for currency, else
NSE), so keep it to one or two calls and resolve keys now, hard-coding them. Its
**last printed line must be** exactly
`{"met": true|false, "value": <number>, "detail": "<short note>"}`. It is dry-run
once at creation and rejected if the output breaks that contract. The first check
is a baseline and never alerts; one e-mail per not-met→met transition, at most
every 15 minutes. When the Zerodha session ends, watchers pause and resume by
themselves after the next login. You cannot pause, resume or cancel: always show
the user the returned `pageUrl`.

```python
# "e-mail me when NIFTY 15m RSI drops under 30"
import json, zapkite as z

rows = z.intraday_candles("NSE:NIFTY 50", 15, days_back=3)
r = z.rsi(z.closes(rows[:-1]))[-1]
print(
    json.dumps(
        {
            "met": r is not None and r < 30,
            "value": round(r, 1) if r else None,
            "detail": "NIFTY 15m RSI14",
        }
    )
)
```

## Worked examples

Each is one call: a question in, an answer out.

**"How is my portfolio doing?"**

```python
import zapkite as z

pos = [p for p in z.positions() if p["quantity"]]
hold = z.holdings()
pnl = sum(p["pnl"] for p in pos)
hp = sum(h["pnl"] for h in hold)
f = z.funds()["equity"]
print(
    f"{len(pos)} open positions, P&L ₹{pnl:,.0f} | {len(hold)} holdings, P&L ₹{hp:,.0f} | cash ₹{f['available']['live_balance']:,.0f}"
)
for p in sorted(pos, key=lambda p: p["pnl"]):
    print(
        f"  {p['tradingsymbol']:<24} {p['quantity']:>6} @ {p['average_price']:,.2f} -> {p['last_price']:,.2f}  ₹{p['pnl']:+,.0f}"
    )
```

**"Is TCS bullish?"**

```python
import zapkite as z

d = z.daily_candles("TCS", days_back=320)
c = z.closes(d)
e50, e200, r = z.ema(c, 50)[-1], z.ema(c, 200)[-1], z.rsi(c)[-1]
m = z.macd(c)["histogram"][-1]
hi = max(x["high"] for x in d[-30:])
lo = min(x["low"] for x in d[-30:])
trend = "above" if c[-1] > e50 > e200 else "below" if c[-1] < e50 < e200 else "mixed vs"
print(
    f"TCS {c[-1]:,.1f}: {trend} EMA50 {e50:,.0f}/EMA200 {e200:,.0f}, RSI14 {r:.0f}, MACD hist {m:+.1f}, "
    f"30d range {lo:,.0f}–{hi:,.0f} ({(c[-1] - lo) / (hi - lo) * 100:.0f}% of range)"
)
```

**"What are option writers positioned for this expiry?"**

```python
import zapkite as z

ch = z.option_chain("NIFTY", strikes_around=12)
rows = ch["strikes"]
oi = lambda side: lambda r: -((r[side] or {}).get("oi") or 0)
print(
    f"NIFTY {ch['spot']:,.0f} exp {ch['expiry']} | PCR {ch['pcr']} | max pain {ch['max_pain']:,.0f}"
)
print(
    "call OI walls:",
    [r["strike"] for r in sorted(rows, key=oi("ce"))[:3]],
    "| put OI walls:",
    [r["strike"] for r in sorted(rows, key=oi("pe"))[:3]],
)
atm = min(rows, key=lambda r: abs(r["strike"] - ch["spot"]))
print(
    f"ATM {atm['strike']:.0f}: CE {atm['ce']['last_price']} IV {atm['ce']['iv']:.1%} | PE {atm['pe']['last_price']} IV {atm['pe']['iv']:.1%}"
)
```

**"How has gold moved this month?"**

```python
import zapkite as z

d = z.continuous_futures("GOLD", days_back=45)
c = z.closes(d)
print(
    f"GOLD front future {c[-1]:,.0f}: {(c[-1] / c[-22] - 1) * 100:+.1f}% over 22 sessions, "
    f"range {min(c[-22:]):,.0f}–{max(c[-22:]):,.0f}, ATR14 {z.atr(d, 14)[-1]:,.0f}"
)
```

**"Which of my positions moved most today?"**

```python
import zapkite as z

pos = [p for p in z.positions() if p["quantity"]]
keys = [f"{p['exchange']}:{p['tradingsymbol']}" for p in pos]
q = z.ohlc(keys)
rows = []
for p, k in zip(pos, keys):
    o = (q.get(k) or {}).get("ohlc", {}).get("open")
    chg = (p["last_price"] / o - 1) * 100 if o else None
    rows.append((p["tradingsymbol"], p["last_price"], chg))
for sym, px, chg in sorted(rows, key=lambda r: -abs(r[2] or 0)):
    print(f"{sym:<24} {px:>10,.2f}  {'' if chg is None else f'{chg:+.2f}% today'}")
```

## Reporting back to the user

State prices and statistics exactly as returned; never fill a gap with an invented
number. Say which instrument a price is from (the NSE share, the front future, a
specific option contract) and whether the market is open. Greeks and IV are
computed, not Kite's: say "indicative". If the session has expired, say so and
send the user to the web app; do not ask for credentials in chat. Timestamps are
IST.
