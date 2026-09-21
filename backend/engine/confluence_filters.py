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
    require_ote: bool = True
    ote_mode: str = "soft_score"  # soft_score | hard
    liquidity_model: str = "session_pools"  # session_pools | eqh_eql_cluster | window_extremes


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
    # OTE soft_score: bonus point when present; never hard-reject here
    if "ote_type" in df.columns:
        ot = int(df["ote_type"].iloc[i])
        if ot == bias:
            score += 1
        elif cfg.require_ote and cfg.ote_mode == "hard" and ot == 0:
            pass  # hard gate applied in _hard_filters_pass

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

    if cfg.require_ote and cfg.ote_mode == "hard":
        ot = int(df["ote_type"].iloc[i]) if "ote_type" in df.columns else 0
        want = 1 if direction == "BUY" else -1
        if ot != want:
            return False

    return True


def _get_filter_arrays(
    df_ind: pd.DataFrame,
    pair: str,
    cfg: ConfluenceFilterConfig,
) -> Dict[str, Any]:
    """Build/cached numpy views for fast filter_signals (once per df + touch/lookback)."""
    pip_size = get_pip_size(pair)
    key = (
        cfg.use_ema_bias_fallback,
        cfg.sweep_lookback,
        cfg.pdh_pdl_touch_pips,
        pip_size,
    )
    # Store on the DataFrame itself — module id(df) keys are unsafe across GC reuse
    bucket = df_ind.attrs.setdefault("_confluence_filter_cache", {})
    cached = bucket.get(key)
    if cached is not None:
        return cached

    n = len(df_ind)
    # Vectorized label build (listcomp strftime over 500k bars is too slow)
    idx_labels = df_ind.index.strftime("%Y-%m-%d %H:%M:%S")
    time_to_idx = {t: i for i, t in enumerate(idx_labels)}

    master_bias = (
        df_ind["master_bias"].to_numpy(dtype=np.int8, copy=False)
        if "master_bias" in df_ind.columns
        else np.zeros(n, dtype=np.int8)
    )
    htf_bias = (
        df_ind["htf_bias"].to_numpy(dtype=np.int8, copy=False)
        if "htf_bias" in df_ind.columns
        else master_bias
    )
    bias = htf_bias if not cfg.use_ema_bias_fallback else master_bias

    is_london = (
        df_ind["is_london_kz"].to_numpy(dtype=bool, copy=False)
        if "is_london_kz" in df_ind.columns
        else np.zeros(n, dtype=bool)
    )
    is_ny = (
        df_ind["is_ny_kz"].to_numpy(dtype=bool, copy=False)
        if "is_ny_kz" in df_ind.columns
        else np.zeros(n, dtype=bool)
    )
    is_sb = (
        df_ind["is_silver_bullet"].to_numpy(dtype=bool, copy=False)
        if "is_silver_bullet" in df_ind.columns
        else np.zeros(n, dtype=bool)
    )
    session_ok = is_london | is_ny | is_sb

    is_discount = (
        df_ind["is_discount"].to_numpy(dtype=bool, copy=False)
        if "is_discount" in df_ind.columns
        else np.zeros(n, dtype=bool)
    )
    is_premium = (
        df_ind["is_premium"].to_numpy(dtype=bool, copy=False)
        if "is_premium" in df_ind.columns
        else np.zeros(n, dtype=bool)
    )
    has_disp = (
        df_ind["has_displacement"].to_numpy(dtype=bool, copy=False)
        if "has_displacement" in df_ind.columns
        else np.zeros(n, dtype=bool)
    )
    sweep = (
        df_ind["sweep_type"].to_numpy(copy=False)
        if "sweep_type" in df_ind.columns
        else np.zeros(n)
    )
    fvg = (
        df_ind["fvg_type"].to_numpy(dtype=np.int8, copy=False)
        if "fvg_type" in df_ind.columns
        else np.zeros(n, dtype=np.int8)
    )
    ifvg = (
        df_ind["ifvg_type"].to_numpy(dtype=np.int8, copy=False)
        if "ifvg_type" in df_ind.columns
        else np.zeros(n, dtype=np.int8)
    )
    ob = (
        df_ind["ob_type"].to_numpy(dtype=np.int8, copy=False)
        if "ob_type" in df_ind.columns
        else np.zeros(n, dtype=np.int8)
    )
    breaker = (
        df_ind["breaker_type"].to_numpy(dtype=np.int8, copy=False)
        if "breaker_type" in df_ind.columns
        else np.zeros(n, dtype=np.int8)
    )
    close = df_ind["close"].to_numpy(dtype=float, copy=False)
    thresh = cfg.pdh_pdl_touch_pips * pip_size

    # Rolling any(sweep != 0) over lookback window (inclusive)
    sweep_nz = (sweep != 0).astype(np.int8)
    csum = np.concatenate(([0], np.cumsum(sweep_nz)))
    lb = cfg.sweep_lookback
    i_arr = np.arange(n)
    lo = np.maximum(0, i_arr - lb)
    recent_sweep = (csum[i_arr + 1] - csum[lo]) > 0

    near_pool = np.zeros(n, dtype=bool)
    for c in ("pdh", "pdl", "eqh", "eql", "ash", "asl", "lsh", "lsl"):
        if c not in df_ind.columns:
            continue
        col = df_ind[c].to_numpy(dtype=float, copy=False)
        valid = ~np.isnan(col)
        near_pool |= valid & (np.abs(close - col) <= thresh)

    score_buy = np.zeros(n, dtype=np.int8)
    score_sell = np.zeros(n, dtype=np.int8)
    score_buy += recent_sweep.astype(np.int8)
    score_sell += recent_sweep.astype(np.int8)
    score_buy += (fvg == 1).astype(np.int8)
    score_sell += (fvg == -1).astype(np.int8)
    score_buy += (ifvg == 1).astype(np.int8)
    score_sell += (ifvg == -1).astype(np.int8)
    score_buy += (ob == 1).astype(np.int8)
    score_sell += (ob == -1).astype(np.int8)
    score_buy += (breaker == 1).astype(np.int8)
    score_sell += (breaker == -1).astype(np.int8)
    score_buy += is_sb.astype(np.int8)
    score_sell += is_sb.astype(np.int8)
    score_buy += has_disp.astype(np.int8)
    score_sell += has_disp.astype(np.int8)
    score_buy += near_pool.astype(np.int8)
    score_sell += near_pool.astype(np.int8)

    cached = {
        "pip_size": pip_size,
        "time_to_idx": time_to_idx,
        "bias": bias,
        "session_ok": session_ok,
        "is_discount": is_discount,
        "is_premium": is_premium,
        "has_disp": has_disp,
        "recent_sweep": recent_sweep,
        "near_pool": near_pool,
        "score_buy": score_buy,
        "score_sell": score_sell,
    }
    bucket[key] = cached
    return cached


