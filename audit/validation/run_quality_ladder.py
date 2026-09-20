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
from audit.validation.write_quality_ladder_report import (
    filter_trades_by_spread_p95,
    run_causality_suite,
    write_quality_ladder_report,
)
from backend.engine.confluence_filters import (
    ConfluenceFilterConfig,
    filter_signals,
    iter_grid_configs,
)
from backend.engine.data_loader import load_pair_data, resample_candles
from backend.engine.metrics import evaluate_gates
from backend.engine.portfolio_backtest import run_portfolio
from backend.engine.strategy_setups import get_all_setup_signals
import numpy as np
import pandas as pd

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


def _synthetic_frames() -> Dict[str, Any]:
    """Tiny smoke frames for pipeline wiring tests (not a real study)."""
    out = {}
    for i, pair in enumerate(PAIRS):
        n = 400
        times = pd.date_range("2020-01-02", periods=n, freq="5min")
        base = 1.10 + i * 0.01
        closes = base + np.cumsum(np.random.default_rng(i).normal(0, 0.0002, n))
        out[pair] = pd.DataFrame(
            {
                "open": closes,
                "high": closes + 0.0003,
                "low": closes - 0.0003,
                "close": closes,
                "spread_pips": 0.8,
            },
            index=times,
        )
    return out


def _build_loopholes(
    frames: Dict[str, Any],
    winner_cfg: ConfluenceFilterConfig,
    oos_m: Dict[str, Any],
    capital: float,
) -> Dict[str, Any]:
    print("Loophole battery (L1/L7/L10/L16)...", flush=True)
    l1 = run_causality_suite(ROOT)
    l7 = filter_trades_by_spread_p95(oos_m.get("trades", []))

    cfg_ema = deepcopy(winner_cfg)
    cfg_ema.use_ema_bias_fallback = True
    cfg_htf = deepcopy(winner_cfg)
    cfg_htf.use_ema_bias_fallback = False
    val_ema = _run_period(frames, cfg_ema, VAL[0], VAL[1], capital)
    val_htf = _run_period(frames, cfg_htf, VAL[0], VAL[1], capital)
    l10 = {
        "with_ema_wr": val_ema.get("wr"),
        "htf_only_wr": val_htf.get("wr"),
        "frozen_uses_ema": winner_cfg.use_ema_bias_fallback,
    }

    l16 = {}
    for cap in (200.0, 2000.0, 10000.0):
        r = _run_period(frames, winner_cfg, OOS_START, datetime.utcnow().strftime("%Y-%m-%d"), cap)
        l16[str(int(cap))] = {
            "wr": r.get("wr"),
            "resolved": r.get("resolved"),
            "net_pnl": r.get("net_pnl"),
            "trades_per_week": r.get("trades_per_week"),
        }

    return {
        "L1_causality": l1,
        "L7_spread": l7,
        "L10_ema_ablation": l10,
        "L16_capital": l16,
    }


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
    parser.add_argument(
        "--smoke-synthetic",
        action="store_true",
        help="Wire-test ladder on synthetic bars (not a PASS/FAIL study)",
    )
    parser.add_argument(
        "--skip-loopholes",
        action="store_true",
        help="Skip L1/L7/L10/L16 battery (faster)",
    )
    args = parser.parse_args()

    oos_end = datetime.utcnow().strftime("%Y-%m-%d")

    if args.smoke_synthetic:
        print("SMOKE MODE: synthetic data only — verdict is NOT a real study.", flush=True)
        integrity = {"ok": True, "errors": [], "smoke": True}
        frames = _synthetic_frames()
        # Narrow dates to synthetic span
        global TRAIN, VAL, OOS_START
        TRAIN = ("2020-01-02", "2020-01-02")
        VAL = ("2020-01-02", "2020-01-02")
        OOS_START = "2020-01-02"
        oos_end = "2020-01-02"
        args.max_grid = min(args.max_grid, 4)
    else:
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
        ranked = []
        for cfg in grid:
            res = _run_period(frames, cfg, TRAIN[0], TRAIN[1], args.capital)
            if res["trades_per_week"] <= 12.0 or args.smoke_synthetic:
                ranked.append((cfg, res))
        ranked.sort(key=lambda x: x[1]["net_pnl"], reverse=True)
        train_candidates = ranked[:5] if ranked else [(grid[0], _run_period(frames, grid[0], TRAIN[0], TRAIN[1], args.capital))]
        print(f"Fallback candidates: {len(train_candidates)}", flush=True)

    best = None
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
            "smoke_synthetic": bool(args.smoke_synthetic),
        },
    )
    print(f"Frozen hash: {digest}", flush=True)

    if args.skip_oos:
        print("Skipping OOS (--skip-oos).")
        raise SystemExit(0)

    print("Running OOS once (hard stop after)...", flush=True)
    oos_m = _run_period(frames, winner_cfg, OOS_START, oos_end, args.capital)
    gates = evaluate_gates(oos_m)
    # Smoke never counts as scientific PASS
    if args.smoke_synthetic:
        verdict = "SMOKE_ONLY"
    else:
        verdict = "PASS" if gates["all_pass"] else "FAIL"

    loopholes = {}
    if not args.skip_loopholes and not args.smoke_synthetic:
        loopholes = _build_loopholes(frames, winner_cfg, oos_m, args.capital)
    elif args.smoke_synthetic:
        loopholes = {"L7_spread": filter_trades_by_spread_p95(oos_m.get("trades", []))}

    report_path = os.path.join(ROOT, "audit", "reports", "QUALITY_LADDER_OOS_RESULT.md")
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    report = write_quality_ladder_report(
        report_path,
        verdict=verdict,
        train_m=train_m,
        val_m=val_m,
        oos_m=oos_m,
        gates=gates,
        filters=_cfg_to_dict(winner_cfg),
        digest=digest,
        kill_log=kill_log,
        integrity=integrity,
        loopholes=loopholes,
    )
    print(f"VERDICT: {verdict}")
    print(f"Report: {report}")
    if verdict == "PASS":
        raise SystemExit(0)
    if verdict == "SMOKE_ONLY":
        raise SystemExit(0)
    raise SystemExit(1)


if __name__ == "__main__":
    main()
