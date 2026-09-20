import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.engine.portfolio_backtest import run_portfolio


def _synth_pair(pair: str, start: str = "2024-01-02 08:00:00", n: int = 80) -> pd.DataFrame:
    times = pd.date_range(start, periods=n, freq="5min")
    # Gentle drift so TP/SL can resolve
    base = 1.1000 if "JPY" not in pair else 150.0
    step = 0.00015 if "JPY" not in pair else 0.02
    closes = base + np.arange(n) * step
    df = pd.DataFrame(
        {
            "open": closes,
            "high": closes + step,
            "low": closes - step * 0.5,
            "close": closes,
            "spread_pips": 0.8,
        },
        index=times,
    )
    return df


def _sig(pair: str, ts: str, direction: str = "BUY") -> dict:
    if direction == "BUY":
        entry, sl, tp = 1.1000, 1.0990, 1.1020
    else:
        entry, sl, tp = 1.1000, 1.1010, 1.0980
    if "JPY" in pair:
        entry, sl, tp = 150.00, 149.80, 150.40
    return {
        "timestamp": ts,
        "pair": pair,
        "setup_id": 1,
        "setup_name": "Test",
        "direction": direction,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "rr": 2.0,
    }


def test_max_one_open_per_pair():
    df = _synth_pair("EURUSD")
    t0 = df.index[5].strftime("%Y-%m-%d %H:%M:%S")
    t1 = df.index[6].strftime("%Y-%m-%d %H:%M:%S")
    # Two near-simultaneous signals on same pair — second should be blocked while first open
    sigs = {
        "EURUSD": [
            _sig("EURUSD", t0, "BUY"),
            _sig("EURUSD", t1, "BUY"),
        ]
    }
    res = run_portfolio(
        {"EURUSD": df},
        sigs,
        starting_balance=10_000.0,
        max_portfolio_open=3,
        enable_breakeven=False,
    )
    assert res["total_trades"] == 1


def test_max_portfolio_open_three():
    frames = {}
    sigs = {}
    pairs = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD"]
    # Same timestamp across 4 pairs — only 3 should open
    for i, pair in enumerate(pairs):
        df = _synth_pair(pair, start="2024-01-02 08:00:00")
        frames[pair] = df
        ts = df.index[5].strftime("%Y-%m-%d %H:%M:%S")
        if "JPY" in pair:
            s = _sig(pair, ts, "BUY")
        else:
            s = _sig(pair, ts, "BUY")
        sigs[pair] = [s]

    res = run_portfolio(
        frames,
        sigs,
        starting_balance=10_000.0,
        max_portfolio_open=3,
        enable_breakeven=False,
    )
    assert res["total_trades"] <= 3
    assert res["total_trades"] >= 1