def filter_signals(
    df_ind: pd.DataFrame,
    signals: List[Dict[str, Any]],
    pair: str,
    cfg: ConfluenceFilterConfig,
) -> List[Dict[str, Any]]:
    """Apply hard filters, min score, active_setups, and max_trades_per_day."""
    if len(df_ind) == 0:
        return []

    arr = _get_filter_arrays(df_ind, pair, cfg)
    pip_size = arr["pip_size"]
    time_to_idx = arr["time_to_idx"]
    bias = arr["bias"]
    session_ok = arr["session_ok"]
    is_discount = arr["is_discount"]
    is_premium = arr["is_premium"]
    has_disp = arr["has_disp"]
    recent_sweep = arr["recent_sweep"]
    near_pool = arr["near_pool"]
    score_buy = arr["score_buy"]
    score_sell = arr["score_sell"]

    active = set(int(s) for s in cfg.active_setups)
    out: List[Dict[str, Any]] = []
    per_day: Dict[str, int] = {}

    for sig in signals:
        if int(sig.get("setup_id", 0)) not in active:
            continue
        ts = sig["timestamp"]
        i = time_to_idx.get(ts)
        if i is None:
            continue

        direction = sig["direction"]
        b = int(bias[i])
        if b == 0:
            continue
        if direction == "BUY" and b != 1:
            continue
        if direction == "SELL" and b != -1:
            continue
        if not session_ok[i]:
            continue
        if direction == "BUY" and not is_discount[i]:
            continue
        if direction == "SELL" and not is_premium[i]:
            continue

        risk = abs(float(sig["entry"]) - float(sig["sl"]))
        if risk < (2.0 * pip_size):
            continue

        if cfg.require_displacement and not has_disp[i]:
            continue
        if cfg.require_recent_sweep and not recent_sweep[i]:
            continue
        if cfg.require_pdh_pdl_touch and not near_pool[i]:
            continue

        sc = int(score_buy[i] if direction == "BUY" else score_sell[i])
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
    """Filter-only grid: stricter confluence + per-pair day caps (portfolio day cap separate)."""
    configs: List[ConfluenceFilterConfig] = []
    # Prefer higher scores first (quality over quantity)
    for min_score in (7, 6, 5, 4):
        for req_disp in (True, False):
            for req_sweep in (True, False):
                for req_pdh in (True, False):
                    for max_day in (1, 2):
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
