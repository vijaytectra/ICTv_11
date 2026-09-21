"""Loss tag helpers."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.engine.loss_tags import tag_validate_loss, tag_trades


def test_thesis_ok_loss():
    t = {
        "outcome": "LOSS",
        "raid_grade": "B",
        "session": "LONDON_KZ",
        "setup_id": 1,
        "event_id": "EURUSD-RAID-1-10",
        "entry_price": 1.1,
        "sl_price": 1.09,
        "soft_flags": ["OTE_PRESENT"],
        "exit_reason": "HIT_SL",
    }
    r = tag_validate_loss(t)
    assert r["tag"] == "THESIS_OK"


def test_bug_grade_c():
    t = {
        "outcome": "LOSS",
        "raid_grade": "C",
        "session": "NY_KZ",
        "setup_id": 1,
        "event_id": "x",
        "entry_price": 1.1,
        "sl_price": 1.09,
    }
    r = tag_validate_loss(t)
    assert r["tag"] == "BUG"
    assert "raid_grade_not_AB" in r["reasons"]


def test_bug_killed_setup():
    t = {
        "outcome": "LOSS",
        "raid_grade": "B",
        "session": "NY_KZ",
        "setup_id": 6,
        "event_id": "x",
        "entry_price": 1.1,
        "sl_price": 1.09,
    }
    r = tag_validate_loss(t)
    assert r["tag"] == "BUG"
    assert "killed_setup_still_present" in r["reasons"]


def test_tag_trades_counts():
    trades = [
        {
            "outcome": "LOSS",
            "raid_grade": "B",
            "session": "NY_KZ",
            "setup_id": 1,
            "event_id": "a",
            "entry_price": 1.0,
            "sl_price": 0.9,
        },
        {
            "outcome": "WIN",
            "raid_grade": "B",
            "session": "NY_KZ",
            "setup_id": 1,
        },
    ]
    out = tag_trades(trades)
    assert out["counts"]["THESIS_OK"] == 1
    assert len(out["losses"]) == 1
