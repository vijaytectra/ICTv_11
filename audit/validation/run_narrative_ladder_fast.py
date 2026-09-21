"""
Fast narrative research runner with 5m parquet cache.
Avoids re-parsing multi-GB 1m CSVs on every run.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from typing import Any, Dict, List, Optional

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from backend.engine.data_loader import load_pair_data, resample_candles
from backend.engine.metrics import binomial_wilson_ci, compute_win_rate
from backend.engine.portfolio_backtest import run_portfolio
from backend.engine.strategy_setups import get_all_setup_signals

PAIRS_DEFAULT = ["EURUSD", "GBPUSD", "USDJPY", "USDCAD", "AUDUSD", "USDCHF"]
TRAIN = ("2020-01-01", "2021-12-31")
VAL = ("2022-01-01", "2023-12-31")
OOS_START = "2024-01-01"
OOS_END_CAP = "2026-12-31"
CACHE_DIR = os.path.join(ROOT, "scratch", "cache_5m_ny")


def _cache_path(pair: str) -> str:
    return os.path.join(CACHE_DIR, f"{pair}_5m_ny.parquet")


def load_or_build_5m(data_dir: str, pair: str, force: bool = False):
    import pandas as pd

    path = _cache_path(pair)
    if not force and os.path.exists(path):
        print(f"  cache hit {pair}: {path}", flush=True)
        df = pd.read_parquet(path)
        if df.index.tz is None:
            df.index = df.index.tz_localize("America/New_York")
        return df
    print(f"  building 5m cache {pair}...", flush=True)
    raw = load_pair_data(data_dir, pair, sample_ratio=1.0)
    df5 = resample_candles(raw, "5m")
    os.makedirs(CACHE_DIR, exist_ok=True)
    # parquet may drop tz; store as UTC then convert back
    out = df5.copy()
    out.index = out.index.tz_convert("UTC").tz_localize(None)
    out.to_parquet(path)
    print(f"  wrote {path} bars={len(df5)}", flush=True)
    return df5


def _oos_end(frames: Dict[str, Any]) -> str:
    last = min(str(df.index[-1])[:10] for df in frames.values())
    return min(last, OOS_END_CAP)


def _period_sigs(sigs, start, end):
    out = {}
    for pair, lst in sigs.items():
        out[pair] = [s for s in lst if start[:10] <= s["timestamp"][:10] <= end[:10]]
    return out


def _setup_matrix(trades: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by = defaultdict(list)
    for t in trades:
        by[int(t.get("setup_id", 0))].append(t)
    rows = []
    for sid in sorted(by):
        m = compute_win_rate(by[sid])
        pnls = [float(x.get("net_pnl", 0)) for x in by[sid]]
        wins = [p for p in pnls if p > 0]
        losses = [abs(p) for p in pnls if p < 0]
        pf = (sum(wins) / sum(losses)) if losses and sum(losses) > 0 else (99.0 if wins else 0.0)
        rows.append(
            {
                "setup_id": sid,
                "trades": len(by[sid]),
                "resolved": m["resolved"],
                "wr": round(m["wr"], 4),
                "pf": round(pf, 2),
                "net_pnl": round(sum(pnls), 2),
            }
        )
    return rows


def _stats(name, res):
    m = compute_win_rate(res.get("trades", []))
    ci = binomial_wilson_ci(m["wins"], m["resolved"])
    return {
        "period": name,
        "start": res.get("period_start"),
        "end": res.get("period_end"),
        "resolved": m["resolved"],
        "wins": m["wins"],
        "losses": m["losses"],
        "excluded": m["excluded"],
        "wr": m["wr"],
        "wilson_95": ci,
        "trades_per_week": res.get("trades_per_week"),
        "net_pnl": res.get("net_pnl"),
        "max_dd_pct": res.get("max_drawdown_pct"),
        "setup_matrix": _setup_matrix(res.get("trades", [])),
    }


def _decision(oos):
    resolved = int(oos.get("resolved", 0))
    wr = float(oos.get("wr", 0.0))
    tpw = float(oos.get("trades_per_week", 0.0) or 0.0)
    if resolved < 50:
        return "INSUFFICIENT SAMPLE"
    if tpw > 12.0:
        return "FAIL"
    if wr >= 0.80:
        return "PASS"
    return "FAIL"


def write_report(path, train, val, oos, decision, oos_window, n_acc, n_rej, pairs):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    body = f"""# NARRATIVE ENGINE OOS RESULT

**Decision:** `{decision}`
**OOS window:** `{oos_window}`
**Pairs:** {pairs}
**News filters:** EXCLUDED this cycle
**Timezone:** EET (Europe/Bucharest) -> America/New_York
**Narrative accepted / rejected (pre-portfolio):** {n_acc} / {n_rej}

## A. Root causes (pre-narrative)
- Pattern AND-gates without raid->disp->MSS->FVG chain
- No event identity / opposing-liquidity 2R gate
- Additive confluence; timezone-naive killzones

