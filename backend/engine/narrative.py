"""
Shared ICT narrative context + pre-trade validation (10Q).

One narrative per closed bar drives all 8 setup recipes.
OTE soft_score (Gap Closure H): missing OTE penalizes confidence, does not hard-reject.
CE: FVG-paradigm entries prefer fvg_ce; reject stale fully-invalidated FVGs.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd

from backend.engine.event_engine import MarketEvent, build_events, latest_event, latest_raid


@dataclass
class NarrativeContext:
    bar_idx: int
    timestamp: str
    htf_bias: int
    session: str
    is_discount: bool
    is_premium: bool
    dealing_high: float
    dealing_low: float
    eq_level: float
    raid: Optional[MarketEvent]
    raid_grade: str
    has_displacement: bool
    has_mss: bool
    has_choch: bool
    fvg_type: int
    fvg_top: float
    fvg_bottom: float
    fvg_ce: float
    fvg_invalidated: bool
    ob_type: int
    breaker_type: int
    breaker_top: float
    breaker_bottom: float
    liquidity_event_id: Optional[str]
    draw_on_liquidity: Optional[float]
    opposing_liquidity: Optional[float]
    in_ote: bool = False
    ote_type: int = 0
    soft_score: float = 1.0
    soft_flags: List[str] = field(default_factory=list)


@dataclass
class ValidationResult:
    ok: bool
    reason: str
    narrative: Optional[NarrativeContext] = None
    entry: float = 0.0
    sl: float = 0.0
    tp: float = 0.0
    rr: float = 2.0
    risk: float = 0.0
    event_id: Optional[str] = None
    soft_score: float = 1.0


def _session_label(df: pd.DataFrame, i: int) -> str:
    if df["is_silver_bullet"].iloc[i]:
        return "SILVER_BULLET"
    if df["is_london_kz"].iloc[i]:
        return "LONDON_KZ"
    if df["is_ny_kz"].iloc[i]:
        return "NY_KZ"
    if "is_asian_range" in df.columns and df["is_asian_range"].iloc[i]:
        return "ASIAN"
    return "OTHER"


def _opposing_liquidity(df: pd.DataFrame, i: int, direction: int) -> Optional[float]:
    """Nearest meaningful opposing pool for TP objective."""
    close = float(df["close"].iloc[i])
    cands: List[float] = []
    if direction == 1:  # BUY → buy-side / highs above
        for col in ("pdh", "ash", "lsh", "eqh"):
            if col in df.columns:
                v = df[col].iloc[i]
                if pd.notna(v) and float(v) > close:
                    cands.append(float(v))
        sh = df["swing_high"].iloc[max(0, i - 20) : i + 1].dropna()
        for v in sh.values:
            if float(v) > close:
                cands.append(float(v))
    else:
        for col in ("pdl", "asl", "lsl", "eql"):
            if col in df.columns:
                v = df[col].iloc[i]
                if pd.notna(v) and float(v) < close:
                    cands.append(float(v))
        sl = df["swing_low"].iloc[max(0, i - 20) : i + 1].dropna()
        for v in sl.values:
            if float(v) < close:
                cands.append(float(v))
    if not cands:
        return None
    if direction == 1:
        return min(cands)  # nearest above
    return max(cands)  # nearest below


def refine_entry_to_ce(
    df: pd.DataFrame,
    i: int,
    direction: str,
    entry: float,
    prefer_ce: bool = True,
) -> float:
    """Prefer FVG CE for FVG-paradigm entries; reject stale invalidated FVGs upstream."""
    if not prefer_ce:
        return entry
    if "fvg_ce" not in df.columns:
        return entry
    ce = df["fvg_ce"].iloc[i]
    if pd.isna(ce):
        # look back a few bars for open FVG CE of matching direction
        bias = 1 if direction == "BUY" else -1
        for j in range(i, max(-1, i - 8), -1):
            if int(df["fvg_type"].iloc[j]) == bias and pd.notna(df["fvg_ce"].iloc[j]):
                if "fvg_lifecycle_state" in df.columns and df["fvg_lifecycle_state"].iloc[j] == "invalidated":
                    continue
                return float(df["fvg_ce"].iloc[j])
        return entry
    if "fvg_lifecycle_state" in df.columns and df["fvg_lifecycle_state"].iloc[i] == "invalidated":
        return entry
    return float(ce)


def build_narrative_at(
    df: pd.DataFrame, i: int, events: List[MarketEvent]
) -> NarrativeContext:
    raid = latest_raid(events, i, lookback=12)
    has_disp = False
    has_mss = False
    has_choch = latest_event(events, i, "CHoCH", lookback=12) is not None
    if raid is not None:
        for e in events:
            if e.parent_id == raid.event_id and e.event_type == "DISPLACEMENT":
                if e.bar_idx <= i:
                    has_disp = True
            if e.parent_id == raid.event_id and e.event_type == "MSS":
                if e.bar_idx <= i:
                    has_mss = True
        if "has_displacement" in df.columns:
            win = df["has_displacement"].iloc[max(0, i - 6) : i + 1]
            if win.any():
                has_disp = True

    eq = float(df["eq_level"].iloc[i]) if "eq_level" in df.columns and pd.notna(df["eq_level"].iloc[i]) else np.nan
    dealing_high = np.nan
    dealing_low = np.nan
    if "eq_level" in df.columns and not np.isnan(eq):
        dealing_high = eq + abs(float(df["close"].iloc[i]) - eq)
        dealing_low = eq - abs(float(df["close"].iloc[i]) - eq)

    fvg_t = int(df["fvg_type"].iloc[i]) if "fvg_type" in df.columns else 0
    # Prefer most recent non-invalidated FVG of any type in lookback for CE
    fvg_ce = np.nan
    fvg_top = np.nan
    fvg_bot = np.nan
    fvg_inv = False
    if fvg_t != 0 and "fvg_ce" in df.columns and pd.notna(df["fvg_ce"].iloc[i]):
        fvg_ce = float(df["fvg_ce"].iloc[i])
        fvg_top = float(df["fvg_top"].iloc[i])
        fvg_bot = float(df["fvg_bottom"].iloc[i])
        if "fvg_lifecycle_state" in df.columns:
            fvg_inv = df["fvg_lifecycle_state"].iloc[i] == "invalidated"
    elif "fvg_type" in df.columns:
        for j in range(i, max(-1, i - 8), -1):
            if int(df["fvg_type"].iloc[j]) == 0:
                continue
            if "fvg_lifecycle_state" in df.columns and df["fvg_lifecycle_state"].iloc[j] == "invalidated":
                continue
            fvg_t = int(df["fvg_type"].iloc[j])
            fvg_ce = float(df["fvg_ce"].iloc[j]) if "fvg_ce" in df.columns else np.nan
            fvg_top = float(df["fvg_top"].iloc[j])
            fvg_bot = float(df["fvg_bottom"].iloc[j])
            break

    ote_t = int(df["ote_type"].iloc[i]) if "ote_type" in df.columns else 0
    in_ote = ote_t != 0

    return NarrativeContext(
        bar_idx=i,
        timestamp=df.index[i].strftime("%Y-%m-%d %H:%M:%S"),
        htf_bias=int(df["master_bias"].iloc[i]) if "master_bias" in df.columns else 0,
        session=_session_label(df, i),
        is_discount=bool(df["is_discount"].iloc[i]) if "is_discount" in df.columns else False,
        is_premium=bool(df["is_premium"].iloc[i]) if "is_premium" in df.columns else False,
        dealing_high=float(dealing_high) if not np.isnan(dealing_high) else float(df["high"].iloc[i]),
        dealing_low=float(dealing_low) if not np.isnan(dealing_low) else float(df["low"].iloc[i]),
        eq_level=float(eq) if not np.isnan(eq) else float(df["close"].iloc[i]),
        raid=raid,
        raid_grade=(raid.grade or "C") if raid else "C",
        has_displacement=has_disp,
        has_mss=has_mss,
        has_choch=has_choch,
        fvg_type=fvg_t,
        fvg_top=fvg_top,
        fvg_bottom=fvg_bot,
        fvg_ce=fvg_ce,
        fvg_invalidated=fvg_inv,
        ob_type=int(df["ob_type"].iloc[i]) if "ob_type" in df.columns else 0,
        breaker_type=int(df["breaker_type"].iloc[i]) if "breaker_type" in df.columns else 0,
        breaker_top=float(df["breaker_top"].iloc[i])
        if "breaker_top" in df.columns and pd.notna(df["breaker_top"].iloc[i])
        else np.nan,
        breaker_bottom=float(df["breaker_bottom"].iloc[i])
        if "breaker_bottom" in df.columns and pd.notna(df["breaker_bottom"].iloc[i])
        else np.nan,
        liquidity_event_id=raid.event_id if raid else None,
        draw_on_liquidity=float(raid.meta.get("pool_level", raid.price)) if raid else None,
        opposing_liquidity=None,
        in_ote=in_ote,
        ote_type=ote_t,
    )


def validate_trade(
    df: pd.DataFrame,
    i: int,
    direction: str,
    entry: float,
    sl: float,
    min_rr: float,
    events: List[MarketEvent],
    used_event_ids: Set[str],
    require_mss: bool = False,
    require_raid_ab: bool = True,
    max_sl_pips: float = 40.0,
    pip_size: float = 0.0001,
    require_ote: bool = True,
    ote_mode: str = "soft_score",
    prefer_fvg_ce: bool = True,
    ote_soft_penalty: float = 0.15,
) -> ValidationResult:
    """
    Pre-trade 10Q filter. Reject incomplete narrative / grade C / <2R opposing liq / duplicates.
    OTE: soft_score mode never hard-rejects on missing OTE.
    """
    nar = build_narrative_at(df, i, events)
    bias = 1 if direction == "BUY" else -1
    soft = 1.0
    flags: List[str] = []

    # Reject stale fully-invalidated FVG paradigm
    if nar.fvg_invalidated and nar.fvg_type == bias:
        return ValidationResult(False, "FVG_INVALIDATED", nar)

    # Q1–Q2: liquidity taken + meaningful
    if nar.raid is None:
        return ValidationResult(False, "NO_LIQUIDITY_RAID", nar)
    if require_raid_ab and nar.raid_grade not in ("A", "B"):
        return ValidationResult(False, "RAID_GRADE_C", nar)
    if nar.raid.direction != bias:
        return ValidationResult(False, "RAID_DIRECTION_MISMATCH", nar)

    # Q3: displacement
    if not nar.has_displacement:
        return ValidationResult(False, "NO_DISPLACEMENT", nar)

    # Q4: MSS when required (CHoCH alone does not satisfy require_mss)
    if require_mss and not nar.has_mss:
        return ValidationResult(False, "NO_MSS", nar)

    # Q5: premium/discount location
    if direction == "BUY" and not nar.is_discount:
        return ValidationResult(False, "NOT_IN_DISCOUNT", nar)
    if direction == "SELL" and not nar.is_premium:
        return ValidationResult(False, "NOT_IN_PREMIUM", nar)

    # Q5b: HTF alignment
    if nar.htf_bias != 0 and nar.htf_bias != bias:
        return ValidationResult(False, "HTF_BIAS_CONFLICT", nar)

    # OTE soft_score (longs prefer discount+OTE; shorts premium+OTE)
    ote_ok = nar.in_ote and (nar.ote_type == bias or nar.ote_type == 0)
    if require_ote:
        if ote_mode == "hard":
            if not ote_ok:
                return ValidationResult(False, "NO_OTE", nar)
        else:
            # soft_score — never hard-reject
            if ote_ok:
                soft += 0.10
                flags.append("OTE_PRESENT")
            else:
                soft -= ote_soft_penalty
                flags.append("OTE_MISSING_SOFT")

    # CE entry refinement
    entry = refine_entry_to_ce(df, i, direction, entry, prefer_ce=prefer_fvg_ce)

    # Structural risk
    risk = abs(entry - sl)
    if risk < 2.0 * pip_size:
        return ValidationResult(False, "RISK_TOO_SMALL", nar)
    if risk > max_sl_pips * pip_size:
        return ValidationResult(False, "RISK_TOO_WIDE", nar)
    if direction == "BUY" and sl >= entry:
        return ValidationResult(False, "INVALID_SL", nar)
    if direction == "SELL" and sl <= entry:
        return ValidationResult(False, "INVALID_SL", nar)

    # Q6–Q7: opposing liquidity must allow >= min_rr
    opp = _opposing_liquidity(df, i, bias)
    nar.opposing_liquidity = opp
    if opp is None:
        return ValidationResult(False, "NO_OPPOSING_LIQUIDITY", nar)
    if direction == "BUY":
        reward_to_opp = opp - entry
    else:
        reward_to_opp = entry - opp
    if reward_to_opp < min_rr * risk - 1e-12:
        return ValidationResult(False, "OPPOSING_LIQ_LT_2R", nar)

    tp = entry + min_rr * risk if direction == "BUY" else entry - min_rr * risk

    # Q9: duplicate event
    eid = nar.liquidity_event_id
    if eid and eid in used_event_ids:
        return ValidationResult(False, "DUPLICATE_EVENT", nar)

    # Session gate
    if nar.session == "OTHER":
        return ValidationResult(False, "OUTSIDE_SESSION", nar)

    nar.soft_score = soft
    nar.soft_flags = flags

    return ValidationResult(
        True,
        "ACCEPTED",
        nar,
        entry=entry,
        sl=sl,
        tp=tp,
        rr=min_rr,
        risk=risk,
        event_id=eid,
        soft_score=soft,
    )


def attach_events_to_frame(df: pd.DataFrame, pair: str) -> Tuple[pd.DataFrame, List[MarketEvent]]:
    events = build_events(df, pair=pair)
    return df, events
