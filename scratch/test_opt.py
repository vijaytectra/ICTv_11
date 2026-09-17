import os
import sys
import pandas as pd
import numpy as np

sys.path.insert(0, r"C:\personal\ICT_v11")

from backend.engine.data_loader import load_pair_data, resample_candles
from backend.engine.strategy_setups import get_all_setup_signals
from backend.engine.backtester import execute_backtest

data_dir = r"C:\Users\Vijayakumar R\Documents"

pairs = ["GBPUSD", "EURUSD", "USDJPY", "USDCAD", "AUDUSD", "USDCHF"]

all_trades = []

for pair in pairs:
    try:
        df = load_pair_data(data_dir, pair, sample_ratio=0.1)
        df_res = resample_candles(df, "5m")
        sigs = get_all_setup_signals(df_res, pair, min_rr=2.0)
        res = execute_backtest(df_res, sigs, pair)
        all_trades.extend(res['trades'])
        print(f"[{pair}] Signals: {len(sigs)} | Trades: {res['total_trades']} | Win Rate: {res['win_rate_pct']}%")
    except Exception as e:
        print(f"Error {pair}: {e}")

print("\n==========================================================================")
print("SETUP-BY-SETUP WIN RATE BREAKDOWN")
print("==========================================================================")
for s_id in range(1, 11):
    s_trades = [t for t in all_trades if t['setup_id'] == s_id]
    s_wins = [t for t in s_trades if t['outcome'] == 'WIN']
    wr = (len(s_wins) / len(s_trades) * 100.0) if s_trades else 0.0
    print(f"Setup #{s_id:<2}: Trades = {len(s_trades):<5} | Win Rate = {wr:>6.2f}%")
