# GAP CLOSURE H — VALIDATE v2 (after L1–L3)

**Base freeze hash:** `7917a2f1603691cd`  
**v2 tag:** `228245804e91bac3`  
**geometry_lock_version:** `H-2026-09-21`  
**kz_table:** `mentorship_2017` · **fvg_law:** B · **OTE:** soft_score  
**liquidity_model:** session_pools  
**Pairs:** ['EURUSD', 'GBPUSD', 'USDJPY', 'USDCAD', 'AUDUSD', 'USDCHF']  
**Validate:** `2022-01-01 -> 2023-12-31`  
**OOS:** **NOT RUN**

## Looseners applied (≤3)

| ID | Change |
|----|--------|
| L1 | B-raid clarity: quality≥1 + displacement → effective grade B |
| L2 | Raid lookback 12 → 20 |
| L3 | Optional MSS: setup 4 accepts CHoCH or MSS |

Locks unchanged: FVG=B, mentorship_2017, ote soft_score, opposing-liq 2R, D/P hard gates.

Narrative accepted / rejected (slice): **94** / **2952**

## Go / No-go

**Recommendation:** `do not OOS yet`

Reasons:
- Validate WR 28.3% well below 80% gate (not close enough to justify OOS burn)
- Wilson lower bound 18.5% < 50%

## Validate headline

| Metric | Value |
|--------|-------|
| Resolved | 60 |
| WR | 28.33% |
| Wilson 95% CI | (0.18506828428432714, 0.4076728516439118) |
| Trades/week | 0.5753424657534246 |
| Expectancy $/trade | -27.2641 |
| Max DD % | 19.885292472292228 |
| Net PnL | -1635.847512240969 |

## Full validate JSON

```json
{
  "period": "VAL",
  "start": "2022-01-01",
  "end": "2023-12-31",
  "resolved": 60,
  "wins": 17,
  "losses": 43,
  "excluded": 0,
  "wr": 0.2833333333333333,
  "wilson_95": [
    0.18506828428432714,
    0.4076728516439118
  ],
  "trades_per_week": 0.5753424657534246,
  "expectancy": -27.2641,
  "net_pnl": -1635.847512240969,
  "max_dd_pct": 19.885292472292228,
  "by_setup": [
    {
      "setup_id": "1",
      "trades": 3,
      "resolved": 3,
      "wins": 2,
      "losses": 1,
      "wr": 0.6667,
      "net_pnl": 302.36
    },
    {
      "setup_id": "2",
      "trades": 13,
      "resolved": 13,
      "wins": 2,
      "losses": 11,
      "wr": 0.1538,
      "net_pnl": -930.59
    },
    {
      "setup_id": "3",
      "trades": 13,
      "resolved": 13,
      "wins": 4,
      "losses": 9,
      "wr": 0.3077,
      "net_pnl": -200.77
    },
    {
      "setup_id": "5",
      "trades": 3,
      "resolved": 3,
      "wins": 2,
      "losses": 1,
      "wr": 0.6667,
      "net_pnl": 279.37
    },
    {
      "setup_id": "6",
      "trades": 28,
      "resolved": 28,
      "wins": 7,
      "losses": 21,
      "wr": 0.25,
      "net_pnl": -1086.22
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
      "net_pnl": -220.55
    },
    {
      "raid_grade": "B",
      "trades": 58,
      "resolved": 58,
      "wins": 17,
      "losses": 41,
      "wr": 0.2931,
      "net_pnl": -1415.3
    }
  ],
  "by_session": [
    {
      "session": "NY_KZ",
      "trades": 27,
      "resolved": 27,
      "wins": 5,
      "losses": 22,
      "wr": 0.1852,
      "net_pnl": -1669.3
    },
    {
      "session": "LONDON_KZ",
      "trades": 8,
      "resolved": 8,
      "wins": 5,
      "losses": 3,
      "wr": 0.625,
      "net_pnl": 681.29
    },
    {
      "session": "SILVER_BULLET",
      "trades": 25,
      "resolved": 25,
      "wins": 7,
      "losses": 18,
      "wr": 0.28,
      "net_pnl": -647.84
    }
  ]
}
```

## OTE soft impact

```json
{
  "with_ote": {
    "label": "with_ote",
    "accepted_signals": 21,
    "resolved_trades": 15,
    "wins": 5,
    "losses": 10,
    "wr": 0.3333,
    "net_pnl": -100.1
  },
  "missing_ote": {
    "label": "missing_ote",
    "accepted_signals": 62,
    "resolved_trades": 45,
    "wins": 12,
    "losses": 33,
    "wr": 0.2667,
    "net_pnl": -1535.75
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

## vs v1

See `GAP_CLOSURE_H_VALIDATE.md` (resolved=14, WR≈42.9%). Autopsy: `GAP_CLOSURE_H_VALIDATE_GATE_AUTOPSY.md`.

## Explicit STOP

- No OOS executed.
- No Tier M / institutional mega-spec.
- Next: human approve one OOS **or** iterate validate again.
