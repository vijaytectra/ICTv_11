# Phase 2 — Track A Reconciliation (EURUSD)

**Date:** 2026-09-22  
**OOS:** NOT RUN  
**Strategy rewrite:** NONE  
**Goal:** Explain why Phase 0 Track A WR ≈29% disagrees with FINAL_VALIDATION ~55% class.

## 1. CODE FACT — baseline mismatch (before numbers)

| Dimension | FINAL_VALIDATION_REPORT | Phase 0 Track A | Same? |
|-----------|-------------------------|-----------------|-------|
| Window | **2024-01-02 → 2026-09-17** | **2022-01-01 → 2023-12-31** | **NO** |
| Pairs | 6 majors | EURUSD only | NO |
| Data load | `sample_ratio=0.25` in `run_quality_optimization_validation.py` | Full NY 5m parquet | **NO** |
| Narrative 10Q | Script calls `get_all_setup_signals(...)` with **defaults**; report volume implies pre-narrative / raw setups | Explicit `use_narrative=False` | Ambiguous historically |
| Geometry lock | Frozen JSON **has no** `fvg_law` / `kz_table` / `fvg_require_displacement` | Explicit FVG=B + mentorship_2017 | **NO** |
| Execution | Per-pair `execute_backtest`, BE **on**, capital $200 | `run_portfolio`, BE **off**, $10k | **NO** |
| Config hash | `d8ca4f7e…` (`strategy_config_frozen.json`) | Gap Closure H freeze `7917a2f1…` | **NO** |

**Classification:** Comparing Phase 0 29% to FINAL 55% as “geometry lock destroyed edge” is **INVALID** until window + sampling + BE + lock are controlled. Those are **CODE FACTS**, not hypotheses.

Dominant FINAL setups by volume: **#9 Breaker (4,526)** and **#2 IFVG (2,997)** — portfolio WR is not uniform across setups (#1 alone was already ~39%).

## 2. MARKET-DATA FACT — controlled EURUSD ablations

All cases: `use_narrative=False`, `kz_table=mentorship_2017`, `liquidity_model=session_pools`, BE off, full parquet, active [1,2,3,4,5,6,9,10].

