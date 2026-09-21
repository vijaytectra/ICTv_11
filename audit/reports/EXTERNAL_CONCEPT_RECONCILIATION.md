# Phase 1 — External Concept Reconciliation (SMC vs ICTv_11)

**Date:** 2026-09-22  
**Primary external source:** [joshyattridge/smart-money-concepts](https://github.com/joshyattridge/smart-money-concepts) (`smc.py`, inspected)  
**Secondary:** geometry lock `H-2026-09-21`, ICTv_11 `ict_indicators.py` / `event_engine.py` / `narrative.py`  
**Rule:** Research only — **no code copied**, no strategy rewrite, no OOS.

### Source hierarchy applied

1. Observed ICTv_11 validate data (Phase 0)  
2. Causal CODE FACTS in ICTv_11  
3. SMC source behavior (as implemented)  
4. ICT DEFINITION (geometry lock)  
5. SMC README claims (not authority)

Every row: Concept · ICTv_11 · External (SMC) · Difference · Look-ahead risk · OOS test required · Decision

---

## A. Core structure / geometry

| Concept | ICTv_11 implementation | External (SMC) | Difference | Look-ahead risk | OOS test required | Decision |
|---------|------------------------|----------------|------------|-----------------|-------------------|----------|
| **Swing high/low** | `find_swing_points(window=5)`: pivot at `k-window` confirmed only after `window` future bars; column active at confirmation bar `k` | `swing_highs_lows(swing_length)`: high must be max of **past and future** `swing_length` bars (`shift(-(L//2))`) | SMC labels pivot on the pivot bar using future prices; ICTv_11 delays activation | **SMC: REPAINTING / LOOK-AHEAD** · ICT: CONFIRMED-LAG (safe) | No — do not adopt SMC swing | **KEEP ICTv_11** · REJECT SMC swing for live |
| **FVG** | FVG=B: wick gap `low[i]>high[i-2]` / bearish mirror; tag at candle-3 close; middle must be displacement; `fvg_ce=(top+bot)/2` | `fvg()`: gap uses `high.shift(1)` vs `low.shift(-1)` (and inverse) — **needs next candle**; tags on middle bar; optional join | Different candle index, no mid-displacement gate, no CE, uses future low/high | **SMC: LOOK-AHEAD** (shift −1) · ICT: causal at bar close | If ever testing “SMC FVG”, must delay tag to candle 3 | **KEEP FVG=B lock** · NEVER vendor SMC FVG as-is |
| **FVG mitigation** | First CE touch = mitigated; far-side body close = invalidation | `MitigatedIndex` scans forward until price crosses Top/Bottom | ICT distinguishes CE mitigate vs far-side invalidate; SMC “mitigate” ≈ zone touch | ICT causal; SMC index is post-hoc label (OK if not used at pivot bar) | Optional: CE vs full-fill WR | **KEEP ICT CE mitigate** |
| **BOS** | Not a separate column; HTF bias uses 1H close vs prior swing | `bos_choch`: BOS when swing sequence continues trend (HH/HL or LH/LL pattern) | SMC BOS ≠ ICT MSS; depends on look-ahead swings | Contaminated via swing input | — | **Do not map 1:1** · keep ICT HTF/MSS semantics |
| **CHoCH** | Event: first break against prior structure (no raid required) | `CHOCH` when swing character flips vs prior BOS pattern | Similar intent; different pivot source | Contaminated via SMC swings | Validate ICT CHoCH only | **KEEP ICT CHoCH events** |
| **MSS** | Body close beyond opposing swing **after** raid+displacement (narrative) | No distinct “MSS after raid” — folded into BOS/CHoCH | ICT MSS is narrative-gated; SMC is structural only | ICT causal if swings lagged | Already on validate path | **KEEP ICT MSS definition** |
| **Order block** | Last opposing candle before expansion (`body > 1.5×` avg) on expansion bar close | `ob()` tied to swing H/L sequence + mitigation flags | Different trigger; SMC needs swings | Contaminated if swings look-ahead | Optional future A/B | **KEEP ICT OB** for now |
| **Breaker** | Close through OB extreme → breaker zone; `BREAKER_RETESTED` at CE | Not a first-class SMC export (OB mitigation / flip implicit) | ICT explicit breaker lifecycle | ICT causal | Setup #6/#9 OOS later | **KEEP ICT breaker** |
| **Liquidity (EQH/EQL)** | Swings within 1.5 pips → `eqh`/`eql` | `liquidity(range_percent=0.01)` clusters swing highs/lows in % range; tracks `Swept` | Similar cluster idea; SMC % of price vs ICT pip tolerance | Contaminated via swings | Attribution already has `eqh_eql_cluster` model | **KEEP session_pools default**; EQH as secondary |
| **Liquidity (session / PDH)** | PDH/PDL, ASH/ASL, LSH/LSL expanding causal pools; ASH window follows `mentorship_2017` | Not in SMC core API | ICT richer institutional pools | ICT: ASH shift-1 for same-bar safety | Done in H4 attribution | **KEEP ICT pools** |
| **Sweep / raid** | Wick through pool + close back; quality 2=major, 1=swing; grades A/B/C | `Swept` index on liquidity clusters | ICT requires rejection close; SMC “swept” is pierce index | ICT better for setups | — | **KEEP ICT sweep engine** |
| **Displacement** | `body_ratio≥0.60` & `body≥1.5×ATR20` | Not a separate SMC indicator | ICT explicit energy gate | Causal | — | **KEEP** |
| **Premium / discount** | Rolling lookback EQ = (max+min)/2 shifted 1 | Not in SMC core | ICT dealing range ≠ raid-defined range | Causal but **ICT DEFINITION gap** | Dealing-range from raid/MSS | **KEEP for now**; flag Phase 2 improvement |
| **OTE** | Rolling 61.8–78.6; soft_score | Not in SMC | Soft vs hard | Causal | Soft already validated path | **KEEP soft_score** |
| **Killzones / SB** | `kz_tables` NY clock; mentorship SB 14–15 | Not in SMC | Session law is ICT-specific | Causal + DST tests exist | — | **KEEP mentorship_2017** |

---

## B. Classification cheat-sheet

| Item | Class |
|------|-------|
| SMC FVG uses `shift(-1)` | **CODE FACT** (SMC source) |
| SMC swings need future bars | **CODE FACT** (SMC source) |
| ICTv_11 swing activation delayed by `window` | **CODE FACT** |
| ICTv_11 FVG=B at candle-3 close | **ICT DEFINITION** (locked) + **CODE FACT** |
| “SMC is more correct ICT” | **UNVALIDATED** / often **CONTRADICTED** for live use due to look-ahead |
| Copying SMC will improve OOS WR | **RESEARCH HYPOTHESIS** — reject until causal port + OOS |
| Geometry lock disagreements vs SMC | **CODE FACT** (documented in `ICT_GEOMETRY_LOCK.md`) |

---

## C. Explicit “do not copy” list

1. **SMC `fvg()`** — future candle in definition.  
2. **SMC `swing_highs_lows()`** — centered window = repaint.  
3. **Anything built on (1)+(2)** (`bos_choch`, `ob`, `liquidity`) without re-anchoring pivots to confirmed-lag swings.  
4. SMC “mitigated index” as a live filter on the formation bar.

Safe research use of SMC: **terminology and UI ideas only**, or offline chart annotation after full confirmation lag.

---

## D. Other authorized repos (brief status — not deep-audited this phase)

| Repo | Relevance | Phase 1 action |
|------|-----------|----------------|
| SrsBlack/ict-knowledge-library | Terminology / setup names | Defer glossary merge to Phase 1b if needed |
| islero/ICT-NT, dextergsm, OPKYEI, etc. | Setup recipes | Defer; same look-ahead audit bar |
| nautechsystems/nautilus_trader | Event clock / replay architecture | Phase 1b architecture notes only |
| freqtrade / backtrader / lumibot | Backtest shells | Do not migrate without parity proof |

---

## E. Decisions for ICTv_11 (no code change)

| Decision | Rationale |
|----------|-----------|
| **Do not vendor `smartmoneyconcepts`** | Look-ahead FVG + swings |
| **Retain FVG=B / mentorship / OTE soft** | Locked; empirically separate from SMC |
| **Retain confirmed-lag swings** | Matches no-lookahead tests |
| **Optional later:** causal re-implementation of “cluster liquidity %” using ICT lagged swings | Attribution model already exists |
| **Phase 2 priority (from this table):** raid-based dealing range / OTE (ICT DEFINITION gap), not SMC import | Aligns with geometry lock note |

---

## F. Suggested OOS tests (only after validate green — not run now)

| Test ID | Hypothesis | Required before OOS |
|---------|------------|---------------------|
| P1-T1 | CE mitigate vs full-gap fill | EURUSD validate A/B |
| P1-T2 | EQH cluster vs session_pools | Attribution already; no default switch |
| P1-T3 | “SMC-style FVG” delayed to bar+1 | Must prove ≠ look-ahead |  
| — | Full SMC parity | **FORBIDDEN** without rewrite |

---

## Explicit STOP

- Phase 1 table complete.  
- **No code copy.** No OOS. No Tier M rewrite.  
- Next (your call): Phase 2 — why Track A EURUSD WR ≈29% under geometry lock, or Phase 1b — Nautilus architecture notes only.
