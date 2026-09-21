"""Regression: limit fills + fixed 1:2 RR geometry must stay honest."""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.engine.backtester import execute_backtest
from backend.engine.data_loader import get_pip_size


def test_fill_preserves_rr_geometry_buy():
    times = pd.date_range("2024-01-02 10:00:00", periods=40, freq="5min")
    close = np.full(40, 1.1000)
    high = np.full(40, 1.1005)
    low = np.full(40, 1.0995)
    # Revisit limit after signal bar, then run to TP
    high[5:] = 1.1035
    df = pd.DataFrame(
        {
            "open": close,
            "high": high,
            "low": low,
            "close": close,
            "spread_pips": 1.0,
        },
        index=times,
    )
    sig = {
        "timestamp": times[0].strftime("%Y-%m-%d %H:%M:%S"),
        "pair": "EURUSD",
        "setup_id": 1,
        "setup_name": "Test",
        "direction": "BUY",
        "entry": 1.1000,
        "sl": 1.0990,
        "tp": 1.1020,
        "rr": 2.0,
    }
    res = execute_backtest(
        df,
        [sig],
        "EURUSD",
        starting_balance=10_000.0,
        max_slippage_pips=0.5,
        enable_breakeven=False,
    )
    assert res["total_trades"] == 1
    t = res["trades"][0]
    risk = t["entry_price"] - t["sl_price"]
    reward = t["tp_price"] - t["entry_price"]
    assert risk > 0
    assert abs(reward / risk - 2.0) < 1e-6
    # Limit fill + slippage (do not re-add full spread on top of working limit)
    assert t["entry_price"] >= sig["entry"]
    assert t["outcome"] == "WIN"
    assert t.get("limit_fill") is True


def test_unfilled_limit_is_not_a_trade():
    times = pd.date_range("2024-01-02 10:00:00", periods=30, freq="5min")
    # Price never returns to limit 1.1000 (stays above)
    close = np.full(30, 1.1015)
    df = pd.DataFrame(
        {
            "open": close,
            "high": close + 0.0003,
            "low": close - 0.0003,
            "close": close,
            "spread_pips": 1.0,
        },
        index=times,
    )
    sig = {
        "timestamp": times[0].strftime("%Y-%m-%d %H:%M:%S"),
        "pair": "EURUSD",
        "setup_id": 1,
        "setup_name": "Test",
        "direction": "BUY",
        "entry": 1.1000,
        "sl": 1.0990,
        "tp": 1.1020,
        "rr": 2.0,
    }
    res = execute_backtest(
        df, [sig], "EURUSD", starting_balance=10_000.0, enable_breakeven=False
    )
    assert res["total_trades"] == 0


def test_gate_mode_timeout_is_flat_not_winloss():
    times = pd.date_range("2024-01-02 10:00:00", periods=50, freq="5min")
    close = np.full(50, 1.1000)
    df = pd.DataFrame(
        {
            "open": close,
            "high": close + 0.0002,
            "low": close - 0.0002,
            "close": close,
            "spread_pips": 0.8,
        },
        index=times,
    )
    sig = {
        "timestamp": times[0].strftime("%Y-%m-%d %H:%M:%S"),
        "pair": "EURUSD",
        "setup_id": 1,
        "setup_name": "Test",
        "direction": "BUY",
        "entry": 1.1000,
        "sl": 1.0900,
        "tp": 1.1200,
        "rr": 2.0,
    }
    res = execute_backtest(
        df, [sig], "EURUSD", starting_balance=10_000.0, enable_breakeven=False
    )
    assert res["trades"][0]["outcome"] == "FLAT"
    assert res["trades"][0]["timed_out"] is True