## B. Missing intelligence addressed
- Event engine + raid grades A/B/C
- Shared narrative 10Q validation
- One trade per liquidity event; USD-block correlation
- EET->NY session clocks; Asian flag fixed

## C. Code modules
- `backend/engine/data_loader.py` (EET->NY)
- `backend/engine/event_engine.py`, `narrative.py`, `trade_journal.py`
- `backend/engine/strategy_setups.py` (narrative consumer)
- `backend/engine/portfolio_backtest.py` (USD block)
- `audit/validation/run_narrative_ladder_fast.py`

## G. Train 2020-2021
```json
{json.dumps(train, indent=2, default=str)}
```

## H. Validation 2022-2023
```json
{json.dumps(val, indent=2, default=str)}
```

## I. Final OOS
```json
{json.dumps(oos, indent=2, default=str)}
```

## L. 8-setup matrix (OOS)
```json
{json.dumps(oos.get("setup_matrix", []), indent=2)}
```

## M. Final decision
**{decision}**

Gates: WR>=80%, 1:2 fixed, 1% risk, no BE, <=12 trades/week, >=50 resolved.
Never manufactured. Hard stop — no OOS retuning.
News excluded. Walk-forward/missed-winner deferred to full runner when cache is warm.
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(body)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default=r"C:\Users\Vijayakumar R\Documents")
    ap.add_argument(
        "--report",
        default=os.path.join(ROOT, "audit", "reports", "NARRATIVE_ENGINE_OOS_RESULT.md"),
    )
    ap.add_argument("--balance", type=float, default=10_000.0)
    ap.add_argument("--pairs", default="EURUSD")
    ap.add_argument("--force-cache", action="store_true")
    args = ap.parse_args()

    pairs = [p.strip().upper() for p in args.pairs.split(",") if p.strip()]
    print("=== Fast narrative ladder ===", flush=True)
    print(f"Pairs: {pairs}", flush=True)

    frames = {}
    for p in pairs:
        frames[p] = load_or_build_5m(args.data_dir, p, force=args.force_cache)
        # restore NY tz if loaded from naive parquet
        if frames[p].index.tz is None:
            import pandas as pd

            frames[p].index = (
                frames[p].index.tz_localize("UTC").tz_convert("America/New_York")
            )
        print(f"  ready {p}: {len(frames[p])} bars", flush=True)

    oos_end = _oos_end(frames)
    oos_window = f"{OOS_START} -> {oos_end}"

    # Cache narrative signals next to 5m cache
    sig_cache = os.path.join(CACHE_DIR, f"narrative_signals_{'_'.join(pairs)}.json")
    if not args.force_cache and os.path.exists(sig_cache):
        print(f"  signal cache hit: {sig_cache}", flush=True)
        with open(sig_cache, "r", encoding="utf-8") as f:
            blob = json.load(f)
        all_sigs = blob["sigs"]
        n_acc = blob["n_acc"]
        n_rej = blob["n_rej"]
    else:
        all_sigs = {}
        n_rej = 0
        n_acc = 0
        for pair, df in frames.items():
            print(f"  narrative signals {pair}...", flush=True)
            rej: List[Dict[str, Any]] = []
            accepted = get_all_setup_signals(
                df,
                pair,
                min_rr=2.0,
                active_setups=[1, 2, 3, 4, 5, 6, 9, 10],
                use_narrative=True,
                rejections=rej,
            )
            all_sigs[pair] = accepted
            n_acc += len(accepted)
            n_rej += len(rej)
            print(f"    accepted={len(accepted)} rejected={len(rej)}", flush=True)
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(sig_cache, "w", encoding="utf-8") as f:
            json.dump({"sigs": all_sigs, "n_acc": n_acc, "n_rej": n_rej}, f)
        print(f"  wrote signal cache {sig_cache}", flush=True)

    def run_span(label, start, end):
        print(f"Portfolio {label} {start}->{end}...", flush=True)
        res = run_portfolio(
            frames,
            _period_sigs(all_sigs, start, end),
            start=start,
            end=end,
            starting_balance=args.balance,
            risk_percent=1.0,
            max_trades_per_day=5,
            enable_breakeven=False,
            enable_usd_block=True,
        )
        print(
            f"  {label}: resolved={res.get('resolved')} wr={res.get('wr', 0):.1%} "
            f"tpw={res.get('trades_per_week', 0):.2f}",
            flush=True,
        )
        return _stats(label, res)

    train = run_span("TRAIN", TRAIN[0], TRAIN[1])
    val = run_span("VAL", VAL[0], VAL[1])
    oos = run_span("OOS", OOS_START, oos_end)
    decision = _decision(oos)

    write_report(
        args.report, train, val, oos, decision, oos_window, n_acc, n_rej, pairs
    )
    print(f"\nDECISION: {decision}", flush=True)
    print(f"Report: {args.report}", flush=True)


if __name__ == "__main__":
    main()
