"""SQLite ops trade journal store."""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, date
from typing import Any, Dict, List, Optional

from backend.journal.export import trades_to_csv
from backend.journal.reasons import REASON_CODES, reason_for_backtest_outcome
from backend.journal.schema import ensure_schema


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return dict(row)


class JournalStore:
    def __init__(self, db_path: str):
        self.db_path = db_path
        parent = os.path.dirname(db_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        ensure_schema(self._conn)

    def close(self) -> None:
        self._conn.close()

    def insert_from_backtest(self, trades: List[Dict[str, Any]]) -> int:
        inserted = 0
        now = _now()
        for t in trades:
            outcome = (t.get("outcome") or "").upper() or None
            entry_time = (
                t.get("timestamp_entry")
                or t.get("entry_time")
                or t.get("timestamp")
                or now
            )
            exit_time = t.get("timestamp_exit") or t.get("exit_time")
            entry = t.get("entry", t.get("entry_price"))
            sl = t.get("sl", t.get("sl_price"))
            tp = t.get("tp", t.get("tp_price"))
            reason = t.get("reason_code") or reason_for_backtest_outcome(outcome or "")
            try:
                cur = self._conn.execute(
                    """
                    INSERT OR IGNORE INTO trades (
                        source, status, pair, setup_id, setup_name, direction,
                        entry, sl, tp, confluence_score, outcome, reason_code, note,
                        entry_time, exit_time, net_pnl, r_multiple, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "backtest",
                        "CLOSED",
                        t.get("pair", ""),
                        t.get("setup_id"),
                        t.get("setup_name"),
                        t.get("direction", ""),
                        entry,
                        sl,
                        tp,
                        t.get("confluence_score"),
                        outcome,
                        reason,
                        t.get("note"),
                        str(entry_time),
                        str(exit_time) if exit_time else None,
                        t.get("net_pnl"),
                        t.get("r_multiple") or t.get("rr"),
                        now,
                        now,
                    ),
                )
                if cur.rowcount:
                    inserted += 1
            except sqlite3.Error:
                continue
        self._conn.commit()
        return inserted

    def insert_proposed_from_alert(self, signal: Dict[str, Any]) -> Optional[int]:
        now = _now()
        entry_time = signal.get("timestamp") or signal.get("entry_time") or now
        try:
            cur = self._conn.execute(
                """
                INSERT OR IGNORE INTO trades (
                    source, status, pair, setup_id, setup_name, direction,
                    entry, sl, tp, confluence_score, outcome, reason_code, note,
                    entry_time, exit_time, net_pnl, r_multiple, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "telegram",
                    "PROPOSED",
                    signal.get("pair", ""),
                    signal.get("setup_id"),
                    signal.get("setup_name"),
                    signal.get("direction", ""),
                    signal.get("entry"),
                    signal.get("sl"),
                    signal.get("tp"),
                    signal.get("confluence_score"),
                    None,
                    None,
                    signal.get("note"),
                    str(entry_time),
                    None,
                    None,
                    signal.get("rr"),
                    now,
                    now,
                ),
            )
            self._conn.commit()
            if cur.rowcount == 0:
                return None
            return int(cur.lastrowid)
        except sqlite3.Error:
            return None

    def list_trades(
        self,
        *,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        source: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        clauses = []
        params: List[Any] = []
        if date_from:
            clauses.append("entry_time >= ?")
            params.append(date_from)
        if date_to:
            clauses.append("entry_time <= ?")
            params.append(date_to + " 23:59:59" if len(date_to) == 10 else date_to)
        if source:
            clauses.append("source = ?")
            params.append(source)
        if status:
            clauses.append("status = ?")
            params.append(status)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        rows = self._conn.execute(
            f"SELECT * FROM trades{where} ORDER BY entry_time DESC, id DESC",
            params,
        ).fetchall()
        return [_row_to_dict(r) for r in rows]

    def today_summary(self, day: Optional[str] = None) -> Dict[str, Any]:
        day = day or date.today().isoformat()
        trades = self.list_trades(date_from=day, date_to=day)
        proposed = sum(1 for t in trades if t["status"] == "PROPOSED")
        taken = sum(1 for t in trades if t["status"] == "TAKEN")
        skipped = sum(1 for t in trades if t["status"] == "SKIPPED")
        wins = sum(1 for t in trades if (t.get("outcome") or "").upper() == "WIN")
        losses = sum(1 for t in trades if (t.get("outcome") or "").upper() == "LOSS")
        closed = wins + losses
        wr = (wins / closed * 100.0) if closed else 0.0
        return {
            "day": day,
            "proposed": proposed,
            "taken": taken,
            "skipped": skipped,
            "wins": wins,
            "losses": losses,
            "win_rate_pct": round(wr, 1),
            "trades": trades,
        }

    def get_trade(self, trade_id: int) -> Optional[Dict[str, Any]]:
        row = self._conn.execute(
            "SELECT * FROM trades WHERE id = ?", (trade_id,)
        ).fetchone()
        return _row_to_dict(row) if row else None

    def update_trade(
        self,
        trade_id: int,
        *,
        status: Optional[str] = None,
        outcome: Optional[str] = None,
        note: Optional[str] = None,
    ) -> Dict[str, Any]:
        row = self.get_trade(trade_id)
        if not row:
            raise KeyError(f"trade {trade_id} not found")

        new_status = status if status is not None else row["status"]
        new_outcome = outcome if outcome is not None else row["outcome"]
        new_note = note if note is not None else row["note"]
        reason = row["reason_code"]

        cur_status = row["status"]
        if status == "SKIPPED":
            new_status = "SKIPPED"
            reason = "SKIPPED_BY_USER"
            new_outcome = new_outcome or "FLAT"
        elif status == "TAKEN" and cur_status == "PROPOSED":
            new_status = "TAKEN"
        elif outcome in ("WIN", "LOSS") and (status == "CLOSED" or cur_status in ("TAKEN", "PROPOSED", "CLOSED")):
            new_status = "CLOSED"
            new_outcome = outcome
            reason = "MANUAL_MARKED_WIN" if outcome == "WIN" else "MANUAL_MARKED_LOSS"
        elif status is not None:
            new_status = status

        now = _now()
        self._conn.execute(
            """
            UPDATE trades SET status=?, outcome=?, note=?, reason_code=?, updated_at=?
            WHERE id=?
            """,
            (new_status, new_outcome, new_note, reason, now, trade_id),
        )
        self._conn.commit()
        return self.get_trade(trade_id)  # type: ignore

    def insert_manual(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        now = _now()
        cur = self._conn.execute(
            """
            INSERT INTO trades (
                source, status, pair, setup_id, setup_name, direction,
                entry, sl, tp, confluence_score, outcome, reason_code, note,
                entry_time, exit_time, net_pnl, r_multiple, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.get("source", "manual"),
                payload.get("status", "PROPOSED"),
                payload.get("pair", ""),
                payload.get("setup_id"),
                payload.get("setup_name"),
                payload.get("direction", ""),
                payload.get("entry"),
                payload.get("sl"),
                payload.get("tp"),
                payload.get("confluence_score"),
                payload.get("outcome"),
                payload.get("reason_code", "OTHER"),
                payload.get("note"),
                str(payload.get("entry_time") or now),
                payload.get("exit_time"),
                payload.get("net_pnl"),
                payload.get("r_multiple"),
                now,
                now,
            ),
        )
        self._conn.commit()
        return self.get_trade(int(cur.lastrowid))  # type: ignore

    def export_csv(
        self, *, date_from: Optional[str] = None, date_to: Optional[str] = None
    ) -> str:
        rows = self.list_trades(date_from=date_from, date_to=date_to)
        return trades_to_csv(rows)

    def reason_codes(self) -> List[str]:
        return list(REASON_CODES)
