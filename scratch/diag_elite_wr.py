"""Elite setups only (1,2,4,10) + confluence filter — post engine-fix WR check."""
from __future__ import annotations

import os
import sys
from collections import defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from backend.engine.backtester import execute_backtest
from backend.engine.confluence_filters import ConfluenceFilterConfig, filter_signals
from backend.engine.data_loader import load_pair_data, resample_candles
from backend.engine.metrics import compute_win_rate
from backend.engine.strategy_setups import get_all_setup_signals

DATA_DIR = r"C:\Users\Vijayakumar R\Documents"
ELITE = [1, 2, 4, 10]


def main() -> None:
    print("Loading EURUSD...", flush=True)
    raw = load_pair_data(DATA_DIR, "EURUSD", sample_ratio=1.0)
    df = resample_candles(raw, "5m")
    df = df[df.index >= "2025-01-01"]
    print(f"  bars={len(df)}", flush=True)

    sigs, ind = get_all_setup_signals(
        df, "EURUSD", min_rr=2.0, active_setups=ELITE, return_indicators=True
    )
    print(f"  raw elite signals={len(sigs)}", flush=True)

    cfg = ConfluenceFilterConfig(
        min_confluence_score=5,
        require_displacement=True,
        require_recent_sweep=True,
        max_trades_per_day=2,
        active_setups=ELITE,
        use_ema_bias_fallback=False,
    )
    filtered = filter_signals(ind, sigs, "EURUSD", cfg)
    print(f"  confluence-filtered={len(filtered)}", flush=True)

    for label, bag in [("RAW elite", sigs), ("CONF>=5 elite", filtered)]:
        by = defaultdict(list)
        for s in bag:
            by[int(s["setup_id"])].append(s)
        print(f"\n=== {label} ===", flush=True)
        all_t = []
        for sid in sorted(by):
            r = execute_backtest(
                df, by[sid], "EURUSD", starting_balance=10_000.0,
                risk_percent=1.0, enable_breakeven=False,
            )
            m = compute_win_rate(r["trades"])
            print(
                f"  setup {sid}: n={m['resolved']} wr={m['wr']:.1%} net={r['net_profit']}",
                flush=True,
            )
            all_t.extend(r["trades"])
        m = compute_win_rate(all_t)
        print(f"  COMBINED: n={m['resolved']} wr={m['wr']:.1%}", flush=True)


if __name__ == "__main__":
    main()
