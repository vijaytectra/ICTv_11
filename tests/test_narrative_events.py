"""Smoke tests for event engine + narrative validation."""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.engine.event_engine import build_events
from backend.engine.narrative import validate_trade


def _mini_df():
    times = pd.date_range("2024-01-15 03:00:00", periods=30, freq="5min", tz="America/New_York")
    n = len(times)
    close = np.linspace(1.1000, 1.1020, n)
    df = pd.DataFrame(
        {
            "open": close - 0.0001,
            "high": close + 0.0005,
            "low": close - 0.0005,
            "close": close,
            "spread_pips": 0.8,
            "sweep_type": 0,
            "sweep_quality": 0,
            "sweep_level": np.nan,
            "sweep_extreme": np.nan,
            "has_displacement": False,
            "swing_high": np.nan,
            "swing_low": np.nan,
            "fvg_type": 0,
            "fvg_top": np.nan,
            "fvg_bottom": np.nan,
            "breaker_type": 0,
            "breaker_top": np.nan,
            "breaker_bottom": np.nan,
            "ob_type": 0,
            "master_bias": 1,
            "is_discount": True,
            "is_premium": False,
            "eq_level": 1.1010,
            "pdh": 1.1080,
            "pdl": 1.0950,
            "ash": np.nan,
            "asl": np.nan,
            "lsh": np.nan,
            "lsl": np.nan,
            "eqh": np.nan,
            "eql": np.nan,
            "is_london_kz": True,
            "is_ny_kz": False,
            "is_silver_bullet": False,
            "is_asian_range": False,
        },
        index=times,
    )
    # Plant a major SSL raid + displacement + bullish FVG
    df.loc[times[5], "sweep_type"] = 1
    df.loc[times[5], "sweep_quality"] = 2
    df.loc[times[5], "sweep_level"] = 1.0990
    df.loc[times[5], "sweep_extreme"] = 1.0985
    df.loc[times[7], "has_displacement"] = True
    df.loc[times[7], "open"] = 1.0990
    df.loc[times[7], "close"] = 1.1015
    df.loc[times[10], "fvg_type"] = 1
    df.loc[times[10], "fvg_top"] = 1.1010
    df.loc[times[10], "fvg_bottom"] = 1.1000
    return df


def test_build_events_emits_raid():
    df = _mini_df()
    events = build_events(df, pair="EURUSD")
    types = {e.event_type for e in events}
    assert "LIQUIDITY_SWEPT" in types
    assert "DISPLACEMENT" in types
    assert "FVG_CREATED" in types


def test_validate_rejects_duplicate_event():
    df = _mini_df()
    events = build_events(df, pair="EURUSD")
    used = set()
    i = 10
    entry = 1.1005
    sl = 1.0980
    v1 = validate_trade(df, i, "BUY", entry, sl, 2.0, events, used, pip_size=0.0001)
    assert v1.ok, v1.reason
    used.add(v1.event_id)
    v2 = validate_trade(df, i, "BUY", entry, sl, 2.0, events, used, pip_size=0.0001)
    assert not v2.ok
    assert v2.reason == "DUPLICATE_EVENT"
