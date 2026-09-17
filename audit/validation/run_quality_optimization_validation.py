import sys
import os
import glob
import math
import json
import hashlib
import pandas as pd
import numpy as np

sys.path.insert(0, r"C:\personal\ICT_v11")

from backend.engine.data_loader import load_pair_data, resample_candles, get_pip_size
from backend.engine.strategy_setups import get_all_setup_signals
from backend.engine.backtester import execute_backtest

# Load frozen config
config_path = r"C:\personal\ICT_v11\config\strategy_config_frozen.json"
with open(config_path, "r") as f:
    frozen_cfg = json.load(f)

cfg_bytes = open(config_path, "rb").read()
config_hash = hashlib.sha256(cfg_bytes).hexdigest()

data_dir = r"C:\Users\Vijayakumar R\Documents"
pairs = ["GBPUSD", "EURUSD", "USDJPY", "USDCAD", "AUDUSD", "USDCHF"]

print("==========================================================================")
print("     INSTITUTIONAL ICT QUALITY-OVER-QUANTITY OPTIMIZATION SUITE           ")
print("==========================================================================")
print(f"Config SHA-256:       {config_hash}")
print(f"Pairs Monitored:       {', '.join(pairs)}")
print(f"Starting Capital:     ${frozen_cfg['starting_capital']:.2f}")
print(f"Target RR:            1:{frozen_cfg['target_rr']:.1f}")
print("==========================================================================")

all_trades = []
raw_signals_count = 0
pair_results = {}

for pair in pairs:
    print(f"[+] Loading 1m data & computing institutional indicators for {pair}...")
    df_raw = load_pair_data(data_dir, pair, sample_ratio=0.25) # 0.25 ratio for fast execution (~150k candles)
    df_5m = resample_candles(df_raw, "5m")
    
    signals = get_all_setup_signals(df_5m, pair, min_rr=frozen_cfg['target_rr'])
    raw_signals_count += len(signals)
    
    res = execute_backtest(
        df_5m,
        signals,
        pair,
        starting_balance=frozen_cfg['starting_capital'],
        risk_percent=frozen_cfg['risk_percent'],
        max_slippage_pips=frozen_cfg['max_slippage_pips'],
        commission_per_lot=frozen_cfg['commission_per_lot'],
        min_lot=frozen_cfg['broker_limits']['min_lot'],
        max_lot=frozen_cfg['broker_limits']['max_lot'],
        lot_step=frozen_cfg['broker_limits']['lot_step'],
        enable_breakeven=frozen_cfg['breakeven_rules']['enabled']
    )
    
    pair_results[pair] = res
    all_trades.extend(res['trades'])

print(f"\nRaw Signals Generated:     {raw_signals_count}")
print(f"Executed Portfolio Trades: {len(all_trades)}")

df_trades = pd.DataFrame(all_trades)
df_trades['dt'] = pd.to_datetime(df_trades['timestamp_entry'])

# Save trade log
trade_log_path = r"C:\personal\ICT_v11\audit\trade_logs\quality_optimization_executed_trades.csv"
df_trades.to_csv(trade_log_path, index=False)

def wilson_ci(k, n):
    if n == 0: return 0.0, 0.0
    z = 1.959964
    p_val = k / n
    denom = 1 + z**2 / n
    centre = (p_val + z**2 / (2 * n)) / denom
    hw = z * math.sqrt((p_val * (1 - p_val) + z**2 / (4 * n)) / n) / denom
    return round(max(0.0, centre - hw) * 100, 2), round(min(1.0, centre + hw) * 100, 2)

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

# Calculate Weekly Trade Metrics
if len(df_trades) > 0:
    min_date = df_trades['dt'].min()
    max_date = df_trades['dt'].max()
    num_weeks = max(1.0, (max_date - min_date).days / 7.0)
    
    df_trades['week_idx'] = df_trades['dt'].dt.to_period('W')
    weekly_counts = df_trades.groupby('week_idx').size()
    
    avg_trades_week = len(df_trades) / num_weeks
    med_trades_week = float(weekly_counts.median())
    p10_trades_week = float(np.percentile(weekly_counts, 10))
    p25_trades_week = float(np.percentile(weekly_counts, 25))
    p75_trades_week = float(np.percentile(weekly_counts, 75))
    p90_trades_week = float(np.percentile(weekly_counts, 90))
    min_trades_week = int(weekly_counts.min())
    max_trades_week = int(weekly_counts.max())
    
    weeks_ge_10 = (weekly_counts >= 10).sum() / len(weekly_counts) * 100.0
    weeks_ge_12 = (weekly_counts >= 12).sum() / len(weekly_counts) * 100.0
else:
    num_weeks = 1.0
    avg_trades_week = med_trades_week = p10_trades_week = p25_trades_week = p75_trades_week = p90_trades_week = 0.0
    min_trades_week = max_trades_week = 0
    weeks_ge_10 = weeks_ge_12 = 0.0

# Setup Level Evaluation
setup_stats = []
active_setups = []
watchlist_setups = []
rejected_setups = []

