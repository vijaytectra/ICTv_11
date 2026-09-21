# OOS FAIL ATTRIBUTION (Gap Closure H)

**Prior OOS decision (existing artifact):** `INSUFFICIENT SAMPLE`
**This pass:** attribution + **one** freeze candidate only. **No new OOS run.**

**geometry_lock_version:** `H-2026-09-21`
**Freeze hash:** `7917a2f1603691cd`
**Freeze path:** `C:\personal\ICT_v11\config\strategy_config_gap_closure_h_freeze.json`

## Artifact row skim

- Rows gathered from scratch/journals: **3**
- Outcome/kind counts: `{'LOSS': 2, 'WIN': 1}`
- Setup_id counts: `{5: 1, 2: 1, 6: 1}`

## Ranked hypotheses (test on VALIDATE only)

1. **H_OTE_SOFT** — Hard OTE / additive confluence over-filtered; soft_score may raise sample without destroying WR  
   Test: `validate` · Metric: accepted_count + Wilson WR
2. **H_KZ_MENTORSHIP** — legacy_hybrid SB 15-16 vs mentorship 14-15 misaligned NY PM window  
   Test: `validate` · Metric: SB setup WR by kz_table
3. **H_FVG_CE** — Entries at FVG edge vs CE worsen fill/SL; prefer fvg_ce  
   Test: `validate` · Metric: mean R / SL-hit rate
4. **H_RAID_GRADE** — Grade C leakage or late displacement lag dominates losses  
   Test: `validate` · Metric: loss rate by raid_grade + disp_lag
5. **H_SESSION_MIX** — Asian expanding / OTHER session bleed lowers WR  
   Test: `validate` · Metric: WR by session label

## Missed winners

Missed-winner scan requires rejection JSONL + frames; run analyze_missed_winners offline when journals exist. Not run against OOS.

## Freeze candidate (do not OOS yet)

```json
{
  "geometry_lock_version": "H-2026-09-21",
  "kz_table": "mentorship_2017",
  "fvg_require_displacement_candle": true,
  "fvg_law": "B",
  "require_ote": true,
  "ote_mode": "soft_score",
  "liquidity_model": "session_pools",
  "min_rr": 2.0,
  "risk_percent": 1.0,
  "active_setups": [
    1,
    2,
    3,
    4,
    5,
    6,
    9,
    10
  ],
  "no_be_for_gates": true,
  "scope": "H1-H6",
  "oos_status": "NOT_RUN_THIS_PASS",
  "config_hash": "7917a2f1603691cd"
}
```

## Explicit STOP

User review required before any OOS PASS/FAIL/INSUFFICIENT run.
