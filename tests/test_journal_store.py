"""Ops journal store tests."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.journal import JournalStore, REASON_CODES


def test_backtest_insert_and_today(tmp_path):
    store = JournalStore(str(tmp_path / "j.db"))
    n = store.insert_from_backtest(
        [
            {
                "pair": "EURUSD",
                "setup_id": 1,
                "setup_name": "Sweep+FVG",
                "direction": "BUY",
                "entry": 1.1,
                "sl": 1.09,
                "tp": 1.12,
                "timestamp_entry": "2026-09-20 10:00:00",
                "timestamp_exit": "2026-09-20 11:00:00",
                "outcome": "WIN",
                "net_pnl": 4.0,
            }
        ]
    )
    assert n == 1
    s = store.today_summary(day="2026-09-20")
    assert s["wins"] == 1
    assert s["trades"][0]["reason_code"] == "HIT_TP"


def test_proposed_taken_win_note(tmp_path):
    store = JournalStore(str(tmp_path / "j.db"))
    tid = store.insert_proposed_from_alert(
        {
            "pair": "GBPUSD",
            "setup_id": 3,
            "setup_name": "Silver Bullet",
            "direction": "SELL",
            "entry": 1.25,
            "sl": 1.26,
            "tp": 1.23,
            "timestamp": "2026-09-20 10:05:00",
        }
    )
    assert tid is not None
    store.update_trade(tid, status="TAKEN")
    row = store.update_trade(tid, outcome="WIN", note="good SB")
    assert row["status"] == "CLOSED"
    assert row["outcome"] == "WIN"
    assert row["reason_code"] == "MANUAL_MARKED_WIN"
    assert row["note"] == "good SB"


def test_skip_reason(tmp_path):
    store = JournalStore(str(tmp_path / "j.db"))
    tid = store.insert_proposed_from_alert(
        {
            "pair": "USDJPY",
            "setup_id": 1,
            "setup_name": "Sweep+FVG",
            "direction": "BUY",
            "entry": 150.0,
            "sl": 149.5,
            "tp": 151.0,
            "timestamp": "2026-09-20 09:00:00",
        }
    )
    row = store.update_trade(tid, status="SKIPPED")
    assert row["status"] == "SKIPPED"
    assert row["reason_code"] == "SKIPPED_BY_USER"


def test_dedupe(tmp_path):
    store = JournalStore(str(tmp_path / "j.db"))
    sig = {
        "pair": "EURUSD",
        "setup_id": 1,
        "setup_name": "Sweep+FVG",
        "direction": "BUY",
        "entry": 1.1,
        "sl": 1.09,
        "tp": 1.12,
        "timestamp": "2026-09-20 10:00:00",
    }
    assert store.insert_proposed_from_alert(sig) is not None
    assert store.insert_proposed_from_alert(sig) is None


def test_csv_has_reason_and_note(tmp_path):
    store = JournalStore(str(tmp_path / "j.db"))
    store.insert_from_backtest(
        [
            {
                "pair": "EURUSD",
                "setup_id": 1,
                "setup_name": "Sweep+FVG",
                "direction": "BUY",
                "entry": 1.1,
                "sl": 1.09,
                "tp": 1.12,
                "timestamp_entry": "2026-09-20 10:00:00",
                "outcome": "LOSS",
                "net_pnl": -2.0,
                "note": "spread",
            }
        ]
    )
    csv_text = store.export_csv(date_from="2026-09-20", date_to="2026-09-20")
    assert "reason_code" in csv_text
    assert "HIT_SL" in csv_text
    assert "note" in csv_text


def test_reason_codes_list():
    assert "HIT_TP" in REASON_CODES
    assert "SKIPPED_BY_USER" in REASON_CODES
