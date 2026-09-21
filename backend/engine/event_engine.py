"""
Causal ICT event engine.

Builds typed market events from indicator columns on closed bars only.
No future bars. Raid grades A/B/C; MSS only after linked raid+displacement.
CHoCH is first counter-structure break (distinct from MSS).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


EVENT_TYPES = (
    "LIQUIDITY_CREATED",
    "LIQUIDITY_SWEPT",
    "DISPLACEMENT",
    "MSS",
    "CHoCH",
    "FVG_CREATED",
    "FVG_MITIGATED",
    "BREAKER_CREATED",
    "BREAKER_RETESTED",
    "SETUP_INVALIDATED",
)


@dataclass
class MarketEvent:
    event_id: str
    event_type: str
    timestamp: str
    bar_idx: int
    direction: int  # 1 bullish / -1 bearish / 0 n/a
    price: float
    meta: Dict[str, Any] = field(default_factory=dict)
    parent_id: Optional[str] = None
    grade: Optional[str] = None  # A/B/C for raids


def _ts(df: pd.DataFrame, i: int) -> str:
    t = df.index[i]
    if hasattr(t, "strftime"):
        return t.strftime("%Y-%m-%d %H:%M:%S")
    return str(t)


def _grade_raid(quality: int, has_disp: bool, has_mss: bool) -> str:
    if quality >= 2 and has_disp and has_mss:
        return "A"
    if quality >= 2 and has_disp:
        return "B"
    if quality >= 1 and has_disp:
        return "B"
    return "C"


def build_events(df: pd.DataFrame, pair: str = "") -> List[MarketEvent]:
    """
    Scan indicator frame and emit causal events in bar order.
    Expects run_all_indicators columns.
    """
    events: List[MarketEvent] = []
    n = len(df)
    if n == 0:
        return events

    sweep_type = df["sweep_type"].values if "sweep_type" in df.columns else np.zeros(n)
    sweep_q = df["sweep_quality"].values if "sweep_quality" in df.columns else np.zeros(n)
    sweep_ext = (
        df["sweep_extreme"].values
        if "sweep_extreme" in df.columns
        else df["sweep_level"].values
        if "sweep_level" in df.columns
        else np.full(n, np.nan)
    )
    has_disp = (
        df["has_displacement"].values
        if "has_displacement" in df.columns
        else np.zeros(n, dtype=bool)
    )
    opens = df["open"].values
    closes = df["close"].values
    highs = df["high"].values
    lows = df["low"].values
    swing_h = (
        pd.Series(df["swing_high"].values).ffill().shift(1).values
        if "swing_high" in df.columns
        else np.full(n, np.nan)
    )
    swing_l = (
        pd.Series(df["swing_low"].values).ffill().shift(1).values
        if "swing_low" in df.columns
        else np.full(n, np.nan)
    )
    fvg_type = df["fvg_type"].values if "fvg_type" in df.columns else np.zeros(n)
    fvg_mit = (
        df["fvg_mitigated"].values.astype(bool)
        if "fvg_mitigated" in df.columns
        else np.zeros(n, dtype=bool)
    )
    fvg_inv = (
        df["fvg_invalidated"].values.astype(bool)
        if "fvg_invalidated" in df.columns
        else np.zeros(n, dtype=bool)
    )
    breaker_type = (
        df["breaker_type"].values if "breaker_type" in df.columns else np.zeros(n)
    )
    in_kz = np.zeros(n, dtype=bool)
    for col in ("is_london_kz", "is_ny_kz", "is_silver_bullet"):
        if col in df.columns:
            in_kz |= df[col].values.astype(bool)

    last_raid_id: Optional[str] = None
    last_raid_dir = 0
    last_raid_idx = -999
    last_disp_id: Optional[str] = None
    last_fvg_id: Optional[str] = None
    last_fvg_idx = -999
    last_fvg_dir = 0
    last_fvg_ce = np.nan
    last_fvg_top = np.nan
    last_fvg_bot = np.nan
    last_brk_id: Optional[str] = None
    last_brk_ce = np.nan
    last_brk_dir = 0
    last_brk_idx = -999
    structure_bias = 0  # last confirmed structure direction
    choch_emitted_for_bias = 0
    prev_pdh = np.nan
    prev_pdl = np.nan
    prev_ash = np.nan
    prev_asl = np.nan
    prev_eqh_count = 0
    prev_eql_count = 0
    pending_setup = False
    seq = 0

    for i in range(n):
        # --- LIQUIDITY_CREATED: new PDH/PDL / session extreme / EQH-EQL ---
        for col, label, direction in (
            ("pdh", "PDH", -1),
            ("pdl", "PDL", 1),
            ("ash", "ASH", -1),
            ("asl", "ASL", 1),
            ("eqh", "EQH", -1),
            ("eql", "EQL", 1),
        ):
            if col not in df.columns:
                continue
            v = df[col].iloc[i]
            if pd.isna(v):
                continue
            vf = float(v)
            created = False
            if col == "pdh" and (np.isnan(prev_pdh) or abs(vf - prev_pdh) > 1e-12):
                if not np.isnan(vf):
                    created = abs(vf - prev_pdh) > 1e-12 if not np.isnan(prev_pdh) else True
                prev_pdh = vf
            elif col == "pdl" and (np.isnan(prev_pdl) or abs(vf - prev_pdl) > 1e-12):
                created = True
                prev_pdl = vf
            elif col == "ash":
                if np.isnan(prev_ash) or vf > prev_ash + 1e-12:
                    created = not np.isnan(vf) and (np.isnan(prev_ash) or vf > prev_ash)
                    prev_ash = vf if not np.isnan(vf) else prev_ash
            elif col == "asl":
                if np.isnan(prev_asl) or vf < prev_asl - 1e-12:
                    created = not np.isnan(vf) and (np.isnan(prev_asl) or vf < prev_asl)
                    prev_asl = vf if not np.isnan(vf) else prev_asl
            elif col == "eqh":
                # first non-nan registration at this bar
                if pd.notna(df["eqh"].iloc[i]) and (
                    i == 0 or pd.isna(df["eqh"].iloc[i - 1])
                ):
                    created = True
                    prev_eqh_count += 1
            elif col == "eql":
                if pd.notna(df["eql"].iloc[i]) and (
                    i == 0 or pd.isna(df["eql"].iloc[i - 1])
                ):
                    created = True
                    prev_eql_count += 1
            if created:
                seq += 1
                events.append(
                    MarketEvent(
                        event_id=f"{pair}-LIQ-{seq}-{i}",
                        event_type="LIQUIDITY_CREATED",
                        timestamp=_ts(df, i),
                        bar_idx=i,
                        direction=direction,
                        price=vf,
                        meta={"pool": label},
                    )
                )

        # --- Liquidity swept ---
        st = int(sweep_type[i])
        if st != 0 and not np.isnan(sweep_ext[i]):
            seq += 1
            eid = f"{pair}-RAID-{seq}-{i}"
            grade = "C"
            if int(sweep_q[i]) >= 2:
                grade = "B"
            ev = MarketEvent(
                event_id=eid,
                event_type="LIQUIDITY_SWEPT",
                timestamp=_ts(df, i),
                bar_idx=i,
                direction=st,
                price=float(sweep_ext[i]),
                meta={
                    "sweep_quality": int(sweep_q[i]),
                    "pool_level": float(df["sweep_level"].iloc[i])
                    if "sweep_level" in df.columns
                    else float(sweep_ext[i]),
                },
                grade=grade,
            )
            events.append(ev)
            # opposing sweep invalidates pending setup
            if pending_setup and last_raid_dir != 0 and st == -last_raid_dir:
                seq += 1
                events.append(
                    MarketEvent(
                        event_id=f"{pair}-INV-{seq}-{i}",
                        event_type="SETUP_INVALIDATED",
                        timestamp=_ts(df, i),
                        bar_idx=i,
                        direction=st,
                        price=float(closes[i]),
                        parent_id=last_raid_id,
                        meta={"reason": "opposing_sweep"},
                    )
                )
                pending_setup = False
            last_raid_id = eid
            last_raid_dir = st
            last_raid_idx = i
            pending_setup = True

        # --- Displacement (prefer post-raid within 6 bars) ---
        if has_disp[i]:
            body_dir = 1 if closes[i] > opens[i] else (-1 if closes[i] < opens[i] else 0)
            linked = (
                last_raid_id is not None
                and 0 <= (i - last_raid_idx) <= 6
                and body_dir == last_raid_dir
            )
            if linked or body_dir != 0:
                seq += 1
                eid = f"{pair}-DISP-{seq}-{i}"
                parent = last_raid_id if linked else None
                events.append(
                    MarketEvent(
                        event_id=eid,
                        event_type="DISPLACEMENT",
                        timestamp=_ts(df, i),
                        bar_idx=i,
                        direction=body_dir,
                        price=float(closes[i]),
                        meta={"linked_to_raid": linked},
                        parent_id=parent,
                    )
                )
                if linked:
                    last_disp_id = eid
                    for e in reversed(events):
                        if e.event_id == last_raid_id:
                            if e.meta.get("sweep_quality", 0) >= 2:
                                e.grade = "B"
                            break

        # --- CHoCH: first break against prior structure (no raid requirement) ---
        choch_dir = 0
        if structure_bias <= 0 and not np.isnan(swing_h[i]) and closes[i] > swing_h[i]:
            choch_dir = 1
        elif structure_bias >= 0 and not np.isnan(swing_l[i]) and closes[i] < swing_l[i]:
            choch_dir = -1
        if choch_dir != 0 and choch_dir != choch_emitted_for_bias:
            # Avoid double-emitting the same break as both CHoCH and MSS on same bar
            will_mss = (
                last_raid_id
                and last_disp_id
                and 0 <= (i - last_raid_idx) <= 12
                and (
                    (last_raid_dir == 1 and choch_dir == 1)
                    or (last_raid_dir == -1 and choch_dir == -1)
                )
            )
            if not will_mss:
                seq += 1
                events.append(
                    MarketEvent(
                        event_id=f"{pair}-CHOCH-{seq}-{i}",
                        event_type="CHoCH",
                        timestamp=_ts(df, i),
                        bar_idx=i,
                        direction=choch_dir,
                        price=float(closes[i]),
                        meta={"prior_bias": structure_bias},
                    )
                )
                structure_bias = choch_dir
                choch_emitted_for_bias = choch_dir

        # --- MSS: body close beyond opposing swing AFTER raid+disp ---
        if last_raid_id and last_disp_id and 0 <= (i - last_raid_idx) <= 12:
            mss_dir = 0
            if last_raid_dir == 1 and not np.isnan(swing_h[i]) and closes[i] > swing_h[i]:
                mss_dir = 1
            elif last_raid_dir == -1 and not np.isnan(swing_l[i]) and closes[i] < swing_l[i]:
                mss_dir = -1
            if mss_dir != 0:
                seq += 1
                eid = f"{pair}-MSS-{seq}-{i}"
                events.append(
                    MarketEvent(
                        event_id=eid,
                        event_type="MSS",
                        timestamp=_ts(df, i),
                        bar_idx=i,
                        direction=mss_dir,
                        price=float(closes[i]),
                        parent_id=last_raid_id,
                        meta={"disp_id": last_disp_id},
                    )
                )
                for e in reversed(events):
                    if e.event_id == last_raid_id:
                        e.grade = _grade_raid(
                            int(e.meta.get("sweep_quality", 0)), True, True
                        )
                        break
                structure_bias = mss_dir
                choch_emitted_for_bias = mss_dir
                last_disp_id = None

        # --- FVG created ---
        ft = int(fvg_type[i])
        if ft != 0:
            seq += 1
            top = (
                float(df["fvg_top"].iloc[i])
                if "fvg_top" in df.columns
                else float(highs[i])
            )
            bot = (
                float(df["fvg_bottom"].iloc[i])
                if "fvg_bottom" in df.columns
                else float(lows[i])
            )
            ce = (
                float(df["fvg_ce"].iloc[i])
                if "fvg_ce" in df.columns and pd.notna(df["fvg_ce"].iloc[i])
                else (top + bot) / 2.0
            )
            eid = f"{pair}-FVG-{seq}-{i}"
            events.append(
                MarketEvent(
                    event_id=eid,
                    event_type="FVG_CREATED",
                    timestamp=_ts(df, i),
                    bar_idx=i,
                    direction=ft,
                    price=ce,
                    parent_id=last_raid_id if last_raid_id and (i - last_raid_idx) <= 8 else None,
                    meta={
                        "fvg_top": top,
                        "fvg_bottom": bot,
                        "fvg_ce": ce,
                    },
                )
            )
            last_fvg_id = eid
            last_fvg_idx = i
            last_fvg_dir = ft
            last_fvg_ce = ce
            last_fvg_top = top
            last_fvg_bot = bot
            pending_setup = True

        # --- FVG_MITIGATED / far-side invalidation ---
        if fvg_mit[i] and last_fvg_id is not None:
            seq += 1
            events.append(
                MarketEvent(
                    event_id=f"{pair}-FVGM-{seq}-{i}",
                    event_type="FVG_MITIGATED",
                    timestamp=_ts(df, i),
                    bar_idx=i,
                    direction=last_fvg_dir,
                    price=float(last_fvg_ce) if not np.isnan(last_fvg_ce) else float(closes[i]),
                    parent_id=last_fvg_id,
                    meta={"reason": "ce_touch"},
                )
            )
        if fvg_inv[i] and last_fvg_id is not None:
            seq += 1
            events.append(
                MarketEvent(
                    event_id=f"{pair}-INV-{seq}-{i}",
                    event_type="SETUP_INVALIDATED",
                    timestamp=_ts(df, i),
                    bar_idx=i,
                    direction=last_fvg_dir,
                    price=float(closes[i]),
                    parent_id=last_fvg_id,
                    meta={"reason": "fvg_far_side_close"},
                )
            )
            pending_setup = False
        # also detect far-side close if lifecycle columns absent
        if (
            last_fvg_id
            and i > last_fvg_idx
            and not fvg_inv[i]
            and not np.isnan(last_fvg_bot)
        ):
            if last_fvg_dir == 1 and closes[i] < last_fvg_bot:
                seq += 1
                events.append(
                    MarketEvent(
                        event_id=f"{pair}-INV-{seq}-{i}",
                        event_type="SETUP_INVALIDATED",
                        timestamp=_ts(df, i),
                        bar_idx=i,
                        direction=last_fvg_dir,
                        price=float(closes[i]),
                        parent_id=last_fvg_id,
                        meta={"reason": "fvg_far_side_close"},
                    )
                )
                pending_setup = False
                last_fvg_id = None
            elif last_fvg_dir == -1 and closes[i] > last_fvg_top:
                seq += 1
                events.append(
                    MarketEvent(
                        event_id=f"{pair}-INV-{seq}-{i}",
                        event_type="SETUP_INVALIDATED",
                        timestamp=_ts(df, i),
                        bar_idx=i,
                        direction=last_fvg_dir,
                        price=float(closes[i]),
                        parent_id=last_fvg_id,
                        meta={"reason": "fvg_far_side_close"},
                    )
                )
                pending_setup = False
                last_fvg_id = None

        # --- Breaker created ---
        bt = int(breaker_type[i])
        if bt != 0:
            seq += 1
            btop = (
                float(df["breaker_top"].iloc[i])
                if "breaker_top" in df.columns
                else float(highs[i])
            )
            bbot = (
                float(df["breaker_bottom"].iloc[i])
                if "breaker_bottom" in df.columns
                else float(lows[i])
            )
            bce = (btop + bbot) / 2.0
            eid = f"{pair}-BRK-{seq}-{i}"
            events.append(
                MarketEvent(
                    event_id=eid,
                    event_type="BREAKER_CREATED",
                    timestamp=_ts(df, i),
                    bar_idx=i,
                    direction=bt,
                    price=float(closes[i]),
                    meta={
                        "breaker_top": btop,
                        "breaker_bottom": bbot,
                        "breaker_ce": bce,
                    },
                )
            )
            last_brk_id = eid
            last_brk_ce = bce
            last_brk_dir = bt
            last_brk_idx = i

        # --- BREAKER_RETESTED: price revisits breaker CE after creation ---
        if (
            last_brk_id
            and i > last_brk_idx
            and not np.isnan(last_brk_ce)
            and lows[i] <= last_brk_ce <= highs[i]
        ):
            seq += 1
            events.append(
                MarketEvent(
                    event_id=f"{pair}-BRKR-{seq}-{i}",
                    event_type="BREAKER_RETESTED",
                    timestamp=_ts(df, i),
                    bar_idx=i,
                    direction=last_brk_dir,
                    price=float(last_brk_ce),
                    parent_id=last_brk_id,
                )
            )
            last_brk_id = None  # one retest emit

        # --- SETUP_INVALIDATED: killzone window end while pending ---
        if pending_setup and i > 0 and in_kz[i - 1] and not in_kz[i]:
            seq += 1
            events.append(
                MarketEvent(
                    event_id=f"{pair}-INV-{seq}-{i}",
                    event_type="SETUP_INVALIDATED",
                    timestamp=_ts(df, i),
                    bar_idx=i,
                    direction=last_raid_dir or last_fvg_dir,
                    price=float(closes[i]),
                    parent_id=last_raid_id or last_fvg_id,
                    meta={"reason": "killzone_window_end"},
                )
            )
            pending_setup = False

    return events


def events_by_bar(events: List[MarketEvent]) -> Dict[int, List[MarketEvent]]:
    out: Dict[int, List[MarketEvent]] = {}
    for e in events:
        out.setdefault(e.bar_idx, []).append(e)
    return out


def latest_raid(
    events: List[MarketEvent], bar_idx: int, lookback: int = 12
) -> Optional[MarketEvent]:
    cands = [
        e
        for e in events
        if e.event_type == "LIQUIDITY_SWEPT"
        and bar_idx - lookback <= e.bar_idx <= bar_idx
    ]
    return cands[-1] if cands else None


def latest_event(
    events: List[MarketEvent],
    bar_idx: int,
    event_type: str,
    lookback: int = 24,
) -> Optional[MarketEvent]:
    cands = [
        e
        for e in events
        if e.event_type == event_type and bar_idx - lookback <= e.bar_idx <= bar_idx
    ]
    return cands[-1] if cands else None
