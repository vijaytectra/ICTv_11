"""Post-fix diagnostic: raw setup WR after RR/fill fixes."""
from __future__ import annotations

import os
import sys
from collections import defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from backend.engine.backtester import execute_backtest
from backend.engine.data_loader import load_pair_data, resample_candles
from backend.engine.metrics import compute_win_rate
from backend.engine.portfolio_backtest import run_portfolio
from backend.engine.strategy_setups import get_all_setup_signals

DATA_DIR = r"C:\Users\Vijayakumar R\Documents"
PAIRS = ["EURUSD", "GBPUSD", "USDJPY"]


def main() -> None:
    frames = {}
    sigs = {}
    print("Loading pairs...", flush=True)
    for p in PAIRS:
        raw = load_pair_data(DATA_DIR, p, sample_ratio=1.0)
        df = resample_candles(raw, "5m")
        frames[p] = df
        raw_sigs, _ = get_all_setup_signals(df, p, min_rr=2.0, return_indicators=True)
        sigs[p] = [s for s in raw_sigs if s["timestamp"][:4] >= "2024"]
        print(f"  {p}: {len(sigs[p])} signals 2024+", flush=True)

    print("\n=== Per-setup EURUSD 2024+ (no confluence) ===", flush=True)
    by_setup = defaultdict(list)
    for s in sigs["EURUSD"]:
        by_setup[int(s["setup_id"])].append(s)
    for sid in sorted(by_setup):
        r = execute_backtest(
            frames["EURUSD"],
            by_setup[sid],
            "EURUSD",
            starting_balance=10_000.0,
            enable_breakeven=False,
        )
        m = compute_win_rate(r["trades"])
        print(
            f"  setup {sid}: resolved={m['resolved']} wr={m['wr']:.1%} "
            f"excluded={m['excluded']} net={r['net_profit']}",
            flush=True,
        )

    print("\n=== Portfolio 3-pair 2024+ no confluence daycap=5 ===", flush=True)
    res = run_portfolio(
        frames,
        sigs,
        start="2024-01-01",
        end="2026-09-21",
        starting_balance=10_000.0,
        max_trades_per_day=5,
        enable_breakeven=False,
    )
    m = compute_win_rate(res["trades"])
    print(
        f"  resolved={m['resolved']} wr={m['wr']:.1%} excluded={m['excluded']} "
        f"tpw={res['trades_per_week']:.2f} net={res['net_pnl']:.2f}",
        flush=True,
    )


if __name__ == "__main__":
    main()
