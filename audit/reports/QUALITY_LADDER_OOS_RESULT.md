# Quality Ladder OOS Result — **FAIL**

Generated: 2026-09-20T21:16:27.172659+00:00
Config hash: `a71a0cd4d82b889ae84b159d11a1a4ae0caaf043133aa24d8b09e13bfbf71a88`

## Gates (OOS)

| Gate | Value | Threshold | Pass |
|------|------:|----------:|:----:|
| WR | 0.2276 | ≥ 0.80 | False |
| Trades/week | 4.080 | ≤ 12.0 | True |
| Resolved | 580 | ≥ 50 | True |

Wilson 95% CI on OOS WR: [0.195, 0.263]

## Period ledger

| Period | WR | Resolved | Trades/week | Net PnL | Max DD% |
|--------|---:|---------:|------------:|--------:|--------:|
| Train | 0.2626 | 438 | 4.194 | -164.72 | 82.36 |
| Val | 0.2020 | 401 | 3.845 | -176.59 | 88.73 |
| OOS | 0.2276 | 580 | 4.080 | -185.10 | 92.70 |

## Frozen filters

```json
{
  "min_confluence_score": 3,
  "require_displacement": true,
  "require_recent_sweep": false,
  "require_pdh_pdl_touch": true,
  "pdh_pdl_touch_pips": 5.0,
  "max_trades_per_day": 2,
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
    "wr": 0.20199501246882792,
    "resolved": 401,
    "net_pnl": -176.5889561192274,
    "kept": false
  },
  {
    "setup_id": 2,
    "wr": 0.4748858447488584,
    "resolved": 219,
    "net_pnl": 52.61552727561269,
    "kept": false
  },
  {
    "setup_id": 3,
    "wr": 0.11812627291242363,
    "resolved": 491,
    "net_pnl": -191.80633254229323,
    "kept": false
  },
  {
    "setup_id": 4,
    "wr": 0.20754716981132076,
    "resolved": 265,
    "net_pnl": -159.19262396852665,
    "kept": false
  },
  {
    "setup_id": 5,
    "wr": 0.5522388059701493,
    "resolved": 335,
    "net_pnl": 789.9964144098471,
    "kept": false
  },
  {
    "setup_id": 6,
    "wr": 0.24919093851132687,
    "resolved": 309,
    "net_pnl": -147.16617235309823,
    "kept": false
  },
  {
    "setup_id": 9,
    "wr": 0.3755868544600939,
    "resolved": 213,
    "net_pnl": -76.80899103469729,
    "kept": false
  },
  {
    "setup_id": 10,
    "wr": 0.425,
    "resolved": 40,
    "net_pnl": 1.9413076901600448,
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
