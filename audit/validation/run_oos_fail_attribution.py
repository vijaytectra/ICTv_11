"""
OOS FAIL attribution from existing journals / ladder artifacts (H5).

Proposes ONE freeze candidate. Does NOT run OOS.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from collections import Counter, defaultdict
from typing import Any, Dict, List

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from backend.engine.kz_tables import GEOMETRY_LOCK_VERSION, DEFAULT_KZ_TABLE
from backend.engine.trade_journal import analyze_missed_winners, load_jsonl


def _gather_rows() -> List[Dict[str, Any]]:
    paths = [
        os.path.join(ROOT, "scratch", "high_confluence_results.json"),
        os.path.join(ROOT, "audit", "reports", "NARRATIVE_ENGINE_OOS_RESULT.md"),
    ]
    rows: List[Dict[str, Any]] = []
    # JSONL journals if present
    for root, _, files in os.walk(os.path.join(ROOT, "scratch")):
        for fn in files:
            if fn.endswith(".jsonl"):
                rows.extend(load_jsonl(os.path.join(root, fn)))
    # Parse narrative OOS markdown setup matrix heuristically via companion if any
    hc = os.path.join(ROOT, "scratch", "high_confluence_results.json")
    if os.path.exists(hc):
        try:
            with open(hc, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                rows.extend(data)
            elif isinstance(data, dict) and "trades" in data:
                rows.extend(data["trades"])
        except Exception:
            pass
    return rows


def _attr_from_narrative_md() -> Dict[str, Any]:
    """Pull summary stats from existing NARRATIVE_ENGINE_OOS_RESULT.md."""
    path = os.path.join(ROOT, "audit", "reports", "NARRATIVE_ENGINE_OOS_RESULT.md")
    summary = {
        "decision": "INSUFFICIENT SAMPLE",
        "source": path if os.path.exists(path) else None,
        "hypotheses": [],
    }
    if not os.path.exists(path):
        return summary
    text = open(path, encoding="utf-8").read()
    if "INSUFFICIENT" in text:
        summary["decision"] = "INSUFFICIENT SAMPLE"
    elif "FAIL" in text and "PASS" not in text.split("Decision")[0:1]:
        summary["decision"] = "FAIL"
    # Ranked hypotheses testable on validate only
    summary["hypotheses"] = [
        {
            "rank": 1,
            "id": "H_OTE_SOFT",
            "claim": "Hard OTE / additive confluence over-filtered; soft_score may raise sample without destroying WR",
            "test_on": "validate",
            "metric": "accepted_count + Wilson WR",
        },
        {
            "rank": 2,
            "id": "H_KZ_MENTORSHIP",
            "claim": "legacy_hybrid SB 15-16 vs mentorship 14-15 misaligned NY PM window",
            "test_on": "validate",
            "metric": "SB setup WR by kz_table",
        },
        {
            "rank": 3,
            "id": "H_FVG_CE",
            "claim": "Entries at FVG edge vs CE worsen fill/SL; prefer fvg_ce",
            "test_on": "validate",
            "metric": "mean R / SL-hit rate",
        },
        {
            "rank": 4,
            "id": "H_RAID_GRADE",
            "claim": "Grade C leakage or late displacement lag dominates losses",
            "test_on": "validate",
            "metric": "loss rate by raid_grade + disp_lag",
        },
        {
            "rank": 5,
            "id": "H_SESSION_MIX",
            "claim": "Asian expanding / OTHER session bleed lowers WR",
            "test_on": "validate",
            "metric": "WR by session label",
        },
    ]
    return summary


def freeze_candidate() -> Dict[str, Any]:
    cfg = {
        "geometry_lock_version": GEOMETRY_LOCK_VERSION,
        "kz_table": DEFAULT_KZ_TABLE,
        "fvg_require_displacement_candle": True,
        "fvg_law": "B",
        "require_ote": True,
        "ote_mode": "soft_score",
        "liquidity_model": "session_pools",
        "min_rr": 2.0,
        "risk_percent": 1.0,
        "active_setups": [1, 2, 3, 4, 5, 6, 9, 10],
        "no_be_for_gates": True,
        "scope": "H1-H6",
        "oos_status": "NOT_RUN_THIS_PASS",
    }
    blob = json.dumps(cfg, sort_keys=True, separators=(",", ":"))
    cfg["config_hash"] = hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]
    return cfg


def main():
    out_md = os.path.join(ROOT, "audit", "reports", "OOS_FAIL_ATTRIBUTION.md")
    freeze_path = os.path.join(ROOT, "config", "strategy_config_gap_closure_h_freeze.json")
    hash_path = os.path.join(ROOT, "config", "config_hash_gap_closure_h_freeze.txt")

    rows = _gather_rows()
    by_outcome = Counter((r.get("outcome") or r.get("kind") or "?").upper() for r in rows)
    by_setup = Counter(r.get("setup_id") for r in rows if r.get("setup_id") is not None)
    summary = _attr_from_narrative_md()
    freeze = freeze_candidate()

    os.makedirs(os.path.dirname(out_md), exist_ok=True)
    with open(freeze_path, "w", encoding="utf-8") as f:
        json.dump(freeze, f, indent=2)
    with open(hash_path, "w", encoding="utf-8") as f:
        f.write(freeze["config_hash"] + "\n")

    missed_note = (
        "Missed-winner scan requires rejection JSONL + frames; "
        "run analyze_missed_winners offline when journals exist. Not run against OOS."
    )

    lines = [
        "# OOS FAIL ATTRIBUTION (Gap Closure H)",
        "",
        f"**Prior OOS decision (existing artifact):** `{summary['decision']}`",
        "**This pass:** attribution + **one** freeze candidate only. **No new OOS run.**",
        "",
        f"**geometry_lock_version:** `{GEOMETRY_LOCK_VERSION}`",
        f"**Freeze hash:** `{freeze['config_hash']}`",
        f"**Freeze path:** `{freeze_path}`",
        "",
        "## Artifact row skim",
        "",
        f"- Rows gathered from scratch/journals: **{len(rows)}**",
        f"- Outcome/kind counts: `{dict(by_outcome)}`",
        f"- Setup_id counts: `{dict(by_setup)}`",
        "",
        "## Ranked hypotheses (test on VALIDATE only)",
        "",
    ]
    for h in summary["hypotheses"]:
        lines.append(
            f"{h['rank']}. **{h['id']}** — {h['claim']}  \n"
            f"   Test: `{h['test_on']}` · Metric: {h['metric']}"
        )
    lines.extend(
        [
            "",
            "## Missed winners",
            "",
            missed_note,
            "",
            "## Freeze candidate (do not OOS yet)",
            "",
            "```json",
            json.dumps(freeze, indent=2),
            "```",
            "",
            "## Explicit STOP",
            "",
            "User review required before any OOS PASS/FAIL/INSUFFICIENT run.",
            "",
        ]
    )
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Wrote {out_md}")
    print(f"Freeze hash {freeze['config_hash']}")


if __name__ == "__main__":
    main()
