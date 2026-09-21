"""
Gap Closure H — VALIDATE v2 after ≤3 looseners (L1–L3).
Base freeze 7917a2f1603691cd locks kept. No OOS.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import defaultdict
from typing import Any, Dict, List, Optional

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from backend.engine.metrics import binomial_wilson_ci, compute_win_rate
from backend.engine.portfolio_backtest import run_portfolio
from backend.engine.strategy_setups import get_all_setup_signals

# Reuse helpers from v1 runner
from audit.validation.run_gap_closure_h_validate import (
    PAIRS,
    VAL,
    CACHE_DIR,
    load_or_build_5m,
    _period_sigs,
    _stats,
    _ote_impact,
    _go_nogo,
    load_merged_config,
)

SLICE_START = "2021-06-01"
V2_CFG = os.path.join(ROOT, "config", "strategy_config_gap_closure_h_validate_v2.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default=r"C:\Users\Vijayakumar R\Documents")
    ap.add_argument(
        "--report",
        default=os.path.join(ROOT, "audit", "reports", "GAP_CLOSURE_H_VALIDATE_v2.md"),
    )
    ap.add_argument("--force-cache", action="store_true")
    args = ap.parse_args()

    base = load_merged_config()
    with open(V2_CFG, encoding="utf-8") as f:
        v2 = json.load(f)
    loosen = v2["validate_looseners"]
    # hash of locks + looseners for cache key
    blob = json.dumps(
        {
            "base": base.get("config_hash"),
            "loosen": loosen,
            "geometry_lock_version": base.get("geometry_lock_version"),
        },
        sort_keys=True,
    )
    v2_hash = hashlib.sha256(blob.encode()).hexdigest()[:16]

    print("=== Gap Closure H VALIDATE v2 (L1–L3) ===", flush=True)
    print(f"Base freeze: {base['config_hash']}", flush=True)
    print(f"v2 tag: {v2_hash}", flush=True)
    print(f"Looseners: {loosen}", flush=True)
    print("OOS: DISABLED", flush=True)

    frames = {}
    for p in PAIRS:
        df = load_or_build_5m(args.data_dir, p, force=False)
        if df.index.tz is None:
            import pandas as pd

            df.index = df.index.tz_localize("UTC").tz_convert("America/New_York")
        # Slice for speed: warmup + validate only
        df = df.loc[SLICE_START : VAL[1]]
        frames[p] = df
        print(f"  ready {p}: {len(df)} bars ({SLICE_START}..{VAL[1]})", flush=True)

    sig_cache = os.path.join(CACHE_DIR, f"narrative_signals_freeze_v2_{v2_hash}.json")
    if not args.force_cache and os.path.exists(sig_cache):
        print(f"  signal cache hit: {sig_cache}", flush=True)
        with open(sig_cache, encoding="utf-8") as f:
            blob_j = json.load(f)
        all_sigs = blob_j["sigs"]
        n_acc = blob_j["n_acc"]
        n_rej = blob_j["n_rej"]
    else:
        all_sigs = {}
        n_acc = 0
        n_rej = 0
        for pair, df in frames.items():
            print(f"  narrative signals {pair} (v2)...", flush=True)
            rej: List[Dict[str, Any]] = []
            accepted = get_all_setup_signals(
                df,
                pair,
                min_rr=2.0,
                active_setups=list(base["active_setups"]),
                use_narrative=True,
                rejections=rej,
                kz_table=base["kz_table"],
                fvg_require_displacement_candle=True,
                liquidity_model=base["liquidity_model"],
                require_ote=True,
                ote_mode="soft_score",
                raid_lookback=int(loosen["L2_raid_lookback"]),
                b_raid_clarity=bool(loosen["L1_b_raid_clarity"]),
                accept_choch_as_mss=bool(loosen["L3_accept_choch_as_mss"]),
            )
            all_sigs[pair] = accepted
            n_acc += len(accepted)
            n_rej += len(rej)
            print(f"    accepted={len(accepted)} rejected={len(rej)}", flush=True)
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(sig_cache, "w", encoding="utf-8") as f:
            json.dump({"sigs": all_sigs, "n_acc": n_acc, "n_rej": n_rej, "v2_hash": v2_hash}, f)

    print(f"Portfolio VAL {VAL[0]}->{VAL[1]}...", flush=True)
    res = run_portfolio(
        frames,
        _period_sigs(all_sigs, VAL[0], VAL[1]),
        start=VAL[0],
        end=VAL[1],
        starting_balance=10_000.0,
        risk_percent=1.0,
        max_slippage_pips=0.5,
        commission_per_lot=3.5,
        max_portfolio_open=3,
        max_trades_per_day=5,
        enable_breakeven=False,
        enable_usd_block=True,
    )
    meta = {}
    for pair, lst in all_sigs.items():
        for s in lst:
            meta[(pair, s.get("timestamp"), s.get("setup_id"))] = s
    for t in res.get("trades", []):
        key = (
            t.get("pair"),
            t.get("timestamp_signal") or t.get("timestamp_entry"),
            t.get("setup_id"),
        )
        s = meta.get(key)
        if s:
            t["raid_grade"] = s.get("raid_grade")
            t["session"] = s.get("session")
            t["event_id"] = s.get("event_id")
            t["in_ote"] = s.get("in_ote")
            t["soft_flags"] = s.get("soft_flags")
            t["soft_score"] = s.get("soft_score")
    val = _stats("VAL", res, VAL[0], VAL[1])
    ote = _ote_impact(_period_sigs(all_sigs, VAL[0], VAL[1]), res.get("trades", []))
    go = _go_nogo(val)
    print(
        f"  VAL: resolved={val['resolved']} wr={val['wr']:.1%} "
        f"tpw={val.get('trades_per_week', 0):.2f} pnl={val.get('net_pnl')}",
        flush=True,
    )

    body = f"""# GAP CLOSURE H — VALIDATE v2 (after L1–L3)

