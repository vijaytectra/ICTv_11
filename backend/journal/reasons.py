"""Ops trade journal reason codes (spec §5)."""
from __future__ import annotations

REASON_CODES = [
    "HIT_TP",
    "HIT_SL",
    "HIT_BE",
    "TIME_EXIT",
    "SKIPPED_BY_USER",
    "MANUAL_MARKED_WIN",
    "MANUAL_MARKED_LOSS",
    "SPREAD_FILTER",
    "CONFLUENCE_FAIL",
    "OTHER",
]


def reason_for_backtest_outcome(outcome: str) -> str:
    o = (outcome or "").upper()
    if o == "WIN":
        return "HIT_TP"
    if o == "LOSS":
        return "HIT_SL"
    if o in ("BREAKEVEN", "BE", "FLAT"):
        return "HIT_BE"
    return "OTHER"
