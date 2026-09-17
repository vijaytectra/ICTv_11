import sys
import os
import glob
import math
import pandas as pd
import numpy as np

sys.path.insert(0, r"C:\personal\ICT_v11")

from backend.engine.data_loader import load_pair_data, resample_candles, get_pip_size
from backend.engine.strategy_setups import get_all_setup_signals
from backend.engine.backtester import execute_backtest

data_dir = r"C:\Users\Vijayakumar R\Documents"
pairs = ["GBPUSD", "EURUSD", "USDJPY", "USDCAD", "AUDUSD", "USDCHF"]

print("--- AUDIT START ---", flush=True)

# 1. Quick Data Stats
data_stats = []
all_dfs_res = {}

for pair in pairs:
    bid_files = sorted(glob.glob(os.path.join(data_dir, f"{pair}_1 Min_Bid_*.csv")))
    df_raw = load_pair_data(data_dir, pair, sample_ratio=0.1)
    df_res = resample_candles(df_raw, "5m")
    all_dfs_res[pair] = df_res
    
    data_stats.append({
        'pair': pair,
        'resampled_5m': len(df_res),
        'start_date': str(df_res.index[0]),
        'end_date': str(df_res.index[-1]),
        'mean_spread': round(df_raw['spread_pips'].mean(), 2)
    })

print("DATA STATS:", flush=True)
print(pd.DataFrame(data_stats).to_string(index=False), flush=True)

all_trades = []
for pair in pairs:
    df_res = all_dfs_res[pair]
    signals = get_all_setup_signals(df_res, pair, min_rr=2.0)
    res = execute_backtest(df_res, signals, pair, starting_balance=200.0, risk_percent=1.0, max_slippage_pips=0.5, commission_per_lot=3.50)
    all_trades.extend(res['trades'])
    print(f"  {pair}: Trades={res['total_trades']}, WinRate={res['win_rate_pct']}%, NetProfit=${res['net_profit']:.2f}", flush=True)

print(f"TOTAL TRADES (0.1 sample): {len(all_trades)}", flush=True)

setup_names = {
    1: "Liquidity Sweep + FVG",
    2: "Liquidity Sweep + IFVG",
    3: "ICT Silver Bullet",
    4: "Turtle Soup (MSS + FVG)",
    5: "OB + FVG Confluence",
    6: "Unicorn (Breaker + FVG)",
    7: "Turtle Soup Reversal [REMOVED]",
    8: "OTE 70.5% Fib [REMOVED]",
    9: "Breaker Block Retest",
    10: "AMD / Power of 3"
}

def wilson_ci(k, n):
    if n == 0: return 0.0, 0.0
    z = 1.959964
    p_val = k / n
    denom = 1 + z**2 / n
    centre = (p_val + z**2 / (2 * n)) / denom
    hw = z * math.sqrt((p_val * (1 - p_val) + z**2 / (4 * n)) / n) / denom
    return round(max(0.0, centre - hw) * 100, 2), round(min(1.0, centre + hw) * 100, 2)

setup_rows = []
for s_id in range(1, 11):
    if s_id in [7, 8]: continue
    s_tr = [t for t in all_trades if t['setup_id'] == s_id]
    s_w = [t for t in s_tr if t['outcome'] == 'WIN']
    s_l = [t for t in s_tr if t['outcome'] == 'LOSS']
    wr = len(s_w) / len(s_tr) * 100.0 if s_tr else 0.0
    ci_low, ci_high = wilson_ci(len(s_w), len(s_tr))
    setup_rows.append({
        'setup_id': s_id,
        'setup_name': setup_names[s_id],
        'trades': len(s_tr),
        'wins': len(s_w),
        'losses': len(s_l),
        'breakevens': 0,
        'true_wr': round(wr, 2),
        'win_be_wr': round(wr, 2),
        '95_ci': f"{ci_low}% - {ci_high}%"
    })

print("WIN RATE TABLE:", flush=True)
print(pd.DataFrame(setup_rows).to_string(index=False), flush=True)

# Out of sample
df_tr_all = pd.DataFrame(all_trades)
df_tr_all['dt'] = pd.to_datetime(df_tr_all['timestamp_entry'])

train_df = df_tr_all[df_tr_all['dt'] < '2025-01-01']
val_df = df_tr_all[(df_tr_all['dt'] >= '2025-01-01') & (df_tr_all['dt'] < '2026-01-01')]
oos_df = df_tr_all[df_tr_all['dt'] >= '2026-01-01']

def metrics_sub(df_sub, label):
    n = len(df_sub)
    if n == 0: return {'period': label, 'trades': 0, 'wr': 0, 'pf': 0, 'net_pnl': 0}
    w = len(df_sub[df_sub['outcome'] == 'WIN'])
    wr = w / n * 100.0
    gp = df_sub[df_sub['net_pnl'] > 0]['net_pnl'].sum()
    gl = abs(df_sub[df_sub['net_pnl'] < 0]['net_pnl'].sum())
    pf = (gp / gl) if gl > 0 else 99.0
    return {'period': label, 'trades': n, 'wr': round(wr, 2), 'pf': round(pf, 2), 'net_pnl': round(df_sub['net_pnl'].sum(), 2)}

print("CHRONOLOGICAL OOS TABLE:", flush=True)
print(pd.DataFrame([
    metrics_sub(train_df, "Train (2024)"),
    metrics_sub(val_df, "Val (2025)"),
    metrics_sub(oos_df, "OOS (2026 YTD)")
]).to_string(index=False), flush=True)

# Monte Carlo 10k
np.random.seed(42)
pnls = df_tr_all['net_pnl'].values
n_sims = 10000
final_bals = []
max_dds = []

for _ in range(n_sims):
    shuff = np.random.choice(pnls, size=len(pnls), replace=True)
    b_path = 200.0 + np.cumsum(shuff)
    final_bals.append(b_path[-1])
    peak = np.maximum.accumulate(b_path)
    dd = (peak - b_path) / peak * 100.0
    max_dds.append(np.max(dd))

print("MONTE CARLO 10k RESULTS:", flush=True)
print(f"5th % Bal: ${np.percentile(final_bals, 5):,.2f}", flush=True)
print(f"50th % Bal: ${np.percentile(final_bals, 50):,.2f}", flush=True)
print(f"95th % Bal: ${np.percentile(final_bals, 95):,.2f}", flush=True)
print(f"Median Max DD: {np.median(max_dds):.2f}%", flush=True)
print(f"95th % Max DD: {np.percentile(max_dds, 95):.2f}%", flush=True)

print("--- AUDIT COMPLETE ---", flush=True)
