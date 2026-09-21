# GAP CLOSURE H — VALIDATE GATE AUTOPSY

**Freeze hash (base):** `7917a2f1603691cd`  
**Window:** validate rejects `2022-01-01 → 2023-12-31` (slice warmup from `2021-06-01`)  
**Pairs:** 6 majors  
**OOS:** not run

## Counts

| | N |
|--|--:|
| Accepted (validate) | 25 |
| Rejected (validate) | 2317 |
| Accepted (full slice) | 30 |
| Rejected (full slice) | 3016 |

## Ranked rejection reasons (validate)

| Rank | Reason | Count | Share of rejects |
|------|--------|------:|-----------------:|
| 1 | `RAID_GRADE_C` | 904 | 39.0% |
| 2 | `NO_LIQUIDITY_RAID` | 488 | 21.1% |
| 3 | `NOT_IN_PREMIUM` | 298 | 12.9% |
| 4 | `RAID_DIRECTION_MISMATCH` | 272 | 11.7% |
| 5 | `NOT_IN_DISCOUNT` | 253 | 10.9% |
| 6 | `OPPOSING_LIQ_LT_2R` | 53 | 2.3% |
| 7 | `NO_MSS` | 34 | 1.5% |
| 8 | `DUPLICATE_EVENT` | 11 | 0.5% |
| 9 | `FVG_INVALIDATED` | 3 | 0.1% |
| 10 | `NO_OPPOSING_LIQUIDITY` | 1 | ~0% |

## Interpretation

1. **RAID_GRADE_C dominates.** Minor swing sweeps (`sweep_quality=1`) stay event-grade `C` unless a *parent-linked* `DISPLACEMENT` upgrades them. Narrative already sees window displacement, but `raid_grade` still reads the event’s stale `C` → hard reject. This is a **B-raid clarity** bug/gap, not a desire to trade pure junk.

2. **NO_LIQUIDITY_RAID** — raid lookback=12 often misses the raid that setups fire on (esp. setup 6/9 lag). Widen lookback is validate-safe.

3. **D/P + direction mismatch** — large but **not loosened** this pass (core ICT location / direction integrity).

4. **NO_MSS (34)** — setup 4 only; CHoCH already emitted separately. Make MSS optional via CHoCH acceptance.

5. Setup 6 produces most raw rejects (`RAID_GRADE_C` 765, `NO_LIQUIDITY_RAID` 424) — benefits most from (1)+(2).

## Chosen looseners (≤3) — validate-only

| # | Change | Targets | Keeps locked |
|---|--------|---------|--------------|
| L1 | **B-raid clarity:** effective grade ≥ B when `sweep_quality≥1` and displacement in window | RAID_GRADE_C | FVG=B, KZ, OTE soft |
| L2 | **Raid lookback 12→20** | NO_LIQUIDITY_RAID | same |
| L3 | **Optional MSS:** setup 4 accepts CHoCH **or** MSS | NO_MSS | same |

**Explicitly not loosened:** opposing-liq 2R, D/P hard gates, FVG law, `mentorship_2017`, `ote_mode=soft_score`.

## Next

Apply L1–L3 → re-validate → `GAP_CLOSURE_H_VALIDATE_v2.md` → **STOP (no OOS)**.

Artifact: `scratch/gate_autopsy_freeze.json`