for s_id in [1, 2, 3, 4, 5, 6, 9, 10]:
    s_tr = [t for t in all_trades if t['setup_id'] == s_id]
    s_w = [t for t in s_tr if t['outcome'] == 'WIN']
    s_l = [t for t in s_tr if t['outcome'] == 'LOSS']
    s_be = [t for t in s_tr if t['outcome'] == 'BREAKEVEN']
    
    n_decisive = len(s_w) + len(s_l)
    true_wr = (len(s_w) / n_decisive * 100.0) if n_decisive > 0 else 0.0
    be_rate = (len(s_be) / len(s_tr) * 100.0) if s_tr else 0.0
    
    ci_low, ci_high = wilson_ci(len(s_w), n_decisive)
    
    gp = sum(t['net_pnl'] for t in s_w)
    gl = abs(sum(t['net_pnl'] for t in s_l))
    pf = (gp / gl) if gl > 0 else (99.0 if gp > 0 else 0.0)
    
    avg_pnl = sum(t['net_pnl'] for t in s_tr) / len(s_tr) if s_tr else 0.0
    s_tr_week = len(s_tr) / num_weeks
    
    # Classification Gate
    if true_wr >= 80.0 and len(s_tr) >= 100 and pf > 1.0:
        status = "ACTIVE"
        active_setups.append(s_id)
    elif true_wr >= 70.0 or (true_wr >= 80.0 and len(s_tr) < 100):
        status = "WATCHLIST (Low Sample or Sub-80%)"
        watchlist_setups.append(s_id)
    else:
        status = "REJECTED (Fails WR Target)"
        rejected_setups.append(s_id)
        
    setup_stats.append({
        'setup_id': s_id,
        'setup_name': setup_names[s_id],
        'trades': len(s_tr),
        'wins': len(s_w),
        'losses': len(s_l),
        'breakevens': len(s_be),
        'true_win_rate': round(true_wr, 2),
        '95_ci': f"{ci_low}% - {ci_high}%",
        'actual_rr': "1:2.0",
        'profit_factor': round(pf, 2),
        'expectancy_usd': round(avg_pnl, 2),
        'trades_week': round(s_tr_week, 2),
        'status': status
    })

df_setup_table = pd.DataFrame(setup_stats)
print("\n--- INSTITUTIONAL SETUP PERFORMANCE LEDGER ---")
print(df_setup_table.to_string(index=False))

# Chronological Split (Train 2024, Validation 2025, Final OOS 2026)
train_df = df_trades[df_trades['dt'] < '2025-01-01']
val_df = df_trades[(df_trades['dt'] >= '2025-01-01') & (df_trades['dt'] < '2026-01-01')]
oos_df = df_trades[df_trades['dt'] >= '2026-01-01']

def subset_metrics(df_sub, label):
    n = len(df_sub)
    if n == 0: return {'period': label, 'trades': 0, 'true_wr': 0, 'be_rate': 0, 'pf': 0, 'expectancy': 0, 'net_pnl': 0, 'status': 'No Trades'}
    w = len(df_sub[df_sub['outcome'] == 'WIN'])
    l = len(df_sub[df_sub['outcome'] == 'LOSS'])
    be = len(df_sub[df_sub['outcome'] == 'BREAKEVEN'])
    n_dec = w + l
    t_wr = (w / n_dec * 100.0) if n_dec > 0 else 0.0
    gp = sum(df_sub[df_sub['outcome'] == 'WIN']['net_pnl'])
    gl = abs(sum(df_sub[df_sub['outcome'] == 'LOSS']['net_pnl']))
    pf = (gp / gl) if gl > 0 else 99.0
    exp = df_sub['net_pnl'].sum() / n
    net = df_sub['net_pnl'].sum()
    st = "PASS (>= 80% WR)" if t_wr >= 80.0 else "TARGET NOT MET (< 80% WR)"
    return {'period': label, 'trades': n, 'true_wr': round(t_wr, 2), 'be_rate': round(be/n*100, 2), 'pf': round(pf, 2), 'expectancy': round(exp, 2), 'net_pnl': round(net, 2), 'status': st}

print("\n--- CHRONOLOGICAL OUT-OF-SAMPLE SPLIT PERFORMANCE ---")
split_stats = [
    subset_metrics(train_df, "Train (2024)"),
    subset_metrics(val_df, "Validation (2025)"),
    subset_metrics(oos_df, "Final OOS (2026 YTD)")
]
print(pd.DataFrame(split_stats).to_string(index=False))

print("\n--- WEEKLY TRADE FREQUENCY METRICS ---")
print(f"Average Trades / Week:    {avg_trades_week:.2f}")
print(f"Median Trades / Week:     {med_trades_week:.2f}")
print(f"P10 Trades / Week:        {p10_trades_week:.2f}")
print(f"P25 Trades / Week:        {p25_trades_week:.2f}")
print(f"P75 Trades / Week:        {p75_trades_week:.2f}")
print(f"P90 Trades / Week:        {p90_trades_week:.2f}")
print(f"Min Trades / Week:        {min_trades_week}")
print(f"Max Trades / Week:        {max_trades_week}")
print(f"% Weeks >= 10 Trades:     {weeks_ge_10:.2f}%")
print(f"% Weeks >= 12 Trades:     {weeks_ge_12:.2f}%")

print("\n--- FINAL ACCEPTANCE GATE CHECK ---")
print(f"Number of Active Setups (WR >= 80%, N >= 100):    {len(active_setups)}")
print(f"Number of Watchlist Setups:                      {len(watchlist_setups)}")
print(f"Number of Rejected Setups:                       {len(rejected_setups)}")

final_pass = (
    len(active_setups) > 0 and
    (oos_df['outcome'].value_counts().get('WIN', 0) / max(1, (oos_df['outcome'].value_counts().get('WIN', 0) + oos_df['outcome'].value_counts().get('LOSS', 0)))) * 100.0 >= 80.0 and
    avg_trades_week >= 10.0
)

print(f"\nFINAL PORTFOLIO QUALITY VERDICT: {'PASS' if final_pass else 'FAIL'}")
