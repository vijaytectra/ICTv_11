"""
Multi-pair portfolio backtest with shared equity, open-position caps,
and USD-block correlation filter.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from backend.engine.backtester import execute_backtest
from backend.engine.metrics import compute_win_rate, trades_per_week

# Long-USD vs short-USD exposure for major FX book
USD_LONG_PAIRS = {"USDJPY", "USDCAD", "USDCHF"}  # BUY = long USD
USD_SHORT_PAIRS = {"EURUSD", "GBPUSD", "AUDUSD"}  # BUY = short USD


def usd_block_side(pair: str, direction: str) -> Optional[str]:
    """Return 'LONG_USD' or 'SHORT_USD' for the trade's USD factor, else None."""
    pair = pair.upper()
    d = direction.upper()
    if pair in USD_LONG_PAIRS:
        return "LONG_USD" if d == "BUY" else "SHORT_USD"
    if pair in USD_SHORT_PAIRS:
        return "SHORT_USD" if d == "BUY" else "LONG_USD"
    return None


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
    max_trades_per_day: int = 5,
    enable_breakeven: bool = False,
    enable_usd_block: bool = True,
    rejections: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Chronological portfolio simulation.
    - Max 1 open per pair
    - Max max_portfolio_open concurrent
    - Max max_trades_per_day
    - USD-block: reject same-session same USD-direction correlated majors
    """
    candidate_trades: List[Dict[str, Any]] = []

    for pair, sigs in signals_by_pair.items():
        if pair not in pairs_data or not sigs:
            continue
        filtered: List[Dict[str, Any]] = []
        for s in sigs:
            ts = s["timestamp"]
            if start and ts[:10] < start[:10]:
                continue
            if end and ts[:10] > end[:10]:
                continue
            filtered.append(s)
        if not filtered:
            continue
        filtered.sort(key=lambda x: x["timestamp"])

        df = pairs_data[pair]
        if start or end:
            lo = (start or "1970-01-01")[:10]
            hi = (end or "2999-12-31")[:10]
            try:
                df_bt = df.loc[lo:hi]
            except Exception:
                df_bt = df
            if len(df_bt) < 10:
                df_bt = df
        else:
            df_bt = df

        result = execute_backtest(
            df_bt,
            filtered,
            pair,
            starting_balance=starting_balance,
            risk_percent=risk_percent,
            max_slippage_pips=max_slippage_pips,
            commission_per_lot=commission_per_lot,
            max_open_trades=1,
            enable_breakeven=enable_breakeven,
        )
        for t in result.get("trades", []):
            row = dict(t)
            row["pair"] = pair
            row["entry_time"] = row.get("timestamp_entry") or row.get("entry_time")
            row["exit_time"] = row.get("timestamp_exit") or row.get("exit_time")
            sig_ts = row.get("timestamp_signal")
            row["session"] = next(
                (s.get("session") for s in filtered if s.get("timestamp") == sig_ts),
                None,
            )
            candidate_trades.append(row)

    candidate_trades.sort(key=lambda t: str(t.get("entry_time") or ""))

    balance = float(starting_balance)
    peak = balance
    max_dd_pct = 0.0
    all_trades: List[Dict[str, Any]] = []
    open_positions: List[Tuple[str, str, Optional[str], Optional[str]]] = []
    trades_on_day: Dict[str, int] = {}

    def _prune_opens(now_ts: str) -> None:
        nonlocal open_positions
        open_positions = [o for o in open_positions if str(o[1]) > now_ts]

    for t in candidate_trades:
        now = str(t.get("entry_time") or "")
        if not now:
            continue
        _prune_opens(now)
        pair = t["pair"]
        direction = str(t.get("direction", "")).upper()
        session = t.get("session")
        usd_side = usd_block_side(pair, direction)

        if any(p == pair for p, *_rest in open_positions):
            continue
        if len(open_positions) >= max_portfolio_open:
            continue
        day = now[:10]
        if trades_on_day.get(day, 0) >= max_trades_per_day:
            continue

        if enable_usd_block and usd_side:
            conflict = False
            for _p, _ex, side, sess in open_positions:
                if side == usd_side and (sess is None or session is None or sess == session):
                    conflict = True
                    break
            if conflict:
                if rejections is not None:
                    rejections.append(
                        {
                            "pair": pair,
                            "timestamp": now,
                            "direction": direction,
                            "rejection_reason": "USD_BLOCK_CORRELATION",
                            "usd_side": usd_side,
                            "session": session,
                        }
                    )
                continue

        pnl = float(t.get("net_pnl", t.get("pnl", 0.0)))
        if starting_balance > 0:
            scale = balance / starting_balance
            pnl = pnl * scale
            t = dict(t)
            t["net_pnl"] = round(pnl, 4)

        balance += pnl
        peak = max(peak, balance)
        dd = (peak - balance) / peak if peak > 0 else 0.0
        max_dd_pct = max(max_dd_pct, dd)

        exit_ts = str(t.get("exit_time") or now)
        open_positions.append((pair, exit_ts, usd_side, session))
        trades_on_day[day] = trades_on_day.get(day, 0) + 1
        all_trades.append(t)

    wr_block = compute_win_rate(all_trades)
    span_start = start or (
        all_trades[0].get("entry_time", "2020-01-01")[:10] if all_trades else "2020-01-01"
    )
    span_end = end or (
        all_trades[-1].get("entry_time", "2020-01-01")[:10] if all_trades else "2020-01-01"
    )
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
        "max_trades_per_day": max_trades_per_day,
        "usd_block_enabled": enable_usd_block,
    }
