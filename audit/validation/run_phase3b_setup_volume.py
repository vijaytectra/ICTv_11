"""
Phase 3b — why #2/#9 volume collapsed vs FINAL (commit 440306d generators).

Measurement only: same current indicators (H lock), compare CURRENT vs LEGACY
setup generators for #2/#6/#9 on EURUSD 2024–2026. No production rewrite. No OOS.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from collections import Counter, defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from backend.engine.data_loader import get_pip_size
from backend.engine.metrics import binomial_wilson_ci, compute_win_rate
from backend.engine.portfolio_backtest import run_portfolio
from backend.engine.strategy_setups import (
    generate_signals_setup_2,
    generate_signals_setup_6,
    generate_signals_setup_9,
    run_all_indicators,
)

CACHE = os.path.join(ROOT, "scratch", "cache_5m_ny", "EURUSD_5m_ny.parquet")
LEGACY_PATH = os.path.join(ROOT, "scratch", "legacy_setups_440306d.py")
OUT_MD = os.path.join(ROOT, "audit", "reports", "PHASE3_SETUP_VOLUME_COLLAPSE.md")
OUT_JSON = os.path.join(ROOT, "scratch", "phase3b_setup_volume.json")

VAL = ("2024-01-01", "2026-09-17")
SLICE = ("2023-06-01", "2026-09-21")


def load_legacy():
    """Load git-exported 440306d generators (read-only audit)."""
    spec = importlib.util.spec_from_file_location("legacy_setups_440306d", LEGACY_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["legacy_setups_440306d"] = mod
    spec.loader.exec_module(mod)
    return mod


def period(sigs, start, end):
    return [s for s in sigs if start <= s["timestamp"][:10] <= end]


def by_setup(trades):
    buckets = defaultdict(lambda: {"wins": 0, "losses": 0, "resolved": 0})
    for t in trades:
        sid = int(t.get("setup_id", -1))
        o = str(t.get("outcome", "")).upper()
        if o == "WIN":
            buckets[sid]["wins"] += 1
            buckets[sid]["resolved"] += 1
        elif o == "LOSS":
            buckets[sid]["losses"] += 1
            buckets[sid]["resolved"] += 1
    out = {}
    for sid, b in sorted(buckets.items()):
        n = b["resolved"]
        out[sid] = {**b, "wr": (b["wins"] / n) if n else None}
    return out


def backtest(label, df, sigs):
    val = period(sigs, VAL[0], VAL[1])
    counts = Counter(int(s["setup_id"]) for s in val)
    res = run_portfolio(
        {"EURUSD": df},
        {"EURUSD": val},
        start=VAL[0],
        end=VAL[1],
        starting_balance=10_000.0,
        risk_percent=1.0,
        max_slippage_pips=0.5,
        commission_per_lot=3.5,
        max_portfolio_open=3,
        max_trades_per_day=5,
        enable_breakeven=False,
        enable_usd_block=False,
    )
    m = compute_win_rate(res.get("trades", []))
    ci = binomial_wilson_ci(m["wins"], m["resolved"])
    out = {
        "label": label,
        "val_signals": len(val),
        "val_by_setup": dict(counts),
        "resolved": m["resolved"],
        "wins": m["wins"],
        "losses": m["losses"],
        "wr": m["wr"],
        "wilson_95": ci,
        "net_pnl": res.get("net_pnl"),
        "wr_by_setup": by_setup(res.get("trades", [])),
    }
    print(
        f"{label}: val={out['val_signals']} by={out['val_by_setup']} "
        f"resolved={out['resolved']} wr={out['wr']:.1%}",
        flush=True,
    )
    return out


def indicator_counts(df_ind, start, end):
    import pandas as pd

    sub = df_ind.loc[start:end]
    return {
        "bars": len(sub),
        "fvg_nonzero": int((sub["fvg_type"] != 0).sum()),
        "ifvg_nonzero": int((sub["ifvg_type"] != 0).sum()) if "ifvg_type" in sub.columns else 0,
        "breaker_nonzero": int((sub["breaker_type"] != 0).sum())
        if "breaker_type" in sub.columns
        else 0,
        "ob_nonzero": int((sub["ob_type"] != 0).sum()) if "ob_type" in sub.columns else 0,
        "sweep_nonzero": int((sub["sweep_type"] != 0).sum())
        if "sweep_type" in sub.columns
        else 0,
        "kz_bars": int(
            (sub["is_london_kz"] | sub["is_ny_kz"] | sub["is_silver_bullet"]).sum()
        ),
    }


def main():
    import pandas as pd

    print("Loading EURUSD…", flush=True)
    df = pd.read_parquet(CACHE)
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC").tz_convert("America/New_York")
    df = df.loc[SLICE[0] : SLICE[1]]
    print(f"bars={len(df)}", flush=True)

    print("Indicators (H lock FVG=B)…", flush=True)
    df_ind = run_all_indicators(
        df,
        "EURUSD",
        kz_table="mentorship_2017",
        fvg_require_displacement_candle=True,
        liquidity_model="session_pools",
    )
    ind = indicator_counts(df_ind, VAL[0], VAL[1])
    print(f"indicator_counts_val={ind}", flush=True)

    cur = []
    cur.extend(generate_signals_setup_2(df_ind, "EURUSD", 2.0))
    cur.extend(generate_signals_setup_6(df_ind, "EURUSD", 2.0))
    cur.extend(generate_signals_setup_9(df_ind, "EURUSD", 2.0))
    r_cur = backtest("CURRENT_gens_2_6_9", df_ind, cur)

    legacy = load_legacy()
    leg = []
    leg.extend(legacy.generate_signals_setup_2(df_ind, "EURUSD", 2.0))
    leg.extend(legacy.generate_signals_setup_6(df_ind, "EURUSD", 2.0))
    leg.extend(legacy.generate_signals_setup_9(df_ind, "EURUSD", 2.0))
    r_leg = backtest("LEGACY_440306d_gens_2_6_9", df_ind, leg)

    payload = {
        "window": {"slice": list(SLICE), "val": list(VAL)},
        "indicators": "current H-lock (FVG=B, mentorship_2017)",
        "indicator_counts_val": ind,
        "current": r_cur,
        "legacy_440306d": r_leg,
        "code_diff_summary": {
            "setup_2_legacy": "ifvg + ob + bias on KZ bar; NO sweep; NO PD; NO displacement gate",
            "setup_2_current": "sweep q>=1 + ifvg + bias + discount/premium + displacement",
            "setup_9_legacy": "same-bar breaker_type + (ob OR fvg) + bias; NOT a CE retest",
            "setup_9_current": "prior-bar breaker + fvg AND ob + CE within 5 pips + displacement",
            "setup_6_legacy": "same-bar breaker + fvg + ob",
            "setup_6_current": "3-bar breaker window + FVG/breaker overlap (no same-bar OB req)",
        },
    }
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)

    def row(r):
        ci = r["wilson_95"]
        return (
            f"| `{r['label']}` | {r['val_signals']} | `{r['val_by_setup']}` | "
            f"{r['resolved']} | {r['wr']:.1%} | [{ci[0]:.1%}, {ci[1]:.1%}] | "
            f"{r['net_pnl']:.0f} |"
        )

    body = f"""# Phase 3b — Setup #2/#9 Volume Collapse Audit

