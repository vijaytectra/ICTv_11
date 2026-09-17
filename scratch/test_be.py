import os
import sys
import pandas as pd
import numpy as np

sys.path.insert(0, r"C:\personal\ICT_v11")

from backend.engine.data_loader import load_pair_data, resample_candles
from backend.engine.strategy_setups import get_all_setup_signals
from backend.engine.data_loader import get_pip_size

data_dir = r"C:\Users\Vijayakumar R\Documents"

def execute_backtest_with_be(
    df: pd.DataFrame,
    signals: list,
    pair: str,
    starting_balance: float = 200.0,
    risk_percent: float = 1.0,
    min_rr: float = 2.0
):
    pip_size = get_pip_size(pair)
    balance = starting_balance
    trades = []
    
    for sig in signals:
        sig_time = sig['timestamp']
        idx_list = df.index[df.index >= sig_time]
        if len(idx_list) == 0: continue
        
        start_idx = df.index.get_loc(idx_list[0])
        direction = sig['direction']
        entry = sig['entry']
        sl = sig['sl']
        risk = abs(entry - sl)
        if risk == 0: continue
        tp = entry + (min_rr * risk) if direction == 'BUY' else entry - (min_rr * risk)
        be_trigger = entry + (1.0 * risk) if direction == 'BUY' else entry - (1.0 * risk)
        
        outcome = 'LOSS'
        exit_time = df.index[-1].strftime('%Y-%m-%d %H:%M:%S')
        sl_current = sl
        
        for i in range(start_idx, len(df)):
            high = df['high'].iloc[i]
            low = df['low'].iloc[i]
            t = df.index[i].strftime('%Y-%m-%d %H:%M:%S')
            
            if direction == 'BUY':
                if high >= be_trigger:
                    sl_current = max(sl_current, entry + (0.2 * pip_size))
                if low <= sl_current:
                    outcome = 'BE' if sl_current > sl else 'LOSS'
                    exit_time = t
                    break
                if high >= tp:
                    outcome = 'WIN'
                    exit_time = t
                    break
            else:
                if low <= be_trigger:
                    sl_current = min(sl_current, entry - (0.2 * pip_size))
                if high >= sl_current:
                    outcome = 'BE' if sl_current < sl else 'LOSS'
                    exit_time = t
                    break
                if low <= tp:
                    outcome = 'WIN'
                    exit_time = t
                    break
                    
        trades.append({'setup_id': sig['setup_id'], 'outcome': outcome})
        
    return trades

pairs = ["GBPUSD", "EURUSD", "USDJPY", "USDCAD", "AUDUSD", "USDCHF"]
all_trades = []

for pair in pairs:
    df = load_pair_data(data_dir, pair, sample_ratio=0.1)
    df_res = resample_candles(df, "5m")
    sigs = get_all_setup_signals(df_res, pair, min_rr=2.0)
    trades = execute_backtest_with_be(df_res, sigs, pair)
    all_trades.extend(trades)

print("\n==========================================================================")
print("ALL 10 ICT SETUPS BREAKEVEN TRAILING SL RESULTS (WIN + BE / TOTAL)")
print("==========================================================================")
setup_names = {
    1: "Liquidity Sweep + FVG",
    2: "Liquidity Sweep + IFVG",
    3: "ICT Silver Bullet",
    4: "Turtle Soup / Reversal",
    5: "OB + FVG Confluence",
    6: "Unicorn (Breaker + FVG)",
    7: "Turtle Soup (MSS + FVG)",
    8: "OTE (61.8%-78.6% Fib)",
    9: "Breaker Block Retest",
    10: "AMD / Power of 3"
}

for s_id in range(1, 11):
    s_trades = [t for t in all_trades if t['setup_id'] == s_id]
    s_wins = [t for t in s_trades if t['outcome'] in ['WIN', 'BE']]
    wr = (len(s_wins) / len(s_trades) * 100.0) if s_trades else 0.0
    print(f"Setup #{s_id:<2} ({setup_names[s_id]:<30}): Trades = {len(s_trades):<5} | Win Rate = {wr:>6.2f}%")
