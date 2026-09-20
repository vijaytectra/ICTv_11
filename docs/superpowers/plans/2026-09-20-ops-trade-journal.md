# Ops Trade Journal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship SQLite trade journal + `/api/journal/*` + Ops panel on the existing FastAPI dashboard so daily work is today’s trades, W/L, and reasons — from backtest fills and Telegram PROPOSED rows — with **no live auto-orders**.

**Architecture:** `backend/journal/` owns schema/store/export. API and Telegram/backtest hooks write into it. `frontend/` adds an Ops Journal section. Parallel to quality ladder; does not require full JForex history.

**Tech Stack:** Python 3, sqlite3 stdlib, FastAPI, existing vanilla HTML/CSS/JS frontend, pytest.

**Spec:** `docs/superpowers/specs/2026-09-20-ops-trade-journal-design.md`

## Global Constraints

- No broker / MT5 / IBKR order placement in this plan
- 8 active setups only in product copy (1,2,3,4,5,6,9,10)
- Dedupe key: `(source, pair, setup_id, entry_time, direction)`
- DB path default: `data/trade_journal.db` (gitignored)
- Reason codes exactly as spec §5

## File map

| Path | Responsibility |
|------|----------------|
| `backend/journal/reasons.py` | Reason code constants + list API payload |
| `backend/journal/schema.py` | `ensure_schema(conn)` |
| `backend/journal/store.py` | JournalStore class |
| `backend/journal/export.py` | CSV bytes/string |
| `backend/journal/__init__.py` | Public exports |
| `backend/api/server.py` | Routes + backtest hook |
| `backend/telegram_alerts/telegram_bot.py` | PROPOSED after successful send |
| `frontend/index.html` | Ops section markup |
| `frontend/css/dashboard.css` | Ops styles |
| `frontend/js/app.js` | Ops API client + actions |
| `config/config.json` | `journal_db_path` |
| `.gitignore` | `data/*.db` |
| `tests/test_journal_store.py` | Required tests |

---

### Task 1: Journal store + schema + tests

**Files:**
- Create: `backend/journal/reasons.py`
- Create: `backend/journal/schema.py`
- Create: `backend/journal/store.py`
- Create: `backend/journal/export.py`
- Create: `backend/journal/__init__.py`
- Create: `tests/test_journal_store.py`
- Create: `.gitignore` (or append if created)
- Create: `data/.gitkeep`

**Interfaces:**
- Produces:
  - `REASON_CODES: list[str]`
  - `class JournalStore:`
    - `__init__(self, db_path: str)`
    - `insert_from_backtest(self, trades: list[dict]) -> int`  # inserted count
    - `insert_proposed_from_alert(self, signal: dict) -> Optional[int]`  # row id or None if dedupe
    - `list_trades(self, *, date_from=None, date_to=None, source=None, status=None) -> list[dict]`
    - `today_summary(self, day: Optional[str] = None) -> dict`  # counts + trades
    - `update_trade(self, trade_id: int, *, status=None, outcome=None, note=None) -> dict`
    - `export_csv(self, *, date_from=None, date_to=None) -> str`

- [ ] **Step 1: Write failing tests** in `tests/test_journal_store.py` covering spec §9 (tmp_path db)

