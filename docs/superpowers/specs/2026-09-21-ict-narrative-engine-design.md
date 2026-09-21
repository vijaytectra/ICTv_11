# ICT Narrative Trade-Selection Engine (Hybrid)

**Date:** 2026-09-21  
**Status:** Approved (brainstorming locks + plan)  
**Approach:** Causal event + narrative layer; 8 setups consume narrative

---

## 1. Goal

Re-engineer trade selection so the system behaves like a selective ICT discretionary trader while remaining causal, deterministic, and statistically honest.

**80% WR is a TARGET/GATE, not an assumption.** Never manufacture it.

## 2. Locked decisions

| Item | Value |
|------|-------|
| Architecture | Hybrid: event/narrative layer + setups 1–6, 9, 10 |
| Train | 2020-01-01 → 2021-12-31 |
| Validate | 2022-01-01 → 2023-12-31 |
| Final OOS | 2024-01-01 → last available bar ≤ 2026-12-31 (label window in report) |
| Timezone | CSV `Time (EET)` → `Europe/Bucharest` → ICT clocks in `America/New_York` |
| News | **Excluded** this cycle |
| Risk | 1% per trade |
| RR | Fixed 1:2; reject if opposing liquidity < 2R (never stretch TP) |
| BE / time-stop | Off for gate |
| Frequency | Do not force trades; FAIL if >12/week OOS; <50 resolved → INSUFFICIENT SAMPLE |
| Prior fixes | Must not regress (FVG bearish, limit-fill, sweep SL, Asian expanding, setup 6/9/10, timeout FLAT) |

## 3. Narrative chain (required before any order)

```
HTF bias → dealing range → liquidity map → draw on liquidity → session
→ raid (grade A/B) → displacement → MSS → FVG/OB/breaker → entry/SL
→ opposing liquidity ≥2R → event dedupe → accept/reject
```

## 4. Event types

`LIQUIDITY_CREATED`, `LIQUIDITY_SWEPT`, `DISPLACEMENT`, `MSS`, `CHoCH`,
`FVG_CREATED`, `FVG_MITIGATED`, `BREAKER_CREATED`, `BREAKER_RETESTED`,
`SETUP_INVALIDATED`

Raid grades: **A** (major pool + displacement + structure), **B** (valid but weaker), **C** (reject by default).

## 5. Journals

- Acceptance: full narrative fields at entry
- Rejection: failed gate + optional offline hypothetical 2R (analysis only)
- Missed winners: rejected A/B that would have hit 2R offline

## 6. Final decision vocabulary

Exactly one of: **PASS** | **FAIL** | **INSUFFICIENT SAMPLE**

## 7. Out of scope

News filters, dashboard, Telegram, broker automation, OOS retuning.
