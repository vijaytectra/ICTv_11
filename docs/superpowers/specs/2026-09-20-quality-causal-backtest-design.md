# Quality Causal Backtest Design (Confluence Ladder)

**Date:** 2026-09-20  
**Status:** Approved in brainstorming (§1–§3); awaiting user review of this file  
**Priority:** Prove or falsify the quality gate before dashboard / Telegram / automation  
**Approach:** Confluence ladder (filter + kill setups; no ML ranker)

---

## 1. Goal

Deliver one frozen, causal portfolio configuration that either:

- **PASS** — meets all OOS gates below, or  
- **FAIL** — hard stop; publish best OOS metrics, config hash, and loophole battery; **no** further tuning on the OOS window.

This phase does **not** include setup-readiness dashboard UI, Telegram UX, or automated broker execution.

---

## 2. Acceptance gates (OOS only decides PASS)

All must hold on **OOS: 2024-01-01 → present**:

| Gate | Rule |
|------|------|
| Causality | `tests/test_no_lookahead.py` and `tests/test_live_causality.py` green; filter layer must not introduce look-ahead |
| Win rate | ≥ **80%**, where WR = wins / (wins + losses) |
| Win definition | Win = hit **TP before SL**. Breakeven / time-stop exits are **excluded** from the WR denominator (gate mode uses neither) |
| Risk | **1%** of equity at entry; broker lot min/step/max enforced |
| RR | Fixed **1:2** TP/SL geometry only |
| Trade management | **No** breakeven, **no** time-stop for the gate run |
| Frequency | **≤ 12.0 trades/week** portfolio average (hard cap). **6–9/week is OK** if WR ≥ 80% |
| Sample | ≥ **50** resolved TP/SL trades on OOS |
| Universe | `EURUSD`, `GBPUSD`, `USDJPY`, `USDCAD`, `AUDUSD`, `USDCHF` only |
| Concurrency | Max **1** open trade per pair; max **3** open portfolio-wide |

### Secondary metrics (reported, not PASS/FAIL)

Expectancy ($ and R), profit factor, max drawdown %, average R, per-setup and per-pair tables, binomial 95% CI on OOS WR, trades/week p50/p90.

### Week definition

ISO week (Mon–Sun), timezone = data timezone (prefer UTC from JForex export; document actual TZ in the result report). Average trades/week uses all calendar weeks in the OOS span that fall within available data.

---

## 3. Date protocol (non-overlapping)

| Phase | Dates | Allowed actions |
|-------|-------|-----------------|
| Train | 2020-01-01 → 2021-12-31 | Search pre-registered filter grid; score candidates |
| Validate | 2022-01-01 → 2023-12-31 | Select **one** winner; apply kill rules; no OOS peeks |
| OOS | 2024-01-01 → present | **Single** frozen run; PASS/FAIL |
| On FAIL | — | Publish report; **no** retuning using OOS |

Replaces any prior 2024/2025/2026 split used in older audit reports.

---

## 4. Data

| Item | Spec |
|------|------|
| Source | User exports from **JForex** (no broker credentials in chat or repo) |
| Path | `C:\Users\Vijayakumar R\Documents` (`config.data_dir`) |
| Pairs | Six majors above |
| Granularity | **1 Minute** Bid and Ask (separate files) |
| Range | 2020-01-01 → present (split in code) |
| Columns | `Time`, `Open`, `High`, `Low`, `Close`, optional `Volume` |
| Time format | `%Y.%m.%d %H:%M:%S` |
| File names | `{PAIR}_1 Min_Bid_*.csv`, `{PAIR}_1 Min_Ask_*.csv` |
| Gate runs | `sample_ratio = 1.0` only (no stride sampling) |

Implementation must not start the train/val/OOS study until Bid/Ask coverage for all six pairs over the full span is verified (integrity check script).

---

## 5. Architecture (confluence ladder)

