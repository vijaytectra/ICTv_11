# Phase 3b — Setup #2/#9 Volume Collapse Audit (+ 3a Track A no-edge)

**Date:** 2026-09-22  
**OOS:** NOT RUN  
**Production rewrite:** NONE  
**Method:** EURUSD only. Compare current vs git `440306d` (FINAL-era) generators; optional legacy indicator stack.

**Window:** validate `2024-01-01 → 2026-09-17` (slice `2023-06-01 → 2026-09-21`)

---

## 1. CODE FACT — generator semantics changed

| Setup | Legacy FINAL-era (`440306d`) | Current (post quality-ladder) |
|------:|------------------------------|-------------------------------|
| **#2** | `ifvg + ob + bias` on London/NY KZ — **no sweep, no PD, no displacement** | `sweep q≥1 + ifvg + bias + discount/premium + displacement` |
| **#9** | **Same-bar** `breaker_type` + `(ob OR fvg)` — fires on **formation**, not retest | Prior-bar breaker + **FVG AND OB** + **CE within 5 pips** + displacement |
| **#6** | Same-bar breaker + FVG + OB | 3-bar breaker window + FVG/breaker **overlap** (no coincident OB) |

FINAL report names (“Liquidity Sweep + IFVG”, “Breaker Block Retest”) **do not match** legacy code. That is a **CODE FACT**.

Legacy `add_master_htf_confluence` was **EMA-only** master bias; current uses HTF structure with EMA fallback (`strategy_setups.py`).

---

## 2. Indicator density under current H lock (MARKET-DATA FACT)

| Metric (val window) | Count |
|---------------------|------:|
| Bars | 203,076 |
| FVG ≠ 0 | 3,427 |
| IFVG ≠ 0 | 2,078 |
| Breaker ≠ 0 | 18,863 |
| OB ≠ 0 | 45,221 |
| Sweep ≠ 0 | 26,246 |
| KZ bars | 76,080 |

Raw IFVG/breaker density is **not** near zero — volume collapse is **gate/generator**, not missing indicators.

---

## 3. Volume / WR — same current H-lock indicators

| Case | Val signals | By setup | Resolved | WR | Wilson 95% | Net PnL |
|------|------------:|----------|--------:|---:|------------|--------:|
| CURRENT gens 2/6/9 | 435 | `{2:13, 6:359, 9:63}` | 304 | **30.3%** | [25.4%, 35.7%] | (see json) |
| LEGACY gens 2/6/9 | 2,105 | `{2:208, 6:12, 9:1885}` | 1,330 | **27.5%** | [25.2%, 30.0%] | (see json) |

**EMPIRICALLY VALIDATED:** Legacy generators restore FINAL-like **mix** (#9-dominant, #6 rare). Current generators invert the mix (#6-dominant).

**CONTRADICTED:** Restoring legacy generators recovers FINAL ~55% WR — legacy WR is **27.5%** on current indicators.

---

## 4. Legacy indicators + legacy gens + FVG disp OFF

| Case | Val signals | By setup | Resolved | WR | Wilson 95% |
|------|------------:|----------|--------:|---:|------------|
| LEGACY stack + gens, disp OFF | 2,443 | `{2:435, 6:81, 9:1927}` | 1,379 | **27.8%** | [25.5%, 30.3%] |

Still ~28% WR. FINAL ~55% remains **NOT REPRODUCED** under full parquet + portfolio path + BE off.

Remaining unreproduced FINAL deltas (CODE FACT / RESEARCH HYPOTHESIS):

| Factor | Class |
|--------|-------|
| `sample_ratio=0.25` in FINAL runner | CODE FACT |
| BE enabled, capital $200, per-pair `execute_backtest` | CODE FACT |
| 6-pair portfolio vs EURUSD-only | CODE FACT |
| Possible pre-fix look-ahead / accounting differences | RESEARCH HYPOTHESIS |
| Report contamination / different trade definition | RESEARCH HYPOTHESIS |

---

## 5. Phase 3a — Track A no-edge (EURUSD, H lock)

| Claim | Class |
|-------|-------|
| Track A under **current** generators ≈30% WR (Phase 2 W1–W4) | EMPIRICALLY VALIDATED |
| Track A under **legacy** #2/#6/#9 ≈27–28% WR on EURUSD 2024–26 | EMPIRICALLY VALIDATED |
| FINAL ~55% is authoritative for current freeze | **REJECTED** |
| Restore legacy #9 into production | **NO** — formation-bar spam; does not restore edge |
| Proceed to OOS on Track A | **NO** |

---

## 6. Decisions

1. Keep current (tighter) #2/#9 semantics — closer to named ICT intent; do not revert.
2. Document Track A **no-edge** on EURUSD under both current and legacy generator eras when measured causally on full data.
3. Research focus remains Track B (narrative) / geometry-locked path — still thin/weak on validate; **no OOS**.
4. Do not chase FINAL 55% via generator rollback.

## Explicit STOP

- No production code change. No OOS. No Tier M.
- Artifacts: `scratch/phase3b_setup_volume.json`, `scratch/phase3b_legacy_full.json`, `scratch/legacy_setups_440306d.py`, runners under `audit/validation/run_phase3b_*`.
