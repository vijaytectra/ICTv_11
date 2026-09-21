"""Regression: ICT FVG 3-candle geometry must be correct."""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.engine.ict_indicators import find_fair_value_gaps


def test_bullish_and_bearish_fvg_geometry():
    # Build synthetic 3-candle bullish FVG at bar 4 and bearish at bar 8
    n = 12
    times = pd.date_range("2024-01-02 10:00:00", periods=n, freq="5min")
    high = np.full(n, 1.1000)
    low = np.full(n, 1.0990)
    open_ = (high + low) / 2
    close = (high + low) / 2
    # Bullish FVG: candle1 high=1.1000, candle3 low=1.1005 → gap
    high[2] = 1.1000
    low[2] = 1.0990
    high[3] = 1.1008
    low[3] = 1.1002
    open_[3] = 1.1002
    close[3] = 1.1008  # displacement middle
    high[4] = 1.1015
    low[4] = 1.1005  # low[4] - high[2] = 0.0005 = 5 pips

    # Bearish FVG: candle1 low=1.1020, candle3 high=1.1010
    high[6] = 1.1030
    low[6] = 1.1020
    high[7] = 1.1025
    low[7] = 1.1015
    open_[7] = 1.1025
    close[7] = 1.1015  # displacement middle
    high[8] = 1.1010
    low[8] = 1.1000  # low[6]-high[8] = 0.0010 = 10 pips

    df = pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close},
        index=times,
    )
    # Pure geometry without displacement gate
    out = find_fair_value_gaps(df, min_gap_pips=2.0, pip_size=0.0001, fvg_require_displacement_candle=False)

    assert out["fvg_type"].iloc[4] == 1
    assert abs(out["fvg_bottom"].iloc[4] - 1.1000) < 1e-9
    assert abs(out["fvg_top"].iloc[4] - 1.1005) < 1e-9
    assert abs(out["fvg_ce"].iloc[4] - 1.10025) < 1e-9

    assert out["fvg_type"].iloc[8] == -1
    assert abs(out["fvg_top"].iloc[8] - 1.1020) < 1e-9
    assert abs(out["fvg_bottom"].iloc[8] - 1.1010) < 1e-9

    # Old bug marked nearly every bar bearish via (high[i-2]-low[i]); keep density low
    assert int((out["fvg_type"] == -1).sum()) <= 3
    assert int((out["fvg_type"] == 1).sum()) >= 1


def test_fvg_ce_and_mitigation():
    n = 10
    times = pd.date_range("2024-01-02 10:00:00", periods=n, freq="5min")
    high = np.full(n, 1.1012)
    low = np.full(n, 1.1006)
    open_ = (high + low) / 2
    close = (high + low) / 2
    # candle1 / middle / candle3 for bullish FVG at bar 4
    high[2], low[2] = 1.1000, 1.0990
    high[3], low[3], open_[3], close[3] = 1.1008, 1.1002, 1.1002, 1.1008
    high[4], low[4], open_[4], close[4] = 1.1015, 1.1005, 1.1006, 1.1012
    # stay above far side (bot=1.1000) then touch CE ~1.10025
    high[5], low[5], open_[5], close[5] = 1.1010, 1.1004, 1.1008, 1.1007
    high[6], low[6], open_[6], close[6] = 1.1004, 1.1002, 1.1003, 1.10028
    df = pd.DataFrame({"open": open_, "high": high, "low": low, "close": close}, index=times)
    out = find_fair_value_gaps(df, min_gap_pips=2.0, pip_size=0.0001, fvg_require_displacement_candle=False)
    assert out["fvg_type"].iloc[4] == 1
    assert bool(out["fvg_mitigated"].iloc[6])
    assert out["fvg_lifecycle_state"].iloc[4] == "mitigated"
