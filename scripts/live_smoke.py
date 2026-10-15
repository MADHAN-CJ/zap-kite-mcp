"""Exercise zapkite against the real Kite Connect API with the credentials in .env.

Usage: uv run python scripts/live_smoke.py
Needs KITE_API_KEY and KITE_ACCESS_TOKEN (a session token from today's Kite login).
"""

from __future__ import annotations

import os
import sys
import traceback
from collections.abc import Callable
from pathlib import Path
from typing import Any

import zapkite as z
from zapkite.errors import DataPlanMissing, ZapKiteError


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def check(name: str, fn: Callable[[], Any]) -> bool:
    try:
        out = fn()
    except DataPlanMissing as e:
        print(f"SKIP {name}: {e}")
        return True
    except ZapKiteError as e:
        print(f"FAIL {name}: {e}")
        return False
    except Exception:
        print(f"FAIL {name}:")
        traceback.print_exc()
        return False
    text = str(out)
    print(f"ok   {name}: {text[:160]}{'…' if len(text) > 160 else ''}")
    return True


def main() -> int:
    load_env(Path(__file__).resolve().parents[1] / ".env")
    if not os.environ.get("KITE_API_KEY") or not os.environ.get("KITE_ACCESS_TOKEN"):
        print("Set KITE_API_KEY and KITE_ACCESS_TOKEN (or put them in .env)")
        return 2
    results = [
        check("profile", lambda: z.profile().get("user_id")),
        check("funds", lambda: z.funds().get("equity", {}).get("available")),
        check("positions", lambda: len(z.positions())),
        check("holdings", lambda: len(z.holdings())),
        check("orders", lambda: len(z.orders())),
        check(
            "market_status", lambda: {k: v["open"] for k, v in z.market_status()["markets"].items()}
        ),
        check("resolve TCS", lambda: z.instrument("TCS")["key"]),
        check("resolve NIFTY", lambda: z.instrument("NIFTY")["key"]),
        check("resolve GOLD", lambda: z.instrument("GOLD")["key"]),
        check("resolve USDINR", lambda: z.instrument("USDINR")["key"]),
        check("ltp", lambda: z.ltp(["NSE:TCS", "NIFTY", "GOLD"])),
        check("quote depth", lambda: z.quote(["NSE:INFY"])["NSE:INFY"]["depth"]["buy"][0]),
        check("expiry_list NIFTY", lambda: z.expiry_list("NIFTY")[:4]),
        check("expiry_list GOLD", lambda: z.expiry_list("GOLD")[:3]),
        check("list_underlyings commodity", lambda: z.list_underlyings("commodity")[:10]),
        check(
            "option_chain NIFTY",
            lambda: {
                k: v for k, v in z.option_chain("NIFTY", strikes_around=3).items() if k != "strikes"
            },
        ),
        check(
            "chain ATM greeks",
            lambda: z.option_chain("NIFTY", strikes_around=1)["strikes"][1]["ce"],
        ),
        check("intraday INFY 15m", lambda: len(z.intraday_candles("INFY", 15, days_back=3))),
        check("daily TCS", lambda: z.daily_candles("TCS", days_back=30)[-1]),
        check("continuous GOLD", lambda: len(z.continuous_futures("GOLD", days_back=60))),
        check(
            "rsi TCS",
            lambda: round(z.rsi(z.closes(z.daily_candles("TCS", days_back=60)))[-1] or 0, 1),
        ),
        check("mf_holdings", lambda: len(z.mf_holdings())),
    ]
    failed = results.count(False)
    print(f"\n{len(results) - failed}/{len(results)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
