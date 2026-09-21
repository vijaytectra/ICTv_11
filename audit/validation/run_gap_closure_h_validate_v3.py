"""
Gap Closure H — VALIDATE v3.
- L1 tightened: major-pool quality≥2 only for B upgrade
- L2/L3 kept
- Kill setups 2/3/6 (validate-only)
- Tag losses BUG | THESIS_OK
No OOS. No new looseners. No Tier M.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from typing import Any, Dict, List

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from backend.engine.loss_tags import tag_trades
from backend.engine.portfolio_backtest import run_portfolio
from backend.engine.strategy_setups import get_all_setup_signals

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
V3_CFG = os.path.join(ROOT, "config", "strategy_config_gap_closure_h_validate_v3.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default=r"C:\Users\Vijayakumar R\Documents")
    ap.add_argument(
        "--report",
        default=os.path.join(ROOT, "audit", "reports", "GAP_CLOSURE_H_VALIDATE_v3.md"),
    )
    ap.add_argument("--force-cache", action="store_true")
    args = ap.parse_args()

    base = load_merged_config()
    with open(V3_CFG, encoding="utf-8") as f:
        v3 = json.load(f)
    loosen = v3["validate_looseners"]
    active = list(v3["active_setups"])
    killed = list(v3.get("killed_setups_validate_only", []))

    blob = json.dumps(
        {
            "base": base.get("config_hash"),
            "loosen": loosen,
            "active": active,
            "killed": killed,
            "geometry_lock_version": base.get("geometry_lock_version"),
            "l1_mode": loosen.get("L1_mode"),
        },
        sort_keys=True,
    )
    v3_hash = hashlib.sha256(blob.encode()).hexdigest()[:16]

    print("=== Gap Closure H VALIDATE v3 ===", flush=True)
    print(f"Base freeze: {base['config_hash']}", flush=True)
    print(f"v3 tag: {v3_hash}", flush=True)
    print(f"L1 mode: {loosen.get('L1_mode')}", flush=True)
    print(f"Active setups: {active}", flush=True)
    print(f"Killed (validate-only): {killed}", flush=True)
    print("OOS: DISABLED", flush=True)

    frames = {}
    for p in PAIRS:
        df = load_or_build_5m(args.data_dir, p, force=False)
        if df.index.tz is None:
            import pandas as pd

            df.index = df.index.tz_localize("UTC").tz_convert("America/New_York")
        df = df.loc[SLICE_START : VAL[1]]
        frames[p] = df
        print(f"  ready {p}: {len(df)} bars", flush=True)

    sig_cache = os.path.join(CACHE_DIR, f"narrative_signals_freeze_v3_{v3_hash}.json")
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
            print(f"  narrative signals {pair} (v3)...", flush=True)
            rej: List[Dict[str, Any]] = []
            accepted = get_all_setup_signals(
                df,
                pair,
                min_rr=2.0,
                active_setups=active,
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
            json.dump(
                {"sigs": all_sigs, "n_acc": n_acc, "n_rej": n_rej, "v3_hash": v3_hash},
                f,
            )

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
    loss_tags = tag_trades(res.get("trades", []))
    go = _go_nogo(val)
    print(
        f"  VAL: resolved={val['resolved']} wr={val['wr']:.1%} "
        f"tpw={val.get('trades_per_week', 0):.2f} pnl={val.get('net_pnl')}",
        flush=True,
    )
    print(f"  Loss tags: {loss_tags['counts']}", flush=True)

    # Persist loss tag rows
    tag_path = os.path.join(ROOT, "scratch", "validate_v3_loss_tags.json")
    with open(tag_path, "w", encoding="utf-8") as f:
        json.dump(loss_tags, f, indent=2, default=str)

    body = f"""# GAP CLOSURE H — VALIDATE v3

**Base freeze hash:** `{base.get("config_hash")}`  
**v3 tag:** `{v3_hash}`  
**geometry_lock_version:** `{base.get("geometry_lock_version")}`  
**kz_table:** mentorship_2017 · **fvg_law:** B · **OTE:** soft_score  
**Validate:** `{VAL[0]} -> {VAL[1]}` · **Pairs:** {PAIRS}  
**OOS:** **NOT RUN**

## Changes vs v2

| Item | v2 | v3 |
|------|----|----|
| L1 B-raid clarity | quality≥1 + disp → B | **quality≥2 (major pool) + disp → B only** |
| L2 raid lookback | 20 | 20 (kept) |
| L3 optional MSS/CHoCH | on | on (kept) |
| Active setups | 1–6,9,10 | **{active}** |
| Killed (validate-only) | — | **{killed}** |

Kill rationale (from v2): {json.dumps(v3.get("kill_rationale", {}), indent=2)}

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

## Loss tags (BUG | THESIS_OK)

**Counts:** `{json.dumps(loss_tags["counts"])}`  
Artifact: `scratch/validate_v3_loss_tags.json`

```json
{json.dumps(loss_tags["losses"][:40], indent=2, default=str)}
```

## Explicit STOP

- No OOS.
- No additional looseners.
- No Tier M / institutional mega-spec.
- Next: human review go/no-go; if WR still poor, thesis/setup redesign — not OOS burn.
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
