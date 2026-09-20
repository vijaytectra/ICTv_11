"""
PASS/FAIL report writer + loophole battery helpers (L7, L10, L16).
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from backend.engine.metrics import binomial_wilson_ci, compute_win_rate


def filter_trades_by_spread_p95(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
    """L7: compare full WR vs excluding entries with spread > p95."""
    spreads = [
        float(t.get("spread_at_entry_pips", t.get("spread_pips", 0.0)) or 0.0)
        for t in trades
    ]
    if not spreads:
        return {
            "p95_spread": None,
            "full": compute_win_rate(trades),
            "ex_high_spread": compute_win_rate([]),
            "n_excluded": 0,
        }
    p95 = float(sorted(spreads)[max(0, int(0.95 * (len(spreads) - 1)))])
    kept = [
        t
        for t in trades
        if float(t.get("spread_at_entry_pips", t.get("spread_pips", 0.0)) or 0.0)
        <= p95
    ]
    return {
        "p95_spread": p95,
        "full": compute_win_rate(trades),
        "ex_high_spread": compute_win_rate(kept),
        "n_excluded": len(trades) - len(kept),
    }


def run_causality_suite(repo_root: str) -> Dict[str, Any]:
    """L1 hook: re-run causality tests; capture pass/fail."""
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_no_lookahead.py",
        "tests/test_live_causality.py",
        "-q",
        "--tb=no",
    ]
    try:
        proc = subprocess.run(
            cmd,
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=180,
        )
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout_tail": (proc.stdout or "")[-500:],
            "stderr_tail": (proc.stderr or "")[-500:],
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def write_quality_ladder_report(
    path: str,
    *,
    verdict: str,
    train_m: Dict[str, Any],
    val_m: Dict[str, Any],
    oos_m: Dict[str, Any],
    gates: Dict[str, Any],
    filters: Dict[str, Any],
    digest: str,
    kill_log: List[Dict[str, Any]],
    integrity: Dict[str, Any],
    loopholes: Optional[Dict[str, Any]] = None,
) -> str:
    loopholes = loopholes or {}
    ci = binomial_wilson_ci(oos_m.get("wins", 0), oos_m.get("resolved", 0))
    lines = [
        f"# Quality Ladder OOS Result — **{verdict}**",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
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
        json.dumps(filters, indent=2),
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
        f"ok={integrity.get('ok')}; errors={json.dumps(integrity.get('errors', []))}",
        "",
        "## Loophole battery",
        "",
    ]

    # L1
    l1 = loopholes.get("L1_causality", {})
    lines.append(f"- **L1 causality suite:** {'PASS' if l1.get('ok') else 'FAIL / not run'}")
    # L7
    l7 = loopholes.get("L7_spread", {})
    if l7:
        lines.append(
            f"- **L7 spread>p95:** p95={l7.get('p95_spread')}; "
            f"full WR={l7.get('full', {}).get('wr')}; "
            f"ex-high WR={l7.get('ex_high_spread', {}).get('wr')}; "
            f"excluded={l7.get('n_excluded')}"
        )
    else:
        lines.append("- **L7 spread>p95:** not run")
    # L10
    l10 = loopholes.get("L10_ema_ablation", {})
    if l10:
        lines.append(
            f"- **L10 EMA bias fallback ablation (val):** "
            f"with_ema WR={l10.get('with_ema_wr')}; "
            f"htf_only WR={l10.get('htf_only_wr')}; "
            f"frozen_uses_ema={l10.get('frozen_uses_ema')}"
        )
    else:
        lines.append("- **L10 EMA ablation:** not run")
    # L16
    l16 = loopholes.get("L16_capital", {})
    if l16:
        lines.append(f"- **L16 capital sensitivity:** `{json.dumps(l16)}`")
    else:
        lines.append("- **L16 capital sensitivity:** not run")

    lines.extend(
        [
            "",
            "## Hard stop",
            "",
            "If FAIL: do not retune using OOS. See design spec.",
            "",
            "## Caveats",
            "",
            "- Backtest ≠ live. No live 80% claim from this study alone.",
            "- 24h max hold in engine may force market exits; those count as WIN/LOSS by PnL sign.",
            "",
        ]
    )

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path
