"""Geometry lock fixtures: FVG=B, CE, KZ mentorship_2017, disagreement vs SMC lookahead."""
import json
import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.engine.ict_indicators import find_fair_value_gaps, tag_killzones
from backend.engine.kz_tables import DEFAULT_KZ_TABLE, GEOMETRY_LOCK_VERSION, KZ_TABLES


FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "geometry")


def test_geometry_lock_version_and_default_kz():
    assert GEOMETRY_LOCK_VERSION == "H-2026-09-21"
    assert DEFAULT_KZ_TABLE == "mentorship_2017"
    assert "mentorship_2017" in KZ_TABLES
    assert "public_2016_2022" in KZ_TABLES
    assert "legacy_hybrid" in KZ_TABLES


def test_mentorship_silver_bullet_14_15():
    times = pd.date_range("2024-06-03 13:55:00", periods=8, freq="5min", tz="America/New_York")
    df = pd.DataFrame(
        {"open": 1.1, "high": 1.11, "low": 1.09, "close": 1.1},
        index=times,
    )
    out = tag_killzones(df, kz_table="mentorship_2017")
    # 14:00–14:55 should be SB under mentorship (14–15)
    assert bool(out.loc[times[1], "is_silver_bullet"])  # 14:00
    assert bool(out.loc[times[2], "is_silver_bullet"])  # 14:05
    # 13:55 is before 14
    assert not bool(out.loc[times[0], "is_silver_bullet"])


def test_legacy_asian_0006_vs_mentorship_2000():
    times = pd.date_range("2024-01-15 21:00:00", periods=3, freq="1h", tz="America/New_York")
    df = pd.DataFrame(
        {"open": 1.1, "high": 1.11, "low": 1.09, "close": 1.1},
        index=times,
    )
    m = tag_killzones(df.copy(), kz_table="mentorship_2017")
    leg = tag_killzones(df.copy(), kz_table="legacy_hybrid")
    assert bool(m["is_asian_range"].iloc[0])
    assert not bool(leg["is_asian_range"].iloc[0])  # 21:00 not in 00–06


def test_dst_bucharest_to_ny_sb_window_concept():
    """EEST summer: Bucharest 21:00 == NY 14:00 → SB under mentorship."""
    # Construct already-converted NY timestamps (data_loader responsibility)
    times = pd.date_range("2024-07-01 14:00:00", periods=2, freq="5min", tz="America/New_York")
    df = pd.DataFrame(
        {"open": 1.1, "high": 1.11, "low": 1.09, "close": 1.1},
        index=times,
    )
    out = tag_killzones(df, kz_table="mentorship_2017")
    assert bool(out["is_silver_bullet"].iloc[0])


def test_fixture_labels_match_oracle():
    os.makedirs(FIXTURE_DIR, exist_ok=True)
    path = os.path.join(FIXTURE_DIR, "fvg_b_labels.json")
    # Write / refresh fixture
    labels = {
        "geometry_lock_version": GEOMETRY_LOCK_VERSION,
        "fvg_law": "B",
        "cases": [
            {
                "name": "bull_wick_gap",
                "expected_fvg_type_at": 4,
                "expected_type": 1,
                "expected_ce": 1.10025,
            }
        ],
        "disagreement_vs_smc": [
            "No future pivot confirmation for FVG validity",
            "Mitigation is CE touch, not full gap fill",
        ],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(labels, f, indent=2)

    n = 8
    times = pd.date_range("2024-01-02 10:00:00", periods=n, freq="5min")
    high = np.full(n, 1.1000)
    low = np.full(n, 1.0990)
    open_ = (high + low) / 2
    close = (high + low) / 2
    high[2], low[2] = 1.1000, 1.0990
    high[3], low[3], open_[3], close[3] = 1.1008, 1.1002, 1.1002, 1.1008
    high[4], low[4] = 1.1015, 1.1005
    df = pd.DataFrame({"open": open_, "high": high, "low": low, "close": close}, index=times)
    out = find_fair_value_gaps(df, fvg_require_displacement_candle=False)
    assert out["fvg_type"].iloc[4] == 1
    assert abs(out["fvg_ce"].iloc[4] - 1.10025) < 1e-9
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    assert data["geometry_lock_version"] == GEOMETRY_LOCK_VERSION
    assert data["fvg_law"] == "B"
