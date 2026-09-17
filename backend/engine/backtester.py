import pandas as pd
import numpy as np
from typing import List, Dict, Any, Tuple
from backend.engine.data_loader import get_pip_size

def execute_backtest(
    df: pd.DataFrame,
    signals: List[Dict[str, Any]],
    pair: str,
    starting_balance: float = 200.0,
    risk_percent: float = 1.0,
    max_slippage_pips: float = 0.5,
    commission_per_lot: float = 3.50,
    max_open_trades: int = 1,
    min_lot: float = 0.01,
    max_lot: float = 100.00,
    lot_step: float = 0.01,
    enable_breakeven: bool = True
) -> Dict[str, Any]:
    """
    Executes a causally rigorous, event-driven Forex backtest.
    - Bid/Ask realistic execution (BUY at Ask, exit at Bid; SELL at Bid, exit at Ask).
    - Recorded slippage and lot-based commission.
    - Strict broker position bounds (0.01 to 100.00 lots).
    - Trailing Breakeven logic (+0.2 pips lock at +1.0R).
    - Conservative Intrabar Ambiguity resolution (SL evaluated first).
    - Unique trade ledger accounting.
    """
    pip_size = get_pip_size(pair)
    balance = starting_balance
    peak_balance = starting_balance
    max_drawdown_dollars = 0.0
    max_drawdown_pct = 0.0
    
    trades_executed = []
    equity_curve = [{'timestamp': df.index[0].strftime('%Y-%m-%d %H:%M:%S'), 'balance': balance}]
    
    # Contract specification
    if "XAU" in pair:
        contract_size = 100
        lot_pip_value = 10.0  # $10/pip per 1.0 lot
    elif "IDX" in pair:
        contract_size = 20
        lot_pip_value = 20.0
    else:
        contract_size = 100000
        lot_pip_value = 10.0  # $10/pip per 1.0 lot for FX standard pairs
        
    df_times = list(df.index)
    time_to_idx = {t.strftime('%Y-%m-%d %H:%M:%S'): i for i, t in enumerate(df_times)}
    
    highs = df['high'].values
    lows = df['low'].values
    closes = df['close'].values
    spread_pips_arr = df['spread_pips'].values if 'spread_pips' in df.columns else np.full(len(df), 1.0)
    
    active_until_idx = -1
    trade_counter = 0
    
    for sig in signals:
        sig_time = sig['timestamp']
        if sig_time not in time_to_idx:
            continue
            
        entry_idx = time_to_idx[sig_time]
        if entry_idx <= active_until_idx:
            continue  # Max open trades per pair enforcement
            
        entry_price = sig['entry']
        sl_price = sig['sl']
        tp_price = sig['tp']
        direction = sig['direction']
        
        # Risk & Stop Distance
        risk_amount = balance * (risk_percent / 100.0)
        sl_distance_pips = abs(entry_price - sl_price) / pip_size
        if sl_distance_pips < 0.5:
            continue
            
        # Calculate Lot Size bounded by broker specifications
        raw_lots = risk_amount / (sl_distance_pips * lot_pip_value)
        stepped_lots = round(raw_lots / lot_step) * lot_step
        lot_size = max(min_lot, min(max_lot, round(stepped_lots, 2)))
        
        # Commission calculation ($3.50 round turn per lot -> $1.75 entry, $1.75 exit)
        commission_entry = (lot_size * commission_per_lot) / 2.0
        commission_exit = (lot_size * commission_per_lot) / 2.0
        total_commission = commission_entry + commission_exit
        
        # Slippage calculations
        entry_slippage_pips = max_slippage_pips
        exit_slippage_pips = max_slippage_pips
        entry_slippage_val = entry_slippage_pips * pip_size
        exit_slippage_val = exit_slippage_pips * pip_size
        
        spread_entry_pips = spread_pips_arr[entry_idx]
        spread_entry_val = spread_entry_pips * pip_size
        
        # Bid / Ask Execution Mechanics
        if direction == 'BUY':
            # BUY entry executed at Ask price = Bid + spread
            actual_entry = entry_price + spread_entry_val + entry_slippage_val
        else:
            # SELL entry executed at Bid price
            actual_entry = entry_price - entry_slippage_val
            
        initial_risk_dist = abs(actual_entry - sl_price)
        current_sl = sl_price
        current_tp = tp_price
        be_triggered = False
        
        # Forward simulate price action
        outcome = None
        exit_price = actual_entry
        exit_idx = entry_idx
        exit_time = sig_time
        is_ambiguous = False
        spread_exit_pips = spread_entry_pips
        
        max_look_ahead = min(len(df), entry_idx + 1440)  # max 24h forward simulation
        
        for k in range(entry_idx + 1, max_look_ahead):
            curr_high = highs[k]
            curr_low = lows[k]
            curr_spread_pips = spread_pips_arr[k]
            curr_spread_val = curr_spread_pips * pip_size
            
            # Bid prices (for BUY exits & SELL SL/TP evaluations)
            bid_high = curr_high
            bid_low = curr_low
            # Ask prices (for SELL exits & BUY evaluations)
            ask_high = curr_high + curr_spread_val
            ask_low = curr_low + curr_spread_val
            
            if direction == 'BUY':
                # Check Breakeven trigger (+1.0R move)
                if enable_breakeven and not be_triggered:
                    if bid_high >= (actual_entry + initial_risk_dist):
                        current_sl = actual_entry + (0.2 * pip_size)
                        be_triggered = True
                        
                # Check Intrabar Ambiguity (both SL & TP hit in same candle)
                sl_hit = (bid_low <= current_sl)
                tp_hit = (bid_high >= current_tp)
                
                if sl_hit and tp_hit:
                    is_ambiguous = True
                    # Conservative handling: SL evaluated first
                    outcome = 'BREAKEVEN' if be_triggered else 'LOSS'
                    exit_price = current_sl - exit_slippage_val
                    exit_idx = k
                    exit_time = df_times[k].strftime('%Y-%m-%d %H:%M:%S')
                    spread_exit_pips = curr_spread_pips
                    break
                elif sl_hit:
                    outcome = 'BREAKEVEN' if be_triggered else 'LOSS'
                    exit_price = current_sl - exit_slippage_val
                    exit_idx = k
                    exit_time = df_times[k].strftime('%Y-%m-%d %H:%M:%S')
                    spread_exit_pips = curr_spread_pips
                    break
                elif tp_hit:
                    outcome = 'WIN'
                    exit_price = current_tp
                    exit_idx = k
                    exit_time = df_times[k].strftime('%Y-%m-%d %H:%M:%S')
                    spread_exit_pips = curr_spread_pips
                    break
                    
            elif direction == 'SELL':
                if enable_breakeven and not be_triggered:
                    if ask_low <= (actual_entry - initial_risk_dist):
                        current_sl = actual_entry - (0.2 * pip_size)
                        be_triggered = True
                        
                sl_hit = (ask_high >= current_sl)
                tp_hit = (ask_low <= current_tp)
                
                if sl_hit and tp_hit:
                    is_ambiguous = True
                    outcome = 'BREAKEVEN' if be_triggered else 'LOSS'
                    exit_price = current_sl + exit_slippage_val
                    exit_idx = k
                    exit_time = df_times[k].strftime('%Y-%m-%d %H:%M:%S')
                    spread_exit_pips = curr_spread_pips
                    break
                elif sl_hit:
                    outcome = 'BREAKEVEN' if be_triggered else 'LOSS'
                    exit_price = current_sl + exit_slippage_val
                    exit_idx = k
                    exit_time = df_times[k].strftime('%Y-%m-%d %H:%M:%S')
                    spread_exit_pips = curr_spread_pips
                    break
                elif tp_hit:
                    outcome = 'WIN'
                    exit_price = current_tp
                    exit_idx = k
                    exit_time = df_times[k].strftime('%Y-%m-%d %H:%M:%S')
                    spread_exit_pips = curr_spread_pips
                    break
                    
        if outcome is None:
            # Market exit at end of window
            exit_idx = max_look_ahead - 1
            exit_price = closes[exit_idx]
            exit_time = df_times[exit_idx].strftime('%Y-%m-%d %H:%M:%S')
            pnl_pips = (exit_price - actual_entry) / pip_size if direction == 'BUY' else (actual_entry - exit_price) / pip_size
            outcome = 'WIN' if pnl_pips > 0 else 'LOSS'
            spread_exit_pips = spread_pips_arr[exit_idx]
            
        active_until_idx = exit_idx
        trade_counter += 1
        
        # PnL calculations
        if direction == 'BUY':
            pnl_pips = (exit_price - actual_entry) / pip_size
        else:
            pnl_pips = (actual_entry - exit_price) / pip_size
            
        gross_pnl_dollars = pnl_pips * lot_pip_value * lot_size
        net_pnl_dollars = gross_pnl_dollars - total_commission
        
        balance += net_pnl_dollars
        if balance > peak_balance:
            peak_balance = balance
        dd_dollars = peak_balance - balance
        dd_pct = (dd_dollars / peak_balance) * 100.0 if peak_balance > 0 else 0.0
        
        if dd_dollars > max_drawdown_dollars:
            max_drawdown_dollars = dd_dollars
        if dd_pct > max_drawdown_pct:
            max_drawdown_pct = dd_pct
            
        trade_id = f"TR-{pair}-{sig_time.replace(' ', 'T').replace(':', '')}-{trade_counter:04d}"
        
        trades_executed.append({
            'trade_id': trade_id,
            'timestamp_entry': sig_time,
            'timestamp_exit': exit_time,
            'pair': pair,
            'setup_id': sig['setup_id'],
            'setup_name': sig['setup_name'],
            'direction': direction,
            'entry_price': round(actual_entry, 5),
            'sl_price': round(sl_price, 5),
            'tp_price': round(tp_price, 5),
            'exit_price': round(exit_price, 5),
            'lot_size': lot_size,
            'outcome': outcome,
            'is_breakeven': be_triggered,
            'is_ambiguous': is_ambiguous,
            'entry_slippage_pips': entry_slippage_pips,
            'exit_slippage_pips': exit_slippage_pips,
            'total_slippage_pips': entry_slippage_pips + exit_slippage_pips,
            'spread_at_entry_pips': round(spread_entry_pips, 2),
            'spread_at_exit_pips': round(spread_exit_pips, 2),
            'commission_entry': round(commission_entry, 2),
            'commission_exit': round(commission_exit, 2),
            'total_commission': round(total_commission, 2),
            'gross_pnl': round(gross_pnl_dollars, 2),
            'net_pnl': round(net_pnl_dollars, 2),
            'balance_after': round(balance, 2)
        })
        
        equity_curve.append({
            'timestamp': exit_time,
            'balance': round(balance, 2)
        })
        
    # Accurate Classification Metrics
    total_trades = len(trades_executed)
    winning_trades = [t for t in trades_executed if t['outcome'] == 'WIN']
    losing_trades = [t for t in trades_executed if t['outcome'] == 'LOSS']
    be_trades = [t for t in trades_executed if t['outcome'] == 'BREAKEVEN']
    
    num_wins = len(winning_trades)
    num_losses = len(losing_trades)
    num_be = len(be_trades)
    
    # Conventional True Win Rate (BE NOT counted as win)
    decisive_trades = num_wins + num_losses
    true_win_rate = (num_wins / decisive_trades * 100.0) if decisive_trades > 0 else 0.0
    be_rate = (num_be / total_trades * 100.0) if total_trades > 0 else 0.0
    
    total_gross_profit = sum(t['net_pnl'] for t in winning_trades)
    total_gross_loss = abs(sum(t['net_pnl'] for t in losing_trades))
    profit_factor = (total_gross_profit / total_gross_loss) if total_gross_loss > 0 else (99.0 if total_gross_profit > 0 else 0.0)
    
    net_profit = balance - starting_balance
    net_return_pct = (net_profit / starting_balance) * 100.0
    
    return {
        'pair': pair,
        'starting_balance': starting_balance,
        'ending_balance': round(balance, 2),
        'net_profit': round(net_profit, 2),
        'net_return_pct': round(net_return_pct, 2),
        'total_trades': total_trades,
        'winning_trades': num_wins,
        'losing_trades': num_losses,
        'breakeven_trades': num_be,
        'true_win_rate_pct': round(true_win_rate, 2),
        'be_rate_pct': round(be_rate, 2),
        'profit_factor': round(profit_factor, 2),
        'max_drawdown_pct': round(max_drawdown_pct, 2),
        'max_drawdown_dollars': round(max_drawdown_dollars, 2),
        'ambiguous_trades': sum(1 for t in trades_executed if t['is_ambiguous']),
        'trades': trades_executed,
        'equity_curve': equity_curve
    }
