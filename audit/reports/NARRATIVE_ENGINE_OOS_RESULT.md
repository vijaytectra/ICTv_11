# NARRATIVE ENGINE OOS RESULT

**Decision:** `INSUFFICIENT SAMPLE`
**OOS window:** `2024-01-01 -> 2026-09-18`
**Pairs:** ['EURUSD', 'GBPUSD', 'USDJPY', 'USDCAD', 'AUDUSD', 'USDCHF']
**News filters:** EXCLUDED this cycle
**Timezone:** EET (Europe/Bucharest) -> America/New_York
**Narrative accepted / rejected (pre-portfolio):** 164 / 8204

## A. Root causes (pre-narrative)
- Pattern AND-gates without raid->disp->MSS->FVG chain
- No event identity / opposing-liquidity 2R gate
- Additive confluence; timezone-naive killzones

## B. Missing intelligence addressed
- Event engine + raid grades A/B/C
- Shared narrative 10Q validation
- One trade per liquidity event; USD-block correlation
- EET->NY session clocks; Asian flag fixed

## C. Code modules
- `backend/engine/data_loader.py` (EET->NY)
- `backend/engine/event_engine.py`, `narrative.py`, `trade_journal.py`
- `backend/engine/strategy_setups.py` (narrative consumer)
- `backend/engine/portfolio_backtest.py` (USD block)
- `audit/validation/run_narrative_ladder_fast.py`

## G. Train 2020-2021
```json
{
  "period": "TRAIN",
  "start": "2020-01-01",
  "end": "2021-12-31",
  "resolved": 42,
  "wins": 13,
  "losses": 29,
  "excluded": 0,
  "wr": 0.30952380952380953,
  "wilson_95": [
    0.19071102858794878,
    0.4602599393608908
  ],
  "trades_per_week": 0.40218878248974005,
  "net_pnl": -793.6519057997702,
  "max_dd_pct": 9.25966175621843,
  "setup_matrix": [
    {
      "setup_id": 1,
      "trades": 13,
      "resolved": 13,
      "wr": 0.3846,
      "pf": 1.15,
      "net_pnl": 131.98
    },
    {
      "setup_id": 2,
      "trades": 24,
      "resolved": 24,
      "wr": 0.25,
      "pf": 0.54,
      "net_pnl": -970.28
    },
    {
      "setup_id": 3,
      "trades": 2,
      "resolved": 2,
      "wr": 0.0,
      "pf": 0.0,
      "net_pnl": -217.49
    },
    {
      "setup_id": 5,
      "trades": 1,
      "resolved": 1,
      "wr": 1.0,
      "pf": 99.0,
      "net_pnl": 190.14
    },
    {
      "setup_id": 6,
      "trades": 2,
      "resolved": 2,
      "wr": 0.5,
      "pf": 1.6,
      "net_pnl": 72.01
    }
  ]
}
```

## H. Validation 2022-2023
```json
{
  "period": "VAL",
  "start": "2022-01-01",
  "end": "2023-12-31",
  "resolved": 32,
  "wins": 7,
  "losses": 25,
  "excluded": 0,
  "wr": 0.21875,
  "wilson_95": [
    0.11023836252604186,
    0.3875499364924353
  ],
  "trades_per_week": 0.3068493150684931,
  "net_pnl": -1403.5499838211435,
  "max_dd_pct": 15.333560711946376,
  "setup_matrix": [
    {
      "setup_id": 1,
      "trades": 7,
      "resolved": 7,
      "wr": 0.2857,
      "pf": 0.69,
      "net_pnl": -159.39
    },
    {
      "setup_id": 2,
      "trades": 17,
      "resolved": 17,
      "wr": 0.2353,
      "pf": 0.52,
      "net_pnl": -665.78
    },
    {
      "setup_id": 3,
      "trades": 2,
      "resolved": 2,
      "wr": 0.5,
      "pf": 1.79,
      "net_pnl": 75.64
    },
    {
      "setup_id": 5,
      "trades": 1,
      "resolved": 1,
      "wr": 0.0,
      "pf": 0.0,
      "net_pnl": -99.92
    },
    {
      "setup_id": 6,
      "trades": 5,
      "resolved": 5,
      "wr": 0.0,
      "pf": 0.0,
      "net_pnl": -554.09
    }
  ]
}
```

## I. Final OOS
```json
{
  "period": "OOS",
  "start": "2024-01-01",
  "end": "2026-09-18",
  "resolved": 49,
  "wins": 14,
  "losses": 35,
  "excluded": 0,
  "wr": 0.2857142857142857,
  "wilson_95": [
    0.178495944588126,
    0.42408883507780093
  ],
  "trades_per_week": 0.34576612903225806,
  "net_pnl": -1399.184174512824,
  "max_dd_pct": 18.752949436673727,
  "setup_matrix": [
    {
      "setup_id": 1,
      "trades": 15,
      "resolved": 15,
      "wr": 0.4667,
      "pf": 1.37,
      "net_pnl": 345.17
    },
    {
      "setup_id": 2,
      "trades": 16,
      "resolved": 16,
      "wr": 0.3125,
      "pf": 0.82,
      "net_pnl": -215.15
    },
    {
      "setup_id": 3,
      "trades": 3,
      "resolved": 3,
      "wr": 0.0,
      "pf": 0.0,
      "net_pnl": -329.22
    },
    {
      "setup_id": 5,
      "trades": 1,
      "resolved": 1,
      "wr": 0.0,
      "pf": 0.0,
      "net_pnl": -105.25
    },
    {
      "setup_id": 6,
      "trades": 14,
      "resolved": 14,
      "wr": 0.1429,
      "pf": 0.28,
      "net_pnl": -1094.72
    }
  ]
}
```

## L. 8-setup matrix (OOS)
```json
[
  {
    "setup_id": 1,
    "trades": 15,
    "resolved": 15,
    "wr": 0.4667,
    "pf": 1.37,
    "net_pnl": 345.17
  },
  {
    "setup_id": 2,
    "trades": 16,
    "resolved": 16,
    "wr": 0.3125,
    "pf": 0.82,
    "net_pnl": -215.15
  },
  {
    "setup_id": 3,
    "trades": 3,
    "resolved": 3,
    "wr": 0.0,
    "pf": 0.0,
    "net_pnl": -329.22
  },
  {
    "setup_id": 5,
    "trades": 1,
    "resolved": 1,
    "wr": 0.0,
    "pf": 0.0,
    "net_pnl": -105.25
  },
  {
    "setup_id": 6,
    "trades": 14,
    "resolved": 14,
    "wr": 0.1429,
    "pf": 0.28,
    "net_pnl": -1094.72
  }
]
```

## M. Final decision
**INSUFFICIENT SAMPLE**

Gates: WR>=80%, 1:2 fixed, 1% risk, no BE, <=12 trades/week, >=50 resolved.
Never manufactured. Hard stop — no OOS retuning.
News excluded. Walk-forward/missed-winner deferred to full runner when cache is warm.
