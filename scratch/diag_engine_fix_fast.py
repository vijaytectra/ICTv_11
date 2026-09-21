"""Fast EURUSD-only WR diagnostic after engine fixes."""
from __future__ import annotations

import os
import sys
from collections import defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from backend.engine.backtester import execute_backtest
from backend.engine.data_loader import load_pair_data, resample_candles
from backend.engine.metrics import compute_win_rate
from backend.engine.strategy_setups import get_all_setup_signals

DATA_DIR = r"C:\Users\Vijayakumar R\Documents"


def main() -> None:
    print("Loading EURUSD...", flush=True)
    raw = load_pair_data(DATA_DIR, "EURUSD", sample_ratio=1.0)
    df = resample_candles(raw, "5m")
    # Focus 2025-2026 for speed while still meaningful
    df = df[df.index >= "2025-01-01"]
    print(f"  bars={len(df)} from {df.index[0]} to {df.index[-1]}", flush=True)

    print("Building signals...", flush=True)
    sigs, _ = get_all_setup_signals(df, "EURUSD", min_rr=2.0, return_indicators=True)
    print(f"  signals={len(sigs)}", flush=True)

    by_setup = defaultdict(list)
    for s in sigs:
        by_setup[int(s["setup_id"])].append(s)

    print("\n=== Per-setup EURUSD 2025+ (limit-fill, no BE, 1:2) ===", flush=True)
    total_trades = []
    for sid in sorted(by_setup):
        r = execute_backtest(
            df,
            by_setup[sid],
            "EURUSD",
            starting_balance=10_000.0,
            risk_percent=1.0,
            enable_breakeven=False,
        )
        m = compute_win_rate(r["trades"])
        filled = r["total_trades"]
        skipped = len(by_setup[sid]) - filled
        print(
            f"  setup {sid}: signals={len(by_setup[sid])} filled={filled} "
            f"unfilled~={skipped} resolved={m['resolved']} wr={m['wr']:.1%} "
            f"flat={m['excluded']} net={r['net_profit']}",
            flush=True,
        )
        total_trades.extend(r["trades"])

    m_all = compute_win_rate(total_trades)
    print(
        f"\nALL setups combined: resolved={m_all['resolved']} wr={m_all['wr']:.1%} "
        f"excluded={m_all['excluded']}",
        flush=True,
    )


if __name__ == "__main__":
    main()
