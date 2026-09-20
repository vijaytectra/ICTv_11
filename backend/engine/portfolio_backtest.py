"""
Multi-pair portfolio backtest with shared equity and open-position caps.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from backend.engine.backtester import execute_backtest
from backend.engine.metrics import compute_win_rate, trades_per_week


def run_portfolio(
    pairs_data: Dict[str, pd.DataFrame],
    signals_by_pair: Dict[str, List[Dict[str, Any]]],
    start: Optional[str] = None,
    end: Optional[str] = None,
    starting_balance: float = 200.0,
    risk_percent: float = 1.0,
    max_slippage_pips: float = 0.5,
    commission_per_lot: float = 3.50,
    max_portfolio_open: int = 3,
    enable_breakeven: bool = False,
) -> Dict[str, Any]:
    """
    Chronological portfolio simulation.
    - Max 1 open per pair (enforced by per-pair active window)
    - Max `max_portfolio_open` concurrent across pairs
    - Shared equity for 1% risk sizing
    """
    # Flatten signals
    queue: List[Tuple[str, Dict[str, Any]]] = []
    for pair, sigs in signals_by_pair.items():
        for s in sigs:
            ts = s["timestamp"]
            if start and ts[:10] < start[:10]:
                continue
            if end and ts[:10] > end[:10]:
                continue
            queue.append((pair, s))
    queue.sort(key=lambda x: x[1]["timestamp"])

    balance = float(starting_balance)
    peak = balance
    max_dd_pct = 0.0
    all_trades: List[Dict[str, Any]] = []

    # open: list of (pair, exit_timestamp_str)
    open_positions: List[Tuple[str, str]] = []

    def _prune_opens(now_ts: str) -> None:
        nonlocal open_positions
        open_positions = [(p, ex) for p, ex in open_positions if ex > now_ts]

    for pair, sig in queue:
        now = sig["timestamp"]
        _prune_opens(now)

        if any(p == pair for p, _ in open_positions):
            continue
        if len(open_positions) >= max_portfolio_open:
            continue
        if pair not in pairs_data:
            continue

        df = pairs_data[pair]
        result = execute_backtest(
            df,
            [sig],
            pair,
            starting_balance=balance,
            risk_percent=risk_percent,
            max_slippage_pips=max_slippage_pips,
            commission_per_lot=commission_per_lot,
            max_open_trades=1,
            enable_breakeven=enable_breakeven,
        )
        trades = result.get("trades", [])
        if not trades:
            continue

        t = dict(trades[0])
        t["pair"] = pair
        t["entry_time"] = t.get("timestamp_entry") or t.get("entry_time") or now
        t["exit_time"] = t.get("timestamp_exit") or t.get("exit_time") or now

        pnl = float(t.get("net_pnl", t.get("pnl", 0.0)))
        balance += pnl
        peak = max(peak, balance)
        dd = (peak - balance) / peak if peak > 0 else 0.0
        max_dd_pct = max(max_dd_pct, dd)

        exit_ts = str(t["exit_time"])
        open_positions.append((pair, exit_ts))
        all_trades.append(t)

    wr_block = compute_win_rate(all_trades)
    span_start = start or (all_trades[0].get("entry_time", "2020-01-01")[:10] if all_trades else "2020-01-01")
    span_end = end or (all_trades[-1].get("entry_time", "2020-01-01")[:10] if all_trades else "2020-01-01")
    tpw = trades_per_week(all_trades, span_start, span_end)

    return {
        "starting_balance": starting_balance,
        "ending_balance": balance,
        "net_pnl": balance - starting_balance,
        "max_drawdown_pct": max_dd_pct * 100.0,
        "trades": all_trades,
        "total_trades": len(all_trades),
        **wr_block,
        "trades_per_week": tpw,
        "period_start": span_start,
        "period_end": span_end,
    }
