"""
Phase 2 — Track A reconciliation (EURUSD only).
Why ~29% WR on validate 2022–2023 vs ~55% class FINAL_VALIDATION?

Apples-to-apples ablations under current code (no OOS, no strategy rewrite):
  W1  validate 2022–2023, FVG=B lock (displacement on) — Phase 0 baseline
  W2  FINAL-like window 2024–2026, FVG=B lock
  W3  validate 2022–2023, displacement OFF (pre-lock ablation)
  All: use_narrative=False, mentorship_2017, soft_score unused (no narrative),
       BE off, portfolio path, full parquet (no sample_ratio).
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter, defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from backend.engine.metrics import binomial_wilson_ci, compute_win_rate
from backend.engine.portfolio_backtest import run_portfolio
from backend.engine.strategy_setups import get_all_setup_signals

CACHE = os.path.join(ROOT, "scratch", "cache_5m_ny", "EURUSD_5m_ny.parquet")
OUT = os.path.join(ROOT, "audit", "reports", "PHASE2_TRACK_A_RECONCILIATION.md")
JSON_OUT = os.path.join(ROOT, "scratch", "phase2_track_a_reconcile.json")

ACTIVE = [1, 2, 3, 4, 5, 6, 9, 10]


def load_eurusd(start: str, end: str):
    import pandas as pd

    df = pd.read_parquet(CACHE)
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC").tz_convert("America/New_York")
    return df.loc[start:end]


def period(sigs, start, end):
    return [s for s in sigs if start <= s["timestamp"][:10] <= end]


def by_setup(trades):
    buckets = defaultdict(lambda: {"wins": 0, "losses": 0, "resolved": 0})
    for t in trades:
        sid = int(t.get("setup_id") or t.get("setup") or -1)
        outcome = (t.get("outcome") or t.get("result") or "").upper()
        if outcome in ("WIN", "TP", "TAKE_PROFIT"):
            buckets[sid]["wins"] += 1
            buckets[sid]["resolved"] += 1
        elif outcome in ("LOSS", "SL", "STOP_LOSS"):
            buckets[sid]["losses"] += 1
            buckets[sid]["resolved"] += 1
    out = {}
    for sid, b in sorted(buckets.items()):
        n = b["resolved"]
        wr = (b["wins"] / n) if n else None
        out[sid] = {**b, "wr": wr}
    return out


def run_case(label, slice_range, val_range, fvg_disp: bool):
    print(f"\n=== {label} ===", flush=True)
    print(f"  slice={slice_range} val={val_range} fvg_disp={fvg_disp}", flush=True)
    df = load_eurusd(slice_range[0], slice_range[1])
    print(f"  bars={len(df)}", flush=True)
    accepted = get_all_setup_signals(
        df,
        "EURUSD",
        min_rr=2.0,
        active_setups=ACTIVE,
        use_narrative=False,
        kz_table="mentorship_2017",
        fvg_require_displacement_candle=fvg_disp,
        liquidity_model="session_pools",
    )
    val_sigs = period(accepted, val_range[0], val_range[1])
    setup_counts = Counter(int(s["setup_id"]) for s in val_sigs)
    print(f"  accepted_slice={len(accepted)} val_sigs={len(val_sigs)} by_setup={dict(setup_counts)}", flush=True)

    res = run_portfolio(
        {"EURUSD": df},
        {"EURUSD": val_sigs},
        start=val_range[0],
        end=val_range[1],
        starting_balance=10_000.0,
        risk_percent=1.0,
        max_slippage_pips=0.5,
        commission_per_lot=3.5,
        max_portfolio_open=3,
        max_trades_per_day=5,
        enable_breakeven=False,
        enable_usd_block=False,
    )
    trades = res.get("trades", [])
    m = compute_win_rate(trades)
    ci = binomial_wilson_ci(m["wins"], m["resolved"])
    setup_wr = by_setup(trades)
    out = {
        "label": label,
        "slice": list(slice_range),
        "val": list(val_range),
        "fvg_require_displacement_candle": fvg_disp,
        "use_narrative": False,
        "kz_table": "mentorship_2017",
        "accepted_slice": len(accepted),
        "val_signals": len(val_sigs),
        "val_signals_by_setup": dict(setup_counts),
        "resolved": m["resolved"],
        "wins": m["wins"],
        "losses": m["losses"],
        "wr": m["wr"],
        "wilson_95": ci,
        "trades_per_week": res.get("trades_per_week"),
        "net_pnl": res.get("net_pnl"),
        "max_dd_pct": res.get("max_drawdown_pct"),
        "wr_by_setup": setup_wr,
    }
    print(
        f"  resolved={out['resolved']} wr={out['wr']:.1%} pnl={out['net_pnl']} "
        f"ci=[{ci[0]:.1%},{ci[1]:.1%}]",
        flush=True,
    )
    for sid, b in setup_wr.items():
        wr_s = f"{b['wr']:.1%}" if b["wr"] is not None else "n/a"
        print(f"    setup#{sid}: n={b['resolved']} wr={wr_s}", flush=True)
    return out


def main():
    cases = [
        run_case(
            "W1_val_2022_2023_FVG_B",
            ("2021-06-01", "2023-12-31"),
            ("2022-01-01", "2023-12-31"),
            True,
        ),
        run_case(
            "W2_final_like_2024_2026_FVG_B",
            ("2023-06-01", "2026-09-21"),
            ("2024-01-01", "2026-09-17"),
            True,
        ),
        run_case(
            "W3_val_2022_2023_disp_OFF",
            ("2021-06-01", "2023-12-31"),
            ("2022-01-01", "2023-12-31"),
            False,
        ),
    ]

    with open(JSON_OUT, "w", encoding="utf-8") as f:
        json.dump(cases, f, indent=2, default=str)

    # Code/data facts for the report (static audit)
    body = f"""# Phase 2 — Track A Reconciliation (EURUSD)