```
1m Bid/Ask CSV
  → load_pair_data + resample 5m
  → existing ICT indicators (no core pattern rewrite this phase)
  → existing setup detectors (setups 1,2,3,4,5,6,9,10)
  → NEW: post-signal confluence filter layer
  → portfolio concurrency + 1% risk + fixed 1:2 backtest
  → train grid → val select + kill → freeze → one OOS
```

### What stays unchanged this phase

- Core indicator math in `backend/engine/ict_indicators.py` (except bugfixes required for causality)  
- Setup *detection* logic in `strategy_setups.py` (filters wrap outputs; setups may be disabled)  
- Bid/Ask fill model, slippage 0.5 pip, commission $3.50/lot, SL-before-TP same-bar rule  

### What is added

- Pre-registered confluence filter module + config schema  
- Train/val/OOS orchestration runner  
- Setup kill reporting  
- Frozen config + hash artifacts  
- PASS/FAIL + loophole battery report  
- Optional equity sensitivity ($200 vs higher) without retuning entries  

---

## 6. Hard filters (always on)

Applied to every candidate config:

1. Signal direction must match `master_bias` ≠ 0  
2. Session: London KZ **or** NY KZ **or** Silver Bullet (Asian-only = off)  
3. Array: BUY only in discount; SELL only in premium  
4. Reject if stop distance &lt; 2 pips  
5. Fixed 1:2 TP/SL; costs as above  
6. Portfolio: 1/pair, max 3 open  
7. Risk 1%; no BE / no time-stop for gate  

---

## 7. Pre-registered train grid

Search **only** these knobs on train (2020–2021). No inventing new filters after seeing val/OOS.

| Knob | Values |
|------|--------|
| `min_confluence_score` | 3, 4, 5, 6 |
| `require_displacement` | false, true |
| `require_recent_sweep` (≤10 bars) | false, true |
| `require_pdh_pdl_touch` | false, true — when true, price within **5.0 pips** of PDH, PDL, EQH, or EQL |
| `max_trades_per_day` (portfolio) | 2, 3 |
| `active_setups` | Start with `[1,2,3,4,5,6,9,10]`; reduce via kill rules on validate |

### Confluence score points

+1 recent sweep · +1 FVG aligned with bias · +1 IFVG · +1 OB · +1 breaker · +1 Silver Bullet window · +1 displacement · +1 PDH/PDL/EQ proximity  

### Explicitly out of grid this phase

Changing SL buffer, FVG min gap, swing window, EMA lengths, or rewriting setup entry geometry.

---

## 8. Validate selection and kill rules

1. From train, keep configs with train WR ≥ 70% **and** trades/week ≤ 15 (loose funnel).  
2. On validate, rank by: WR ≥ 80%, then ≤ 12.0 trades/week, then expectancy &gt; 0, then lower max DD.  
3. Pick **one** portfolio winner. If none meet WR ≥ 80% and ≤ 12.0/week on val, freeze the **best val expectancy** config that still has ≤ 12.0/week, mark `val_gate_met: false`, and proceed to OOS knowing PASS is unlikely (still one OOS run; no extra tuning).  
4. Run each setup **solo** on validate with that winner’s filters.  
5. **Kill** a setup if: val WR &lt; 70%, or &lt; 15 resolved trades, or expectancy ≤ 0.  
6. Re-run portfolio with survivors; confirm ≤ 12.0/week and WR still acceptable on val.  
7. Freeze `active_setups` (expected survivors: often 2–4; fewer allowed).  

“Eight setups” is inventory, not a live quota.

If validate cannot produce ≥ 50 resolved trades, require WR ≥ 80% and ≤ 12/week on available sample and **flag sample risk** in the freeze notes; OOS still requires ≥ 50 for PASS.

---

## 9. Freeze artifacts

| Path | Content |
|------|---------|
| `config/strategy_config_quality_ladder.json` | Winner knobs, `active_setups`, dates, costs, portfolio caps, `breakeven_rules.enabled: false` |
| `config/config_hash_quality_ladder.txt` | SHA-256 of frozen JSON |

No parameter changes after freeze.

---

## 10. Execution model (all periods)

