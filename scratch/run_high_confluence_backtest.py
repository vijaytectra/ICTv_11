import sys
import os
import glob
import math
import json
import pandas as pd
import numpy as np
from typing import List, Dict, Any

sys.path.insert(0, r"C:\personal\ICT_v11")

from backend.engine.data_loader import load_pair_data, resample_candles, get_pip_size
from backend.engine.ict_indicators import (
    find_swing_points, find_htf_structure_and_bias, find_institutional_liquidity_pools,
    find_displacement_and_expansion, find_premium_discount_zones,
    find_fair_value_gaps, find_inverted_fvgs, find_liquidity_sweeps,
    find_order_blocks, find_breaker_blocks, find_ote_zones, tag_killzones
)
from backend.engine.backtester import execute_backtest

data_dir = r"C:\Users\Vijayakumar R\Documents"
pairs = ["GBPUSD", "EURUSD", "USDJPY", "USDCAD", "AUDUSD", "USDCHF"]

print("==========================================================================", flush=True)
print("     HIGH-CONFLUENCE ICT 80%+ WIN RATE MULTI-PERIOD BACKTEST ENGINE       ", flush=True)
print("==========================================================================", flush=True)

def run_calibrated_indicators(df: pd.DataFrame, pair: str) -> pd.DataFrame:
    pip_size = get_pip_size(pair)
    df = find_swing_points(df, window=5)
    df = find_htf_structure_and_bias(df)
    df = find_institutional_liquidity_pools(df, pip_size=pip_size)
    df = find_displacement_and_expansion(df, atr_period=20)
    df = find_premium_discount_zones(df, lookback=40)
    df = find_fair_value_gaps(df, min_gap_pips=1.8, pip_size=pip_size)
    df = find_inverted_fvgs(df)
    df = find_liquidity_sweeps(df, lookback=40)
    df = find_order_blocks(df, lookback=8)
    df = find_breaker_blocks(df, lookback=30)
    df = find_ote_zones(df, lookback=30)
    df = tag_killzones(df)
    
    # 50/200 EMA
    df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
    ema_trend = np.where((df['close'] > df['ema_50']) & (df['ema_50'] > df['ema_200']), 1,
                         np.where((df['close'] < df['ema_50']) & (df['ema_50'] < df['ema_200']), -1, 0))
                         
    df['master_bias'] = np.where(df['htf_bias'] != 0, df['htf_bias'], ema_trend)
    return df

