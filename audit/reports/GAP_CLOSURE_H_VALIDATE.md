# GAP CLOSURE H — VALIDATE ONLY

**Freeze hash:** `7917a2f1603691cd`  
**geometry_lock_version:** `H-2026-09-21`  
**kz_table:** `mentorship_2017` · **fvg_law:** `B` · **OTE:** `require_ote=True` / `ote_mode=soft_score`  
**liquidity_model:** `session_pools`  
**Pairs:** ['EURUSD', 'GBPUSD', 'USDJPY', 'USDCAD', 'AUDUSD', 'USDCHF']  
**Validate window:** `2022-01-01 -> 2023-12-31`  
**OOS this run:** **NOT RUN** (hard stop)

Narrative accepted / rejected (full history pre-portfolio): **77** / **7484**

## Go / No-go

**Recommendation:** `do not OOS yet`

Reasons:
- INSUFFICIENT SAMPLE on validate: resolved=14 < 50
- Validate WR 42.9% well below 80% gate (not close enough to justify OOS burn)
- Very low activity (tpw=0.13); selectivity may be too high or underpowered

## Train (optional sanity)

_skipped (optional)_

## Validate 2022-2023 (required)

```json
{
  "period": "VAL",
  "start": "2022-01-01",
  "end": "2023-12-31",
  "resolved": 14,
  "wins": 6,
  "losses": 8,
  "excluded": 0,
  "wr": 0.42857142857142855,
  "wilson_95": [
    0.21380798904474121,
    0.6740935542034926
  ],
  "trades_per_week": 0.13424657534246576,
  "expectancy": 26.0912,
  "net_pnl": 365.2775570631675,
  "max_dd_pct": 4.375835785320524,
  "by_setup": [
    {
      "setup_id": "1",
      "trades": 3,
      "resolved": 3,
      "wins": 2,
      "losses": 1,
      "wr": 0.6667,
      "net_pnl": 301.97
    },
    {
      "setup_id": "2",
      "trades": 3,
      "resolved": 3,
      "wins": 0,
      "losses": 3,
      "wr": 0.0,
      "net_pnl": -344.21
    },
    {
      "setup_id": "3",
      "trades": 1,
      "resolved": 1,
      "wins": 1,
      "losses": 0,
      "wr": 1.0,
      "net_pnl": 216.98
    },
    {
      "setup_id": "6",
      "trades": 7,
      "resolved": 7,
      "wins": 3,
      "losses": 4,
      "wr": 0.4286,
      "net_pnl": 190.53
    }
  ],
  "by_raid_grade": [
    {
      "raid_grade": "A",
      "trades": 2,
      "resolved": 2,
      "wins": 0,
      "losses": 2,
      "wr": 0.0,
      "net_pnl": -229.39
    },
    {
      "raid_grade": "B",
      "trades": 12,
      "resolved": 12,
      "wins": 6,
      "losses": 6,
      "wr": 0.5,
      "net_pnl": 594.67
    }
  ],
  "by_session": [
    {
      "session": "NY_KZ",
      "trades": 7,
      "resolved": 7,
      "wins": 2,
      "losses": 5,
      "wr": 0.2857,
      "net_pnl": -119.84
    },
    {
      "session": "LONDON_KZ",
      "trades": 3,
      "resolved": 3,
      "wins": 2,
      "losses": 1,
      "wr": 0.6667,
      "net_pnl": 306.51
    },
    {
      "session": "SILVER_BULLET",
      "trades": 4,
      "resolved": 4,
      "wins": 2,
      "losses": 2,
      "wr": 0.5,
      "net_pnl": 178.61
    }
  ]
}
```

### Headline
| Metric | Value |
|--------|-------|
| Resolved | 14 |
| WR | 42.86% |
| Wilson 95% CI | (0.21380798904474121, 0.6740935542034926) |
| Trades/week | 0.13424657534246576 |
| Expectancy $/trade | 26.0912 |
| Max DD % | 4.375835785320524 |
| Net PnL | 365.2775570631675 |

### By setup
```json
[
  {
    "setup_id": "1",
    "trades": 3,
    "resolved": 3,
    "wins": 2,
    "losses": 1,
    "wr": 0.6667,
    "net_pnl": 301.97
  },
  {
    "setup_id": "2",
    "trades": 3,
    "resolved": 3,
    "wins": 0,
    "losses": 3,
    "wr": 0.0,
    "net_pnl": -344.21
  },
  {
    "setup_id": "3",
    "trades": 1,
    "resolved": 1,
    "wins": 1,
    "losses": 0,
    "wr": 1.0,
    "net_pnl": 216.98
  },
  {
    "setup_id": "6",
    "trades": 7,
    "resolved": 7,
    "wins": 3,
    "losses": 4,
    "wr": 0.4286,
    "net_pnl": 190.53
  }
]
```

### By raid grade
```json
[
  {
    "raid_grade": "A",
    "trades": 2,
    "resolved": 2,
    "wins": 0,
    "losses": 2,
    "wr": 0.0,
    "net_pnl": -229.39
  },
  {
    "raid_grade": "B",
    "trades": 12,
    "resolved": 12,
    "wins": 6,
    "losses": 6,
    "wr": 0.5,
    "net_pnl": 594.67
  }
]
```

### By session
```json
[
  {
    "session": "NY_KZ",
    "trades": 7,
    "resolved": 7,
    "wins": 2,
    "losses": 5,
    "wr": 0.2857,
    "net_pnl": -119.84
  },
  {
    "session": "LONDON_KZ",
    "trades": 3,
    "resolved": 3,
    "wins": 2,
    "losses": 1,
    "wr": 0.6667,
    "net_pnl": 306.51
  },
  {
    "session": "SILVER_BULLET",
    "trades": 4,
    "resolved": 4,
    "wins": 2,
    "losses": 2,
    "wr": 0.5,
    "net_pnl": 178.61
  }
]
```

## OTE soft impact (validate fills)

```json
{
  "with_ote": {
    "label": "with_ote",
    "accepted_signals": 6,
    "resolved_trades": 3,
    "wins": 1,
    "losses": 2,
    "wr": 0.3333,
    "net_pnl": -10.76
  },
  "missing_ote": {
    "label": "missing_ote",
    "accepted_signals": 22,
    "resolved_trades": 11,
    "wins": 5,
    "losses": 6,
    "wr": 0.4545,
    "net_pnl": 376.04
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

## Explicit STOP

- No OOS executed.
- No parameter retune on validate.
- Tier M not started.
- Next human action: approve one OOS **or** fix issues and re-validate.
