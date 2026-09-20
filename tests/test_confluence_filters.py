import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.engine.confluence_filters import (
    ConfluenceFilterConfig,
    filter_signals,
    score_bar,
)


def _make_df(n: int = 30) -> pd.DataFrame:
    times = pd.date_range("2024-01-02 10:00:00", periods=n, freq="5min")  # SB window-ish
    df = pd.DataFrame(
        {
            "open": 1.10,
            "high": 1.101,
            "low": 1.099,
            "close": 1.100,
            "spread_pips": 0.8,
            "master_bias": 1,
            "htf_bias": 1,
            "is_london_kz": False,
            "is_ny_kz": False,
            "is_silver_bullet": True,
            "is_discount": True,
            "is_premium": False,
            "sweep_type": 0,
            "fvg_type": 1,
            "ifvg_type": 0,
            "ob_type": 1,
            "breaker_type": 0,
            "has_displacement": True,
            "pdh": 1.105,
            "pdl": 1.095,
            "eqh": np.nan,
            "eql": np.nan,
            "ash": np.nan,
            "asl": np.nan,
            "lsh": np.nan,
            "lsl": np.nan,
        },
        index=times,
    )
    df.loc[df.index[5], "sweep_type"] = 1
    return df


def test_score_bar_counts_components():
    df = _make_df()
    cfg = ConfluenceFilterConfig()
    # bar 10: sweep in lookback, fvg, ob, sb, displacement
    sc = score_bar(df, 10, "BUY", 0.0001, cfg)
    assert sc >= 4


def test_filter_rejects_wrong_array():
    df = _make_df()
    df["is_discount"] = False
    cfg = ConfluenceFilterConfig(min_confluence_score=1)
    sigs = [
        {
            "timestamp": df.index[10].strftime("%Y-%m-%d %H:%M:%S"),
            "pair": "EURUSD",
            "setup_id": 1,
            "direction": "BUY",
            "entry": 1.1000,
            "sl": 1.0990,
            "tp": 1.1020,
        }
    ]
    out = filter_signals(df, sigs, "EURUSD", cfg)
    assert out == []


def test_filter_accepts_high_score():
    df = _make_df()
    # Put close near pdh for pool point
    df["close"] = 1.1048
    cfg = ConfluenceFilterConfig(min_confluence_score=3, max_trades_per_day=5)
    ts = df.index[10].strftime("%Y-%m-%d %H:%M:%S")
    sigs = [
        {
            "timestamp": ts,
            "pair": "EURUSD",
            "setup_id": 1,
            "direction": "BUY",
            "entry": 1.1000,
            "sl": 1.0990,
            "tp": 1.1020,
        }
    ]
    out = filter_signals(df, sigs, "EURUSD", cfg)
    assert len(out) == 1
    assert out[0]["confluence_score"] >= 3


def test_max_trades_per_day():
    df = _make_df(n=40)
    df["close"] = 1.1048
    cfg = ConfluenceFilterConfig(min_confluence_score=1, max_trades_per_day=1)
    sigs = []
    for i in (10, 15, 20):
        sigs.append(
            {
                "timestamp": df.index[i].strftime("%Y-%m-%d %H:%M:%S"),
                "pair": "EURUSD",
                "setup_id": 1,
                "direction": "BUY",
                "entry": 1.1000,
                "sl": 1.0990,
                "tp": 1.1020,
            }
        )
    out = filter_signals(df, sigs, "EURUSD", cfg)
    assert len(out) == 1
