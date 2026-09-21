"""
Gate autopsy for freeze validate rejects — VALIDATE WINDOW ONLY.
No OOS. Counts narrative rejection reasons to drive ≤3 looseners.
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter, defaultdict
from typing import Any, Dict, List

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from backend.engine.strategy_setups import get_all_setup_signals

PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "USDCAD", "AUDUSD", "USDCHF"]
CACHE_DIR = os.path.join(ROOT, "scratch", "cache_5m_ny")
FREEZE = os.path.join(ROOT, "config", "strategy_config_gap_closure_h_freeze.json")
# Warmup + validate only (skip 2024+ for speed)
SLICE_START = "2021-06-01"
VAL_START = "2022-01-01"
VAL_END = "2023-12-31"


def load_pair(pair: str):
    import pandas as pd

    path = os.path.join(CACHE_DIR, f"{pair}_5m_ny.parquet")
    df = pd.read_parquet(path)
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC").tz_convert("America/New_York")
    df = df.loc[SLICE_START:VAL_END]
    return df


def main():
    with open(FREEZE, encoding="utf-8") as f:
        freeze = json.load(f)

    reason_all = Counter()
    reason_val = Counter()
    by_setup_val = defaultdict(Counter)
    grade_at_reject = Counter()
    n_acc_val = 0
    n_rej_val = 0
    n_acc_all = 0
    n_rej_all = 0

    for pair in PAIRS:
        print(f"autopsy {pair}...", flush=True)
        df = load_pair(pair)
        print(f"  bars={len(df)}", flush=True)
        rej: List[Dict[str, Any]] = []
        accepted = get_all_setup_signals(
            df,
            pair,
            min_rr=2.0,
            active_setups=list(freeze["active_setups"]),
            use_narrative=True,
            rejections=rej,
            kz_table=freeze["kz_table"],
            fvg_require_displacement_candle=bool(
                freeze.get("fvg_require_displacement_candle", True)
            ),
            liquidity_model=freeze.get("liquidity_model", "session_pools"),
            require_ote=bool(freeze.get("require_ote", True)),
            ote_mode=freeze.get("ote_mode", "soft_score"),
        )
        n_acc_all += len(accepted)
        n_rej_all += len(rej)
        for s in accepted:
            if VAL_START <= s["timestamp"][:10] <= VAL_END:
                n_acc_val += 1
        for r in rej:
            reason = r.get("rejection_reason", "?")
            reason_all[reason] += 1
            ts = (r.get("timestamp") or "")[:10]
            if VAL_START <= ts <= VAL_END:
                n_rej_val += 1
                reason_val[reason] += 1
                by_setup_val[int(r.get("setup_id", 0))][reason] += 1
                g = r.get("raid_grade") or (r.get("narrative") or {}).get("raid_grade")
                grade_at_reject[str(g)] += 1
        print(
            f"  accepted={len(accepted)} rejected={len(rej)} "
            f"(val rej tallied separately)",
            flush=True,
        )

    top = reason_val.most_common(15)
    report = {
        "freeze_hash": freeze.get("config_hash"),
        "slice": f"{SLICE_START}..{VAL_END}",
        "validate": f"{VAL_START}..{VAL_END}",
        "accepted_all_slice": n_acc_all,
        "rejected_all_slice": n_rej_all,
        "accepted_validate": n_acc_val,
        "rejected_validate": n_rej_val,
        "reason_counts_validate": dict(top),
        "reason_counts_all_slice": dict(reason_all.most_common(20)),
        "raid_grade_on_validate_rejects": dict(grade_at_reject),
        "by_setup_top_reasons": {
            str(sid): dict(c.most_common(5)) for sid, c in sorted(by_setup_val.items())
        },
    }

    out_json = os.path.join(ROOT, "scratch", "gate_autopsy_freeze.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(json.dumps(report, indent=2), flush=True)
    print(f"wrote {out_json}", flush=True)


if __name__ == "__main__":
    main()
