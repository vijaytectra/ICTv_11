# LIQUIDITY MODEL ATTRIBUTION

**geometry_lock_version:** `H-2026-09-21`
**Default remains:** `session_pools` (do not switch without evidence).

## Models

| Model | Role |
|-------|------|
| `session_pools` | PDH/PDL/ASH/ASL/LSH/LSL (default) |
| `eqh_eql_cluster` | Equal highs/lows clusters |
| `window_extremes` | Causal rolling window highs/lows |

## Results

```json
[
  {
    "pair": "SYNTH-EURUSD",
    "bars": 500,
    "models": {
      "session_pools": {
        "pool_touch_bars": 162,
        "major_raid_bars": 1,
        "touch_per_1k_bars": 324.0
      },
      "eqh_eql_cluster": {
        "pool_touch_bars": 1,
        "major_raid_bars": 1,
        "touch_per_1k_bars": 2.0
      },
      "window_extremes": {
        "pool_touch_bars": 118,
        "major_raid_bars": 1,
        "touch_per_1k_bars": 236.0
      }
    }
  }
]
```

## Recommendation

- Keep `liquidity_model=session_pools` as freeze default.
- Re-evaluate `eqh_eql_cluster` on validate only if A-grade raid density is sparse under session pools.
- `window_extremes` is exploratory; higher touch rate is expected and not itself edge.

**STOP:** No default switch this pass.
