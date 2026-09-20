# Quality Causal Backtest (Confluence Ladder) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove or falsify OOS gates (WR ≥ 80%, ≤ 12.0 trades/week, ≥ 50 resolved TP/SL, 1% risk, fixed 1:2, zero look-ahead) via a pre-registered confluence ladder on 6 majors.

**Architecture:** Keep existing ICT indicators + setups. Add a post-signal confluence filter, portfolio caps (1/pair, max 3), gate-mode backtest (BE off), train/val/OOS orchestration, freeze + PASS/FAIL report. Data integrity gate blocks study until JForex CSVs are complete.

**Tech Stack:** Python, pandas/numpy, existing `backend/engine/*`, pytest, FastAPI unchanged this phase.

**Spec:** `docs/superpowers/specs/2026-09-20-quality-causal-backtest-design.md`

## Global Constraints

- Universe: EURUSD, GBPUSD, USDJPY, USDCAD, AUDUSD, USDCHF only
- Dates: Train 2020-01-01→2021-12-31; Val 2022-01-01→2023-12-31; OOS 2024-01-01→present
- `sample_ratio = 1.0` on all gate runs
- Gate: `enable_breakeven=False`; fixed RR 2.0; risk 1.0%
- WR: wins/(wins+losses); WIN=TP before SL only
- Frequency: ≤ 12.0 trades/week hard cap
- OOS PASS needs ≥ 50 resolved TP/SL trades
- Pre-registered grid only; OOS once; hard stop on FAIL
- Data dir: `C:\Users\Vijayakumar R\Documents`
- No dashboard/Telegram readiness work in this plan

## File map

| Path | Role |
|------|------|
| `backend/engine/confluence_filters.py` | Score + filter signals; filter config dataclass |
| `backend/engine/portfolio_backtest.py` | Multi-pair backtest with max 3 open; metrics |
| `backend/engine/metrics.py` | WR, trades/week, binomial CI, gate evaluation |
| `backend/engine/strategy_setups.py` | Add `active_setups` + return indicators for scoring |
| `backend/engine/backtester.py` | Ensure BE can stay off (already supported) |
| `audit/validation/check_jforex_data.py` | Coverage/integrity for Bid/Ask CSVs |
| `audit/validation/run_quality_ladder.py` | Train → val → kill → freeze → OOS |
| `config/strategy_config_quality_ladder.json` | Written by runner on freeze |
| `config/config_hash_quality_ladder.txt` | SHA-256 |
| `audit/reports/QUALITY_LADDER_OOS_RESULT.md` | PASS/FAIL report |
| `tests/test_confluence_filters.py` | Unit tests for score/filter |
| `tests/test_metrics_gates.py` | WR / week / gate helpers |
| `tests/test_data_integrity.py` | Integrity checker unit tests (synthetic files) |

---

### Task 1: JForex data integrity checker

**Files:**
- Create: `audit/validation/check_jforex_data.py`
- Create: `tests/test_data_integrity.py`

**Interfaces:**
- Produces: `check_data_coverage(data_dir: str, pairs: list[str], start: str, end: str) -> dict` with keys `ok: bool`, `pairs: dict[str, dict]`, `errors: list[str]`

- [ ] **Step 1: Write failing tests** for missing Bid file and OK synthetic pair

```python
# tests/test_data_integrity.py
import os
from audit.validation.check_jforex_data import check_data_coverage

def test_missing_bid_fails(tmp_path):
    r = check_data_coverage(str(tmp_path), ["EURUSD"], "2020-01-01", "2021-12-31")
    assert r["ok"] is False
    assert any("EURUSD" in e for e in r["errors"])
```

- [ ] **Step 2: Run test — expect FAIL (module missing)**

Run: `pytest tests/test_data_integrity.py::test_missing_bid_fails -v`

- [ ] **Step 3: Implement checker**

Requirements:
- Glob `{PAIR}_1 Min_Bid_*.csv` and `{PAIR}_1 Min_Ask_*.csv`
- Parse time with `%Y.%m.%d %H:%M:%S`
- Report min/max time, row count, % missing Ask alignment, gap stats (median Δt should be ~60s)
- `ok` only if all 6 pairs have Bid+Ask spanning requested `[start, end]` with ≥ 80% of expected 1m bars on weekdays (document heuristic in docstring)
- CLI: `python audit/validation/check_jforex_data.py` prints PASS/FAIL JSON summary

- [ ] **Step 4: Tests pass**

- [ ] **Step 5: Commit** `feat: add JForex data integrity coverage checker`

---

### Task 2: Confluence filter module

**Files:**
- Create: `backend/engine/confluence_filters.py`
- Create: `tests/test_confluence_filters.py`
- Modify: `backend/engine/strategy_setups.py` — add `get_all_setup_signals_filtered` / `active_setups` param

**Interfaces:**
- Produces:
  - `@dataclass ConfluenceFilterConfig` with fields: `min_confluence_score: int`, `require_displacement: bool`, `require_recent_sweep: bool`, `require_pdh_pdl_touch: bool`, `pdh_pdl_touch_pips: float = 5.0`, `max_trades_per_day: int`, `active_setups: list[int]`, `use_ema_bias_fallback: bool = True`
  - `score_bar(df, i: int, direction: str, pip_size: float, cfg) -> int`
  - `filter_signals(df_ind, signals: list[dict], pair: str, cfg: ConfluenceFilterConfig) -> list[dict]`
- Consumes: indicator columns from `run_all_indicators`

Score points (spec §7): +1 sweep (≤10 bars) · +1 FVG w/ bias · +1 IFVG · +1 OB · +1 breaker · +1 Silver Bullet · +1 displacement · +1 PDH/PDL/EQ within 5 pips