| Rule | Detail |
|------|--------|
| Decision bar | Closed **5m** only (from 1m ≤ T) |
| Entry | BUY @ Ask, SELL @ Bid |
| Slippage | 0.5 pip entry and exit |
| Commission | $3.50 RT / lot |
| Same-bar SL+TP | **SL first** |
| Sizing | 1% equity at signal; lot bounds enforced |

---

## 11. PASS/FAIL report

Deliverable: `audit/reports/QUALITY_LADDER_OOS_RESULT.md` (+ hash files).

Must include:

- Binary **PASS** or **FAIL**  
- Gates table with numbers  
- Train / Val / OOS ledger  
- Setup kill list  
- Frozen config path + hash  
- Loophole battery results (Section 12)  
- Binomial CI and honest caveats  

On FAIL: still publish best OOS metrics; do not retune on OOS.

---

## 12. Loophole battery (explicit tests / disclosures)

### Engineering / causality

| ID | Loophole | Action |
|----|----------|--------|
| L1 | Look-ahead in indicators/setups/filters | Mutation tests must stay green |
| L2 | 5m bar using future 1m | Assert bar at T uses only 1m ≤ T |
| L3 | HTF bias from incomplete hour | Assert completed HTF only |
| L4 | `sample_ratio` distortion | Gate runs force 1.0 |
| L5 | Iterative filter invention using OOS | Pre-registered grid; OOS once; hard stop |

### Execution realism

| ID | Loophole | Action |
|----|----------|--------|
| L6 | Mid-price fantasy fills | Require Ask path; flag missing Ask |
| L7 | News spread blowouts | Compare full vs excluding spread &gt; p95 |
| L8 | Same-bar optimism | SL-first; document |
| L9 | Lot rounding ≠ 1% risk | Report realized risk % distribution |

### Strategy / ICT

| ID | Loophole | Action |
|----|----------|--------|
| L10 | EMA fallback in `master_bias` | Ablation HTF-only vs HTF+EMA on val; disclose frozen choice |
| L11 | Loose sweep / pool quality | Grid knobs; sensitivity in report |
| L12 | UI “10 setups” vs 7–8 disabled | Report active IDs only |
| L13 | Overfit confluence threshold | Discrete pre-reg values only |
| L14 | 80% @ true 1:2 after costs unreachable | If FAIL, state as scientific result |

### Operational

| ID | Loophole | Action |
|----|----------|--------|
| L15 | Backtest ≠ live | No live 80% claim from this study |
| L16 | $200 lot floor distorts 1% | Report; optional $2k/$10k sensitivity without retuning |
| L17 | Correlated USD multi-pair risk | Max 3 open; report concurrent exposure |

---

## 13. Out of scope (later phases)

- Dashboard “70–80% forming” readiness meters  
- Telegram readiness notifications  
- Full automation / broker order routing  
- Rewriting core ICT detectors from reference repos  
- Gold / indices universe  

---

## 14. Reference context

Prior live-causal validation on a different date split did **not** find an 80% OOS model (best solo ~74% Unicorn). This study is a new protocol with stricter frequency caps and a pre-registered ladder — it may still **FAIL**. Failure is an acceptable, honest outcome.

Reference repos used historically for ICT/SMC ideas and frameworks are research context only; this design does not require vendoring them.

---

## 15. Approval record

| Item | Choice |
|------|--------|
| Phase priority | Quality causal backtest first (A) |
| Frequency | Cap ≤12/week; 6–9 OK if WR≥80% (B) |
| Universe | 6 majors (A) |
| Approach | Confluence ladder (A) |
| Optimization freedom | Filter + kill setups (B) |
| WR definition | TP-before-SL; BE/time-stop excluded (A) |
| Concurrency | 1/pair + max 3 portfolio (C) |
| Trade management | Pure fixed RR for gate (A) |
| OOS sample | ≥50 resolved (B) |
| Fail policy | Hard stop (A) |
| Dates | Train 2020–21 / Val 2022–23 / OOS 2024→present (A) |
| Data | User JForex export to Documents (C + A) |

Brainstorming design sections §1–§3: **user approved**.

