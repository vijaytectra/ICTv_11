"""
Tag validate losses as BUG | THESIS_OK (offline attribution only).

BUG = engine / narrative integrity smell.
THESIS_OK = complete ICT chain; market simply hit SL / time exit.
"""
from __future__ import annotations

from typing import Any, Dict, List


def tag_validate_loss(trade: Dict[str, Any]) -> Dict[str, Any]:
    """
    Return {tag, reasons[]} for a LOSS (or flat-as-loss) trade.
    Does not change live gating.
    """
    reasons: List[str] = []
    outcome = str(trade.get("outcome", "")).upper()
    if outcome not in ("LOSS", "FLAT"):
        return {"tag": "N/A", "reasons": ["not_a_loss"]}

    grade = trade.get("raid_grade")
    session = trade.get("session")
    soft_flags = trade.get("soft_flags") or []
    setup_id = trade.get("setup_id")

    # --- BUG smells ---
    if grade not in ("A", "B"):
        reasons.append("raid_grade_not_AB")
    if not session or session == "OTHER":
        reasons.append("outside_or_missing_session")
    if trade.get("event_id") is None and trade.get("raid_grade") is None:
        reasons.append("missing_narrative_meta")
    # CE / entry anomalies
    entry = trade.get("entry_price", trade.get("entry"))
    sl = trade.get("sl_price", trade.get("sl"))
    if entry is not None and sl is not None:
        try:
            if float(entry) == float(sl):
                reasons.append("entry_equals_sl")
        except (TypeError, ValueError):
            reasons.append("bad_price_fields")
    # Setup killed as toxic still appearing would be a config bug
    if setup_id in (2, 3, 6):
        reasons.append("killed_setup_still_present")

    if reasons:
        return {"tag": "BUG", "reasons": reasons}

    # --- THESIS_OK: A/B raid, valid session, narrative present ---
    ok_reasons = [
        f"raid_grade={grade}",
        f"session={session}",
        f"setup={setup_id}",
    ]
    if "OTE_MISSING_SOFT" in soft_flags:
        ok_reasons.append("ote_missing_soft_accepted")
    if "OTE_PRESENT" in soft_flags:
        ok_reasons.append("ote_present")
    exit_reason = trade.get("exit_reason") or trade.get("reason_code") or trade.get("exit_type")
    if exit_reason:
        ok_reasons.append(f"exit={exit_reason}")
    return {"tag": "THESIS_OK", "reasons": ok_reasons}


def tag_trades(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
    rows = []
    counts = {"BUG": 0, "THESIS_OK": 0, "N/A": 0}
    for t in trades:
        if str(t.get("outcome", "")).upper() != "LOSS":
            continue
        tagged = tag_validate_loss(t)
        counts[tagged["tag"]] = counts.get(tagged["tag"], 0) + 1
        rows.append(
            {
                "pair": t.get("pair"),
                "setup_id": t.get("setup_id"),
                "timestamp": t.get("timestamp_entry") or t.get("timestamp_signal"),
                "raid_grade": t.get("raid_grade"),
                "session": t.get("session"),
                "net_pnl": t.get("net_pnl"),
                **tagged,
            }
        )
    return {"counts": counts, "losses": rows}