def generate_calibrated_signals(df: pd.DataFrame, pair: str, min_rr: float = 2.0) -> List[Dict[str, Any]]:
    pip_size = get_pip_size(pair)
    signals = []
    
    # All active trading sessions (London KZ, NY KZ, Asian KZ, Silver Bullet)
    kz_mask = df['is_london_kz'] | df['is_ny_kz'] | df['is_silver_bullet'] | df['is_asian_range']
    kz_indices = np.where(kz_mask)[0]
    kz_indices = kz_indices[kz_indices >= 5]
    
    for i in kz_indices:
        bias = df['master_bias'].iloc[i]
        if bias == 0: continue
        
        # Check sweep within last 10 candles
        recent_sweeps = df['sweep_type'].iloc[max(0, i-10):i+1]
        has_sweep = not (recent_sweeps == 0).all()
        if not has_sweep: continue
        
        last_sweep_idx = recent_sweeps[recent_sweeps != 0].index[-1]
        sweep_dir = df.loc[last_sweep_idx, 'sweep_type']
        
        is_disc = df['is_discount'].iloc[i]
        is_prem = df['is_premium'].iloc[i]
        
        ftype = df['fvg_type'].iloc[i]
        ifvg_t = df['ifvg_type'].iloc[i] if 'ifvg_type' in df.columns else 0
        ob_t = df['ob_type'].iloc[i] if 'ob_type' in df.columns else 0
        brk_t = df['breaker_type'].iloc[i] if 'breaker_type' in df.columns else 0
        ote_t = df['ote_type'].iloc[i] if 'ote_type' in df.columns else 0
        has_disp = df['has_displacement'].iloc[i]
        
        # --- BUY SIGNALS ---
        if bias == 1 and sweep_dir == 1 and is_disc:
            # Check setup confluence
            s_id = 0
            s_name = ""
            if brk_t == 1 and ftype == 1:
                s_id, s_name = 6, "Unicorn (Breaker + FVG)"
            elif ob_t == 1 and ftype == 1:
                s_id, s_name = 5, "OB + FVG Confluence"
            elif ifvg_t == 1:
                s_id, s_name = 2, "Liquidity Sweep + IFVG"
            elif brk_t == 1:
                s_id, s_name = 9, "Breaker Block Retest"
            elif ftype == 1 and has_disp:
                s_id, s_name = 1, "Liquidity Sweep + FVG"
            elif ote_t == 1:
                s_id, s_name = 4, "Turtle Soup (MSS + FVG)"
            elif df['is_silver_bullet'].iloc[i] and ftype == 1:
                s_id, s_name = 3, "ICT Silver Bullet"
            elif df['is_asian_range'].iloc[i] and ftype == 1:
                s_id, s_name = 10, "AMD / Power of 3"
                
            if s_id > 0:
                fvg_b = df['fvg_bottom'].iloc[i] if ftype == 1 else df['close'].iloc[i] - (3.0 * pip_size)
                fvg_t_val = df['fvg_top'].iloc[i] if ftype == 1 else df['close'].iloc[i]
                entry = (fvg_t_val + fvg_b) / 2.0
                sl = df['low'].iloc[max(0, i-4):i+1].min() - (2.0 * pip_size)
                risk = entry - sl
                if (2.0 * pip_size) <= risk <= (30.0 * pip_size):
                    tp = entry + (min_rr * risk)
                    signals.append({
                        'timestamp': df.index[i].strftime('%Y-%m-%d %H:%M:%S'),
                        'pair': pair,
                        'setup_id': s_id,
                        'setup_name': s_name,
                        'direction': 'BUY',
                        'entry': round(entry, 5),
                        'sl': round(sl, 5),
                        'tp': round(tp, 5),
                        'rr': min_rr,
                        'sl_pips': round(risk / pip_size, 1),
                        'spread_pips': round(df['spread_pips'].iloc[i], 1)
                    })
                    
        # --- SELL SIGNALS ---
        elif bias == -1 and sweep_dir == -1 and is_prem:
            s_id = 0
            s_name = ""
            if brk_t == -1 and ftype == -1:
                s_id, s_name = 6, "Unicorn (Breaker + FVG)"
            elif ob_t == -1 and ftype == -1:
                s_id, s_name = 5, "OB + FVG Confluence"
            elif ifvg_t == -1:
                s_id, s_name = 2, "Liquidity Sweep + IFVG"
            elif brk_t == -1:
                s_id, s_name = 9, "Breaker Block Retest"
            elif ftype == -1 and has_disp:
                s_id, s_name = 1, "Liquidity Sweep + FVG"
            elif ote_t == -1:
                s_id, s_name = 4, "Turtle Soup (MSS + FVG)"
            elif df['is_silver_bullet'].iloc[i] and ftype == -1:
                s_id, s_name = 3, "ICT Silver Bullet"
            elif df['is_asian_range'].iloc[i] and ftype == -1:
                s_id, s_name = 10, "AMD / Power of 3"
                
            if s_id > 0:
                fvg_t_val = df['fvg_top'].iloc[i] if ftype == -1 else df['close'].iloc[i] + (3.0 * pip_size)
                fvg_b = df['fvg_bottom'].iloc[i] if ftype == -1 else df['close'].iloc[i]
                entry = (fvg_t_val + fvg_b) / 2.0
                sl = df['high'].iloc[max(0, i-4):i+1].max() + (2.0 * pip_size)
                risk = sl - entry
                if (2.0 * pip_size) <= risk <= (30.0 * pip_size):
                    tp = entry - (min_rr * risk)
                    signals.append({
                        'timestamp': df.index[i].strftime('%Y-%m-%d %H:%M:%S'),
                        'pair': pair,
                        'setup_id': s_id,
                        'setup_name': s_name,
                        'direction': 'SELL',
                        'entry': round(entry, 5),
                        'sl': round(sl, 5),
                        'tp': round(tp, 5),
                        'rr': min_rr,
                        'sl_pips': round(risk / pip_size, 1),
                        'spread_pips': round(df['spread_pips'].iloc[i], 1)
                    })
                    
    return signals

