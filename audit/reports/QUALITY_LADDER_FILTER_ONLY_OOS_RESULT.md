# Quality Ladder OOS Result — **FAIL**

Generated: 2026-09-21T10:44:31.551529+00:00
Config hash: `84c21821d4ee45123a218b063e3505ce553db3237574dde2b494ad6c19f60ca3`

## Gates (OOS)

| Gate | Value | Threshold | Pass |
|------|------:|----------:|:----:|
| WR | 0.3824 | ≥ 0.80 | False |
| Trades/week max | 7.507 | ≤ 12.0 | True |
| Trades/week min | 7.507 | ≥ 10.0 | False |
| Resolved | 1067 | ≥ 50 | True |
| Portfolio day cap | 5 | ≤ 5 | True |

Wilson 95% CI on OOS WR: [0.354, 0.412]

## Period ledger

| Period | WR | Resolved | Trades/week | Net PnL | Max DD% |
|--------|---:|---------:|------------:|--------:|--------:|
| Train | 0.3794 | 788 | 7.546 | -81.97 | 42.82 |
| Val | 0.3809 | 785 | 7.527 | -62.25 | 48.48 |
| OOS | 0.3824 | 1067 | 7.507 | -73.42 | 51.23 |

## Frozen filters

```json
{
  "min_confluence_score": 5,
  "require_displacement": false,
  "require_recent_sweep": false,
  "require_pdh_pdl_touch": false,
  "pdh_pdl_touch_pips": 5.0,
  "max_trades_per_day": 1,
  "active_setups": [
    1
  ],
  "use_ema_bias_fallback": true
}
```

## Kill log (validate solo)

```json
[
  {
    "setup_id": 1,
    "wr": 0.38089171974522296,
    "resolved": 785,
    "net_pnl": -62.2514765096561,
    "kept": false
  },
  {
    "setup_id": 2,
    "wr": 0.49584199584199584,
    "resolved": 962,
    "net_pnl": 3079.538340732623,
    "kept": false
  },
  {
    "setup_id": 3,
    "wr": 0.3356926188068756,
    "resolved": 989,
    "net_pnl": -158.83156762998055,
    "kept": false
  },
  {
    "setup_id": 4,
    "wr": 0.37822878228782286,
    "resolved": 542,
    "net_pnl": -101.63800476255075,
    "kept": false
  },
  {
    "setup_id": 5,
    "wr": 0.5708289611752361,
    "resolved": 953,
    "net_pnl": 218350.33884612785,
    "kept": false
  },
  {
    "setup_id": 6,
    "wr": 0.4175257731958763,
    "resolved": 582,
    "net_pnl": -28.662460188187424,
    "kept": false
  },
  {
    "setup_id": 9,
    "wr": 0.4304556354916067,
    "resolved": 834,
    "net_pnl": -24.61593082961781,
    "kept": false
  },
  {
    "setup_id": 10,
    "wr": 0.4175824175824176,
    "resolved": 182,
    "net_pnl": -4.603417715161299,
    "kept": false
  }
]
```

## Data integrity

ok=True; errors=[]

## Loophole battery

- **L1 causality suite:** FAIL / not run
- **L7 spread>p95:** not run
- **L10 EMA ablation:** not run
- **L16 capital sensitivity:** not run

## Hard stop

If FAIL: do not retune using OOS. See design spec.

## Caveats

- Backtest ≠ live. No live 80% claim from this study alone.
- 24h max hold in engine may force market exits; those count as WIN/LOSS by PnL sign.
