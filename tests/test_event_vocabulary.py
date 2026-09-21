"""H1 event vocabulary tests — causal emitters, no lookahead."""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.engine.event_engine import build_events


def _base(n=40):
    times = pd.date_range("2024-01-15 02:00:00", periods=n, freq="5min", tz="America/New_York")
    close = np.linspace(1.1000, 1.1050, n)
    df = pd.DataFrame(
        {
            "open": close - 0.0001,
            "high": close + 0.0004,
            "low": close - 0.0004,
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
            "fvg_mitigated": False,
            "fvg_invalidated": False,
            "breaker_type": 0,
            "breaker_top": np.nan,
            "breaker_bottom": np.nan,
            "pdh": 1.1060,
            "pdl": 1.0980,
            "ash": np.nan,
            "asl": np.nan,
            "eqh": np.nan,
            "eql": np.nan,
            "is_london_kz": True,
            "is_ny_kz": False,
            "is_silver_bullet": False,
        },
        index=times,
    )
    return df, times


def test_liquidity_created_on_new_pdh():
    df, times = _base()
    df.loc[times[0], "pdh"] = 1.1060
    df.loc[times[5], "pdh"] = 1.1070  # new PDH
    events = build_events(df, pair="EURUSD")
    created = [e for e in events if e.event_type == "LIQUIDITY_CREATED"]
    assert any(e.meta.get("pool") == "PDH" for e in created)


def test_choch_distinct_from_mss():
    df, times = _base()
    # Prior bearish structure; bullish CHoCH without raid+disp
    df.loc[times[3], "swing_high"] = 1.1010
    df.loc[times[8], "close"] = 1.1015
    df.loc[times[8], "open"] = 1.1005
    df.loc[times[8], "high"] = 1.1016
    events = build_events(df, pair="EURUSD")
    types = {e.event_type for e in events}
    assert "CHoCH" in types
    # No MSS without raid chain
    assert "MSS" not in types or all(
        e.event_type != "MSS" or e.parent_id for e in events if e.event_type == "MSS"
    )


def test_fvg_mitigated_and_invalidated_events():
    df, times = _base()
    df.loc[times[5], "fvg_type"] = 1
    df.loc[times[5], "fvg_top"] = 1.1010
    df.loc[times[5], "fvg_bottom"] = 1.1000
    df.loc[times[5], "fvg_ce"] = 1.1005
    df.loc[times[8], "fvg_mitigated"] = True
    events = build_events(df, pair="EURUSD")
    assert any(e.event_type == "FVG_CREATED" for e in events)
    assert any(e.event_type == "FVG_MITIGATED" for e in events)

    df2, times2 = _base()
    df2.loc[times2[5], "fvg_type"] = 1
    df2.loc[times2[5], "fvg_top"] = 1.1010
    df2.loc[times2[5], "fvg_bottom"] = 1.1000
    df2.loc[times2[5], "fvg_ce"] = 1.1005
    df2.loc[times2[9], "fvg_invalidated"] = True
    events2 = build_events(df2, pair="EURUSD")
    inv = [e for e in events2 if e.event_type == "SETUP_INVALIDATED"]
    assert any(e.meta.get("reason") == "fvg_far_side_close" for e in inv)


def test_breaker_retested():
    df, times = _base()
    df.loc[times[4], "breaker_type"] = 1
    df.loc[times[4], "breaker_top"] = 1.1010
    df.loc[times[4], "breaker_bottom"] = 1.1000
    # CE = 1.1005 — touch later
    df.loc[times[10], "low"] = 1.1004
    df.loc[times[10], "high"] = 1.1006
    events = build_events(df, pair="EURUSD")
    assert any(e.event_type == "BREAKER_CREATED" for e in events)
    assert any(e.event_type == "BREAKER_RETESTED" for e in events)


def test_setup_invalidated_kz_end():
    df, times = _base(n=20)
    df["is_london_kz"] = False
    df.loc[times[2:8], "is_london_kz"] = True
    df.loc[times[3], "sweep_type"] = 1
    df.loc[times[3], "sweep_quality"] = 2
    df.loc[times[3], "sweep_extreme"] = 1.0990
    df.loc[times[3], "sweep_level"] = 1.0995
    events = build_events(df, pair="EURUSD")
    inv = [e for e in events if e.event_type == "SETUP_INVALIDATED"]
    assert any(e.meta.get("reason") == "killzone_window_end" for e in inv)


def test_no_lookahead_event_bar_idx():
    df, times = _base()
    df.loc[times[5], "sweep_type"] = 1
    df.loc[times[5], "sweep_quality"] = 2
    df.loc[times[5], "sweep_extreme"] = 1.0990
    events = build_events(df.iloc[:6], pair="EURUSD")
    # Events only on bars present; raid at 5
    assert all(e.bar_idx <= 5 for e in events)
    assert any(e.event_type == "LIQUIDITY_SWEPT" for e in events)
