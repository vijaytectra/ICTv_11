"""CSV export for ops trade journal."""
from __future__ import annotations

import csv
import io
from typing import Any, Dict, List


CSV_COLUMNS = [
    "id",
    "source",
    "status",
    "pair",
    "setup_id",
    "setup_name",
    "direction",
    "entry",
    "sl",
    "tp",
    "confluence_score",
    "outcome",
    "reason_code",
    "note",
    "entry_time",
    "exit_time",
    "net_pnl",
    "r_multiple",
    "created_at",
    "updated_at",
]


def trades_to_csv(rows: List[Dict[str, Any]]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=CSV_COLUMNS, extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow({k: r.get(k) for k in CSV_COLUMNS})
    return buf.getvalue()