Hard filters always: master_bias align, London|NY|SB session, discount/premium array, min 2 pip risk (signals already carry SL/TP)

- [ ] **Step 1: Failing unit tests** for score and hard filter reject

- [ ] **Step 2: Implement `confluence_filters.py`**

- [ ] **Step 3: Extend `get_all_setup_signals`**

```python
def get_all_setup_signals(
    df, pair, min_rr=2.0, active_setups=None, return_indicators=False
):
    # active_setups default [1,2,3,4,5,6,9,10]
    # map id -> generate_signals_setup_N
    # if return_indicators: return signals, df_ind else signals
```

- [ ] **Step 4: Tests pass + existing causality tests still pass**

Run: `pytest tests/test_confluence_filters.py tests/test_no_lookahead.py tests/test_live_causality.py -v`

- [ ] **Step 5: Commit** `feat: add confluence filter layer and active_setups selection`

---

### Task 3: Metrics + gate evaluation

**Files:**
- Create: `backend/engine/metrics.py`
- Create: `tests/test_metrics_gates.py`

**Interfaces:**
- `compute_win_rate(trades) -> dict` with wins, losses, excluded, wr
- `trades_per_week(trades, start, end) -> float` ISO weeks in span
- `binomial_wilson_ci(wins, n, alpha=0.05) -> tuple[float,float]`
- `evaluate_gates(metrics, min_wr=0.80, max_tpw=12.0, min_resolved=50) -> dict` pass/fail per gate

Outcome mapping: `WIN` counts win; `LOSS` counts loss; `BREAKEVEN` and anything else excluded from WR denom.

- [ ] **Step 1–4: TDD then commit** `feat: add backtest gate metrics helpers`

---

### Task 4: Portfolio backtest (max 3 open)

**Files:**
- Create: `backend/engine/portfolio_backtest.py`
- Modify: use `execute_backtest` per pair OR chronological merge

**Interfaces:**
- `run_portfolio(pairs_data: dict[str, pd.DataFrame], signals_by_pair: dict[str, list], *, starting_balance, risk_percent, max_portfolio_open=3, enable_breakeven=False, ...) -> dict`
- Chronological across pairs; skip signal if portfolio already has 3 opens; still 1 open per pair via existing per-pair logic
- Shared equity for 1% risk

Preferred algorithm: merge all signals by timestamp; maintain `open_positions` list with exit times from a single-pass simulator calling into shared fill rules (extract or wrap `execute_backtest` carefully). Minimum viable: sort all signals globally; for each signal, if pair free and `len(open) < 3`, run forward path on that pair’s df until exit, update balance and open set.

- [ ] **Step 1: Unit test** with tiny synthetic 2-pair dfs proving max 3 and 1/pair

- [ ] **Step 2: Implement**

- [ ] **Step 3: Commit** `feat: add multi-pair portfolio backtest with open caps`

---

### Task 5: Quality ladder runner (train/val/kill/freeze/OOS)

**Files:**
- Create: `audit/validation/run_quality_ladder.py`

**Interfaces:**
- CLI flags: `--data-dir`, `--skip-oos` (for dry), `--capital` default 200
- Pre-registered grid from spec §7 (product of knobs; prune if > 64 by fixing order and early stop on train funnel)
- Writes freeze JSON + hash
- Calls data integrity first; abort if not `ok`

Flow:
1. `check_data_coverage` full span 2020→present  
2. For each grid cfg on train → metrics  
3. Funnel train WR≥70% and tpw≤15  
4. Val select per spec §8  
5. Solo setup kill  
6. Freeze  
7. OOS once → report markdown  

- [ ] **Step 1: Implement runner**

- [ ] **Step 2: Dry-run on whatever data exists** (may FAIL integrity until download complete)

- [ ] **Step 3: Commit** `feat: add quality confluence ladder train/val/OOS runner`

---

### Task 6: PASS/FAIL report + loophole battery hooks

**Files:**
- Create report writer inside runner or `audit/validation/write_quality_ladder_report.py`
- Re-run causality tests as subprocess section in report
- L7: metrics excluding spread > p95
- L10: val ablation note for `use_ema_bias_fallback` true vs false (run once on val winner)
- L16: optional capital sensitivity 200 / 2000 / 10000 without retuning

- [ ] **Step 1: Implement report markdown writer matching spec §11–§12**

- [ ] **Step 2: Commit** `docs: add quality ladder OOS result report generator`

---

### Task 7: End-to-end study (blocked on data)

- [ ] **Step 1:** User confirms download complete  
- [ ] **Step 2:** `python audit/validation/check_jforex_data.py` → PASS  
- [ ] **Step 3:** `python audit/validation/run_quality_ladder.py`  
- [ ] **Step 4:** Commit freeze artifacts + `QUALITY_LADDER_OOS_RESULT.md` (PASS or FAIL)  
- [ ] **Step 5:** Hard stop if FAIL — no OOS retune  

---

## Spec coverage self-check

| Spec section | Task |
|--------------|------|
| Gates / WR / frequency / sample | 3, 5, 6 |
| Date splits | 5 |
| Data / JForex | 1, 7 |
| Confluence grid + kill | 2, 5 |
| Portfolio caps | 4 |
| Freeze + hash | 5 |
| Loopholes L1–L17 | 6 (+ existing causality tests) |
| No dashboard/Telegram | honored (out of plan) |
| Reference appendix | already in spec §16 |

## Execution note

While JForex data downloads: complete Tasks 1–6 with synthetic tests. Task 7 waits for integrity PASS.
