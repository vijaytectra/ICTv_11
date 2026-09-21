"""W4: Track A 2024-2026 EURUSD without setup #6."""
from __future__ import annotations

import json
import os
import sys
from collections import Counter, defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from backend.engine.metrics import binomial_wilson_ci, compute_win_rate
from backend.engine.portfolio_backtest import run_portfolio
from backend.engine.strategy_setups import get_all_setup_signals

CACHE = os.path.join(ROOT, "scratch", "cache_5m_ny", "EURUSD_5m_ny.parquet")


def main():
    import pandas as pd

    df = pd.read_parquet(CACHE)
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC").tz_convert("America/New_York")
    df = df.loc["2023-06-01":"2026-09-21"]
    print(f"bars={len(df)}", flush=True)
    accepted = get_all_setup_signals(
        df,
        "EURUSD",
        min_rr=2.0,
        active_setups=[1, 2, 3, 4, 5, 9, 10],
        use_narrative=False,
        kz_table="mentorship_2017",
        fvg_require_displacement_candle=True,
        liquidity_model="session_pools",
    )
    val = [s for s in accepted if "2024-01-01" <= s["timestamp"][:10] <= "2026-09-17"]
    print(f"val_sigs={len(val)} by_setup={dict(Counter(int(s['setup_id']) for s in val))}", flush=True)
    res = run_portfolio(
        {"EURUSD": df},
        {"EURUSD": val},
        start="2024-01-01",
        end="2026-09-17",
        starting_balance=10_000.0,
        risk_percent=1.0,
        max_slippage_pips=0.5,
        commission_per_lot=3.5,
        max_portfolio_open=3,
        max_trades_per_day=5,
        enable_breakeven=False,
        enable_usd_block=False,
    )
    m = compute_win_rate(res.get("trades", []))
    ci = binomial_wilson_ci(m["wins"], m["resolved"])
    buckets = defaultdict(lambda: {"wins": 0, "losses": 0})
    for t in res.get("trades", []):
        sid = int(t.get("setup_id", -1))
        o = str(t.get("outcome", "")).upper()
        if o == "WIN":
            buckets[sid]["wins"] += 1
        elif o == "LOSS":
            buckets[sid]["losses"] += 1
    by_setup = {}
    for sid, b in sorted(buckets.items()):
        n = b["wins"] + b["losses"]
        by_setup[sid] = {**b, "resolved": n, "wr": (b["wins"] / n) if n else None}
    out = {
        "label": "W4_2024_2026_no_setup6",
        "resolved": m["resolved"],
        "wins": m["wins"],
        "losses": m["losses"],
        "wr": m["wr"],
        "wilson_95": ci,
        "net_pnl": res.get("net_pnl"),
        "val_signals": len(val),
        "wr_by_setup": by_setup,
    }
    print(json.dumps(out, indent=2, default=str), flush=True)
    path = os.path.join(ROOT, "scratch", "phase2_w4.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, default=str)
    print(f"Wrote {path}", flush=True)


if __name__ == "__main__":
    main()