def run_calibrated_audit():
    all_trades = []
    print("\n[+] Loading Data and Running Calibrated Signals for 6 Major Pairs...", flush=True)
    
    for pair in pairs:
        print(f"  Processing {pair}...", flush=True)
        df_raw = load_pair_data(data_dir, pair, sample_ratio=0.3)
        df_res = resample_candles(df_raw, "5m")
        df_res = run_calibrated_indicators(df_res, pair)
        signals = generate_calibrated_signals(df_res, pair, min_rr=2.0)
        
        res = execute_backtest(
            df_res,
            signals,
            pair,
            starting_balance=200.0,
            risk_percent=1.0,
            max_slippage_pips=0.5,
            commission_per_lot=3.50
        )
        all_trades.extend(res['trades'])
        print(f"    -> {pair}: Signals={len(signals)} | Executed Trades={res['total_trades']} | Win Rate={res.get('win_rate_pct', 0.0)}%", flush=True)
        
    df_trades = pd.DataFrame(all_trades)
    if len(df_trades) == 0:
        print("No trades executed.", flush=True)
        return
        
    df_trades['dt'] = pd.to_datetime(df_trades['timestamp_entry'])
    
    train_trades = df_trades[df_trades['dt'] < '2025-01-01']
    val_trades = df_trades[(df_trades['dt'] >= '2025-01-01') & (df_trades['dt'] < '2026-01-01')]
    oos_trades = df_trades[df_trades['dt'] >= '2026-01-01']
    
    def get_period_stats(df_sub, label, total_weeks):
        n = len(df_sub)
        if n == 0:
            return {'Period': label, 'Trades': 0, 'Win Rate %': '0.0%', 'Profit Factor': 0.0, 'Net PnL ($)': '$0.00', 'Trades/Wk': 0.0}
        wins = len(df_sub[df_sub['outcome'] == 'WIN'])
        losses = len(df_sub[df_sub['outcome'] == 'LOSS'])
        wr = (wins / n) * 100.0
        
        gp = df_sub[df_sub['net_pnl'] > 0]['net_pnl'].sum()
        gl = abs(df_sub[df_sub['net_pnl'] < 0]['net_pnl'].sum())
        pf = (gp / gl) if gl > 0 else 99.0
        pnl = df_sub['net_pnl'].sum()
        tpw = n / max(1, total_weeks)
        
        return {
            'Period': label,
            'Trades': n,
            'Wins': wins,
            'Losses': losses,
            'True Win Rate %': f"{wr:.2f}%",
            'Profit Factor': f"{pf:.2f}",
            'Net PnL ($)': f"${pnl:+.2f}",
            'Trades/Wk': f"{tpw:.1f}"
        }
        
    p_train = get_period_stats(train_trades, "Train (2024.01.02 - 2024.12.31)", 52)
    p_val = get_period_stats(val_trades, "Validation (2025.01.01 - 2025.12.31)", 52)
    p_oos = get_period_stats(oos_trades, "Final OOS (2026.01.01 - 2026.09.17)", 37)
    
    summary_df = pd.DataFrame([p_train, p_val, p_oos])
    
    print("\n==========================================================================", flush=True)
    print("      CHRONOLOGICAL TRAIN / VALIDATION / OUT-OF-SAMPLE AUDIT TABLE       ", flush=True)
    print("==========================================================================", flush=True)
    print(summary_df.to_string(index=False), flush=True)
    
    # Setup breakdown
    print("\n----------------------------------------------------------------------------------------", flush=True)
    print("Setup #  Setup Name                                    Trades   Win Rate %   Net PnL ($)", flush=True)
    print("----------------------------------------------------------------------------------------", flush=True)
    
    setup_names = {
        1: "Liquidity Sweep + FVG",
        2: "Liquidity Sweep + IFVG",
        3: "ICT Silver Bullet",
        4: "Turtle Soup (MSS + FVG)",
        5: "OB + FVG Confluence",
        6: "Unicorn (Breaker + FVG)",
        9: "Breaker Block Retest",
        10: "AMD / Power of 3"
    }
    
    for s_id in [1, 2, 3, 4, 5, 6, 9, 10]:
        s_tr = [t for t in all_trades if t['setup_id'] == s_id]
        s_w = [t for t in s_tr if t['outcome'] == 'WIN']
        wr = (len(s_w) / len(s_tr) * 100.0) if s_tr else 0.0
        pnl = sum(t['net_pnl'] for t in s_tr)
        print(f"  #{s_id:<2}   {setup_names[s_id]:<42} {len(s_tr):<8} {wr:>8.1f}%   ${pnl:>10.2f}", flush=True)
        
    print("================================================================------------------------\n", flush=True)

if __name__ == "__main__":
    run_calibrated_audit()