**Date:** 2026-09-22  
**OOS:** NOT RUN  
**Strategy rewrite:** NONE  
**Goal:** Explain why Phase 0 Track A WR ≈29% disagrees with FINAL_VALIDATION ~55% class.

## 1. CODE FACT — baseline mismatch (before numbers)

| Dimension | FINAL_VALIDATION_REPORT | Phase 0 Track A | Same? |
|-----------|-------------------------|-----------------|-------|
| Window | **2024-01-02 → 2026-09-17** | **2022-01-01 → 2023-12-31** | **NO** |
| Pairs | 6 majors | EURUSD only | NO |
| Data load | `sample_ratio=0.25` in `run_quality_optimization_validation.py` | Full NY 5m parquet | **NO** |
| Narrative 10Q | Script calls `get_all_setup_signals(...)` with **defaults**; report volume implies pre-narrative / raw setups | Explicit `use_narrative=False` | Ambiguous historically |
| Geometry lock | Frozen JSON **has no** `fvg_law` / `kz_table` / `fvg_require_displacement` | Explicit FVG=B + mentorship_2017 | **NO** |
| Execution | Per-pair `execute_backtest`, BE **on**, capital $200 | `run_portfolio`, BE **off**, $10k | **NO** |
| Config hash | `d8ca4f7e…` (`strategy_config_frozen.json`) | Gap Closure H freeze `7917a2f1…` | **NO** |

**Classification:** Comparing Phase 0 29% to FINAL 55% as “geometry lock destroyed edge” is **INVALID** until window + sampling + BE + lock are controlled. Those are **CODE FACTS**, not hypotheses.

Dominant FINAL setups by volume: **#9 Breaker (4,526)** and **#2 IFVG (2,997)** — portfolio WR is not uniform across setups (#1 alone was already ~39%).

## 2. MARKET-DATA FACT — controlled EURUSD ablations

All cases: `use_narrative=False`, `kz_table=mentorship_2017`, `liquidity_model=session_pools`, BE off, full parquet, active [1,2,3,4,5,6,9,10].

```json
{json.dumps(cases, indent=2, default=str)}
```

### Summary table

| Case | Window | FVG disp | Resolved | WR | Wilson 95% | Net PnL |
|------|--------|:--------:|--------:|---:|------------|--------:|
"""
    for c in cases:
        ci = c["wilson_95"]
        body += (
            f"| `{c['label']}` | {c['val'][0]}→{c['val'][1]} | "
            f"{'ON' if c['fvg_require_displacement_candle'] else 'OFF'} | "
            f"{c['resolved']} | {c['wr']:.1%} | "
            f"[{ci[0]:.1%}, {ci[1]:.1%}] | {c['net_pnl']:.0f} |\n"
        )

    body += """
## 3. Interpretation (classified)

"""
    w1 = cases[0]
    w2 = cases[1]
    w3 = cases[2]
    # Auto-classify based on results
    body += f"""| Claim | Class |
|-------|-------|
| W1 (2022–23, FVG=B) WR ≈ {w1['wr']:.1%} | MARKET-DATA FACT (reconfirm Phase 0) |
| W2 (2024–26, FVG=B) WR ≈ {w2['wr']:.1%} | MARKET-DATA FACT |
| W3 (2022–23, disp OFF) WR ≈ {w3['wr']:.1%} | MARKET-DATA FACT |
| Window alone can move WR materially | {"EMPIRICALLY VALIDATED" if abs(w1["wr"] - w2["wr"]) >= 0.05 else "NOT SUPPORTED at 5pp"} (\\|W2−W1\\|={abs(w2["wr"]-w1["wr"]):.1%}) |
| Displacement ON vs OFF on 2022–23 | {"EMPIRICALLY MATERIAL" if abs(w1["wr"] - w3["wr"]) >= 0.03 else "SMALL / NOT MATERIAL"} (\\|W1−W3\\|={abs(w1["wr"]-w3["wr"]):.1%}) |
| FINAL ~55% is reconfirmed under H lock on EURUSD full data | {"SUPPORTED" if w2["wr"] >= 0.50 else "NOT RECONFIRMED"} (W2={w2["wr"]:.1%}) |
| Phase 0 29% proves no edge forever | CONTRADICTED if W2 ≥50%; else still regime-dependent — UNVALIDATED globally |

## 4. Decisions (no code change)

1. **Do not treat FINAL_VALIDATION ~55% as geometry-lock baseline** until re-run under freeze + full data + same window.
2. **Keep FVG=B lock** unless W3 clearly restores edge *and* ICT DEFINITION is revisited (not this phase).
3. **Track A on 2022–2023 EURUSD remains weak** under current locks — do not OOS from Track A validate alone.
4. Next (Phase 3 candidate): if W2 ≥50% on EURUSD, decide whether validate gate should be **2024-slice** vs **2022–23**, or document regime failure on 2022–23.

## Explicit STOP

- No OOS. No Tier M. No SMC copy.
- Report artifact: `scratch/phase2_track_a_reconcile.json`
"""
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(body)
    print(f"\nWrote {OUT}", flush=True)
    print(f"Wrote {JSON_OUT}", flush=True)


if __name__ == "__main__":
    main()