```python
def test_backtest_insert_and_today(tmp_path):
    store = JournalStore(str(tmp_path / "j.db"))
    n = store.insert_from_backtest([{
        "pair": "EURUSD", "setup_id": 1, "setup_name": "Sweep+FVG",
        "direction": "BUY", "entry": 1.1, "sl": 1.09, "tp": 1.12,
        "timestamp_entry": "2026-09-20 10:00:00",
        "timestamp_exit": "2026-09-20 11:00:00",
        "outcome": "WIN", "net_pnl": 4.0,
    }])
    assert n == 1
    s = store.today_summary(day="2026-09-20")
    assert s["wins"] == 1

def test_proposed_taken_win_note(tmp_path): ...
def test_skip_reason(tmp_path): ...
def test_dedupe(tmp_path): ...
def test_csv_has_reason_and_note(tmp_path): ...
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `pytest tests/test_journal_store.py -v`

- [ ] **Step 3: Implement reasons, schema, store, export**

Schema SQL (unique index on dedupe key).  
Map backtest `outcome` WIN→`HIT_TP`, LOSS→`HIT_SL`, BREAKEVEN→`HIT_BE`; if exit looks like max window without TP/SL clarity use `TIME_EXIT` when outcome set from market exit — for v1 map WIN/LOSS/BREAKEVEN only as above.  
`insert_proposed_from_alert` uses `signal['timestamp']` as `entry_time`, status `PROPOSED`, source `telegram`.  
`update_trade` enforces PATCH rules from spec §6.

- [ ] **Step 4: Tests PASS**

- [ ] **Step 5: Commit**

```bash
git add backend/journal tests/test_journal_store.py .gitignore data/.gitkeep
git commit -m "feat: add SQLite trade journal store with reason codes"
```

---

### Task 2: FastAPI journal routes

**Files:**
- Modify: `backend/api/server.py`
- Modify: `config/config.json` — add `"journal_db_path": "data/trade_journal.db"`

**Interfaces:**
- Consumes: `JournalStore` from Task 1
- Produces: HTTP endpoints per spec §6

- [ ] **Step 1: Add helper** `_journal_store() -> JournalStore` resolving path from config (relative to repo root)

- [ ] **Step 2: Register routes** before `StaticFiles` mount (order matters — API first)

```python
@app.get("/api/journal/today")
@app.get("/api/journal/trades")
@app.post("/api/journal/trades")
@app.patch("/api/journal/trades/{trade_id}")
@app.get("/api/journal/export.csv")
@app.get("/api/journal/reason-codes")
```

Use `Response(content=csv, media_type="text/csv")` for export.  
Pydantic models for PATCH body: `status`, `outcome`, `note` optional.

- [ ] **Step 3: After successful backtest aggregation**, call `insert_from_backtest(aggregated_trades)` (best-effort log errors, do not fail response)

- [ ] **Step 4: Manual smoke** with TestClient or curl against tmp — optional unit with `TestClient`

- [ ] **Step 5: Commit** `feat: expose /api/journal endpoints and persist backtest trades`

---

### Task 3: Telegram → PROPOSED

**Files:**
- Modify: `backend/telegram_alerts/telegram_bot.py`
- Modify: `backend/telegram_alerts/mt5_monitor.py` if it constructs the bot (pass db path or use config lookup)

**Interfaces:**
- After `send_trade_signal` returns True → `JournalStore(...).insert_proposed_from_alert(signal)`
- Failures to journal must **not** fail the Telegram send return value (log warning)

- [ ] **Step 1: Implement hook** in `send_trade_signal`

- [ ] **Step 2: Unit test** with monkeypatch `send_message` → True and tmp db asserts PROPOSED row

- [ ] **Step 3: Commit** `feat: log Telegram signals as PROPOSED journal rows`

---

### Task 4: Dashboard Ops Journal panel

**Files:**
- Modify: `frontend/index.html`
- Modify: `frontend/css/dashboard.css`
- Modify: `frontend/js/app.js`

**UX:**
- Section id `ops-journal` near top (after header metrics or as first main block)
- Counters from `GET /api/journal/today`
- Table + buttons Taken / Skip / Win / Loss
- Note input per row or modal
- Export button → `/api/journal/export.csv`
- Subtitle: `8 active setups • journal only • no auto-orders`
- Soften header “10 Setups” claim to “8 active setups” where user-facing live/ops copy appears (keep research backtest labels accurate)

- [ ] **Step 1: HTML structure** for counters + table + export

- [ ] **Step 2: JS** `refreshOpsJournal()`, `patchTrade(id, body)`, wire buttons

- [ ] **Step 3: CSS** consistent with existing dark dashboard (no new framework)

- [ ] **Step 4: Manual check** — open `:8000`, today panel loads empty without error

- [ ] **Step 5: Commit** `feat: add Ops Journal panel to dashboard`

---

### Task 5: Spec status + smoke checklist

**Files:**
- Modify: `docs/superpowers/specs/2026-09-20-ops-trade-journal-design.md` — status → Implemented (or Partially) when done

- [ ] **Step 1: Run full journal tests**

`pytest tests/test_journal_store.py -v`

- [ ] **Step 2: Document smoke checklist** in plan completion notes:
  1. Start `python run_live_monitor.py`
  2. Open Ops panel
  3. Run backtest → rows appear
  4. (If Telegram configured) alert → PROPOSED → Taken → Win

- [ ] **Step 3: Commit** any doc status tweak

---

## Spec coverage self-check

| Spec section | Task |
|--------------|------|
| SQLite + fields + dedupe | 1 |
| Reason codes | 1 |
| API | 2 |
| Backtest hook | 2 |
| Telegram PROPOSED | 3 |
| Dashboard Ops | 4 |
| CSV export | 1 + 2 + 4 |
| No live auto | honored |
| Tests §9 | 1 |

## Out of scope (do not implement here)

Live/paper broker execution, auto W/L from live price, Streamlit, quality ladder OOS run.
