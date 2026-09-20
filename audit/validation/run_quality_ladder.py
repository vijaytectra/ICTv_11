"""
Quality confluence ladder: train → validate → kill → freeze → single OOS.
Blocked until JForex data integrity PASS.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from audit.validation.check_jforex_data import check_data_coverage
from backend.engine.confluence_filters import (
    ConfluenceFilterConfig,
    filter_signals,
    iter_grid_configs,
)
from backend.engine.data_loader import load_pair_data, resample_candles
from backend.engine.metrics import binomial_wilson_ci, evaluate_gates
from backend.engine.portfolio_backtest import run_portfolio
from backend.engine.strategy_setups import get_all_setup_signals

PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "USDCAD", "AUDUSD", "USDCHF"]
TRAIN = ("2020-01-01", "2021-12-31")
VAL = ("2022-01-01", "2023-12-31")
OOS_START = "2024-01-01"


def _cfg_to_dict(cfg: ConfluenceFilterConfig) -> Dict[str, Any]:
    return {
        "min_confluence_score": cfg.min_confluence_score,
        "require_displacement": cfg.require_displacement,
        "require_recent_sweep": cfg.require_recent_sweep,
        "require_pdh_pdl_touch": cfg.require_pdh_pdl_touch,
        "pdh_pdl_touch_pips": cfg.pdh_pdl_touch_pips,
        "max_trades_per_day": cfg.max_trades_per_day,
        "active_setups": list(cfg.active_setups),
        "use_ema_bias_fallback": cfg.use_ema_bias_fallback,
    }


def _load_pair_frames(data_dir: str) -> Dict[str, Any]:
    out = {}
    for pair in PAIRS:
        raw = load_pair_data(data_dir, pair, sample_ratio=1.0)
        df5 = resample_candles(raw, "5m")
        out[pair] = df5
    return out


def _signals_for_period(
    frames: Dict[str, Any],
    cfg: ConfluenceFilterConfig,
    start: str,
    end: str,
) -> Dict[str, List[Dict[str, Any]]]:
    by_pair: Dict[str, List[Dict[str, Any]]] = {}
    for pair, df in frames.items():
        raw_sigs, df_ind = get_all_setup_signals(
            df,
            pair,
            min_rr=2.0,
            active_setups=cfg.active_setups,
            return_indicators=True,
        )
        # Restrict raw to period before filter (cheap)
        raw_sigs = [
            s
            for s in raw_sigs
            if start[:10] <= s["timestamp"][:10] <= end[:10]
        ]
        by_pair[pair] = filter_signals(df_ind, raw_sigs, pair, cfg)
    return by_pair


def _run_period(
    frames: Dict[str, Any],
    cfg: ConfluenceFilterConfig,
    start: str,
    end: str,
    capital: float,
) -> Dict[str, Any]:
    sigs = _signals_for_period(frames, cfg, start, end)
    return run_portfolio(
        frames,
        sigs,
        start=start,
        end=end,
        starting_balance=capital,
        risk_percent=1.0,
        max_portfolio_open=3,
        enable_breakeven=False,
    )


def _kill_setups(
    frames: Dict[str, Any],
    base_cfg: ConfluenceFilterConfig,
    capital: float,
) -> Tuple[ConfluenceFilterConfig, List[Dict[str, Any]]]:
    survivors = []
    kill_log = []
    for sid in list(base_cfg.active_setups):
        trial = deepcopy(base_cfg)
        trial.active_setups = [sid]
        res = _run_period(frames, trial, VAL[0], VAL[1], capital)
        wr = res["wr"]
        resolved = res["resolved"]
        # Expectancy proxy: net_pnl
        exp = res["net_pnl"]
        keep = (wr >= 0.70) and (resolved >= 15) and (exp > 0)
        kill_log.append(
            {
                "setup_id": sid,
                "wr": wr,
                "resolved": resolved,
                "net_pnl": exp,
                "kept": keep,
            }
        )
        if keep:
            survivors.append(sid)
    out = deepcopy(base_cfg)
    out.active_setups = survivors if survivors else list(base_cfg.active_setups)[:1]
    return out, kill_log


def _write_freeze(cfg: ConfluenceFilterConfig, extra: Dict[str, Any]) -> str:
    path = os.path.join(ROOT, "config", "strategy_config_quality_ladder.json")
    payload = {
        "strategy_name": "ICT_Quality_Confluence_Ladder",
        "version": "1.0.0",
        "timeframe": "5m",
        "starting_capital": extra.get("capital", 200.0),
        "risk_percent": 1.0,
        "target_rr": 2.0,
        "max_slippage_pips": 0.5,
        "commission_per_lot": 3.50,
        "max_portfolio_open": 3,
        "breakeven_rules": {"enabled": False},
        "dates": {
            "train": list(TRAIN),
            "validate": list(VAL),
            "oos_start": OOS_START,
        },
        "filters": _cfg_to_dict(cfg),
        "val_gate_met": extra.get("val_gate_met", False),
        "kill_log": extra.get("kill_log", []),
    }
    text = json.dumps(payload, indent=2, sort_keys=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    hash_path = os.path.join(ROOT, "config", "config_hash_quality_ladder.txt")
    with open(hash_path, "w", encoding="utf-8") as f:
        f.write(digest + "\n")
    return digest


def _write_report(
    verdict: str,
    train_m: Dict[str, Any],
    val_m: Dict[str, Any],
    oos_m: Dict[str, Any],
    gates: Dict[str, Any],
    cfg: ConfluenceFilterConfig,
    digest: str,
    kill_log: List[Dict[str, Any]],
    integrity: Dict[str, Any],
) -> str:
    path = os.path.join(ROOT, "audit", "reports", "QUALITY_LADDER_OOS_RESULT.md")
    ci = binomial_wilson_ci(oos_m.get("wins", 0), oos_m.get("resolved", 0))
    lines = [
        f"# Quality Ladder OOS Result — **{verdict}**",
        "",
        f"Generated: {datetime.utcnow().isoformat()}Z",
        f"Config hash: `{digest}`",
        "",
        "## Gates (OOS)",
        "",
        "| Gate | Value | Threshold | Pass |",
        "|------|------:|----------:|:----:|",
        f"| WR | {oos_m.get('wr', 0):.4f} | ≥ 0.80 | {gates['win_rate']['pass']} |",
        f"| Trades/week | {oos_m.get('trades_per_week', 0):.3f} | ≤ 12.0 | {gates['trades_per_week']['pass']} |",
        f"| Resolved | {oos_m.get('resolved', 0)} | ≥ 50 | {gates['min_resolved']['pass']} |",
        "",
        f"Wilson 95% CI on OOS WR: [{ci[0]:.3f}, {ci[1]:.3f}]",
        "",
        "## Period ledger",
        "",
        "| Period | WR | Resolved | Trades/week | Net PnL | Max DD% |",
        "|--------|---:|---------:|------------:|--------:|--------:|",
        f"| Train | {train_m.get('wr', 0):.4f} | {train_m.get('resolved', 0)} | {train_m.get('trades_per_week', 0):.3f} | {train_m.get('net_pnl', 0):.2f} | {train_m.get('max_drawdown_pct', 0):.2f} |",
        f"| Val | {val_m.get('wr', 0):.4f} | {val_m.get('resolved', 0)} | {val_m.get('trades_per_week', 0):.3f} | {val_m.get('net_pnl', 0):.2f} | {val_m.get('max_drawdown_pct', 0):.2f} |",
        f"| OOS | {oos_m.get('wr', 0):.4f} | {oos_m.get('resolved', 0)} | {oos_m.get('trades_per_week', 0):.3f} | {oos_m.get('net_pnl', 0):.2f} | {oos_m.get('max_drawdown_pct', 0):.2f} |",
        "",
        "## Frozen filters",
        "",
        "```json",
        json.dumps(_cfg_to_dict(cfg), indent=2),
        "```",
        "",
        "## Kill log (validate solo)",
        "",
        "```json",
        json.dumps(kill_log, indent=2),
        "```",
        "",
        "## Data integrity",
        "",
        f"ok={integrity.get('ok')}; errors={integrity.get('errors')}",
        "",
        "## Hard stop",
        "",
        "If FAIL: do not retune using OOS. See design spec.",
        "",
    ]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default=r"C:\Users\Vijayakumar R\Documents")
    parser.add_argument("--capital", type=float, default=200.0)
    parser.add_argument("--skip-oos", action="store_true")
    parser.add_argument(
        "--max-grid",
        type=int,
        default=64,
        help="Cap grid size (full grid is 64)",
    )
    args = parser.parse_args()

    oos_end = datetime.utcnow().strftime("%Y-%m-%d")
    print("Checking data integrity...", flush=True)
    integrity = check_data_coverage(
        args.data_dir, PAIRS, "2020-01-01", oos_end
    )
    if not integrity["ok"]:
        print("DATA INTEGRITY FAIL — aborting ladder until download is complete.")
        print(json.dumps(integrity, indent=2))
        raise SystemExit(2)

    print("Loading 5m frames (full sample_ratio=1.0)...", flush=True)
    frames = _load_pair_frames(args.data_dir)

    grid = iter_grid_configs()[: args.max_grid]
    print(f"Train grid size: {len(grid)}", flush=True)

    train_candidates = []
    for i, cfg in enumerate(grid):
        res = _run_period(frames, cfg, TRAIN[0], TRAIN[1], args.capital)
        if res["wr"] >= 0.70 and res["trades_per_week"] <= 15.0:
            train_candidates.append((cfg, res))
        if (i + 1) % 8 == 0:
            print(f"  train progress {i+1}/{len(grid)}", flush=True)

    print(f"Train funnel survivors: {len(train_candidates)}", flush=True)
    if not train_candidates:
        # Fall back: best train expectancy with tpw <= 12
        ranked = []
        for cfg in grid:
            res = _run_period(frames, cfg, TRAIN[0], TRAIN[1], args.capital)
            if res["trades_per_week"] <= 12.0:
                ranked.append((cfg, res))
        ranked.sort(key=lambda x: x[1]["net_pnl"], reverse=True)
        train_candidates = ranked[:5]
        print(f"Fallback candidates: {len(train_candidates)}", flush=True)

    # Validate selection
    best = None
    best_val = None
    val_gate_met = False
    for cfg, _ in train_candidates:
        val_res = _run_period(frames, cfg, VAL[0], VAL[1], args.capital)
        gates = evaluate_gates(val_res)
        score = (
            int(gates["win_rate"]["pass"]),
            int(gates["trades_per_week"]["pass"]),
            val_res["wr"],
            val_res["net_pnl"],
            -val_res["max_drawdown_pct"],
        )
        if best is None or score > best[0]:
            best = (score, cfg, val_res)
            best_val = val_res
            val_gate_met = bool(gates["all_pass"])

    assert best is not None
    _, winner_cfg, val_m = best
    print("Kill setups on validate...", flush=True)
    winner_cfg, kill_log = _kill_setups(frames, winner_cfg, args.capital)
    val_m = _run_period(frames, winner_cfg, VAL[0], VAL[1], args.capital)
    train_m = _run_period(frames, winner_cfg, TRAIN[0], TRAIN[1], args.capital)

    digest = _write_freeze(
        winner_cfg,
        {
            "capital": args.capital,
            "val_gate_met": val_gate_met,
            "kill_log": kill_log,
        },
    )
    print(f"Frozen hash: {digest}", flush=True)

    if args.skip_oos:
        print("Skipping OOS (--skip-oos).")
        raise SystemExit(0)

    print("Running OOS once (hard stop after)...", flush=True)
    oos_m = _run_period(frames, winner_cfg, OOS_START, oos_end, args.capital)
    gates = evaluate_gates(oos_m)
    verdict = "PASS" if gates["all_pass"] else "FAIL"
    report = _write_report(
        verdict,
        train_m,
        val_m,
        oos_m,
        gates,
        winner_cfg,
        digest,
        kill_log,
        integrity,
    )
    print(f"VERDICT: {verdict}")
    print(f"Report: {report}")
    raise SystemExit(0 if verdict == "PASS" else 1)


if __name__ == "__main__":
    main()