**Date:** 2026-09-22  
**OOS:** NOT RUN  
**Production rewrite:** NONE  
**Method:** Same EURUSD indicators under H lock; compare **current** vs **legacy (git `440306d`)** generators for setups 2/6/9 only.

**Window:** validate `{VAL[0]} → {VAL[1]}` (slice `{SLICE[0]} → {SLICE[1]}`)

## 1. CODE FACT — generator semantics changed

| Setup | Legacy FINAL-era (`440306d`) | Current (post quality-ladder) |
|------:|------------------------------|-------------------------------|
| **#2** | `ifvg + ob + bias` on KZ bar — **no sweep, no PD, no displacement** | `sweep q≥1 + ifvg + bias + discount/premium + displacement` |
| **#9** | **Same-bar** `breaker_type` + `(ob OR fvg)` — fires on formation, not retest | Prior-bar breaker + **FVG AND OB** + **CE within 5 pips** + displacement |
| **#6** | Same-bar breaker + FVG + OB | 3-bar breaker window + FVG/breaker **overlap** (no OB coincident) |

Naming in FINAL (“Liquidity Sweep + IFVG”, “Breaker Block Retest”) **does not match** legacy code behavior. That is a **CODE FACT**.

## 2. Indicator density (MARKET-DATA FACT — current H lock)

```json
{json.dumps(ind, indent=2)}
```

## 3. Volume / WR under identical indicators

```json
{json.dumps({"current": r_cur, "legacy_440306d": r_leg}, indent=2, default=str)}
```

| Case | Val signals | By setup | Resolved | WR | Wilson 95% | Net PnL |
|------|------------:|----------|--------:|---:|------------|--------:|
{row(r_cur)}
{row(r_leg)}

## 4. Classification

| Claim | Class |
|-------|-------|
| #2/#9 fire-rate collapse is from **generator tighten**, not FVG=B alone | EMPIRICALLY VALIDATED if legacy val_signals ≫ current |
| Legacy #9 was mislabeled “retest” | CODE FACT |
| Restoring legacy generators recovers FINAL ~55% WR | {"SUPPORTED" if r_leg["wr"] >= 0.50 else "NOT SUPPORTED"} (legacy WR={r_leg["wr"]:.1%}) |
| Current tightened #2/#9 are ICT-truer | ICT DEFINITION (retest/CE) — RESEARCH judgment, not data |
| Should restore legacy #9 into production | **NO** without new validate plan — risk of reintroducing formation-bar spam |

## 5. Decisions (Phase 3a implication)

1. **Do not restore** legacy #2/#9 into live/freeze path (misnamed; formation-bar #9).
2. **Track A no-edge under current generators** on EURUSD remains standing (~30% in Phase 2).
3. If legacy WR ≥50% here: FINAL headline was **generator-era artifact**, not geometry lock — still not a license to ship legacy.
4. Track B (narrative) stays the only selective research path; do not OOS Track A.

## Explicit STOP

- No production code change. No OOS. No Tier M.
- Artifacts: `scratch/phase3b_setup_volume.json`, `scratch/legacy_setups_440306d.py` (git export only).
"""
    os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write(body)
    print(f"Wrote {OUT_MD}", flush=True)
    print(f"Wrote {OUT_JSON}", flush=True)


if __name__ == "__main__":
    main()
