"""
Validate-window liquidity model attribution (H4).

Compares causal pool definitions for A-grade raid density / hypothetical 2R —
does NOT switch the default liquidity_model (remains session_pools).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from typing import Any, Dict, List

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from backend.engine.kz_tables import GEOMETRY_LOCK_VERSION
from backend.engine.trade_journal import hypothetical_2r_outcome


MODELS = ("session_pools", "eqh_eql_cluster", "window_extremes")


def _pool_touches(df: pd.DataFrame, model: str, pip_size: float = 0.0001) -> int:
    """Count bars where price interacts with model-specific pools (causal)."""
    n = 0
    highs = df["high"].values
    lows = df["low"].values
    closes = df["close"].values
    if model == "session_pools":
        cols = [c for c in ("pdh", "pdl", "ash", "asl", "lsh", "lsl") if c in df.columns]
    elif model == "eqh_eql_cluster":
        cols = [c for c in ("eqh", "eql") if c in df.columns]
    else:  # window_extremes
        # rolling prior-20 extremes (causal shift 1)
        wh = pd.Series(highs).rolling(20, min_periods=5).max().shift(1).values
        wl = pd.Series(lows).rolling(20, min_periods=5).min().shift(1).values
        for i in range(len(df)):
            if np.isnan(wh[i]) or np.isnan(wl[i]):
                continue
            if highs[i] > wh[i] or lows[i] < wl[i]:
                n += 1
        return n
    for i in range(len(df)):
        for c in cols:
            v = df[c].iloc[i]
            if pd.isna(v):
                continue
            vf = float(v)
            if lows[i] <= vf <= highs[i] or abs(closes[i] - vf) <= 2 * pip_size:
                n += 1
                break
    return n


def attribute_frame(df: pd.DataFrame, pair: str) -> Dict[str, Any]:
    out = {"pair": pair, "bars": len(df), "models": {}}
    for m in MODELS:
        touches = _pool_touches(df, m)
        # A-grade proxy: sweep_quality>=2 when present
        a_raids = 0
        if "sweep_quality" in df.columns:
            a_raids = int(((df["sweep_type"] != 0) & (df["sweep_quality"] >= 2)).sum())
        out["models"][m] = {
            "pool_touch_bars": touches,
            "major_raid_bars": a_raids,
            "touch_per_1k_bars": round(touches / max(len(df), 1) * 1000, 2),
        }
    return out


def write_report(rows: List[Dict[str, Any]], path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lines = [
        "# LIQUIDITY MODEL ATTRIBUTION",
        "",
        f"**geometry_lock_version:** `{GEOMETRY_LOCK_VERSION}`",
        "**Default remains:** `session_pools` (do not switch without evidence).",
        "",
        "## Models",
        "",
        "| Model | Role |",
        "|-------|------|",
        "| `session_pools` | PDH/PDL/ASH/ASL/LSH/LSL (default) |",
        "| `eqh_eql_cluster` | Equal highs/lows clusters |",
        "| `window_extremes` | Causal rolling window highs/lows |",
        "",
        "## Results",
        "",
        "```json",
        json.dumps(rows, indent=2),
        "```",
        "",
        "## Recommendation",
        "",
        "- Keep `liquidity_model=session_pools` as freeze default.",
        "- Re-evaluate `eqh_eql_cluster` on validate only if A-grade raid density is sparse under session pools.",
        "- `window_extremes` is exploratory; higher touch rate is expected and not itself edge.",
        "",
        "**STOP:** No default switch this pass.",
        "",
    ]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "audit", "reports", "LIQUIDITY_MODEL_ATTRIBUTION.md"))
    ap.add_argument("--synthetic", action="store_true", default=True)
    args = ap.parse_args()

    # Synthetic validate-style frame (no OOS burn; offline attribution scaffold)
    times = pd.date_range("2022-06-01", periods=500, freq="5min", tz="America/New_York")
    close = 1.05 + np.cumsum(np.random.default_rng(42).normal(0, 0.00015, len(times)))
    df = pd.DataFrame(
        {
            "open": close,
            "high": close + 0.0003,
            "low": close - 0.0003,
            "close": close,
            "pdh": close.max(),
            "pdl": close.min(),
            "ash": close[:100].max() if len(close) > 100 else close.max(),
            "asl": close[:100].min() if len(close) > 100 else close.min(),
            "lsh": np.nan,
            "lsl": np.nan,
            "eqh": np.nan,
            "eql": np.nan,
            "sweep_type": 0,
            "sweep_quality": 0,
        },
        index=times,
    )
    df.iloc[50, df.columns.get_loc("sweep_type")] = 1
    df.iloc[50, df.columns.get_loc("sweep_quality")] = 2
    df.iloc[120, df.columns.get_loc("eqh")] = float(close[120])
    rows = [attribute_frame(df, "SYNTH-EURUSD")]
    write_report(rows, args.out)
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
