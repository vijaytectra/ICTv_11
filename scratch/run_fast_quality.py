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

config_path = r"C:\personal\ICT_v11\config\strategy_config_frozen.json"
with open(config_path, "r") as f:
    frozen_cfg = json.load(f)

data_dir = r"C:\Users\Vijayakumar R\Documents"
pairs = ["GBPUSD", "EURUSD", "USDJPY", "USDCAD", "AUDUSD", "USDCHF"]

print("==========================================================================")
print("     INSTITUTIONAL ICT FAST QUALITY OPTIMIZATION RUNNER                   ")
print("==========================================================================")

all_trades = []
raw_signals_count = 0

for pair in pairs:
    print(f"[+] Processing {pair} (sample_ratio=0.05)...")
    df_raw = load_pair_data(data_dir, pair, sample_ratio=0.05)
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
    all_trades.extend(res['trades'])

print(f"\nRaw Signals Generated:     {raw_signals_count}")
print(f"Executed Portfolio Trades: {len(all_trades)}")

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

setup_stats = []
for s_id in [1, 2, 3, 4, 5, 6, 9, 10]:
    s_tr = [t for t in all_trades if t['setup_id'] == s_id]
    s_w = [t for t in s_tr if t['outcome'] == 'WIN']
    s_l = [t for t in s_tr if t['outcome'] == 'LOSS']
    s_be = [t for t in s_tr if t['outcome'] == 'BREAKEVEN']
    
    n_decisive = len(s_w) + len(s_l)
    true_wr = (len(s_w) / n_decisive * 100.0) if n_decisive > 0 else 0.0
    ci_low, ci_high = wilson_ci(len(s_w), n_decisive)
    
    gp = sum(t['net_pnl'] for t in s_w)
    gl = abs(sum(t['net_pnl'] for t in s_l))
    pf = (gp / gl) if gl > 0 else (99.0 if gp > 0 else 0.0)
    avg_pnl = sum(t['net_pnl'] for t in s_tr) / len(s_tr) if s_tr else 0.0
    
    if true_wr >= 80.0 and len(s_tr) >= 5:
        status = "ACTIVE"
    elif true_wr >= 70.0:
        status = "WATCHLIST"
    else:
        status = "REJECTED"
        
    setup_stats.append({
        'setup_id': s_id,
        'setup_name': setup_names[s_id],
        'trades': len(s_tr),
        'wins': len(s_w),
        'losses': len(s_l),
        'breakevens': len(s_be),
        'true_win_rate': round(true_wr, 2),
        '95_ci': f"{ci_low}% - {ci_high}%",
        'profit_factor': round(pf, 2),
        'expectancy_usd': round(avg_pnl, 2),
        'status': status
    })

print("\n--- INSTITUTIONAL FAST SETUP LEDGER ---")
print(pd.DataFrame(setup_stats).to_string(index=False))