```json
[
  {
    "label": "W1_val_2022_2023_FVG_B",
    "slice": [
      "2021-06-01",
      "2023-12-31"
    ],
    "val": [
      "2022-01-01",
      "2023-12-31"
    ],
    "fvg_require_displacement_candle": true,
    "use_narrative": false,
    "kz_table": "mentorship_2017",
    "accepted_slice": 500,
    "val_signals": 387,
    "val_signals_by_setup": {
      "6": 325,
      "2": 6,
      "3": 15,
      "9": 26,
      "4": 10,
      "1": 4,
      "5": 1
    },
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
    "max_dd_pct": 41.71135385103764,
    "wr_by_setup": {
      "1": {
        "wins": 1,
        "losses": 2,
        "resolved": 3,
        "wr": 0.3333333333333333
      },
      "2": {
        "wins": 1,
        "losses": 4,
        "resolved": 5,
        "wr": 0.2
      },
      "3": {
        "wins": 3,
        "losses": 10,
        "resolved": 13,
        "wr": 0.23076923076923078
      },
      "4": {
        "wins": 0,
        "losses": 5,
        "resolved": 5,
        "wr": 0.0
      },
      "5": {
        "wins": 0,
        "losses": 1,
        "resolved": 1,
        "wr": 0.0
      },
      "6": {
        "wins": 72,
        "losses": 162,
        "resolved": 234,
        "wr": 0.3076923076923077
      },
      "9": {
        "wins": 1,
        "losses": 5,
        "resolved": 6,
        "wr": 0.16666666666666666
      }
    }
  },
  {
    "label": "W2_final_like_2024_2026_FVG_B",
    "slice": [
      "2023-06-01",
      "2026-09-21"
    ],
    "val": [
      "2024-01-01",
      "2026-09-17"
    ],
    "fvg_require_displacement_candle": true,
    "use_narrative": false,
    "kz_table": "mentorship_2017",
    "accepted_slice": 597,
    "val_signals": 483,
    "val_signals_by_setup": {
      "2": 13,
      "6": 359,
      "9": 63,
      "3": 25,
      "4": 14,
      "5": 4,
      "1": 5
    },
    "resolved": 320,
    "wins": 97,
    "losses": 223,
    "wr": 0.303125,
    "wilson_95": [
      0.25534829680896215,
      0.35557242823086604
    ],
    "trades_per_week": 2.260343087790111,
    "net_pnl": -4281.348159624558,
    "max_dd_pct": 45.17801728768124,
    "wr_by_setup": {
      "1": {
        "wins": 2,
        "losses": 1,
        "resolved": 3,
        "wr": 0.6666666666666666
      },
      "2": {
        "wins": 8,
        "losses": 3,
        "resolved": 11,
        "wr": 0.7272727272727273
      },
      "3": {
        "wins": 4,
        "losses": 16,
        "resolved": 20,
        "wr": 0.2
      },
      "4": {
        "wins": 1,
        "losses": 4,
        "resolved": 5,
        "wr": 0.2
      },
      "5": {
        "wins": 0,
        "losses": 1,
        "resolved": 1,
        "wr": 0.0
      },
      "6": {
        "wins": 74,
        "losses": 192,
        "resolved": 266,
        "wr": 0.2781954887218045
      },
      "9": {
        "wins": 8,
        "losses": 6,
        "resolved": 14,
        "wr": 0.5714285714285714
      }
    }
  },
  {
    "label": "W3_val_2022_2023_disp_OFF",
    "slice": [
      "2021-06-01",
      "2023-12-31"
    ],
    "val": [
      "2022-01-01",
      "2023-12-31"
    ],
    "fvg_require_displacement_candle": false,
    "use_narrative": false,
    "kz_table": "mentorship_2017",
    "accepted_slice": 623,
    "val_signals": 491,
    "val_signals_by_setup": {
      "6": 386,
      "2": 15,
      "9": 52,
      "3": 15,
      "4": 14,
      "10": 1,
      "1": 6,
      "5": 2
    },
    "resolved": 311,
    "wins": 91,
    "losses": 220,
    "wr": 0.29260450160771706,
    "wilson_95": [
      0.24481695259563932,
      0.3454530185727163
    ],
    "trades_per_week": 2.9821917808219176,
    "net_pnl": -4408.474023267591,
    "max_dd_pct": 45.24612468204506,
    "wr_by_setup": {
      "1": {
        "wins": 2,
        "losses": 2,
        "resolved": 4,
        "wr": 0.5
      },
      "2": {
        "wins": 3,
        "losses": 10,
        "resolved": 13,
        "wr": 0.23076923076923078
      },
      "3": {
        "wins": 3,
        "losses": 8,
        "resolved": 11,
        "wr": 0.2727272727272727
      },
      "4": {
        "wins": 0,
        "losses": 6,
        "resolved": 6,
        "wr": 0.0
      },
      "5": {
        "wins": 0,
        "losses": 2,
        "resolved": 2,
        "wr": 0.0
      },
      "6": {
        "wins": 79,
        "losses": 181,
        "resolved": 260,
        "wr": 0.3038461538461538
      },
      "9": {
        "wins": 4,
        "losses": 11,
        "resolved": 15,
        "wr": 0.26666666666666666
      }
    }
  }
]
```

### Summary table

| Case | Window | FVG disp | Active | Resolved | WR | Wilson 95% | Net PnL |
|------|--------|:--------:|--------|--------:|---:|------------|--------:|
| `W1` | 2022–23 | ON | 1–6,9,10 | 267 | **29.2%** | [24.1%, 34.9%] | −4047 |
| `W2` | 2024–26 | ON | 1–6,9,10 | 320 | **30.3%** | [25.5%, 35.6%] | −4281 |
| `W3` | 2022–23 | OFF | 1–6,9,10 | 311 | **29.3%** | [24.5%, 34.5%] | −4408 |
| `W4` | 2024–26 | ON | **kill #6** | 83 | **32.5%** | [23.4%, 43.2%] | −1290 |

