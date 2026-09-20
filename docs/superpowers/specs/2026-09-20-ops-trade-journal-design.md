# Ops Trade Journal + Dashboard Design

**Date:** 2026-09-20  
**Status:** Approved in brainstorming (§1–§3); awaiting user review of this file  
**Priority track:** Parallel with quality causal ladder (**no live auto-execution**)  
**Approach:** Journal module + thin API + extend existing FastAPI/`frontend` dashboard  

**Related:** `docs/superpowers/specs/2026-09-20-quality-causal-backtest-design.md`  
**Reference ideas (not vendored):** [jwaang/auto-ict](https://github.com/jwaang/auto-ict) journal/CSV/dashboard habit  

---

## 1. Goal

Build a durable **trade journal** and **daily ops panel** on `http://localhost:8000` so the user’s daily work is:

- See how many trades/proposals today  
- See wins / losses  
- See **auto reason codes** + optional free-text notes  

Fed by:

1. **Backtest / quality ladder** completed trades (`source=backtest`, `status=CLOSED`)  
2. **Telegram alerts** as `PROPOSED` rows the user marks Taken / Skipped / Win / Loss  

**Explicitly out of scope this phase:** broker order placement, IBKR/MT5 auto-fill, auto Win/Loss from live price for Telegram trades.

---

## 2. Locked decisions

| Item | Choice |
|------|--------|
| Overall phase | **B** — ladder + parallel ops journal (no live auto) |
| Setups | All **8 active** (1,2,3,4,5,6,9,10); 7–8 remain disabled |
| Journal sources | **C** — backtest/ladder + Telegram/manual |
| UI | **A** — extend existing FastAPI dashboard on `:8000` |
| Storage | **C** — SQLite + CSV export on demand |
| Reasons | **B** — auto codes + optional free-text note |
| Telegram flow | **A** — auto **PROPOSED** → Taken/Skipped → Win/Loss |
| Implementation approach | **1** — `backend/journal/` + API + dashboard panel |

Silver Bullet (and any single setup) is only an *example* in product talk — the journal covers all active setups.

---

## 3. Architecture

```
Telegram alert success ──► journal.insert_proposed ──► status=PROPOSED
                                                      │
                         user (dashboard) ────────────┼──► TAKEN / SKIPPED
                                                      └──► WIN / LOSS + note

Backtest / ladder fills ──► journal.insert_from_backtest ──► status=CLOSED
                                                      outcome + reason_code

Dashboard / API ──► SQLite (data/trade_journal.db) ──► CSV export
```

### Components

| Piece | Role |
|-------|------|
| `data/trade_journal.db` | SQLite file (gitignored) |
| `backend/journal/` | Schema, store, reasons, export |
| `backend/api/server.py` | `/api/journal/*`; hook backtest writes |
| `backend/telegram_alerts/` | After successful alert → PROPOSED |
| `frontend/` | Ops Journal panel |

---

## 4. Data model

### Status lifecycle

| Status | Meaning |
|--------|---------|
| `PROPOSED` | Alert logged; not yet acted |
| `TAKEN` | User confirms they took the trade (outcome may still be open) |
| `SKIPPED` | User skipped; reason `SKIPPED_BY_USER` |
| `CLOSED` | Terminal — has outcome (backtest always lands here; manual after Win/Loss) |

### Core columns

`id` (INTEGER PK),  
`source` (`backtest` | `telegram` | `manual`),  
`status` (above),  
`pair`, `setup_id`, `setup_name`, `direction`,  
`entry`, `sl`, `tp`,  
`confluence_score` (nullable),  
`outcome` (`WIN` | `LOSS` | `FLAT` | null),  
`reason_code`, `note` (nullable text),  
`entry_time`, `exit_time` (nullable),  
`net_pnl` (nullable), `r_multiple` (nullable),  
`created_at`, `updated_at`

### Dedupe

Unique key: `(source, pair, setup_id, entry_time, direction)`  
Second insert with same key is a no-op (idempotent).

---

## 5. Reason codes

| Code | Use |
|------|-----|
| `HIT_TP` | Backtest win — TP before SL |
| `HIT_SL` | Backtest loss — SL before TP |
| `HIT_BE` | Breakeven / flat (if ever enabled) |
| `TIME_EXIT` | Forced max-hold / window exit |
| `SKIPPED_BY_USER` | User skipped PROPOSED |
| `MANUAL_MARKED_WIN` | User marked win (Telegram path) |
| `MANUAL_MARKED_LOSS` | User marked loss |
| `SPREAD_FILTER` | Wide spread noted / rejected |
| `CONFLUENCE_FAIL` | Below min score (if logged) |
| `OTHER` | Fallback + note |

Backtest uses `HIT_TP` / `HIT_SL` / `TIME_EXIT`.  
Telegram closes use `MANUAL_MARKED_WIN` / `MANUAL_MARKED_LOSS` plus optional `note`.

---

## 6. API

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/journal/today` | Today summary counts + rows (server local date, document TZ = machine local unless config overrides) |
| `GET` | `/api/journal/trades` | Query: `from`, `to`, `source`, `status` |
| `POST` | `/api/journal/trades` | Rare manual insert |
| `PATCH` | `/api/journal/trades/{id}` | Body: `status` and/or `outcome` and/or `note` |
| `GET` | `/api/journal/export.csv` | CSV download (`from`, `to`) |
| `GET` | `/api/journal/reason-codes` | Fixed list for UI |

Internal helpers (Python): `insert_from_backtest(trades)`, `insert_proposed_from_alert(signal)`.

### PATCH rules

- `PROPOSED` → `TAKEN` or `SKIPPED`  
- `SKIPPED` → set `reason_code=SKIPPED_BY_USER`, `outcome` null or `FLAT`  
- `TAKEN` + `outcome=WIN|LOSS` → `status=CLOSED`, set `MANUAL_MARKED_*`  
- Optional `note` anytime after create  

---

## 7. Dashboard UX

Same app (`frontend/` served by FastAPI):

1. Keep research/backtest controls.  
2. Add **Ops Journal** section (prefer default-visible for daily habit; Research remains available):  
   - Today counters: Proposed, Taken, Skipped, Wins, Losses, WR among closed taken/backtest  
   - Table: time, pair, setup, direction, score, status, outcome, reason, note  
   - Actions: Taken | Skip | Win | Loss + note  
   - Export CSV button  
3. Copy: “8 active setups • journal only • no auto-orders” (not “10 setups” as live claim).

---

## 8. File map

| Path | Role |
|------|------|
| `backend/journal/__init__.py` | Package |
| `backend/journal/schema.py` | DDL / ensure_schema |
| `backend/journal/store.py` | CRUD, dedupe, today summary |
| `backend/journal/reasons.py` | Constants |
| `backend/journal/export.py` | CSV |
| `backend/api/server.py` | Routes + backtest hook |
| `backend/telegram_alerts/telegram_bot.py` | PROPOSED on successful send |
| `frontend/index.html`, `css/dashboard.css`, `js/app.js` | Ops panel |
| `config/config.json` | `journal_db_path` default `data/trade_journal.db` |
| `.gitignore` | `data/trade_journal.db`, `data/*.db` |
| `tests/test_journal_store.py` | Store/API behavior tests |

---

## 9. Tests (required)

1. Insert backtest CLOSED → listed / counted  
2. PROPOSED → TAKEN → WIN + note  
3. SKIP → `SKIPPED_BY_USER`  
4. Dedupe identical key → single row  
5. CSV contains `reason_code` and `note`  

---

## 10. Borrow from auto-ict (ideas only)

**Borrow:** per-trade context (setup, confluence, outcome, reasons), journal + daily review habit, CSV for offline chart review.  

**Do not borrow:** IBKR live/paper auto-execution, Streamlit second UI, ES/MES-only strategy modes as ICT_v11 edge, their published ~34% WR config.

---

## 11. Parallelism with quality ladder

| Track | Dependency |
|-------|------------|
| Ops journal | Can implement without full 2020–present JForex data |
| Quality ladder Task 7 | Still blocked on data integrity PASS for all 6 majors |

Neither track enables live auto-orders.

---

## 12. Delivery order (implementation plan later)

1. SQLite schema + store + unit tests  
2. API routes  
3. Wire Telegram + `/api/backtest`  
4. Dashboard Ops panel  
5. CSV export  

After this spec is user-approved on disk → invoke writing-plans for `docs/superpowers/plans/2026-09-20-ops-trade-journal.md`.

---

## 13. Approval record

| Item | Decision |
|------|----------|
| §1 Architecture | Approved |
| §2 API / reasons / UI | Approved |
| §3 Files / tests / auto-ict borrow | Approved |
| Brainstorming Qs | Sources C, UI A, storage C, reasons B, Telegram A, Approach 1 |
