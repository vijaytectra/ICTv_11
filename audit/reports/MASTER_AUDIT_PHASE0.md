# ICTv_11 — MASTER AUDIT PHASE 0

**Date:** 2026-09-22  
**Scope:** Repository audit + one-pair readiness (EURUSD first).  
**Strategy logic:** **NOT rewritten in this phase** (per mega-spec §13).  
**OOS:** **NOT RUN.** External repo deep-dives: deferred to Phase 1.

---

## 1. Repository Audit (CODE FACT)

### Layout

| Path | Role |
|------|------|
| `backend/engine/data_loader.py` | 1m Bid/Ask CSV → EET→NY → 5m resample |
| `backend/engine/ict_indicators.py` | Swings, HTF bias, pools, FVG, OB, breaker, OTE, KZ |
| `backend/engine/event_engine.py` | Causal event vocabulary (raid/disp/MSS/CHoCH/FVG/…) |
| `backend/engine/narrative.py` | Shared 10Q pre-trade validation |
| `backend/engine/strategy_setups.py` | Setups 1–6,9,10 generators + narrative consumer |
| `backend/engine/backtester.py` | Bid/Ask fills, 1% risk, 1:2 RR, commission/slip |
| `backend/engine/portfolio_backtest.py` | Multi-pair, USD-block, day caps |
| `backend/engine/confluence_filters.py` | Quality-ladder additive filters (parallel path) |
| `backend/journal/` | Ops SQLite journal (PROPOSED/TAKEN/…) |
| `backend/api/server.py` | FastAPI + dashboard |
| `config/` | Freeze / ladder / validate v2–v3 configs |
| `docs/geometry/ICT_GEOMETRY_LOCK.md` | FVG=B, mentorship_2017, OTE soft |
| `audit/reports/` | Prior causal + narrative + gap-closure results |
| `tests/` | No-lookahead, FVG, TZ, narrative, journal, RR |

### Dependency map (as implemented)

```text
RAW 1m Bid/Ask CSV (EET)
  → data_loader (Europe/Bucharest → America/New_York)
  → resample 5m
  → run_all_indicators (swings → HTF → pools → disp → PD → FVG=B → sweeps → OB → breaker → OTE → KZ)
  → setup generators (#1–6,9,10)
  → build_events (typed narrative events)
  → validate_trade (10Q + OTE soft + CE prefer)
  → portfolio_backtest (USD block, day/open caps)
  → execute_backtest (Ask entry BUY / Bid exit BUY; reverse for SELL)
  → metrics / reports / optional ops journal
```

### Two research tracks (CODE FACT — important)

| Track | Entry | Status |
|-------|-------|--------|
| **A. Pattern + confluence ladder** | `confluence_filters` + setups without full narrative | Large sample; ~55% WR class in `FINAL_VALIDATION_REPORT.md` |
| **B. Narrative 10Q engine** | `event_engine` + `narrative.validate_trade` | Selective; Gap Closure H validate thin / weak WR |

Do **not** mix Track A headline numbers with Track B acceptance rates.

---

## 2. Baseline facts (classified)

### From `FINAL_VALIDATION_REPORT.md` (Track A — MARKET-DATA FACT / prior audit)

| Metric | Value | Class |
|--------|------:|-------|
| Executed trades | 10,809 | MARKET-DATA FACT (report) |
| Portfolio WR | ~51–62% by setup; overall ~55% class | MARKET-DATA FACT (report) |
| Expectancy | ~+0.65R | MARKET-DATA FACT (report) |
| PF | ~1.45–2.19 | MARKET-DATA FACT (report) |
| Look-ahead unit tests | claimed clean | CODE FACT (tests exist) |
| Frozen hash | `d8ca4f7e…` | CODE FACT |

### Setup WR table (prompt / FINAL_VALIDATION — RESEARCH BASELINE)

| Setup | WR (approx) | Class |
|-------|------------:|-------|
| #1 Sweep+FVG | ~39% | MARKET-DATA FACT (report) |
| #2 Sweep+IFVG | ~55% | MARKET-DATA FACT (report) |
| #3 Silver Bullet | ~51% | MARKET-DATA FACT (report) |
| #4 Turtle Soup | ~46% (tiny n) | INSUFFICIENT SAMPLE |
| #5 OB+FVG | ~58% | MARKET-DATA FACT (report) |
| #6 Unicorn | ~61% (small n) | UNVALIDATED at scale |
| #9 Breaker retest | ~57% | MARKET-DATA FACT (report) |
| #10 AMD | ~0–insufficient | INSUFFICIENT SAMPLE |

### From Gap Closure H (Track B — MARKET-DATA FACT)

| Run | Resolved | WR | Class |
|-----|--------:|---:|-------|
| Validate v1 (freeze) | 14 | 42.9% | INSUFFICIENT SAMPLE |
| Validate v2 (L1–L3 loose) | 60 | 28.3% | EMPIRICALLY WEAK |
| Validate v3 (L1 tight + kill 2/3/6) | *in progress* | — | PENDING |

**ICT DEFINITION (locked):** FVG=B, `mentorship_2017`, OTE `soft_score` — `docs/geometry/ICT_GEOMETRY_LOCK.md`.

**CONTRADICTED BY DATA:** Historical “80% WR” claims (prompt + FINAL_VALIDATION: look-ahead / curve-fit artifact).

**UNVALIDATED:** That narrative Track B currently beats Track A on expectancy after costs.

---

## 3. Critical risks found in code (audit only — no fix yet)