**Base freeze hash:** `{base.get("config_hash")}`  
**v2 tag:** `{v2_hash}`  
**geometry_lock_version:** `{base.get("geometry_lock_version")}`  
**kz_table:** `{base.get("kz_table")}` · **fvg_law:** B · **OTE:** soft_score  
**liquidity_model:** session_pools  
**Pairs:** {PAIRS}  
**Validate:** `{VAL[0]} -> {VAL[1]}`  
**OOS:** **NOT RUN**

## Looseners applied (≤3)

| ID | Change |
|----|--------|
| L1 | B-raid clarity: quality≥1 + displacement → effective grade B |
| L2 | Raid lookback 12 → 20 |
| L3 | Optional MSS: setup 4 accepts CHoCH or MSS |

Locks unchanged: FVG=B, mentorship_2017, ote soft_score, opposing-liq 2R, D/P hard gates.

Narrative accepted / rejected (slice): **{n_acc}** / **{n_rej}**

## Go / No-go

**Recommendation:** `{go["recommend"]}`

Reasons:
{chr(10).join("- " + r for r in go["reasons"])}

## Validate headline

| Metric | Value |
|--------|-------|
| Resolved | {val.get("resolved")} |
| WR | {float(val.get("wr") or 0):.2%} |
| Wilson 95% CI | {val.get("wilson_95")} |
| Trades/week | {val.get("trades_per_week")} |
| Expectancy $/trade | {val.get("expectancy")} |
| Max DD % | {val.get("max_dd_pct")} |
| Net PnL | {val.get("net_pnl")} |

## Full validate JSON

```json
{json.dumps(val, indent=2, default=str)}
```

## OTE soft impact

```json
{json.dumps(ote, indent=2, default=str)}
```

## vs v1

See `GAP_CLOSURE_H_VALIDATE.md` (resolved=14, WR≈42.9%). Autopsy: `GAP_CLOSURE_H_VALIDATE_GATE_AUTOPSY.md`.

## Explicit STOP

- No OOS executed.
- No Tier M / institutional mega-spec.
- Next: human approve one OOS **or** iterate validate again.
"""
    os.makedirs(os.path.dirname(args.report), exist_ok=True)
    with open(args.report, "w", encoding="utf-8") as f:
        f.write(body)
    print(f"\nRECOMMEND: {go['recommend']}", flush=True)
    for r in go["reasons"]:
        print(f"  - {r}", flush=True)
    print(f"Report: {args.report}", flush=True)
    print("STOP: OOS not run.", flush=True)


if __name__ == "__main__":
    main()