W4 detail (`scratch/phase2_w4.json`): #2 n=11 WR 72.7%; #9 n=42 WR **28.6%**; #3 n=20 WR 20%.

### Setup mix — the actual smoking gun (MARKET-DATA FACT)

| Source | Dominant volume | Notes |
|--------|-----------------|-------|
| FINAL_VALIDATION (6 pairs, 2024–26, old runner) | **#9** 4,526 · **#2** 2,997 · #6 only **54** | Portfolio WR ~55% class |
| W1/W2 current Track A (EURUSD, H lock) | **#6 Unicorn ~84%** of val signals (325/387; 359/483) | #6 alone ~28–31% WR; #2/#9 scarce |

Under current generators, Track A is essentially a **Unicorn portfolio**, not the FINAL #9+#2 portfolio.

## 3. Interpretation (classified)

| Claim | Class |
|-------|-------|
| W1 ≈29.2% reconfirms Phase 0 | MARKET-DATA FACT |
| W2 ≈30.3% on FINAL-like window | MARKET-DATA FACT |
| Window alone explains 29→55 | **CONTRADICTED** (\|W2−W1\|=1.1pp) |
| FVG displacement ON explains collapse | **CONTRADICTED** (\|W1−W3\|≈0) |
| Kill #6 restores FINAL ~55% | **CONTRADICTED** (W4=32.5%) |
| FINAL ~55% reconfirmed under H lock + full EURUSD | **NOT RECONFIRMED** |
| Current #9 CE-retest is not FINAL #9 | RESEARCH HYPOTHESIS (code comments require CE; FINAL volume incompatible) |
| Old `sample_ratio=0.25` + BE-on + $200 capital contaminated FINAL | CODE FACT (runner) + UNVALIDATED magnitude |
| Track A under current H-lock code has no EURUSD edge ≈30% WR | EMPIRICALLY VALIDATED (W1–W4) |

## 4. Root cause (ordered)

1. **Apples ≠ oranges (CODE FACT):** FINAL window/sampling/BE/config ≠ Phase 0; comparison was invalid as stated.
2. **Even after controlling window + FVG disp (MARKET-DATA FACT):** WR stays ~30% — lock/window are **not** the WR driver.
3. **Universe shift (MARKET-DATA FACT):** current Track A is #6-heavy; FINAL was #9/#2-heavy. Killing #6 does not resurrect #9 WR (28.6% now vs ~57% in FINAL).
4. **Implication:** FINAL ~55% must be treated as a **stale baseline** under *current* generators + geometry lock until a bit-identical reproduction exists. Do not use it as a Phase 3 target.

## 5. Decisions (no strategy rewrite this phase)

1. Keep FVG=B / mentorship_2017 — displacement ablation did not move WR.
2. Do **not** OOS Track A from EURUSD validate (~30% WR).
3. Treat FINAL_VALIDATION headline WR as **non-authoritative** for H-lock code.
4. Phase 3 candidates (pick one; no auto-run):
   - **3a** Document Track A no-edge under H lock (EURUSD) and focus Track B / narrative only.
   - **3b** CODE audit: why #2/#9 fire rates collapsed vs FINAL (generator/IFVG/breaker CE) — measurement only.
   - **3c** EURUSD-only improve path only after 3b identifies a causal bug (not curve-fit).

## Explicit STOP

- No OOS. No Tier M. No SMC copy. No generator rewrite in Phase 2.
- Artifacts: `scratch/phase2_track_a_reconcile.json`, `scratch/phase2_w4.json`, runner `audit/validation/run_phase2_track_a_reconcile.py`