| Issue | Evidence | Class |
|-------|----------|-------|
| Dual tracks can confuse “edge” | Narrative vs confluence produce different universes | CODE FACT |
| `FINAL_LIVE_CAUSAL_VALIDATION.md` WR tables disagree with `FINAL_VALIDATION_REPORT.md` | Same repo, incompatible headlines | RESEARCH HYPOTHESIS: report contamination / different windows / BE handling |
| Setup #3 generator may still be “FVG in SB window”-adjacent | Needs line-level audit vs strict SB chain (§24) | RESEARCH HYPOTHESIS |
| HTF is 1H + EMA fallback, not full 4H/15M stack (§18) | `find_htf_structure_and_bias` | CODE FACT |
| OTE uses rolling-30, not raid dealing-range | `find_ote_zones` | CODE FACT / ICT DEFINITION gap |
| Prem/discount rolling lookback ≠ raid-defined dealing range | `find_premium_discount_zones` | CODE FACT |
| v2 L1 (q≥1→B) destroyed WR | autopsy + v2 report | EMPIRICALLY VALIDATED |
| Setups 2/3/6 toxic on narrative validate v2 | WR 15/31/25% | EMPIRICALLY VALIDATED (Track B only) |

---

## 4. One-pair policy (EURUSD first) — **EXECUTED**

### EURUSD validate 2022–2023 smoke (`PHASE0_EURUSD_TRACK_AB.md`)

| Track | Val signals | Resolved | WR | Net PnL | Class |
|-------|------------:|--------:|---:|--------:|-------|
| **A** no narrative (setups 1–6,9,10) | 387 | 267 | **29.2%** | −$4,047 | MARKET-DATA FACT |
| **B** narrative v3 active [1,4,5,9,10] | 1 | 1 | 100% (n=1) | +$206 | INSUFFICIENT SAMPLE |

**Implication (RESEARCH HYPOTHESIS → needs six-pair confirm):** Under current geometry lock (FVG=B + mentorship_2017), Track A EURUSD validate is **not** the old ~55% report world — either the lock changed the setup universe, or prior reports used different filters/windows. **Do not trust old WR tables until re-run under freeze locks.**

Track B after L1 tighten + kill 2/3/6 is **too sparse** on EURUSD alone.

### Gap Closure validate v3 (6 majors, prior turn completed)

| Metric | v3 |
|--------|-----|
| Resolved | 6 |
| WR | 33.3% |
| Loss tags | THESIS_OK=4, BUG=0 |
| Go/no-go | **do not OOS yet** |

Report: `GAP_CLOSURE_H_VALIDATE_v3.md`

### Explicit non-goals this phase

- No OOS
- No hyperopt / grid search
- No vendoring SMC libraries
- No restoring setups #7/#8
- No manufacturing 80% WR
- No Tier M full rewrite until Phase 0 audit signed off

---

## 5. External research (authorized) — status

| Source | Use | Status |
|--------|-----|--------|
| joshyattridge/smart-money-concepts | Swing/BOS/FVG patterns — audit look-ahead | **DONE** — look-ahead confirmed; do not copy |
| SrsBlack/ict-knowledge-library | Terminology | Deferred Phase 1b |
| nautechsystems/nautilus_trader | Architecture reference only | Deferred Phase 1b |
| freqtrade / backtrader / lumibot | Backtest architecture | Deferred Phase 1b |
| YouTube / forums | Hypotheses only | Not authority |

Phase 1 table: `audit/reports/EXTERNAL_CONCEPT_RECONCILIATION.md`

---

## 6. Recommended phased plan (after you approve Phase 0)

| Phase | Goal | Stop rule |
|-------|------|-----------|
| **0** | This audit + EURUSD Track A vs B | **DONE — awaiting sign-off** |
| **1** | External concept reconciliation (no copy) | **DONE** — `EXTERNAL_CONCEPT_RECONCILIATION.md` |
| **2** | Reconcile Track A under freeze locks (why 29% vs old 55%) — CODE/DATA audit | **DONE** — `PHASE2_TRACK_A_RECONCILIATION.md` |
| **3** | EURUSD-only improve *or* document no-edge | **DONE** — 3b volume audit + 3a Track A no-edge (`PHASE3_SETUP_VOLUME_COLLAPSE.md`) |
| **4** | Expand to 6 pairs validate | Go/no-go — **blocked** until Track B or a new locked path clears EURUSD |
| **5** | **One** locked OOS (only if validate supports) | LOCK OOS forever |

---

## 7. Immediate answer to mega-spec intent

> “Does ICTv_11 contain a genuine causal edge?”

**Current honest answer (Phase 0):**

- Old Track A report (~55% / +0.65R): **NOT RECONFIRMED** under current H-lock generators (EURUSD W1–W4 ≈29–33% WR). Stale vs current #6-heavy universe — see Phase 2 report.
- Phase 0 Track A EURUSD validate ~29%: **reconfirmed**; window/FVG-disp/kill-#6 do not restore FINAL.
- Track B narrative: **not viable yet** (n≈1–6 after v3 tighten).
- **80% WR:** `NOT SUPPORTED` — **CONTRADICTED BY DATA** as a manufacturing target.

---

## Explicit STOP (Phase 0)

- Phase 0–3 complete. Track A EURUSD: **no-edge** under current and legacy gens (~28–30% WR). FINAL ~55% unreproduced. Phase 4 (6-pair) blocked until a validate-green path exists. No OOS.
- No OOS.
- Next pair expansion only after you approve.
