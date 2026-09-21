"""
Narrative-engine research ladder: Train → Val freeze → single OOS.
Bins: 2020–2021 / 2022–2023 / 2024→last available ≤2026-12-31.
News filters: EXCLUDED (documented).
Hard stop on OOS FAIL — no retuning.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from backend.engine.data_loader import load_pair_data, resample_candles
from backend.engine.metrics import binomial_wilson_ci, compute_win_rate, evaluate_gates, trades_per_week
from backend.engine.portfolio_backtest import run_portfolio
from backend.engine.strategy_setups import get_all_setup_signals
from backend.engine.trade_journal import analyze_missed_winners

PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "USDCAD", "AUDUSD", "USDCHF"]
TRAIN = ("2020-01-01", "2021-12-31")
VAL = ("2022-01-01", "2023-12-31")
OOS_START = "2024-01-01"
OOS_END_CAP = "2026-12-31"

ACTIVE_SETUPS = [1, 2, 3, 4, 5, 6, 9, 10]


def _load_frames(data_dir: str, pairs: List[str]) -> Dict[str, Any]:
    out = {}
    for pair in pairs:
        print(f"  load {pair}...", flush=True)
        raw = load_pair_data(data_dir, pair, sample_ratio=1.0)
        out[pair] = resample_candles(raw, "5m")
        print(f"    {pair}: {len(out[pair])} bars {out[pair].index[0]} -> {out[pair].index[-1]}", flush=True)
    return out


def _oos_end(frames: Dict[str, Any]) -> str:
    last = min(str(df.index[-1])[:10] for df in frames.values())
    return min(last, OOS_END_CAP)


def _build_signals(
    frames: Dict[str, Any],
) -> Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, List[Dict[str, Any]]]]:
    sigs: Dict[str, List[Dict[str, Any]]] = {}
    all_rej: Dict[str, List[Dict[str, Any]]] = {}
    for pair, df in frames.items():
        print(f"  narrative signals {pair}...", flush=True)
        rej: List[Dict[str, Any]] = []
        accepted = get_all_setup_signals(
            df,
            pair,
            min_rr=2.0,
            active_setups=ACTIVE_SETUPS,
            use_narrative=True,
            rejections=rej,
        )
        sigs[pair] = accepted
        all_rej[pair] = rej
        print(f"    accepted={len(accepted)} rejected={len(rej)}", flush=True)
    return sigs, all_rej


def _period_sigs(
    sigs: Dict[str, List[Dict[str, Any]]], start: str, end: str
) -> Dict[str, List[Dict[str, Any]]]:
    out: Dict[str, List[Dict[str, Any]]] = {}
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
        pnls = [float(t.get("net_pnl", 0)) for t in by[sid]]
        wins = [p for p in pnls if p > 0]
        losses = [abs(p) for p in pnls if p < 0]
        pf = (sum(wins) / sum(losses)) if losses and sum(losses) > 0 else (99.0 if wins else 0.0)
        rows.append(
            {
                "setup_id": sid,
                "trades": len(by[sid]),
                "resolved": m["resolved"],
                "wr": m["wr"],
                "pf": round(pf, 2),
                "net_pnl": round(sum(pnls), 2),
            }
        )
    return rows


def _walk_forward(
    frames: Dict[str, Any],
    all_sigs: Dict[str, List[Dict[str, Any]]],
    balance: float,
) -> List[Dict[str, Any]]:
    """
    Simple causal walk-forward: 2y train label / 1y apply windows (reporting only;
    no parameter search — narrative rules are frozen).
    """
    windows = [
        ("2020-01-01", "2021-12-31", "2022-01-01", "2022-12-31"),
        ("2021-01-01", "2022-12-31", "2023-01-01", "2023-12-31"),
        ("2022-01-01", "2023-12-31", "2024-01-01", "2024-12-31"),
    ]
    rows = []
    for tr0, tr1, te0, te1 in windows:
        res = run_portfolio(
            frames,
            _period_sigs(all_sigs, te0, te1),
            start=te0,
            end=te1,
            starting_balance=balance,
            risk_percent=1.0,
            enable_breakeven=False,
            enable_usd_block=True,
        )
        m = compute_win_rate(res.get("trades", []))
        rows.append(
            {
                "train": f"{tr0}→{tr1}",
                "test": f"{te0}→{te1}",
                "resolved": m["resolved"],
                "wr": m["wr"],
                "tpw": res.get("trades_per_week"),
                "net_pnl": res.get("net_pnl"),
            }
        )
    return rows

    resolved = int(oos.get("resolved", 0))
    wr = float(oos.get("wr", 0.0))
    tpw = float(oos.get("trades_per_week", 0.0))
    if resolved < 50:
        return "INSUFFICIENT SAMPLE"
    if tpw > 12.0:
        return "FAIL"
    if wr >= 0.80:
        return "PASS"
    return "FAIL"


def _stats_block(name: str, res: Dict[str, Any]) -> Dict[str, Any]:
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


def write_report(
    path: str,
    train: Dict[str, Any],
    val: Dict[str, Any],
    oos: Dict[str, Any],
    decision: str,
    missed: List[Dict[str, Any]],
    oos_window: str,
    n_rej: int,
    walk_forward: Optional[List[Dict[str, Any]]] = None,
) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lines = [
        "# NARRATIVE ENGINE OOS RESULT",
        "",
        f"**Decision:** `{decision}`",
        f"**OOS window:** `{oos_window}`",
        f"**News filters:** EXCLUDED this cycle",
        f"**Timezone:** EET (Europe/Bucharest) → America/New_York",
        f"**Narrative rejections (all periods candidates):** {n_rej}",
        "",
        "## A. Root causes (pre-narrative)",
        "- Pattern AND-gates without raid→disp→MSS→FVG chain",
        "- No event identity / opposing-liquidity 2R gate",
        "- Additive confluence; timezone-naive killzones",
        "",
        "## B. Missing intelligence addressed",
        "- Event engine + raid grades A/B/C",
        "- Shared narrative 10Q validation",
        "- One trade per liquidity event; USD-block correlation",
        "",
        "## G. Train 2020–2021",
        "```json",
        json.dumps(train, indent=2, default=str),
        "```",
        "",
        "## H. Validation 2022–2023",
        "```json",
        json.dumps(val, indent=2, default=str),
        "```",
        "",
        "## I. Final OOS 2024→",
        "```json",
        json.dumps(oos, indent=2, default=str),
        "```",
        "",
        "## Walk-forward (frozen rules)",
        "```json",
        json.dumps(walk_forward or [], indent=2, default=str),
        "```",
        "",
        "## J. Missed-winner sample (offline 2R)",
        f"Count: {len(missed)}",
        "```json",
        json.dumps(missed[:50], indent=2, default=str),
        "```",
        "",
        "## L. 8-setup matrix (OOS)",
        "```json",
        json.dumps(oos.get("setup_matrix", []), indent=2),
        "```",
        "",
        "## M. Final decision",
        f"**{decision}**",
        "",
        "Gates: WR≥80%, 1:2 fixed, 1% risk, no BE, ≤12 trades/week, ≥50 resolved.",
        "Never manufactured. Hard stop — no OOS retuning.",
        "",
    ]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--data-dir",
        default=r"C:\Users\Vijayakumar R\Documents",
    )
    ap.add_argument(
        "--report",
        default=os.path.join(ROOT, "audit", "reports", "NARRATIVE_ENGINE_OOS_RESULT.md"),
    )
    ap.add_argument("--balance", type=float, default=10_000.0)
    ap.add_argument(
        "--pairs",
        default=",".join(PAIRS),
        help="Comma-separated pairs (default: all 6 majors)",
    )
    ap.add_argument("--fast", action="store_true", help="Skip walk-forward and missed-winner scan")
    args = ap.parse_args()

    pairs = [p.strip().upper() for p in args.pairs.split(",") if p.strip()]

    print("=== Narrative ladder ===", flush=True)
    print(f"Pairs: {pairs}", flush=True)
    print("Loading frames...", flush=True)
    frames = _load_frames(args.data_dir, pairs)
    oos_end = _oos_end(frames)
    oos_window = f"{OOS_START} -> {oos_end}"

    print("Building narrative signals...", flush=True)
    all_sigs, all_rej = _build_signals(frames)
    n_rej = sum(len(v) for v in all_rej.values())

    port_rej: List[Dict[str, Any]] = []

    def run_span(label: str, start: str, end: str) -> Dict[str, Any]:
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
            rejections=port_rej,
        )
        return _stats_block(label, res)

    train = run_span("TRAIN", TRAIN[0], TRAIN[1])
    val = run_span("VAL", VAL[0], VAL[1])
    oos = run_span("OOS", OOS_START, oos_end)

    flat_rej = []
    for pair, rows in all_rej.items():
        for r in rows:
            if OOS_START <= str(r.get("timestamp", ""))[:10] <= oos_end:
                flat_rej.append(r)
    if args.fast:
        missed = []
        wf = []
        print("Fast mode: skip walk-forward + missed-winner scan", flush=True)
    else:
        missed = analyze_missed_winners(flat_rej[:300], frames)
        print("Walk-forward folds...", flush=True)
        wf = _walk_forward(frames, all_sigs, args.balance)

    decision = _decision(oos)

    # Attach setup matrix already inside oos
    write_report(
        args.report,
        train,
        val,
        oos,
        decision,
        missed,
        oos_window,
        n_rej + len(port_rej),
        walk_forward=wf,
    )
    print(f"\nDECISION: {decision}", flush=True)
    print(f"Report: {args.report}", flush=True)
    print(
        f"OOS wr={oos['wr']:.1%} resolved={oos['resolved']} tpw={oos['trades_per_week']:.2f}",
        flush=True,
    )


if __name__ == "__main__":
    main()
