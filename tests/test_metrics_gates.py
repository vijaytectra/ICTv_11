import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.engine.metrics import (
    binomial_wilson_ci,
    compute_win_rate,
    evaluate_gates,
    trades_per_week,
)


def test_win_rate_excludes_breakeven():
    trades = [
        {"outcome": "WIN"},
        {"outcome": "WIN"},
        {"outcome": "LOSS"},
        {"outcome": "BREAKEVEN"},
    ]
    m = compute_win_rate(trades)
    assert m["wins"] == 2
    assert m["losses"] == 1
    assert m["excluded"] == 1
    assert abs(m["wr"] - (2 / 3)) < 1e-9


def test_trades_per_week():
    trades = [
        {"entry_time": "2024-01-01 10:00:00"},
        {"entry_time": "2024-01-02 10:00:00"},
        {"entry_time": "2024-01-08 10:00:00"},
    ]
    # 14 days = 2 weeks, 3 trades => 1.5 / week
    tpw = trades_per_week(trades, "2024-01-01", "2024-01-14")
    assert abs(tpw - 1.5) < 1e-9


def test_evaluate_gates_pass():
    metrics = {"wr": 0.82, "trades_per_week": 9.0, "resolved": 60}
    g = evaluate_gates(metrics)
    assert g["all_pass"] is True


def test_evaluate_gates_fail_wr():
    metrics = {"wr": 0.70, "trades_per_week": 9.0, "resolved": 60}
    g = evaluate_gates(metrics)
    assert g["all_pass"] is False
    assert g["win_rate"]["pass"] is False


def test_wilson_ci_bounds():
    lo, hi = binomial_wilson_ci(40, 50)
    assert 0.0 <= lo <= 0.8 <= hi <= 1.0
