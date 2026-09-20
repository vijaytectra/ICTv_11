"""
Post-signal confluence filters for the quality ladder study.
Causal: only uses columns already present on closed bars in df_ind.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from backend.engine.data_loader import get_pip_size


@dataclass
class ConfluenceFilterConfig:
    min_confluence_score: int = 4
    require_displacement: bool = False
    require_recent_sweep: bool = False
    require_pdh_pdl_touch: bool = False
    pdh_pdl_touch_pips: float = 5.0
    max_trades_per_day: int = 3
    active_setups: List[int] = field(default_factory=lambda: [1, 2, 3, 4, 5, 6, 9, 10])
    use_ema_bias_fallback: bool = True
    sweep_lookback: int = 10


def _session_ok(df: pd.DataFrame, i: int) -> bool:
    return bool(
        df["is_london_kz"].iloc[i]
        or df["is_ny_kz"].iloc[i]
        or df["is_silver_bullet"].iloc[i]
    )


def _near_pool(df: pd.DataFrame, i: int, pip_size: float, touch_pips: float) -> bool:
    close = float(df["close"].iloc[i])
    thresh = touch_pips * pip_size
    cols = [
        "pdh",
        "pdl",
        "eqh",
        "eql",
        "ash",
        "asl",
        "lsh",
        "lsl",
    ]
    for c in cols:
        if c not in df.columns:
            continue
        v = df[c].iloc[i]
        if pd.isna(v):
            continue
        if abs(close - float(v)) <= thresh:
            return True
    return False


def score_bar(
    df: pd.DataFrame,
    i: int,
    direction: str,
    pip_size: float,
    cfg: ConfluenceFilterConfig,
) -> int:
    """Confluence points at bar i for BUY/SELL (spec §7)."""
    bias = 1 if direction == "BUY" else -1
    score = 0

    lb = cfg.sweep_lookback
    recent = df["sweep_type"].iloc[max(0, i - lb) : i + 1]
    if (recent != 0).any():
        score += 1

    if "fvg_type" in df.columns and int(df["fvg_type"].iloc[i]) == bias:
        score += 1
    if "ifvg_type" in df.columns and int(df["ifvg_type"].iloc[i]) == bias:
        score += 1
    if "ob_type" in df.columns and int(df["ob_type"].iloc[i]) == bias:
        score += 1
    if "breaker_type" in df.columns and int(df["breaker_type"].iloc[i]) == bias:
        score += 1
    if "is_silver_bullet" in df.columns and bool(df["is_silver_bullet"].iloc[i]):
        score += 1
    if "has_displacement" in df.columns and bool(df["has_displacement"].iloc[i]):
        score += 1
    if _near_pool(df, i, pip_size, cfg.pdh_pdl_touch_pips):
        score += 1

    return int(score)


def _hard_filters_pass(
    df: pd.DataFrame,
    i: int,
    sig: Dict[str, Any],
    pip_size: float,
    cfg: ConfluenceFilterConfig,
) -> bool:
    direction = sig["direction"]
    bias = int(df["master_bias"].iloc[i]) if "master_bias" in df.columns else 0
    if not cfg.use_ema_bias_fallback and "htf_bias" in df.columns:
        bias = int(df["htf_bias"].iloc[i])

    if bias == 0:
        return False
    if direction == "BUY" and bias != 1:
        return False
    if direction == "SELL" and bias != -1:
        return False
    if not _session_ok(df, i):
        return False
    if direction == "BUY" and not bool(df["is_discount"].iloc[i]):
        return False
    if direction == "SELL" and not bool(df["is_premium"].iloc[i]):
        return False

    risk = abs(float(sig["entry"]) - float(sig["sl"]))
    if risk < (2.0 * pip_size):
        return False

    if cfg.require_displacement and not bool(df["has_displacement"].iloc[i]):
        return False

    if cfg.require_recent_sweep:
        recent = df["sweep_type"].iloc[max(0, i - cfg.sweep_lookback) : i + 1]
        if (recent == 0).all():
            return False

    if cfg.require_pdh_pdl_touch and not _near_pool(
        df, i, pip_size, cfg.pdh_pdl_touch_pips
    ):
        return False

    return True


def filter_signals(
    df_ind: pd.DataFrame,
    signals: List[Dict[str, Any]],
    pair: str,
    cfg: ConfluenceFilterConfig,
) -> List[Dict[str, Any]]:
    """Apply hard filters, min score, active_setups, and max_trades_per_day."""
    pip_size = get_pip_size(pair)
    time_to_idx = {t.strftime("%Y-%m-%d %H:%M:%S"): i for i, t in enumerate(df_ind.index)}
    active = set(cfg.active_setups)
    out: List[Dict[str, Any]] = []
    per_day: Dict[str, int] = {}

    for sig in signals:
        if int(sig.get("setup_id", 0)) not in active:
            continue
        ts = sig["timestamp"]
        if ts not in time_to_idx:
            continue
        i = time_to_idx[ts]
        if not _hard_filters_pass(df_ind, i, sig, pip_size, cfg):
            continue
        sc = score_bar(df_ind, i, sig["direction"], pip_size, cfg)
        if sc < cfg.min_confluence_score:
            continue
        day = ts[:10]
        if per_day.get(day, 0) >= cfg.max_trades_per_day:
            continue
        enriched = dict(sig)
        enriched["confluence_score"] = sc
        out.append(enriched)
        per_day[day] = per_day.get(day, 0) + 1

    return out


def iter_grid_configs() -> List[ConfluenceFilterConfig]:
    """Pre-registered train grid from design spec §7."""
    configs: List[ConfluenceFilterConfig] = []
    for min_score in (3, 4, 5, 6):
        for req_disp in (False, True):
            for req_sweep in (False, True):
                for req_pdh in (False, True):
                    for max_day in (2, 3):
                        configs.append(
                            ConfluenceFilterConfig(
                                min_confluence_score=min_score,
                                require_displacement=req_disp,
                                require_recent_sweep=req_sweep,
                                require_pdh_pdl_touch=req_pdh,
                                max_trades_per_day=max_day,
                            )
                        )
    return configs
