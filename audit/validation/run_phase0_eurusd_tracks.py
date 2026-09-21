"""
Phase 0 — EURUSD-only Track A vs Track B smoke (validate 2022-2023).
No OOS. No strategy rewrite. Measurement only.
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from backend.engine.metrics import binomial_wilson_ci, compute_win_rate
from backend.engine.portfolio_backtest import run_portfolio
from backend.engine.strategy_setups import get_all_setup_signals

CACHE = os.path.join(ROOT, "scratch", "cache_5m_ny", "EURUSD_5m_ny.parquet")
VAL = ("2022-01-01", "2023-12-31")
SLICE = ("2021-06-01", "2023-12-31")
OUT = os.path.join(ROOT, "audit", "reports", "PHASE0_EURUSD_TRACK_AB.md")


def load_eurusd():
    import pandas as pd

    df = pd.read_parquet(CACHE)
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC").tz_convert("America/New_York")
    return df.loc[SLICE[0] : SLICE[1]]


def period(sigs, start, end):
    return [s for s in sigs if start <= s["timestamp"][:10] <= end]


def run_track(label, df, use_narrative: bool, active):
    print(f"=== {label} ===", flush=True)
    rej = []
    kwargs = dict(
        min_rr=2.0,
        active_setups=active,
        use_narrative=use_narrative,
        rejections=rej if use_narrative else None,
        kz_table="mentorship_2017",
        fvg_require_displacement_candle=True,
        liquidity_model="session_pools",
        require_ote=True,
        ote_mode="soft_score",
        raid_lookback=20,
        b_raid_clarity=True,  # tightened q>=2 in narrative.py
        accept_choch_as_mss=True,
    )
    if not use_narrative:
        kwargs.pop("rejections")
        accepted = get_all_setup_signals(df, "EURUSD", **kwargs)
        rej = []
    else:
        accepted = get_all_setup_signals(df, "EURUSD", **kwargs)

    val_sigs = period(accepted, VAL[0], VAL[1])
    print(f"  accepted_all={len(accepted)} val_sigs={len(val_sigs)} rej={len(rej)}", flush=True)
    if use_narrative and rej:
        reasons = Counter(r.get("rejection_reason") for r in rej if VAL[0] <= (r.get("timestamp") or "")[:10] <= VAL[1])
        print(f"  top val rejects: {reasons.most_common(5)}", flush=True)
    else:
        reasons = Counter()

    res = run_portfolio(
        {"EURUSD": df},
        {"EURUSD": val_sigs},
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
        "use_narrative": use_narrative,
        "accepted_slice": len(accepted),
        "val_signals": len(val_sigs),
        "rejected_val_top": dict(reasons.most_common(8)),
        "resolved": m["resolved"],
        "wins": m["wins"],
        "losses": m["losses"],
        "wr": m["wr"],
        "wilson_95": ci,
        "trades_per_week": res.get("trades_per_week"),
        "net_pnl": res.get("net_pnl"),
        "max_dd_pct": res.get("max_drawdown_pct"),
    }
    print(
        f"  resolved={out['resolved']} wr={out['wr']:.1%} pnl={out['net_pnl']}",
        flush=True,
    )
    return out


def main():
    # Track A: all 8 active setups, no narrative
    # Track B: narrative with v3 active set [1,4,5,9,10] (2/3/6 killed on validate path)
    df = load_eurusd()
    print(f"EURUSD bars={len(df)}", flush=True)
    a = run_track("TRACK_A_no_narrative", df, False, [1, 2, 3, 4, 5, 6, 9, 10])
    b = run_track("TRACK_B_narrative_v3_active", df, True, [1, 4, 5, 9, 10])

    body = f"""# PHASE 0 — EURUSD Track A vs Track B

**Window:** validate `{VAL[0]} → {VAL[1]}` (slice warmup from `{SLICE[0]}`)  
**Pair:** EURUSD only  
**OOS:** NOT RUN  
**Geometry locks:** FVG=B, mentorship_2017, OTE soft_score

## Track A — pattern setups, no narrative 10Q

```json
{json.dumps(a, indent=2, default=str)}
```

## Track B — narrative 10Q (active [1,4,5,9,10], L1 q≥2, L2/L3 on)

```json
{json.dumps(b, indent=2, default=str)}
```

## Classification

| Claim | Class |
|-------|-------|
| Track A produces larger sample on EURUSD validate | MARKET-DATA FACT (this run) |
| Track B is more selective | MARKET-DATA FACT (this run) |
| Which track has genuine edge | UNVALIDATED until six-pair + locked OOS |
| 80% WR | NOT SUPPORTED |

## STOP

No OOS. Expand to other pairs only after reviewing this EURUSD smoke.
"""
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(body)
    print(f"Wrote {OUT}", flush=True)


if __name__ == "__main__":
    main()
