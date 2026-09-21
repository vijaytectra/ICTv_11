"""Gate metrics for quality ladder PASS/FAIL evaluation."""
from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple


def compute_win_rate(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
    wins = 0
    losses = 0
    excluded = 0
    for t in trades:
        outcome = str(t.get("outcome", "")).upper()
        if outcome == "WIN":
            wins += 1
        elif outcome == "LOSS":
            losses += 1
        else:
            # BREAKEVEN / FLAT / TIME_EXIT / unknown — excluded from WR denominator
            excluded += 1
    resolved = wins + losses
    wr = (wins / resolved) if resolved > 0 else 0.0
    return {
        "wins": wins,
        "losses": losses,
        "excluded": excluded,
        "resolved": resolved,
        "wr": wr,
    }


def trades_per_week(
    trades: List[Dict[str, Any]],
    start: str,
    end: str,
    timestamp_key: str = "entry_time",
) -> float:
    """Average executed trades per ISO week over [start, end] inclusive."""
    start_d = datetime.strptime(start[:10], "%Y-%m-%d").date()
    end_d = datetime.strptime(end[:10], "%Y-%m-%d").date()
    if end_d < start_d:
        return 0.0

    # Number of ISO weeks spanning the range (at least 1)
    n_days = (end_d - start_d).days + 1
    n_weeks = max(1.0, n_days / 7.0)

    count = 0
    for t in trades:
        ts = t.get(timestamp_key) or t.get("timestamp") or t.get("entry_timestamp")
        if not ts:
            continue
        day = str(ts)[:10]
        if start[:10] <= day <= end[:10]:
            count += 1
    return count / n_weeks


def binomial_wilson_ci(
    wins: int, n: int, alpha: float = 0.05
) -> Tuple[float, float]:
    """Wilson score interval for binomial proportion."""
    if n <= 0:
        return (0.0, 0.0)
    # z for 95%
    z = 1.959963984540054
    if abs(alpha - 0.05) > 1e-9:
        # simple fallback; 95% is the study default
        z = 1.959963984540054
    p = wins / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (p + z2 / (2 * n)) / denom
    margin = (z / denom) * math.sqrt((p * (1 - p) / n) + (z2 / (4 * n * n)))
    return (max(0.0, center - margin), min(1.0, center + margin))


def evaluate_gates(
    metrics: Dict[str, Any],
    min_wr: float = 0.80,
    max_tpw: float = 12.0,
    min_tpw: float = 10.0,
    min_resolved: int = 50,
) -> Dict[str, Any]:
    wr = float(metrics.get("wr", 0.0))
    tpw = float(metrics.get("trades_per_week", 0.0))
    resolved = int(metrics.get("resolved", 0))
    gates = {
        "win_rate": {"value": wr, "threshold": min_wr, "pass": wr >= min_wr},
        "trades_per_week_max": {
            "value": tpw,
            "threshold": max_tpw,
            "pass": tpw <= max_tpw,
        },
        "trades_per_week_min": {
            "value": tpw,
            "threshold": min_tpw,
            "pass": tpw >= min_tpw,
        },
        # Back-compat alias used by older report/selection code
        "trades_per_week": {
            "value": tpw,
            "threshold": max_tpw,
            "pass": (tpw <= max_tpw) and (tpw >= min_tpw),
        },
        "min_resolved": {
            "value": resolved,
            "threshold": min_resolved,
            "pass": resolved >= min_resolved,
        },
    }
    gates["all_pass"] = all(
        g["pass"]
        for k, g in gates.items()
        if isinstance(g, dict) and "pass" in g and k != "trades_per_week"
    )
    # all_pass uses min/max separately; alias must not double-count
    gates["all_pass"] = (
        gates["win_rate"]["pass"]
        and gates["trades_per_week_max"]["pass"]
        and gates["trades_per_week_min"]["pass"]
        and gates["min_resolved"]["pass"]
    )
    return gates
