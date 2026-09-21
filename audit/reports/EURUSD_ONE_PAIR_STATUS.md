# EURUSD — One-Pair Status Report (Phases 0–3)

**Date:** 2026-09-22  
**Pair:** EURUSD only (primary research pair)  
**Geometry lock:** `H-2026-09-21` · FVG=B · `mentorship_2017` · OTE `soft_score`  
**Freeze:** `7917a2f1603691cd`  
**OOS:** **NOT RUN**

Interactive view: canvas `EURUSD-one-pair-status.canvas.tsx`

---

## Verdict

**Track A has no EURUSD edge** under current causal measurement (**~28–32% WR**).  
**FINAL_VALIDATION ~55% is unreproduced.**  
**Track B narrative is too sparse** on EURUSD (n≈1 in Phase 0; 6 majors v3 n=6 @ 33%).  
**Do not OOS. Do not expand to six pairs yet.**

---

## Phase board

| Phase | Goal | Status | Outcome |
|------:|------|--------|---------|
| **0** | Audit + EURUSD Track A vs B | DONE | A: 29.2% WR (n=267); B: n=1 |
| **1** | SMC vs ICTv_11 concepts (no copy) | DONE | SMC FVG/swings look-ahead — reject |
| **2** | Why 29% vs FINAL ~55% | DONE | Not window/FVG lock; mix → #6 |
| **3** | Volume collapse + document no-edge | DONE | Legacy restores mix, not WR |
| **4** | Six-pair validate | **BLOCKED** | Needs validate-green path |
| **5** | One locked OOS | NOT RUN | Gate not met |

---

## Track A (pattern, no narrative 10Q)

All: full parquet, portfolio, BE off, `use_narrative=false`.

| Case | Window | Notes | Resolved | WR |
|------|--------|-------|--------:|---:|
| W1 | 2022–23 | FVG=B ON, setups 1–6,9,10 | 267 | **29.2%** |
| W2 | 2024–26 | FVG=B ON (FINAL-like window) | 320 | **30.3%** |
| W3 | 2022–23 | Displacement OFF | 311 | **29.3%** |
| W4 | 2024–26 | Kill setup #6 | 83 | **32.5%** |
| Current gens 2/6/9 | 2024–26 | H-lock indicators | 304 | **30.3%** |
| Legacy gens 2/6/9 | 2024–26 | Same indicators, `440306d` gens | 1,330 | **27.5%** |
| Legacy stack + gens | 2024–26 | EMA bias + disp OFF | 1,379 | **27.8%** |

**Phase 0 smoke:** 387 val signals → 267 resolved → WR 29.2% → PnL −$4,047 → max DD ~42%.

---

## Why FINAL ~55% is gone

| Finding | Class |
|---------|-------|
| Current Track A is **#6-heavy** (~84% of volume @ ~30% WR) | MARKET-DATA FACT |
| FINAL was **#9/#2-heavy** (#6 only 54 trades in report) | MARKET-DATA FACT (report) |
| Legacy #9 = same-bar breaker formation, **not** CE retest | CODE FACT |
| Legacy #2 = ifvg+ob, **no** sweep/PD | CODE FACT |
| Restoring legacy gens restores mix, **not** ~55% WR | EMPIRICALLY VALIDATED |
| Do not restore legacy generators to production | DECISION |

---

## Track B (narrative 10Q)

| Scope | Resolved | WR | Note |
|-------|--------:|---:|------|
| Phase 0 EURUSD only | 1 | 100% | Insufficient sample |
| Gap Closure H v3 (6 majors) | 6 | 33.3% | do not OOS; killed 2/3/6 |

---

## Locks held

- FVG=B, mentorship_2017, OTE soft_score — **kept**
- No SMC copy, no legacy #9 restore, no Tier M, no OOS

---

## Source reports

- `PHASE0_EURUSD_TRACK_AB.md`
- `EXTERNAL_CONCEPT_RECONCILIATION.md`
- `PHASE2_TRACK_A_RECONCILIATION.md`
- `PHASE3_SETUP_VOLUME_COLLAPSE.md`
- `GAP_CLOSURE_H_VALIDATE_v3.md`
- `MASTER_AUDIT_PHASE0.md`
