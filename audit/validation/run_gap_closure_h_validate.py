"""
Gap Closure H — VALIDATE ONLY under freeze hash 7917a2f1603691cd.

Hard stop: no OOS. No retune. No Tier M.
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

PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "USDCAD", "AUDUSD", "USDCHF"]
TRAIN = ("2020-01-01", "2021-12-31")
VAL = ("2022-01-01", "2023-12-31")
CACHE_DIR = os.path.join(ROOT, "scratch", "cache_5m_ny")
FREEZE_PATH = os.path.join(ROOT, "config", "strategy_config_gap_closure_h_freeze.json")
LADDER_PATH = os.path.join(ROOT, "config", "strategy_config_quality_ladder.json")


def load_merged_config() -> Dict[str, Any]:
    ladder: Dict[str, Any] = {}
    if os.path.exists(LADDER_PATH):
        with open(LADDER_PATH, encoding="utf-8") as f:
            ladder = json.load(f)
    with open(FREEZE_PATH, encoding="utf-8") as f:
        freeze = json.load(f)
    # Base ladder execution params + freeze geometry locks (freeze wins on locks)
    cfg = {
        "starting_capital": ladder.get("starting_capital", 10_000.0),
        "risk_percent": freeze.get("risk_percent", ladder.get("risk_percent", 1.0)),
        "target_rr": freeze.get("min_rr", ladder.get("target_rr", 2.0)),
        "commission_per_lot": ladder.get("commission_per_lot", 3.5),
        "max_slippage_pips": ladder.get("max_slippage_pips", 0.5),
        "max_portfolio_open": ladder.get("max_portfolio_open", 3),
        "max_trades_per_day": ladder.get("max_trades_per_day", 5),
        "breakeven_rules": ladder.get("breakeven_rules", {"enabled": False}),
        "timeframe": ladder.get("timeframe", "5m"),
        "dates": ladder.get(
            "dates",
            {
                "train": list(TRAIN),
                "validate": list(VAL),
                "oos_start": "2024-01-01",
            },
        ),
        # Locked freeze flags
        "geometry_lock_version": freeze["geometry_lock_version"],
        "kz_table": freeze["kz_table"],
        "fvg_require_displacement_candle": freeze.get(
            "fvg_require_displacement_candle", True
        ),
        "fvg_law": freeze.get("fvg_law", "B"),
        "require_ote": freeze.get("require_ote", True),
        "ote_mode": freeze.get("ote_mode", "soft_score"),
        "liquidity_model": freeze.get("liquidity_model", "session_pools"),
        "active_setups": freeze.get("active_setups", [1, 2, 3, 4, 5, 6, 9, 10]),
        "no_be_for_gates": freeze.get("no_be_for_gates", True),
        "config_hash": freeze.get("config_hash"),
    }
    return cfg


def _cache_path(pair: str) -> str:
    return os.path.join(CACHE_DIR, f"{pair}_5m_ny.parquet")


def load_or_build_5m(data_dir: str, pair: str, force: bool = False):
    import pandas as pd

    path = _cache_path(pair)
    if not force and os.path.exists(path):
        print(f"  cache hit {pair}", flush=True)
        df = pd.read_parquet(path)
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC").tz_convert("America/New_York")
        return df
    print(f"  building 5m cache {pair}...", flush=True)
    raw = load_pair_data(data_dir, pair, sample_ratio=1.0)
    df5 = resample_candles(raw, "5m")
    os.makedirs(CACHE_DIR, exist_ok=True)
    out = df5.copy()
    out.index = out.index.tz_convert("UTC").tz_localize(None)
    out.to_parquet(path)
    return df5


def _period_sigs(sigs, start, end):
    out = {}
    for pair, lst in sigs.items():
        out[pair] = [s for s in lst if start[:10] <= s["timestamp"][:10] <= end[:10]]
    return out


def _bucket_matrix(trades: List[Dict[str, Any]], key: str) -> List[Dict[str, Any]]:
    by = defaultdict(list)
    for t in trades:
        by[str(t.get(key, "?"))].append(t)
    rows = []
    for k in sorted(by, key=lambda x: (len(x), x)):
        m = compute_win_rate(by[k])
        pnls = [float(x.get("net_pnl", 0)) for x in by[k]]
        rows.append(
            {
                key: k,
                "trades": len(by[k]),
                "resolved": m["resolved"],
                "wins": m["wins"],
                "losses": m["losses"],
                "wr": round(m["wr"], 4),
                "net_pnl": round(sum(pnls), 2),
            }
        )
    return rows


def _expectancy(trades: List[Dict[str, Any]]) -> float:
    m = compute_win_rate(trades)
    if m["resolved"] == 0:
        return 0.0
    pnls = [
        float(t.get("net_pnl", 0))
        for t in trades
        if str(t.get("outcome", "")).upper() in ("WIN", "LOSS")
    ]
    return round(sum(pnls) / len(pnls), 4) if pnls else 0.0


def _stats(name, res, start, end):
    trades = res.get("trades", [])
    m = compute_win_rate(trades)
    ci = binomial_wilson_ci(m["wins"], m["resolved"])
    return {
        "period": name,
        "start": start,
        "end": end,
        "resolved": m["resolved"],
        "wins": m["wins"],
        "losses": m["losses"],
        "excluded": m["excluded"],
        "wr": m["wr"],
        "wilson_95": ci,
        "trades_per_week": res.get("trades_per_week"),
        "expectancy": _expectancy(trades),
        "net_pnl": res.get("net_pnl"),
        "max_dd_pct": res.get("max_drawdown_pct"),
        "by_setup": _bucket_matrix(trades, "setup_id"),
        "by_raid_grade": _bucket_matrix(trades, "raid_grade"),
        "by_session": _bucket_matrix(trades, "session"),
    }


def _ote_impact(sigs_period: Dict[str, List], trades: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compare accepted signals / filled trades with vs without OTE soft flag."""
    flat_sigs = [s for lst in sigs_period.values() for s in lst]
    with_ote = [s for s in flat_sigs if s.get("in_ote") or "OTE_PRESENT" in (s.get("soft_flags") or [])]
    miss_ote = [s for s in flat_sigs if "OTE_MISSING_SOFT" in (s.get("soft_flags") or [])]

    # Match trades back to signals by event_id / timestamp+pair
    def trade_ote_flag(t):
        if t.get("in_ote") or "OTE_PRESENT" in (t.get("soft_flags") or []):
            return "with_ote"
        if "OTE_MISSING_SOFT" in (t.get("soft_flags") or []):
            return "missing_ote"
        eid = t.get("event_id")
        sig_ts = t.get("timestamp_signal") or t.get("timestamp_entry")
        for s in flat_sigs:
            if eid and s.get("event_id") == eid:
                if s.get("in_ote") or "OTE_PRESENT" in (s.get("soft_flags") or []):
                    return "with_ote"
                return "missing_ote"
            if (
                s.get("timestamp") == sig_ts
                and s.get("pair") == t.get("pair")
                and s.get("setup_id") == t.get("setup_id")
            ):
                if s.get("in_ote") or "OTE_PRESENT" in (s.get("soft_flags") or []):
                    return "with_ote"
                return "missing_ote"
        return "unknown"

    by = defaultdict(list)
    for t in trades:
        by[trade_ote_flag(t)].append(t)

    def pack(label, rows, n_sig):
        m = compute_win_rate(rows)
        return {
            "label": label,
            "accepted_signals": n_sig,
            "resolved_trades": m["resolved"],
            "wins": m["wins"],
            "losses": m["losses"],
            "wr": round(m["wr"], 4),
            "net_pnl": round(sum(float(x.get("net_pnl", 0)) for x in rows), 2),
        }

    return {
        "with_ote": pack("with_ote", by.get("with_ote", []), len(with_ote)),
        "missing_ote": pack("missing_ote", by.get("missing_ote", []), len(miss_ote)),
        "unknown": pack("unknown", by.get("unknown", []), 0),
    }


