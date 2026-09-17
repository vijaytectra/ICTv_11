import pandas as pd
import numpy as np
from typing import List, Dict, Any, Tuple
from backend.engine.data_loader import get_pip_size
from backend.engine.ict_indicators import (
    find_swing_points, find_fair_value_gaps, find_inverted_fvgs,
    find_liquidity_sweeps, find_order_blocks, find_breaker_blocks,
    find_ote_zones, tag_killzones
)

class EventDrivenLiveSimulator:
    """
    Event-driven live market simulation engine.
    Processes market state strictly chronologically at time T.
    Access to future data T+1... is physically impossible in this structure.
    """
    def __init__(
        self,
        pair: str,
        starting_capital: float = 200.0,
        risk_percent: float = 1.0,
        target_rr: float = 2.0,
        max_slippage_pips: float = 0.5,
        commission_per_lot: float = 3.50,
        min_lot: float = 0.01,
        max_lot: float = 100.00,
        lot_step: float = 0.01,
        enable_breakeven: bool = True,
        confluence_threshold: int = 4
    ):
        self.pair = pair
        self.pip_size = get_pip_size(pair)
        self.starting_capital = starting_capital
        self.risk_percent = risk_percent
        self.target_rr = target_rr
        self.max_slippage_pips = max_slippage_pips
        self.commission_per_lot = commission_per_lot
        self.min_lot = min_lot
        self.max_lot = max_lot
        self.lot_step = lot_step
        self.enable_breakeven = enable_breakeven
        self.confluence_threshold = confluence_threshold
        
        # Contract specifications
        if "XAU" in pair:
            self.lot_pip_value = 10.0
        elif "IDX" in pair:
            self.lot_pip_value = 20.0
        else:
            self.lot_pip_value = 10.0  # $10/pip per 1.0 standard FX lot
            
    def run_simulation(
        self,
        df_1m: pd.DataFrame,
        df_5m: pd.DataFrame,
        df_15m: pd.DataFrame = None,
        df_1h: pd.DataFrame = None
    ) -> Dict[str, Any]:
        balance = self.starting_capital
        peak_balance = self.starting_capital
        max_dd_dollars = 0.0
        max_dd_pct = 0.0
        
        # Compute causal indicators on 5m candles
        df_5m_ind = find_swing_points(df_5m, window=5)
        df_5m_ind = find_fair_value_gaps(df_5m_ind, min_gap_pips=2.5, pip_size=self.pip_size)
        df_5m_ind = find_inverted_fvgs(df_5m_ind)
        df_5m_ind = find_liquidity_sweeps(df_5m_ind, lookback=50)
        df_5m_ind = find_order_blocks(df_5m_ind, lookback=8)
        df_5m_ind = find_breaker_blocks(df_5m_ind, lookback=30)
        df_5m_ind = find_ote_zones(df_5m_ind, lookback=30)
        df_5m_ind = tag_killzones(df_5m_ind)
        
        # HTF EMA Bias on 5m (causal 50/200 EMA)
        df_5m_ind['ema_fast'] = df_5m_ind['close'].ewm(span=50, adjust=False).mean()
        df_5m_ind['ema_slow'] = df_5m_ind['close'].ewm(span=200, adjust=False).mean()
        df_5m_ind['master_bias'] = np.where(
            (df_5m_ind['close'] > df_5m_ind['ema_fast']) & (df_5m_ind['ema_fast'] > df_5m_ind['ema_slow']), 1,
            np.where((df_5m_ind['close'] < df_5m_ind['ema_fast']) & (df_5m_ind['ema_fast'] < df_5m_ind['ema_slow']), -1, 0)
        )
        
        times_5m = list(df_5m_ind.index)
        n_5m = len(df_5m_ind)
        
        # 1m lookup index for fast execution
        times_1m = list(df_1m.index)
        t1m_to_idx = {t.strftime('%Y-%m-%d %H:%M:%S'): i for i, t in enumerate(times_1m)}
        
        highs_1m = df_1m['high'].values
        lows_1m = df_1m['low'].values
        closes_1m = df_1m['close'].values
        spread_pips_1m = df_1m['spread_pips'].values if 'spread_pips' in df_1m.columns else np.full(len(df_1m), 1.0)
        
        active_until_1m_idx = -1
        executed_trades = []
        trade_counter = 0
        raw_signals_count = 0
        
        # Sequential Event Loop over 5m candle closes
        for i in range(15, n_5m):
            t_curr = times_5m[i]
            t_curr_str = t_curr.strftime('%Y-%m-%d %H:%M:%S')
            
            if t_curr_str not in t1m_to_idx:
                continue
            entry_1m_idx = t1m_to_idx[t_curr_str]
            
            # Position Availability Check
            if entry_1m_idx <= active_until_1m_idx:
                continue
                
            # Current State Information strictly <= t_curr
            is_kz = df_5m_ind['is_london_kz'].iloc[i] or df_5m_ind['is_ny_kz'].iloc[i] or df_5m_ind['is_silver_bullet'].iloc[i]
            bias = df_5m_ind['master_bias'].iloc[i]
            if not is_kz or bias == 0:
                continue
                
            # Causal Confluence Score Evaluation
            ftype = df_5m_ind['fvg_type'].iloc[i]
            ifvg_t = df_5m_ind['ifvg_type'].iloc[i]
            ob_t = df_5m_ind['ob_type'].iloc[i]
            btype = df_5m_ind['breaker_type'].iloc[i]
            ote_t = df_5m_ind['ote_type'].iloc[i]
            
            recent_sweeps = df_5m_ind['sweep_type'].iloc[i-3:i+1]
            has_sweep = (recent_sweeps != 0).any()
            
            # Compute Confluence Points
            score = 0
            if has_sweep: score += 1
            if ftype == bias: score += 1
            if ob_t == bias: score += 1
            if btype == bias: score += 1
            if ifvg_t == bias: score += 1
            if ote_t == bias: score += 1
            if df_5m_ind['is_silver_bullet'].iloc[i]: score += 1
            
            # Entry Signal Check
            direction = None
            setup_id = 0
            setup_name = ""
            entry_price = 0.0
            sl_price = 0.0
            tp_price = 0.0
            
            # Primary Confluence Model Setups:
            if score >= self.confluence_threshold:
                if bias == 1:
                    direction = 'BUY'
                    # 50% CE FVG / OB entry
                    if ftype == 1:
                        entry_price = (df_5m_ind['fvg_top'].iloc[i] + df_5m_ind['fvg_bottom'].iloc[i]) / 2.0
                        sl_price = df_5m_ind['low'].iloc[i-3:i+1].min() - (3.5 * self.pip_size)
                    elif ob_t == 1:
                        entry_price = (df_5m_ind['ob_top'].iloc[i] + df_5m_ind['ob_bottom'].iloc[i]) / 2.0
                        sl_price = df_5m_ind['ob_bottom'].iloc[i] - (3.5 * self.pip_size)
                    else:
                        entry_price = df_5m_ind['close'].iloc[i]
                        sl_price = df_5m_ind['low'].iloc[i-3:i+1].min() - (3.5 * self.pip_size)
                        
                    risk = entry_price - sl_price
                    if risk > (2.0 * self.pip_size):
                        tp_price = entry_price + (self.target_rr * risk)
                        setup_id = 5 if (ob_t == 1 and ftype == 1) else (2 if ifvg_t == 1 else (6 if btype == 1 else 1))
                        setup_name = f"Confluence Score {score} ICT Setup"
                    else:
                        direction = None
                        
                elif bias == -1:
                    direction = 'SELL'
                    if ftype == -1:
                        entry_price = (df_5m_ind['fvg_top'].iloc[i] + df_5m_ind['fvg_bottom'].iloc[i]) / 2.0
                        sl_price = df_5m_ind['high'].iloc[i-3:i+1].max() + (3.5 * self.pip_size)
                    elif ob_t == -1:
                        entry_price = (df_5m_ind['ob_top'].iloc[i] + df_5m_ind['ob_bottom'].iloc[i]) / 2.0
                        sl_price = df_5m_ind['ob_top'].iloc[i] + (3.5 * self.pip_size)
                    else:
                        entry_price = df_5m_ind['close'].iloc[i]
                        sl_price = df_5m_ind['high'].iloc[i-3:i+1].max() + (3.5 * self.pip_size)
                        
                    risk = sl_price - entry_price
                    if risk > (2.0 * self.pip_size):
                        tp_price = entry_price - (self.target_rr * risk)
                        setup_id = 5 if (ob_t == -1 and ftype == -1) else (2 if ifvg_t == -1 else (6 if btype == -1 else 1))
                        setup_name = f"Confluence Score {score} ICT Setup"
                    else:
                        direction = None

            if direction is None:
                continue
                
            raw_signals_count += 1
            
            # Position Sizing & Bounded Lot Calculation
            risk_amount = balance * (self.risk_percent / 100.0)
            sl_distance_pips = abs(entry_price - sl_price) / self.pip_size
            
            raw_lots = risk_amount / (sl_distance_pips * self.lot_pip_value)
            stepped_lots = round(raw_lots / self.lot_step) * self.lot_step
            lot_size = max(self.min_lot, min(self.max_lot, round(stepped_lots, 2)))
            
            # Commission & Slippage
            commission_entry = (lot_size * self.commission_per_lot) / 2.0
            commission_exit = (lot_size * self.commission_per_lot) / 2.0
            total_commission = commission_entry + commission_exit
            
            entry_slippage_val = self.max_slippage_pips * self.pip_size
            exit_slippage_val = self.max_slippage_pips * self.pip_size
            
            spread_entry_pips = spread_pips_1m[entry_1m_idx]
            spread_entry_val = spread_entry_pips * self.pip_size
            
            if direction == 'BUY':
                actual_entry = entry_price + spread_entry_val + entry_slippage_val
            else:
                actual_entry = entry_price - entry_slippage_val
                
            initial_risk_dist = abs(actual_entry - sl_price)
            current_sl = sl_price
            current_tp = tp_price
            be_triggered = False
            
            # Replay 1-Minute Data Sequentially for Order Execution
            outcome = None
            exit_price = actual_entry
            exit_1m_idx = entry_1m_idx
            exit_time_str = t_curr_str
            is_ambiguous = False
            spread_exit_pips = spread_entry_pips
            
            max_lookahead_1m = min(len(df_1m), entry_1m_idx + 1440)  # max 24h simulation
            
            for k in range(entry_1m_idx + 1, max_lookahead_1m):
                curr_high = highs_1m[k]
                curr_low = lows_1m[k]
                curr_spread_pips = spread_pips_1m[k]
                curr_spread_val = curr_spread_pips * self.pip_size
                
                bid_high = curr_high
                bid_low = curr_low
                ask_high = curr_high + curr_spread_val
                ask_low = curr_low + curr_spread_val
                
                if direction == 'BUY':
                    if self.enable_breakeven and not be_triggered:
                        if bid_high >= (actual_entry + initial_risk_dist):
                            current_sl = actual_entry + (0.2 * self.pip_size)
                            be_triggered = True
                            
                    sl_hit = (bid_low <= current_sl)
                    tp_hit = (bid_high >= current_tp)
                    
                    if sl_hit and tp_hit:
                        is_ambiguous = True
                        outcome = 'BREAKEVEN' if be_triggered else 'LOSS'
                        exit_price = current_sl - exit_slippage_val
                        exit_1m_idx = k
                        exit_time_str = times_1m[k].strftime('%Y-%m-%d %H:%M:%S')
                        spread_exit_pips = curr_spread_pips
                        break
                    elif sl_hit:
                        outcome = 'BREAKEVEN' if be_triggered else 'LOSS'
                        exit_price = current_sl - exit_slippage_val
                        exit_1m_idx = k
                        exit_time_str = times_1m[k].strftime('%Y-%m-%d %H:%M:%S')
                        spread_exit_pips = curr_spread_pips
                        break
                    elif tp_hit:
                        outcome = 'WIN'
                        exit_price = current_tp
                        exit_1m_idx = k
                        exit_time_str = times_1m[k].strftime('%Y-%m-%d %H:%M:%S')
                        spread_exit_pips = curr_spread_pips
                        break
                        
                elif direction == 'SELL':
                    if self.enable_breakeven and not be_triggered:
                        if ask_low <= (actual_entry - initial_risk_dist):
                            current_sl = actual_entry - (0.2 * self.pip_size)
                            be_triggered = True
                            
                    sl_hit = (ask_high >= current_sl)
                    tp_hit = (ask_low <= current_tp)
                    
                    if sl_hit and tp_hit:
                        is_ambiguous = True
                        outcome = 'BREAKEVEN' if be_triggered else 'LOSS'
                        exit_price = current_sl + exit_slippage_val
                        exit_1m_idx = k
                        exit_time_str = times_1m[k].strftime('%Y-%m-%d %H:%M:%S')
                        spread_exit_pips = curr_spread_pips
                        break
                    elif sl_hit:
                        outcome = 'BREAKEVEN' if be_triggered else 'LOSS'
                        exit_price = current_sl + exit_slippage_val
                        exit_1m_idx = k
                        exit_time_str = times_1m[k].strftime('%Y-%m-%d %H:%M:%S')
                        spread_exit_pips = curr_spread_pips
                        break
                    elif tp_hit:
                        outcome = 'WIN'
                        exit_price = current_tp
                        exit_1m_idx = k
                        exit_time_str = times_1m[k].strftime('%Y-%m-%d %H:%M:%S')
                        spread_exit_pips = curr_spread_pips
                        break
                        
            if outcome is None:
                exit_1m_idx = max_lookahead_1m - 1
                exit_price = closes_1m[exit_1m_idx]
                exit_time_str = times_1m[exit_1m_idx].strftime('%Y-%m-%d %H:%M:%S')
                pnl_pips = (exit_price - actual_entry) / self.pip_size if direction == 'BUY' else (actual_entry - exit_price) / self.pip_size
                outcome = 'WIN' if pnl_pips > 0 else 'LOSS'
                spread_exit_pips = spread_pips_1m[exit_1m_idx]
                
            active_until_1m_idx = exit_1m_idx
            trade_counter += 1
            
            if direction == 'BUY':
                pnl_pips = (exit_price - actual_entry) / self.pip_size
            else:
                pnl_pips = (actual_entry - exit_price) / self.pip_size
                
            gross_pnl = pnl_pips * self.lot_pip_value * lot_size
            net_pnl = gross_pnl - total_commission
            
            start_bal_trade = balance
            balance += net_pnl
            if balance > peak_balance:
                peak_balance = balance
            dd_dollars = peak_balance - balance
            dd_pct = (dd_dollars / peak_balance) * 100.0 if peak_balance > 0 else 0.0
            
            if dd_dollars > max_dd_dollars: max_dd_dollars = dd_dollars
            if dd_pct > max_dd_pct: max_dd_pct = dd_pct
            
            trade_id = f"TR-{self.pair}-{t_curr_str.replace(' ', 'T').replace(':', '')}-{trade_counter:04d}"
            
            executed_trades.append({
                'trade_id': trade_id,
                'pair': self.pair,
                'setup_id': setup_id,
                'setup_name': setup_name,
                'direction': direction,
                'timestamp_entry': t_curr_str,
                'timestamp_exit': exit_time_str,
                'starting_balance': round(start_bal_trade, 2),
                'risk_amount': round(risk_amount, 2),
                'lot_size': lot_size,
                'entry_price': round(actual_entry, 5),
                'sl_price': round(sl_price, 5),
                'tp_price': round(tp_price, 5),
                'exit_price': round(exit_price, 5),
                'outcome': outcome,
                'is_breakeven': be_triggered,
                'is_ambiguous': is_ambiguous,
                'spread_entry_pips': round(spread_entry_pips, 2),
                'spread_exit_pips': round(spread_exit_pips, 2),
                'commission': round(total_commission, 2),
                'slippage_pips': self.max_slippage_pips * 2,
                'gross_pnl': round(gross_pnl, 2),
                'net_pnl': round(net_pnl, 2),
                'ending_balance': round(balance, 2)
            })
            
        winning_trades = [t for t in executed_trades if t['outcome'] == 'WIN']
        losing_trades = [t for t in executed_trades if t['outcome'] == 'LOSS']
        be_trades = [t for t in executed_trades if t['outcome'] == 'BREAKEVEN']
        
        n_dec = len(winning_trades) + len(losing_trades)
        true_wr = (len(winning_trades) / n_dec * 100.0) if n_dec > 0 else 0.0
        
        gp = sum(t['net_pnl'] for t in winning_trades)
        gl = abs(sum(t['net_pnl'] for t in losing_trades))
        pf = (gp / gl) if gl > 0 else (99.0 if gp > 0 else 0.0)
        
        return {
            'pair': self.pair,
            'confluence_threshold': self.confluence_threshold,
            'starting_capital': self.starting_capital,
            'ending_balance': round(balance, 2),
            'net_profit': round(balance - self.starting_capital, 2),
            'raw_signals': raw_signals_count,
            'total_trades': len(executed_trades),
            'wins': len(winning_trades),
            'losses': len(losing_trades),
            'breakevens': len(be_trades),
            'true_win_rate': round(true_wr, 2),
            'profit_factor': round(pf, 2),
            'max_drawdown_pct': round(max_dd_pct, 2),
            'trades': executed_trades
        }
