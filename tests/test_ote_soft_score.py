"""H3: OTE soft_score accepts without OTE; flags/score when present."""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.engine.event_engine import build_events
from backend.engine.narrative import refine_entry_to_ce, validate_trade


def _df():
    times = pd.date_range("2024-01-15 03:00:00", periods=30, freq="5min", tz="America/New_York")
    n = len(times)
    close = np.linspace(1.1000, 1.1020, n)
    df = pd.DataFrame(
        {
            "open": close - 0.0001,
            "high": close + 0.0005,
            "low": close - 0.0005,
            "close": close,
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
            "fvg_ce": np.nan,
            "fvg_lifecycle_state": "",
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
            "ote_type": 0,
            "is_london_kz": True,
            "is_ny_kz": False,
            "is_silver_bullet": False,
            "is_asian_range": False,
        },
        index=times,
    )
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
    df.loc[times[10], "fvg_ce"] = 1.1005
    return df, times


def test_soft_accept_without_ote():
    df, times = _df()
    events = build_events(df, pair="EURUSD")
    v = validate_trade(
        df, 10, "BUY", 1.1005, 1.0980, 2.0, events, set(),
        require_ote=True, ote_mode="soft_score", pip_size=0.0001,
    )
    assert v.ok, v.reason
    assert "OTE_MISSING_SOFT" in (v.narrative.soft_flags or [])
    assert v.soft_score < 1.0


def test_ote_present_boosts_score():
    df, times = _df()
    df.loc[times[10], "ote_type"] = 1
    events = build_events(df, pair="EURUSD")
    v = validate_trade(
        df, 10, "BUY", 1.1005, 1.0980, 2.0, events, set(),
        require_ote=True, ote_mode="soft_score", pip_size=0.0001,
    )
    assert v.ok
    assert "OTE_PRESENT" in v.narrative.soft_flags
    assert v.soft_score >= 1.0


def test_refine_entry_to_ce():
    df, times = _df()
    refined = refine_entry_to_ce(df, 10, "BUY", 1.1008, prefer_ce=True)
    assert abs(refined - 1.1005) < 1e-9