def _go_nogo(val: Dict[str, Any]) -> Dict[str, Any]:
    resolved = int(val.get("resolved", 0))
    wr = float(val.get("wr", 0.0) or 0.0)
    tpw = float(val.get("trades_per_week", 0.0) or 0.0)
    ci = val.get("wilson_95") or [0.0, 0.0]
    lo = float(ci[0]) if ci else 0.0
    reasons = []
    recommend = "do not OOS yet"

    if resolved < 50:
        reasons.append(f"INSUFFICIENT SAMPLE on validate: resolved={resolved} < 50")
    if wr < 0.50:
        reasons.append(f"Validate WR {wr:.1%} well below 80% gate (not close enough to justify OOS burn)")
    elif wr < 0.80:
        reasons.append(f"Validate WR {wr:.1%} < 80% gate")
    if lo < 0.50 and resolved >= 20:
        reasons.append(f"Wilson lower bound {lo:.1%} < 50%")
    if tpw > 12.0:
        reasons.append(f"trades/week {tpw:.2f} > 12 cap")
    if tpw < 0.5 and resolved < 50:
        reasons.append(f"Very low activity (tpw={tpw:.2f}); selectivity may be too high or underpowered")

    # Approve OOS only if validate is reasonably close to gate or sample is healthy with non-awful WR
    if resolved >= 50 and wr >= 0.70 and lo >= 0.55 and tpw <= 12.0:
        recommend = "approve OOS"
        reasons.append("Validate sample >=50, WR>=70%, Wilson lo>=55%, tpw<=12 — worth one honest OOS")
    elif resolved >= 50 and wr >= 0.80 and tpw <= 12.0:
        recommend = "approve OOS"
        reasons.append("Validate meets WR>=80% and sample/frequency gates")
    else:
        if not reasons:
            reasons.append("Validate not strong enough vs 80% WR / sample gates")

    return {"recommend": recommend, "reasons": reasons}


