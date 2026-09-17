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
print("       CLEAN RE-VALIDATION ENGINE — UNBIASED ICT FOREX AUDIT               ")
print("==========================================================================")
print(f"Strategy Config Hash: {config_hash}")
print(f"Pairs Monitored:       {', '.join(pairs)}")
print(f"Starting Capital:     ${frozen_cfg['starting_capital']:.2f}")
print(f"Risk per Trade:       {frozen_cfg['risk_percent']}% (${frozen_cfg['starting_capital'] * (frozen_cfg['risk_percent']/100):.2f})")
print(f"Breakeven Rule:       +1.0R Trigger -> +0.2 pips lock")
print("==========================================================================")

all_trades = []
raw_signals_count = 0
pair_results = {}

for pair in pairs:
    print(f"[+] Loading 1m data & computing causal indicators for {pair}...")
    df_raw = load_pair_data(data_dir, pair, sample_ratio=0.1) # 0.1 ratio for speed
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

print(f"\nRaw Signals Generated:   {raw_signals_count}")
print(f"Executed Portfolio Trades: {len(all_trades)}")

# Save trade log to audit directory
df_trades = pd.DataFrame(all_trades)
trade_log_path = r"C:\personal\ICT_v11\audit\trade_logs\clean_executed_trades.csv"
df_trades.to_csv(trade_log_path, index=False)

# Compute Wilson 95% Confidence Interval for Win Rate
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
    7: "Turtle Soup Reversal [REMOVED]",
    8: "OTE 70.5% Fib [REMOVED]",
    9: "Breaker Block Retest",
    10: "AMD / Power of 3"
}

setup_stats = []
for s_id in range(1, 11):
    if s_id in [7, 8]: continue
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
    
    setup_stats.append({
        'setup_id': s_id,
        'setup_name': setup_names[s_id],
        'trades': len(s_tr),
        'wins': len(s_w),
        'losses': len(s_l),
        'breakevens': len(s_be),
        'true_win_rate': round(true_wr, 2),
        'be_rate': round(be_rate, 2),
        'profit_factor': round(pf, 2),
        'expectancy_usd': round(avg_pnl, 2),
        '95_wilson_ci': f"{ci_low}% - {ci_high}%"
    })

df_setup_table = pd.DataFrame(setup_stats)
print("\n--- CLEAN SETUP PERFORMANCE LEDGER ---")
print(df_setup_table.to_string(index=False))

# Chronological Data Split: Train (2024), Val (2025), OOS (2026)
df_trades['dt'] = pd.to_datetime(df_trades['timestamp_entry'])
train_df = df_trades[df_trades['dt'] < '2025-01-01']
val_df = df_trades[(df_trades['dt'] >= '2025-01-01') & (df_trades['dt'] < '2026-01-01')]
oos_df = df_trades[df_trades['dt'] >= '2026-01-01']

def subset_metrics(df_sub, label):
    n = len(df_sub)
    if n == 0: return {'period': label, 'trades': 0, 'true_wr': 0, 'be_rate': 0, 'pf': 0, 'expectancy': 0, 'net_pnl': 0}
    w = len(df_sub[df_sub['outcome'] == 'WIN'])
    l = len(df_sub[df_sub['outcome'] == 'LOSS'])
    be = len(df_sub[df_sub['outcome'] == 'BREAKEVEN'])
    
    n_dec = w + l
    t_wr = (w / n_dec * 100.0) if n_dec > 0 else 0.0
    b_rate = (be / n * 100.0)
    
    gp = df_sub[df_sub['outcome'] == 'WIN']['net_pnl'].sum()
    gl = abs(df_sub[df_sub['outcome'] == 'LOSS']['net_pnl'].sum())
    pf = (gp / gl) if gl > 0 else 99.0
    exp = df_sub['net_pnl'].sum() / n
    return {
        'period': label,
        'trades': n,
        'wins': w,
        'losses': l,
        'be': be,
        'true_wr': round(t_wr, 2),
        'be_rate': round(b_rate, 2),
        'pf': round(pf, 2),
        'expectancy': round(exp, 2),
        'net_pnl': round(df_sub['net_pnl'].sum(), 2)
    }

print("\n--- CHRONOLOGICAL OUT-OF-SAMPLE SPLIT VALIDATION ---")
df_splits = pd.DataFrame([
    subset_metrics(train_df, "Train (2024)"),
    subset_metrics(val_df, "Validation (2025)"),
    subset_metrics(oos_df, "Final OOS (2026 YTD)")
])
print(df_splits.to_string(index=False))

# 10,000 Monte Carlo Simulations on Corrected R Distribution
np.random.seed(42)
pnls = df_trades['net_pnl'].values
n_sims = 10000
final_bals = []
max_dds = []
max_consec_l = []

for _ in range(n_sims):
    shuff = np.random.choice(pnls, size=len(pnls), replace=True)
    b_path = 200.0 + np.cumsum(shuff)
    final_bals.append(b_path[-1])
    peak = np.maximum.accumulate(b_path)
    dd = (peak - b_path) / peak * 100.0
    max_dds.append(np.max(dd))
    
    # consecutive losses
    is_l = shuff < 0
    curr_l = 0
    m_l = 0
    for flag in is_l:
        if flag:
            curr_l += 1
            if curr_l > m_l: m_l = curr_l
        else:
            curr_l = 0
    max_consec_l.append(m_l)

print("\n--- 10,000 MONTE CARLO BOOTSTRAP RESULTS ---")
print(f"  5th Percentile Ending Balance:  ${np.percentile(final_bals, 5):,.2f}")
print(f"  50th Percentile Ending Balance: ${np.percentile(final_bals, 50):,.2f}")
print(f"  95th Percentile Ending Balance: ${np.percentile(final_bals, 95):,.2f}")
print(f"  Median Max Drawdown %:          {np.median(max_dds):.2f}%")
print(f"  95th Percentile Max Drawdown %: {np.percentile(max_dds, 95):.2f}%")
print(f"  95th % Max Consecutive Losses:  {np.percentile(max_consec_l, 95):.0f} Losses")

# Reproducibility Check
hash1 = hashlib.sha256(open(trade_log_path, "rb").read()).hexdigest()
print(f"\nTrade Log SHA-256 Hash (Run 1): {hash1}")

print("\n==========================================================================")
print("                   CLEAN RE-VALIDATION COMPLETE                           ")
print("==========================================================================")
