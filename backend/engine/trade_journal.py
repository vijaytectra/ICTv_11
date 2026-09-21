"""
Research trade / rejection journals + offline missed-winner analysis.

Hypothetical 2R outcomes are for analysis only — never feed back into live decisions.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


def append_jsonl(path: str, row: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, default=str) + "\n")


def narrative_to_dict(nar) -> Dict[str, Any]:
    if nar is None:
        return {}
    raid = nar.raid
    return {
        "htf_bias": nar.htf_bias,
        "session": nar.session,
        "is_discount": nar.is_discount,
        "is_premium": nar.is_premium,
        "raid_grade": nar.raid_grade,
        "liquidity_event_id": nar.liquidity_event_id,
        "has_displacement": nar.has_displacement,
        "has_mss": nar.has_mss,
        "draw_on_liquidity": nar.draw_on_liquidity,
        "opposing_liquidity": nar.opposing_liquidity,
        "raid_timestamp": raid.timestamp if raid else None,
        "raid_price": raid.price if raid else None,
    }


def record_acceptance(
    path: str,
    trade: Dict[str, Any],
    validation: Any,
) -> None:
    row = {
        "kind": "ACCEPT",
        **{k: trade.get(k) for k in (
            "timestamp", "pair", "setup_id", "setup_name", "direction",
            "entry", "sl", "tp", "rr", "event_id",
        )},
        "reason": getattr(validation, "reason", "ACCEPTED"),
        "narrative": narrative_to_dict(getattr(validation, "narrative", None)),
    }
    append_jsonl(path, row)


def record_rejection(
    path: str,
    candidate: Dict[str, Any],
    reason: str,
    narrative: Any = None,
) -> None:
    row = {
        "kind": "REJECT",
        **candidate,
        "rejection_reason": reason,
        "narrative": narrative_to_dict(narrative),
    }
    append_jsonl(path, row)


def hypothetical_2r_outcome(
    df: pd.DataFrame,
    signal_idx: int,
    direction: str,
    entry: float,
    sl: float,
    rr: float = 2.0,
    max_bars: int = 1440,
) -> str:
    """
    Offline what-if: if limit filled next bars, would TP (2R) or SL hit first?
    Returns WIN / LOSS / UNFILLED / FLAT. Never used for live filtering.
    """
    if signal_idx + 1 >= len(df):
        return "UNFILLED"
    risk = abs(entry - sl)
    if risk <= 0:
        return "UNFILLED"
    tp = entry + rr * risk if direction == "BUY" else entry - rr * risk
    highs = df["high"].values
    lows = df["low"].values
    fill_idx = None
    for k in range(signal_idx + 1, min(len(df), signal_idx + 1 + 72)):
        if direction == "BUY" and lows[k] <= entry:
            fill_idx = k
            break
        if direction == "SELL" and highs[k] >= entry:
            fill_idx = k
            break
    if fill_idx is None:
        return "UNFILLED"
    end = min(len(df), fill_idx + max_bars)
    for k in range(fill_idx, end):
        if direction == "BUY":
            if lows[k] <= sl:
                return "LOSS"
            if highs[k] >= tp:
                return "WIN"
        else:
            if highs[k] >= sl:
                return "LOSS"
            if lows[k] <= tp:
                return "WIN"
    return "FLAT"


def analyze_missed_winners(
    rejections: List[Dict[str, Any]],
    frames: Dict[str, pd.DataFrame],
) -> List[Dict[str, Any]]:
    """Find rejected A/B candidates that would have been WIN at 2R offline."""
    missed = []
    for r in rejections:
        if r.get("raid_grade") not in ("A", "B") and r.get("narrative", {}).get("raid_grade") not in ("A", "B"):
            # still check if we have entry geometry
            pass
        pair = r.get("pair")
        ts = r.get("timestamp")
        if pair not in frames or not ts:
            continue
        df = frames[pair]
        # map timestamp
        try:
            labels = df.index.strftime("%Y-%m-%d %H:%M:%S")
            time_to_idx = {t: i for i, t in enumerate(labels)}
        except Exception:
            time_to_idx = {t.strftime("%Y-%m-%d %H:%M:%S"): i for i, t in enumerate(df.index)}
        if ts not in time_to_idx:
            continue
        i = time_to_idx[ts]
        direction = r.get("direction")
        entry = r.get("entry")
        sl = r.get("sl")
        if not direction or entry is None or sl is None:
            continue
        hypo = hypothetical_2r_outcome(df, i, direction, float(entry), float(sl))
        if hypo == "WIN":
            missed.append({**r, "hypothetical_2r": hypo})
    return missed


def load_jsonl(path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        return []
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows
