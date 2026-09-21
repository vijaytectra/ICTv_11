# GAP CLOSURE H — DoD Report

**Date:** 2026-09-21  
**Scope:** H1–H6 only  
**OOS this pass:** **NOT RUN** (explicit stop)

## Locks applied

| Item | Value |
|------|-------|
| FVG | B — wick gap + middle displacement; CE mid; mitigate=CE touch |
| KZ | mentorship_2017 (Asia 20–00, London 01–05, NY 07–10, SB 03–04/10–11/14–15) |
| OTE | soft_score (never hard-reject) |
| Liquidity model default | session_pools |
| geometry_lock_version | `H-2026-09-21` |

## Deliverables

| ID | Artifact / code | Status |
|----|-----------------|--------|
| H1 | `event_engine.py` + `tests/test_event_vocabulary.py` | Done |
| H2 | `docs/geometry/ICT_GEOMETRY_LOCK.md`, `kz_tables.py`, FVG CE/lifecycle, fixtures | Done |
| H3 | `narrative.py` soft_score + CE refine; `tests/test_ote_soft_score.py` | Done |
| H4 | `liquidity_model` flag; `audit/reports/LIQUIDITY_MODEL_ATTRIBUTION.md` | Done |
| H5 | `audit/reports/OOS_FAIL_ATTRIBUTION.md` + freeze hash | Done |
| H6 | `backend/journal/` + `/api/journal/*` + Ops UI | Done |

## Freeze candidate (review before OOS)

- Config: `config/strategy_config_gap_closure_h_freeze.json`
- Hash: see `config/config_hash_gap_closure_h_freeze.txt`
- Includes: geometry_lock_version, kz_table, FVG/OTE flags, liquidity_model=session_pools

## 10 trader questions → code gates

| # | Trader question | Gate |
|---|-----------------|------|
| 1 | Was liquidity taken? | `LIQUIDITY_SWEPT` + `nar.raid` |
| 2 | Was the raid meaningful (A/B)? | `raid_grade in {A,B}` |
| 3 | Did displacement follow? | `has_displacement` / linked `DISPLACEMENT` |
| 4 | Did structure shift (MSS)? | `has_mss` when `require_mss`; else `CHoCH` for awareness |
| 5 | Are we in discount (long) / premium (short)? | `is_discount` / `is_premium` |
| 6 | Is HTF aligned? | `master_bias` match |
| 7 | Is OTE present? | soft_score boost / `OTE_MISSING_SOFT` (no hard reject) |
| 8 | Does opposing liquidity allow ≥2R? | `OPPOSING_LIQ_LT_2R` reject |
| 9 | Is this a duplicate event? | `used_event_ids` / `DUPLICATE_EVENT` |
| 10 | Are we in a valid session window? | KZ / SB under `mentorship_2017` |

Additional structural gates: FVG CE prefer entry; reject `FVG_INVALIDATED`; fixed 1:2 RR; 1% risk; no BE for gates.

## Tests

Relevant pytest: FVG geometry, event vocabulary, geometry lock/KZ, OTE soft, journal store, narrative smoke — green.

## Explicit STOP

**Do not run OOS** until you review the freeze candidate and approve a follow-up pass.
