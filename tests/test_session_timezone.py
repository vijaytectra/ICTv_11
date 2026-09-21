"""Regression: EET→NY conversion and Asian session flag."""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.engine.data_loader import SOURCE_TZ, ICT_TZ, _localize_eet_to_ny
from backend.engine.ict_indicators import (
    find_institutional_liquidity_pools,
    tag_killzones,
)


def test_eet_to_ny_conversion_offset():
    # Winter EET = UTC+2; NY = UTC-5 → EET 07:00 = NY 00:00
    s = pd.Series(["2024.01.15 07:00:00"])
    # parse then localize path used by loader
    naive = pd.to_datetime(s, format="%Y.%m.%d %H:%M:%S")
    localized = naive.dt.tz_localize(SOURCE_TZ, ambiguous="infer", nonexistent="shift_forward")
    ny = localized.dt.tz_convert(ICT_TZ)
    assert str(ny.iloc[0].tz) in ("America/New_York", "US/Eastern") or "New_York" in str(ny.iloc[0].tz)
    assert ny.iloc[0].hour == 0


def test_asian_range_matches_ash_window():
    # Build NY-indexed bars spanning Asian + London
    times = pd.date_range(
        "2024-01-15 00:00:00", periods=12, freq="1h", tz="America/New_York"
    )
    df = pd.DataFrame(
        {
            "open": 1.1,
            "high": 1.101,
            "low": 1.099,
            "close": 1.1,
            "spread_pips": 1.0,
        },
        index=times,
    )
    df = tag_killzones(df)
    # Hours 0–5 inclusive → asian; hour 6+ not asian range
    assert df["is_asian_range"].iloc[0]
    assert df["is_asian_range"].iloc[5]
    assert not df["is_asian_range"].iloc[6]


def test_asian_pool_no_full_day_lookahead():
    times = pd.date_range(
        "2024-01-15 00:00:00", periods=10, freq="1h", tz="America/New_York"
    )
    high = [1.100, 1.101, 1.105, 1.102, 1.103, 1.104, 1.110, 1.109, 1.108, 1.107]
    low = [1.099, 1.098, 1.097, 1.100, 1.101, 1.102, 1.105, 1.104, 1.103, 1.102]
    df = pd.DataFrame(
        {
            "open": high,
            "high": high,
            "low": low,
            "close": high,
            "spread_pips": 1.0,
            "swing_high": float("nan"),
            "swing_low": float("nan"),
        },
        index=times,
    )
    out = find_institutional_liquidity_pools(df, pip_size=0.0001)
    # At 01:00 (bar 1), ash must not yet know the 02:00 high of 1.105
    assert out["ash"].iloc[1] == 1.101
    # After Asian ends (bar 6 = 06:00), ash should stay at Asian max (1.105 from 02:00)
    assert out["ash"].iloc[6] == 1.105