---

## 16. Appendix — Reference repos → ICT_v11 (borrow / do not borrow)

**Policy:** Concepts and architecture patterns only. Do **not** vendor these repos, copy license-unclear strategy code wholesale, or replace the causal engine with an un-audited SMC package during the quality-ladder study.

### ICT / SMC concept sources

| Repo | Borrow (ideas / checks) | Do not borrow |
|------|-------------------------|---------------|
| **SrsBlack/ict-knowledge-library** | Concept vocabulary for confluence labels (Silver Bullet, AMD/Po3, CE, Judas, killzones, dealing ranges). Use to name filters and report sections correctly. | Treating concept text as proof of edge; auto-generating setups from wiki pages. |
| **joshyattridge/smart-money-concepts** | Definition checklist: FVG, swings, BOS/CHoCH, OB, liquidity clusters, sessions, retracements. Compare against `ict_indicators.py` / `ICT_REFERENCE_MAPPING.md` for gaps (esp. BOS/CHoCH / MSS). | `pip install smartmoneyconcepts` as production signal source without causality + Bid/Ask audit. |
| **MobiusQuant/OpenMobius-skill** | Consistent ICT/SMC rule language for agents and docs. | Using it as a trading runtime. |
| **islero/ICT-NT** | Multi-TF ICT + Turtle Soup on an event engine — later reference for live-parity automation. | Migrating this study onto Nautilus mid-research. |
| **sixscripts-ai/train-ict** | Only if it provides clear labeled methodology useful for *future* research. | Mixing ML training into the locked confluence-ladder grid. |
| **dextergsm/ict-trading**, **fallenpheonix23/ict-trading-bot**, **OPKYEI/ICT-Trading**, **futureteck/ICT_Automated_Trading_System**, **zakariab0/ozo** | Optional idea sparks (session filters, alert phrasing). | Copying bot logic, MT5 “auto trade” patterns, or unverified WR claims. |

### Framework / quant sources

| Repo | Borrow | Do not borrow |
|------|--------|---------------|
| **nautechsystems/nautilus_trader** | Event-driven discipline, deterministic replay, fill realism, backtest≈live boundary. Informs `event_simulation_engine.py` and loophole battery (L1–L9). | Full rewrite of ICT_v11 into Nautilus for this PASS/FAIL study. |
| **mementum/backtrader** | Broker/commission mental model (`next()` causality). | Running the 80% grid inside backtrader (too slow / different stack). |
| **freqtrade/freqtrade** | Later: Telegram alert ops, dry-run, pair whitelist patterns. | Crypto-bot defaults or strategy plugins as ICT edge. |
| **Lumiwealth/lumibot** | Later: paper→live broker wrapper ideas. | Replacing current backtester now. |
| **tauricresearch/tradingagents** | Optional multi-agent research UX later. | LLM agents deciding entries for the OOS gate. |

### Already absorbed in ICT_v11 (no need to re-import)

Swings, HTF structure/bias, institutional pools (PDH/PDL/sessions/EQH-EQL), displacement, premium/discount, FVG/IFVG, sweeps, OB, breaker, OTE, killzones/Silver Bullet, AMD/Po3, multi-setup portfolio, Bid/Ask backtest, Telegram alert shell, causality tests.

### Explicit gaps vs references (tracked; only filter-layer this phase)

| Gap | Reference push | This study |
|-----|----------------|------------|
| Pure structure bias vs EMA fallback | smc BOS/CHoCH; knowledge-library MSS | Ablation L10 on validate; no silent rewrite of core unless required for causality bugfix |
| MSS body close after sweep | ICT-NT / knowledge-library | Prefer via existing setups + confluence; no new setup IDs in grid |
| CE (50% FVG) entry discipline | knowledge-library | Already used in several setups; keep; don’t invent new geometry on OOS |
| Session / SB quality | smc sessions + ICT SB rules | Hard session filter + score +1 for SB window |

### Own forks (context only)

`vijaytectra/ICTv_11` / `vijayr13233/ICTv_11` — project lineage, not external dependencies.
