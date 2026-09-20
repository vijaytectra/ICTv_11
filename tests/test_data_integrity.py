import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from audit.validation.check_jforex_data import check_data_coverage


def _write_side(tmp_path, pair: str, side: str, start: str, periods: int, freq: str = "1min"):
    times = pd.date_range(start, periods=periods, freq=freq)
    df = pd.DataFrame(
        {
            "Time": times.strftime("%Y.%m.%d %H:%M:%S"),
            "Open": 1.1,
            "High": 1.101,
            "Low": 1.099,
            "Close": 1.1005,
            "Volume": 1,
        }
    )
    path = tmp_path / f"{pair}_1 Min_{side}_test.csv"
    df.to_csv(path, index=False)
    return path


def test_missing_bid_fails(tmp_path):
    r = check_data_coverage(str(tmp_path), ["EURUSD"], "2020-01-01", "2020-01-31")
    assert r["ok"] is False
    assert any("EURUSD" in e and "Bid" in e for e in r["errors"])


def test_bid_ask_present_short_range_ok(tmp_path):
    # Dense 1m over a few weekdays in Jan 2020
    _write_side(tmp_path, "EURUSD", "Bid", "2020-01-06 00:00:00", periods=5 * 24 * 60)
    _write_side(tmp_path, "EURUSD", "Ask", "2020-01-06 00:00:00", periods=5 * 24 * 60)
    r = check_data_coverage(
        str(tmp_path),
        ["EURUSD"],
        "2020-01-06",
        "2020-01-10",
        min_weekday_coverage=0.80,
    )
    assert r["ok"] is True, r["errors"]
    assert r["pairs"]["EURUSD"]["ask_alignment"] >= 0.95


def test_missing_ask_fails(tmp_path):
    _write_side(tmp_path, "EURUSD", "Bid", "2020-01-06 00:00:00", periods=1000)
    r = check_data_coverage(str(tmp_path), ["EURUSD"], "2020-01-06", "2020-01-10")
    assert r["ok"] is False
    assert any("Ask" in e for e in r["errors"])
