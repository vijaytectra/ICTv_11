# GAP CLOSURE H — VALIDATE v3

**Base freeze hash:** `7917a2f1603691cd`  
**v3 tag:** `21243406f58ffc6a`  
**geometry_lock_version:** `H-2026-09-21`  
**kz_table:** mentorship_2017 · **fvg_law:** B · **OTE:** soft_score  
**Validate:** `2022-01-01 -> 2023-12-31` · **Pairs:** ['EURUSD', 'GBPUSD', 'USDJPY', 'USDCAD', 'AUDUSD', 'USDCHF']  
**OOS:** **NOT RUN**

## Changes vs v2

| Item | v2 | v3 |
|------|----|----|
| L1 B-raid clarity | quality≥1 + disp → B | **quality≥2 (major pool) + disp → B only** |
| L2 raid lookback | 20 | 20 (kept) |
| L3 optional MSS/CHoCH | on | on (kept) |
| Active setups | 1–6,9,10 | **[1, 4, 5, 9, 10]** |
| Killed (validate-only) | — | **[2, 3, 6]** |

Kill rationale (from v2): {
  "2": "v2 validate WR 15.4% (2/13), pnl -931",
  "3": "v2 validate WR 30.8% (4/13), pnl -201",
  "6": "v2 validate WR 25.0% (7/28), pnl -1086 \u2014 dominant loser"
}

Narrative accepted / rejected (slice): **11** / **322**

## Go / No-go

**Recommendation:** `do not OOS yet`

Reasons:
- INSUFFICIENT SAMPLE on validate: resolved=6 < 50
- Validate WR 33.3% well below 80% gate (not close enough to justify OOS burn)
- Very low activity (tpw=0.06); selectivity may be too high or underpowered

## Validate headline

| Metric | Value |
|--------|-------|
| Resolved | 6 |
| WR | 33.33% |
| Wilson 95% CI | (0.09677141110578041, 0.700006684861608) |
| Trades/week | 0.057534246575342465 |
| Expectancy $/trade | -7.2726 |
| Max DD % | 2.21777085600001 |
| Net PnL | -43.63554126131021 |

## Full validate JSON

```json
{
  "period": "VAL",
  "start": "2022-01-01",
  "end": "2023-12-31",
  "resolved": 6,
  "wins": 2,
  "losses": 4,
  "excluded": 0,
  "wr": 0.3333333333333333,
  "wilson_95": [
    0.09677141110578041,
    0.700006684861608
  ],
  "trades_per_week": 0.057534246575342465,
  "expectancy": -7.2726,
  "net_pnl": -43.63554126131021,
  "max_dd_pct": 2.21777085600001,
  "by_setup": [
    {
      "setup_id": "1",
      "trades": 5,
      "resolved": 5,
      "wins": 2,
      "losses": 3,
      "wr": 0.4,
      "net_pnl": 70.06
    },
    {
      "setup_id": "5",
      "trades": 1,
      "resolved": 1,
      "wins": 0,
      "losses": 1,
      "wr": 0.0,
      "net_pnl": -113.7
    }
  ],
  "by_raid_grade": [
    {
      "raid_grade": "B",
      "trades": 6,
      "resolved": 6,
      "wins": 2,
      "losses": 4,
      "wr": 0.3333,
      "net_pnl": -43.64
    }
  ],
  "by_session": [
    {
      "session": "NY_KZ",
      "trades": 4,
      "resolved": 4,
      "wins": 1,
      "losses": 3,
      "wr": 0.25,
      "net_pnl": -124.54
    },
    {
      "session": "SILVER_BULLET",
      "trades": 2,
      "resolved": 2,
      "wins": 1,
      "losses": 1,
      "wr": 0.5,
      "net_pnl": 80.91
    }
  ]
}
```

## OTE soft impact

```json
{
  "with_ote": {
    "label": "with_ote",
    "accepted_signals": 5,
    "resolved_trades": 5,
    "wins": 1,
    "losses": 4,
    "wr": 0.2,
    "net_pnl": -247.83
  },
  "missing_ote": {
    "label": "missing_ote",
    "accepted_signals": 3,
    "resolved_trades": 1,
    "wins": 1,
    "losses": 0,
    "wr": 1.0,
    "net_pnl": 204.2
  },
  "unknown": {
    "label": "unknown",
    "accepted_signals": 0,
    "resolved_trades": 0,
    "wins": 0,
    "losses": 0,
    "wr": 0.0,
    "net_pnl": 0
  }
}
```

## Loss tags (BUG | THESIS_OK)

**Counts:** `{"BUG": 0, "THESIS_OK": 4, "N/A": 0}`  
Artifact: `scratch/validate_v3_loss_tags.json`

```json
[
  {
    "pair": "GBPUSD",
    "setup_id": 1,
    "timestamp": "2022-08-04 07:25:00",
    "raid_grade": "B",
    "session": "NY_KZ",
    "net_pnl": -104.76,
    "tag": "THESIS_OK",
    "reasons": [
      "raid_grade=B",
      "session=NY_KZ",
      "setup=1",
      "ote_present"
    ]
  },
  {
    "pair": "GBPUSD",
    "setup_id": 1,
    "timestamp": "2022-12-30 12:35:00",
    "raid_grade": "B",
    "session": "NY_KZ",
    "net_pnl": -110.2859,
    "tag": "THESIS_OK",
    "reasons": [
      "raid_grade=B",
      "session=NY_KZ",
      "setup=1",
      "ote_present"
    ]
  },
  {
    "pair": "USDCHF",
    "setup_id": 5,
    "timestamp": "2023-01-23 08:35:00",
    "raid_grade": "B",
    "session": "NY_KZ",
    "net_pnl": -113.6965,
    "tag": "THESIS_OK",
    "reasons": [
      "raid_grade=B",
      "session=NY_KZ",
      "setup=5",
      "ote_present"
    ]
  },
  {
    "pair": "USDCAD",
    "setup_id": 1,
    "timestamp": "2023-07-24 03:45:00",
    "raid_grade": "B",
    "session": "SILVER_BULLET",
    "net_pnl": -120.8765,
    "tag": "THESIS_OK",
    "reasons": [
      "raid_grade=B",
      "session=SILVER_BULLET",
      "setup=1",
      "ote_present"
    ]
  }
]
```

## Explicit STOP

- No OOS.
- No additional looseners.
- No Tier M / institutional mega-spec.
- Next: human review go/no-go; if WR still poor, thesis/setup redesign — not OOS burn.
