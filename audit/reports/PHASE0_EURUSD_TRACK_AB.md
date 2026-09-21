# PHASE 0 — EURUSD Track A vs Track B

**Window:** validate `2022-01-01 → 2023-12-31` (slice warmup from `2021-06-01`)  
**Pair:** EURUSD only  
**OOS:** NOT RUN  
**Geometry locks:** FVG=B, mentorship_2017, OTE soft_score

## Track A — pattern setups, no narrative 10Q

```json
{
  "label": "TRACK_A_no_narrative",
  "use_narrative": false,
  "accepted_slice": 500,
  "val_signals": 387,
  "rejected_val_top": {},
  "resolved": 267,
  "wins": 78,
  "losses": 189,
  "wr": 0.29213483146067415,
  "wilson_95": [
    0.24084552470269374,
    0.34932061720438556
  ],
  "trades_per_week": 2.5602739726027397,
  "net_pnl": -4047.4993377572,
  "max_dd_pct": 41.71135385103764
}
```

## Track B — narrative 10Q (active [1,4,5,9,10], L1 q≥2, L2/L3 on)

```json
{
  "label": "TRACK_B_narrative_v3_active",
  "use_narrative": true,
  "accepted_slice": 1,
  "val_signals": 1,
  "rejected_val_top": {
    "RAID_GRADE_C": 12,
    "NOT_IN_PREMIUM": 8,
    "NOT_IN_DISCOUNT": 6,
    "OPPOSING_LIQ_LT_2R": 5,
    "NO_LIQUIDITY_RAID": 4,
    "RAID_DIRECTION_MISMATCH": 2,
    "NO_MSS": 2,
    "DUPLICATE_EVENT": 1
  },
  "resolved": 1,
  "wins": 1,
  "losses": 0,
  "wr": 1.0,
  "wilson_95": [
    0.20654931437723745,
    1.0
  ],
  "trades_per_week": 0.00958904109589041,
  "net_pnl": 206.36000000000058,
  "max_dd_pct": 0.0
}
```

## Classification

| Claim | Class |
|-------|-------|
| Track A produces larger sample on EURUSD validate | MARKET-DATA FACT (this run) |
| Track B is more selective | MARKET-DATA FACT (this run) |
| Which track has genuine edge | UNVALIDATED until six-pair + locked OOS |
| 80% WR | NOT SUPPORTED |

## STOP

No OOS. Expand to other pairs only after reviewing this EURUSD smoke.
