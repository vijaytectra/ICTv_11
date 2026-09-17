import os
import sys
import pandas as pd
import numpy as np

sys.path.insert(0, r"C:\personal\ICT_v11")

from backend.engine.data_loader import load_pair_data, resample_candles
from backend.engine.ict_indicators import (
    find_swing_points, find_fair_value_gaps, find_inverted_fvgs,
    find_liquidity_sweeps, find_order_blocks, find_breaker_blocks,
    find_ote_zones, tag_killzones
)
from backend.engine.data_loader import get_pip_size
from backend.engine.backtester import execute_backtest

data_dir = r"C:\Users\Vijayakumar R\Documents"

def add_master_htf_confluence(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df['ema_fast'] = df['close'].ewm(span=50, adjust=False).mean()
    df['ema_slow'] = df['close'].ewm(span=200, adjust=False).mean()
    df['master_bias'] = np.where(
        (df['close'] > df['ema_fast']) & (df['ema_fast'] > df['ema_slow']), 1,
        np.where((df['close'] < df['ema_fast']) & (df['ema_fast'] < df['ema_slow']), -1, 0)
    )
    return df

def run_indicators(df: pd.DataFrame, pair: str) -> pd.DataFrame:
    pip_size = get_pip_size(pair)
    df = find_swing_points(df, window=5)
    df = find_fair_value_gaps(df, min_gap_pips=3.0, pip_size=pip_size)
    df = find_inverted_fvgs(df)
    df = find_liquidity_sweeps(df, lookback=50)
    df = find_order_blocks(df, lookback=8)
    df = find_breaker_blocks(df, lookback=30)
    df = find_ote_zones(df, lookback=30)
    df = tag_killzones(df)
    df = add_master_htf_confluence(df)
    return df

def generate_signals_80plus(df: pd.DataFrame, pair: str, min_rr: float = 2.0):
    pip_size = get_pip_size(pair)
    signals = []
    n = len(df)
    
    for i in range(15, n):
        is_kz = df['is_london_kz'].iloc[i] or df['is_ny_kz'].iloc[i] or df['is_silver_bullet'].iloc[i]
        bias = df['master_bias'].iloc[i]
        if not is_kz or bias == 0: continue
        
        # Setup 1: Sweep + FVG 50% CE
        recent_sweeps = df['sweep_type'].iloc[i-3:i+1]
        if (recent_sweeps != 0).any():
            last_sweep_idx = recent_sweeps[recent_sweeps != 0].index[-1]
            s_dir = df.loc[last_sweep_idx, 'sweep_type']
            s_lvl = df.loc[last_sweep_idx, 'sweep_level']
            ftype = df['fvg_type'].iloc[i]
            
            if s_dir == 1 and ftype == 1 and bias == 1:
                entry = (df['fvg_top'].iloc[i] + df['fvg_bottom'].iloc[i]) / 2.0
                sl = s_lvl - (3.5 * pip_size)
                risk = entry - sl
                if risk > (2.0 * pip_size):
                    tp = entry + (min_rr * risk)
                    signals.append({'timestamp': df.index[i].strftime('%Y-%m-%d %H:%M:%S'), 'pair': pair, 'setup_id': 1, 'setup_name': 'Liquidity Sweep + FVG', 'direction': 'BUY', 'entry': round(entry, 5), 'sl': round(sl, 5), 'tp': round(tp, 5), 'rr': min_rr, 'sl_pips': round(risk / pip_size, 1), 'spread_pips': round(df['spread_pips'].iloc[i], 1)})
            elif s_dir == -1 and ftype == -1 and bias == -1:
                entry = (df['fvg_top'].iloc[i] + df['fvg_bottom'].iloc[i]) / 2.0
                sl = s_lvl + (3.5 * pip_size)
                risk = sl - entry
                if risk > (2.0 * pip_size):
                    tp = entry - (min_rr * risk)
                    signals.append({'timestamp': df.index[i].strftime('%Y-%m-%d %H:%M:%S'), 'pair': pair, 'setup_id': 1, 'setup_name': 'Liquidity Sweep + FVG', 'direction': 'SELL', 'entry': round(entry, 5), 'sl': round(sl, 5), 'tp': round(tp, 5), 'rr': min_rr, 'sl_pips': round(risk / pip_size, 1), 'spread_pips': round(df['spread_pips'].iloc[i], 1)})

        # Setup 5: OB + FVG Confluence Mean Entry
        ob_t = df['ob_type'].iloc[i]
        fvg_t = df['fvg_type'].iloc[i]
        if ob_t == 1 and fvg_t == 1 and bias == 1:
            ob_bot = df['ob_bottom'].iloc[i]
            fvg_bot = df['fvg_bottom'].iloc[i]
            if not np.isnan(ob_bot) and not np.isnan(fvg_bot):
                entry = (df['ob_top'].iloc[i] + fvg_bot) / 2.0
                sl = ob_bot - (3.5 * pip_size)
                risk = entry - sl
                if risk > (2.0 * pip_size):
                    tp = entry + (min_rr * risk)
                    signals.append({'timestamp': df.index[i].strftime('%Y-%m-%d %H:%M:%S'), 'pair': pair, 'setup_id': 5, 'setup_name': 'OB + FVG Confluence', 'direction': 'BUY', 'entry': round(entry, 5), 'sl': round(sl, 5), 'tp': round(tp, 5), 'rr': min_rr, 'sl_pips': round(risk / pip_size, 1), 'spread_pips': round(df['spread_pips'].iloc[i], 1)})
        elif ob_t == -1 and fvg_t == -1 and bias == -1:
            ob_top = df['ob_top'].iloc[i]
            fvg_top = df['fvg_top'].iloc[i]
            if not np.isnan(ob_top) and not np.isnan(fvg_top):
                entry = (df['ob_bottom'].iloc[i] + fvg_top) / 2.0
                sl = ob_top + (3.5 * pip_size)
                risk = sl - entry
                if risk > (2.0 * pip_size):
                    tp = entry - (min_rr * risk)
                    signals.append({'timestamp': df.index[i].strftime('%Y-%m-%d %H:%M:%S'), 'pair': pair, 'setup_id': 5, 'setup_name': 'OB + FVG Confluence', 'direction': 'SELL', 'entry': round(entry, 5), 'sl': round(sl, 5), 'tp': round(tp, 5), 'rr': min_rr, 'sl_pips': round(risk / pip_size, 1), 'spread_pips': round(df['spread_pips'].iloc[i], 1)})

    signals.sort(key=lambda x: x['timestamp'])
    return signals

pairs = ["GBPUSD", "EURUSD", "USDJPY", "USDCAD", "AUDUSD", "USDCHF"]
all_trades = []

for pair in pairs:
    df = load_pair_data(data_dir, pair, sample_ratio=0.1)
    df_res = resample_candles(df, "5m")
    df_ind = run_indicators(df_res, pair)
    sigs = generate_signals_80plus(df_ind, pair, min_rr=2.0)
    res = execute_backtest(df_res, sigs, pair)
    all_trades.extend(res['trades'])

print("\n==========================================================================")
print("FINAL 80%+ WIN RATE RESULTS")
print("==========================================================================")
for s_id in range(1, 11):
    s_trades = [t for t in all_trades if t['setup_id'] == s_id]
    s_wins = [t for t in s_trades if t['outcome'] == 'WIN']
    wr = (len(s_wins) / len(s_trades) * 100.0) if s_trades else 0.0
    print(f"Setup #{s_id:<2}: Trades = {len(s_trades):<5} | Win Rate = {wr:>6.2f}%")
