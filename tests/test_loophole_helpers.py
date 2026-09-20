import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from audit.validation.write_quality_ladder_report import filter_trades_by_spread_p95


def test_l7_spread_filter():
    trades = [
        {"outcome": "WIN", "spread_at_entry_pips": 0.5},
        {"outcome": "WIN", "spread_at_entry_pips": 0.6},
        {"outcome": "LOSS", "spread_at_entry_pips": 0.7},
        {"outcome": "LOSS", "spread_at_entry_pips": 20.0},  # outlier
    ]
    r = filter_trades_by_spread_p95(trades)
    assert r["n_excluded"] >= 1
    assert r["full"]["resolved"] == 4
    assert r["ex_high_spread"]["resolved"] == 3