def write_report(
    path: str,
    cfg: Dict[str, Any],
    train: Optional[Dict[str, Any]],
    val: Dict[str, Any],
    ote: Dict[str, Any],
    n_acc: int,
    n_rej: int,
    pairs: List[str],
    go: Dict[str, Any],
):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    train_block = (
        f"```json\n{json.dumps(train, indent=2, default=str)}\n```"
        if train
        else "_skipped (optional)_"
    )
    body = f"""# GAP CLOSURE H — VALIDATE ONLY

**Freeze hash:** `{cfg.get("config_hash")}`  
**geometry_lock_version:** `{cfg.get("geometry_lock_version")}`  
**kz_table:** `{cfg.get("kz_table")}` · **fvg_law:** `{cfg.get("fvg_law")}` · **OTE:** `require_ote={cfg.get("require_ote")}` / `ote_mode={cfg.get("ote_mode")}`  
**liquidity_model:** `{cfg.get("liquidity_model")}`  
**Pairs:** {pairs}  
**Validate window:** `{VAL[0]} -> {VAL[1]}`  
**OOS this run:** **NOT RUN** (hard stop)

Narrative accepted / rejected (full history pre-portfolio): **{n_acc}** / **{n_rej}**

## Go / No-go

**Recommendation:** `{go["recommend"]}`

Reasons:
{chr(10).join("- " + r for r in go["reasons"])}

## Train (optional sanity)

{train_block}

## Validate 2022-2023 (required)

```json
{json.dumps(val, indent=2, default=str)}
```

### Headline
| Metric | Value |
|--------|-------|
| Resolved | {val.get("resolved")} |
| WR | {float(val.get("wr") or 0):.2%} |
| Wilson 95% CI | {val.get("wilson_95")} |
| Trades/week | {val.get("trades_per_week")} |
| Expectancy $/trade | {val.get("expectancy")} |
| Max DD % | {val.get("max_dd_pct")} |
| Net PnL | {val.get("net_pnl")} |

### By setup
```json
{json.dumps(val.get("by_setup", []), indent=2)}
```

### By raid grade
```json
{json.dumps(val.get("by_raid_grade", []), indent=2)}
```

### By session
```json
{json.dumps(val.get("by_session", []), indent=2)}
```

## OTE soft impact (validate fills)

```json
{json.dumps(ote, indent=2, default=str)}
```

## Explicit STOP

- No OOS executed.
- No parameter retune on validate.
- Tier M not started.
- Next human action: approve one OOS **or** fix issues and re-validate.
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(body)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default=r"C:\Users\Vijayakumar R\Documents")
    ap.add_argument(
        "--report",
        default=os.path.join(ROOT, "audit", "reports", "GAP_CLOSURE_H_VALIDATE.md"),
    )
    ap.add_argument("--skip-train", action="store_true", help="Skip optional train span")
    ap.add_argument("--force-cache", action="store_true")
    ap.add_argument("--balance", type=float, default=None)
    args = ap.parse_args()

    cfg = load_merged_config()
    assert cfg.get("config_hash") == "7917a2f1603691cd", cfg.get("config_hash")
    balance = float(args.balance or cfg["starting_capital"] or 10_000.0)
    # Prefer research-scale capital if ladder left at $200 toy
    if balance < 1000:
        balance = 10_000.0

    print("=== Gap Closure H VALIDATE-ONLY ===", flush=True)
    print(f"Freeze hash: {cfg['config_hash']}", flush=True)
    print(f"Pairs: {PAIRS}", flush=True)
    print("OOS: DISABLED", flush=True)

    frames = {}
    for p in PAIRS:
        frames[p] = load_or_build_5m(args.data_dir, p, force=args.force_cache)
        if frames[p].index.tz is None:
            import pandas as pd

            frames[p].index = (
                frames[p].index.tz_localize("UTC").tz_convert("America/New_York")
            )
        print(f"  ready {p}: {len(frames[p])} bars", flush=True)

    # Fresh signal cache keyed by freeze hash (do not reuse pre-H cache)
    sig_cache = os.path.join(
        CACHE_DIR, f"narrative_signals_freeze_{cfg['config_hash']}.json"
    )
    if not args.force_cache and os.path.exists(sig_cache):
        print(f"  signal cache hit: {sig_cache}", flush=True)
        with open(sig_cache, encoding="utf-8") as f:
            blob = json.load(f)
        all_sigs = blob["sigs"]
        n_acc = blob["n_acc"]
        n_rej = blob["n_rej"]
    else:
        all_sigs = {}
        n_acc = 0
        n_rej = 0
        for pair, df in frames.items():
            print(f"  narrative signals {pair} (freeze)...", flush=True)
            rej: List[Dict[str, Any]] = []
            accepted = get_all_setup_signals(
                df,
                pair,
                min_rr=float(cfg["target_rr"]),
                active_setups=list(cfg["active_setups"]),
                use_narrative=True,
                rejections=rej,
                kz_table=cfg["kz_table"],
                fvg_require_displacement_candle=bool(
                    cfg["fvg_require_displacement_candle"]
                ),
                liquidity_model=cfg["liquidity_model"],
                require_ote=bool(cfg["require_ote"]),
                ote_mode=cfg["ote_mode"],
            )
            all_sigs[pair] = accepted
            n_acc += len(accepted)
            n_rej += len(rej)
            print(f"    accepted={len(accepted)} rejected={len(rej)}", flush=True)
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(sig_cache, "w", encoding="utf-8") as f:
            json.dump({"sigs": all_sigs, "n_acc": n_acc, "n_rej": n_rej}, f)
        print(f"  wrote {sig_cache}", flush=True)

    def run_span(label, start, end):
        print(f"Portfolio {label} {start}->{end}...", flush=True)
        res = run_portfolio(
            frames,
            _period_sigs(all_sigs, start, end),
            start=start,
            end=end,
            starting_balance=balance,
            risk_percent=float(cfg["risk_percent"]),
            max_slippage_pips=float(cfg["max_slippage_pips"]),
            commission_per_lot=float(cfg["commission_per_lot"]),
            max_portfolio_open=int(cfg["max_portfolio_open"]),
            max_trades_per_day=int(cfg["max_trades_per_day"]),
            enable_breakeven=bool(cfg.get("breakeven_rules", {}).get("enabled", False)),
            enable_usd_block=True,
        )
        # Enrich trades with signal metadata for attribution
        meta = {}
        for pair, lst in all_sigs.items():
            for s in lst:
                meta[(pair, s.get("timestamp"), s.get("setup_id"))] = s
        for t in res.get("trades", []):
            # Match signal time (entry fill time may differ)
            key = (
                t.get("pair"),
                t.get("timestamp_signal") or t.get("timestamp_entry"),
                t.get("setup_id"),
            )
            s = meta.get(key)
            if not s:
                # fallback: event_id
                for pair, lst in all_sigs.items():
                    if pair != t.get("pair"):
                        continue
                    for cand in lst:
                        if cand.get("event_id") and cand.get("event_id") == t.get("event_id"):
                            s = cand
                            break
                        if (
                            cand.get("timestamp")
                            == (t.get("timestamp_signal") or t.get("timestamp_entry"))
                            and cand.get("setup_id") == t.get("setup_id")
                        ):
                            s = cand
                            break
                    if s:
                        break
            if s:
                t["raid_grade"] = s.get("raid_grade")
                t["session"] = s.get("session")
                t["event_id"] = s.get("event_id")
                t["in_ote"] = s.get("in_ote")
                t["soft_flags"] = s.get("soft_flags")
                t["soft_score"] = s.get("soft_score")
        st = _stats(label, res, start, end)
        print(
            f"  {label}: resolved={st['resolved']} wr={st['wr']:.1%} "
            f"tpw={st.get('trades_per_week', 0):.2f} pnl={st.get('net_pnl')}",
            flush=True,
        )
        return st, res

    train = None
    if not args.skip_train:
        train, _ = run_span("TRAIN", TRAIN[0], TRAIN[1])

    val, val_res = run_span("VAL", VAL[0], VAL[1])
    ote = _ote_impact(_period_sigs(all_sigs, VAL[0], VAL[1]), val_res.get("trades", []))
    go = _go_nogo(val)

    write_report(args.report, cfg, train, val, ote, n_acc, n_rej, PAIRS, go)
    print(f"\nRECOMMEND: {go['recommend']}", flush=True)
    for r in go["reasons"]:
        print(f"  - {r}", flush=True)
    print(f"Report: {args.report}", flush=True)
    print("STOP: OOS not run.", flush=True)


if __name__ == "__main__":
    main()
