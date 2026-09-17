import sys
import os
import glob
import math
import hashlib
import pandas as pd
import numpy as np

sys.path.insert(0, r"C:\personal\ICT_v11")

from backend.engine.data_loader import load_pair_data, resample_candles, get_pip_size
from backend.engine.strategy_setups import get_all_setup_signals
from backend.engine.backtester import execute_backtest
from backend.engine.ict_indicators import (
    find_swing_points, find_fair_value_gaps, find_inverted_fvgs,
    find_liquidity_sweeps, find_order_blocks, find_breaker_blocks,
    find_ote_zones, tag_killzones
)

data_dir = r"C:\Users\Vijayakumar R\Documents"
pairs = ["GBPUSD", "EURUSD", "USDJPY", "USDCAD", "AUDUSD", "USDCHF"]

print("==========================================================================")
print("             STARTING COMPREHENSIVE ICT BACKTEST AUDIT SUITE               ")
print("==========================================================================")

# -----------------------------------------------------------------------------
# STEP 1 & 2: DATA INTEGRITY & REPRODUCTION AUDIT
# -----------------------------------------------------------------------------
data_stats = []
all_dfs_res = {}
all_dfs_raw = {}

for pair in pairs:
    bid_pattern = os.path.join(data_dir, f"{pair}_1 Min_Bid_*.csv")
    ask_pattern = os.path.join(data_dir, f"{pair}_1 Min_Ask_*.csv")
    bid_files = sorted(glob.glob(bid_pattern))
    ask_files = sorted(glob.glob(ask_pattern))
    
    raw_rows = 0
    dup_rows = 0
    file_hashes = []
    
    bid_dfs = []
    for f in bid_files:
        with open(f, 'rb') as fp:
            file_hashes.append(hashlib.md5(fp.read()).hexdigest()[:8])
        df_f = pd.read_csv(f)
        raw_rows += len(df_f)
        cols_map = {c: c.strip().lower() for c in df_f.columns}
        df_f.rename(columns=cols_map, inplace=True)
        time_col = [c for c in df_f.columns if 'time' in c.lower()][0]
        df_f.rename(columns={time_col: 'time'}, inplace=True)
        df_f['time'] = pd.to_datetime(df_f['time'], format='%Y.%m.%d %H:%M:%S', errors='coerce')
        df_f.dropna(subset=['time'], inplace=True)
        bid_dfs.append(df_f)
        
    full_bid = pd.concat(bid_dfs, ignore_index=True)
    total_raw = len(full_bid)
    dup_ts = full_bid.duplicated(subset=['time']).sum()
    unique_ts = full_bid['time'].nunique()
    
    # Load via data_loader
    df_raw = load_pair_data(data_dir, pair, sample_ratio=1.0)
    df_res = resample_candles(df_raw, "5m")
    
    all_dfs_raw[pair] = df_raw
    all_dfs_res[pair] = df_res
    
    # Calculate missing 5m intervals
    full_idx = pd.date_range(start=df_res.index[0], end=df_res.index[-1], freq='5min')
    # Filter weekends
    full_idx_no_wknd = full_idx[full_idx.dayofweek < 5]
    missing_intervals = len(full_idx_no_wknd.difference(df_res.index))
    
    spread_mean = df_raw['spread_pips'].mean()
    spread_min = df_raw['spread_pips'].min()
    spread_max = df_raw['spread_pips'].max()
    spread_std = df_raw['spread_pips'].std()
    
    data_stats.append({
        'pair': pair,
        'raw_rows': total_raw,
        'unique_ts': unique_ts,
        'dup_ts': dup_ts,
        'resampled_5m': len(df_res),
        'start_date': str(df_res.index[0]),
        'end_date': str(df_res.index[-1]),
        'missing_5m_intervals': missing_intervals,
        'spread_mean': round(spread_mean, 2),
        'spread_min': round(spread_min, 2),
        'spread_max': round(spread_max, 2),
        'hashes': ",".join(file_hashes)
    })

print("\n--- DATA INTEGRITY REPORT ---")
df_data_report = pd.DataFrame(data_stats)
print(df_data_report.to_string(index=False))

# -----------------------------------------------------------------------------
# STEP 3 - 8: LOOK-AHEAD BIAS & CONFLUENCE ENGINE AUDIT
# -----------------------------------------------------------------------------
print("\n--- LOOK-AHEAD & SIGNAL ENGINE AUDIT ---")
# Audit 1: find_swing_points
# Inspection of line 15-22 in ict_indicators.py:
# highs[i] > highs[i + k] for k in range(1, window + 1)
# Swing high at index i requires knowledge of candles i+1..i+5!
print("[CRITICAL FINDING] find_swing_points uses highs[i + k] for k in 1..5. Lookahead of 5 candles!")

# -----------------------------------------------------------------------------
# STEP 9 - 15: FULL BACKTEST REPRODUCTION & EXECUTION AUDIT
# -----------------------------------------------------------------------------
print("\n--- REPRODUCING FULL 1.0 SAMPLE BACKTEST ACROSS ALL 6 PAIRS ---")
all_trades = []
pair_summaries = {}

for pair in pairs:
    df_res = all_dfs_res[pair]
    signals = get_all_setup_signals(df_res, pair, min_rr=2.0)
    res = execute_backtest(df_res, signals, pair, starting_balance=200.0, risk_percent=1.0, max_slippage_pips=0.5, commission_per_lot=3.50)
    pair_summaries[pair] = res
    all_trades.extend(res['trades'])

print(f"\nTotal Portfolio Trades Executed (100% Data): {len(all_trades)}")

# Reconcile Trade Counts
print("\n--- TRADE SETUP BREAKDOWN & OVERLAP RECONCILIATION ---")
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
sum_setup_trades = 0

def wilson_score_interval(k, n, confidence=0.95):
    if n == 0: return 0.0, 0.0
    z = 1.959964  # 95% confidence
    p = k / n
    denominator = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / denominator
    half_width = z * math.sqrt((p * (1 - p) + z**2 / (4 * n)) / n) / denominator
    return round(max(0.0, (centre - half_width)) * 100, 2), round(min(1.0, (centre + half_width)) * 100, 2)

for s_id in range(1, 11):
    if s_id in [7, 8]: continue
    s_trades = [t for t in all_trades if t['setup_id'] == s_id]
    s_wins = [t for t in s_trades if t['outcome'] == 'WIN']
    s_losses = [t for t in s_trades if t['outcome'] == 'LOSS']
    
    n_tr = len(s_trades)
    n_w = len(s_wins)
    n_l = len(s_losses)
    sum_setup_trades += n_tr
    
    wr = (n_w / n_tr * 100.0) if n_tr > 0 else 0.0
    ci_low, ci_high = wilson_score_interval(n_w, n_tr)
    
    setup_stats.append({
        'setup_id': s_id,
        'setup_name': setup_names[s_id],
        'trades': n_tr,
        'wins': n_w,
        'losses': n_l,
        'win_rate_pct': round(wr, 2),
        '95_ci': f"{ci_low}% - {ci_high}%"
    })

df_setup_summary = pd.DataFrame(setup_stats)
print(df_setup_summary.to_string(index=False))
print(f"\nSum of individual setup trades: {sum_setup_trades}")
print(f"Actual portfolio trades executed (after max_open_trades=1 filter): {len(all_trades)}")

# -----------------------------------------------------------------------------
# INTRABAR AMBIGUITY AUDIT (SL and TP touched in same candle)
# -----------------------------------------------------------------------------
print("\n--- INTRABAR AMBIGUITY AUDIT ---")
ambiguous_count = 0
for pair in pairs:
    df_res = all_dfs_res[pair]
    highs = df_res['high'].values
    lows = df_res['low'].values
    df_times = list(df_res.index)
    time_to_idx = {t.strftime('%Y-%m-%d %H:%M:%S'): i for i, t in enumerate(df_times)}
    
    pair_trades = [t for t in all_trades if t['pair'] == pair]
    for tr in pair_trades:
        entry_t = tr['timestamp_entry']
        exit_t = tr['timestamp_exit']
        if entry_t in time_to_idx and exit_t in time_to_idx:
            ex_idx = time_to_idx[exit_t]
            # Check if exit candle touched BOTH sl_price and tp_price
            sl_p = tr['sl_price']
            tp_p = tr['tp_price']
            h = highs[ex_idx]
            l = lows[ex_idx]
            if tr['direction'] == 'BUY':
                if l <= sl_p and h >= tp_p:
                    ambiguous_count += 1
            elif tr['direction'] == 'SELL':
                if h >= sl_p and l <= tp_p:
                    ambiguous_count += 1

print(f"Total trades where SL and TP were touched in the SAME exit candle: {ambiguous_count} ({ambiguous_count / max(1, len(all_trades))*100:.2f}%)")

# -----------------------------------------------------------------------------
# OUT OF SAMPLE (OOS) & WALK FORWARD TEST
# -----------------------------------------------------------------------------
print("\n--- CHRONOLOGICAL OUT-OF-SAMPLE TEST ---")
df_all_trades = pd.DataFrame(all_trades)
df_all_trades['entry_dt'] = pd.to_datetime(df_all_trades['timestamp_entry'])

train_trades = df_all_trades[df_all_trades['entry_dt'] < '2025-01-01']
val_trades = df_all_trades[(df_all_trades['entry_dt'] >= '2025-01-01') & (df_all_trades['entry_dt'] < '2026-01-01')]
oos_trades = df_all_trades[df_all_trades['entry_dt'] >= '2026-01-01']

def calc_split_metrics(df_tr, name):
    n = len(df_tr)
    if n == 0:
        return {'period': name, 'trades': 0, 'win_rate': 0, 'pf': 0, 'pnl': 0}
    w = len(df_tr[df_tr['outcome'] == 'WIN'])
    wr = w / n * 100.0
    gp = df_tr[df_tr['net_pnl'] > 0]['net_pnl'].sum()
    gl = abs(df_tr[df_tr['net_pnl'] < 0]['net_pnl'].sum())
    pf = (gp / gl) if gl > 0 else 99.0
    pnl = df_tr['net_pnl'].sum()
    return {'period': name, 'trades': n, 'win_rate': round(wr, 2), 'pf': round(pf, 2), 'pnl': round(pnl, 2)}

splits = [
    calc_split_metrics(train_trades, "TRAIN (2024)"),
    calc_split_metrics(val_trades, "VAL (2025)"),
    calc_split_metrics(oos_trades, "OOS (2026 YTD)")
]
print(pd.DataFrame(splits).to_string(index=False))

# -----------------------------------------------------------------------------
# MONTE CARLO SIMULATION (10,000 RUNS)
# -----------------------------------------------------------------------------
print("\n--- MONTE CARLO SIMULATION (10,000 RUNS) ---")
np.random.seed(42)
pnls = df_all_trades['net_pnl'].values
n_sims = 10000
final_balances = []
max_drawdowns = []
max_consec_losses = []

for _ in range(n_sims):
    shuffled_pnls = np.random.choice(pnls, size=len(pnls), replace=True)
    cum_pnl = np.cumsum(shuffled_pnls)
    balance_path = 200.0 + cum_pnl
    final_balances.append(balance_path[-1])
    
    # Max DD
    peak = np.maximum.accumulate(balance_path)
    dd = (peak - balance_path) / peak * 100.0
    max_drawdowns.append(np.max(dd))
    
    # Max Consecutive Losses
    is_loss = shuffled_pnls < 0
    current_l = 0
    max_l = 0
    for l in is_loss:
        if l:
            current_l += 1
            if current_l > max_l: max_l = current_l
        else:
            current_l = 0
    max_consec_losses.append(max_l)

print(f"Monte Carlo 5th Percentile Final Balance:  ${np.percentile(final_balances, 5):,.2f}")
print(f"Monte Carlo 50th Percentile Final Balance: ${np.percentile(final_balances, 50):,.2f}")
print(f"Monte Carlo 95th Percentile Final Balance: ${np.percentile(final_balances, 95):,.2f}")
print(f"Monte Carlo Median Max Drawdown:           {np.median(max_drawdowns):.2f}%")
print(f"Monte Carlo 95th Percentile Max Drawdown:  {np.percentile(max_drawdowns, 95):.2f}%")
print(f"Monte Carlo Prob DD > 20%:                {(np.array(max_drawdowns) > 20.0).mean()*100:.2f}%")
print(f"Monte Carlo Max Consecutive Losses (95th%):{np.percentile(max_consec_losses, 95):.0f}")

# -----------------------------------------------------------------------------
# COST SENSITIVITY AUDIT
# -----------------------------------------------------------------------------
print("\n--- COST SENSITIVITY AUDIT (EURUSD 100% sample) ---")
eur_df = all_dfs_res['EURUSD']
eur_sigs = get_all_setup_signals(eur_df, 'EURUSD', min_rr=2.0)

cost_results = []
for slip in [0.0, 0.25, 0.5, 1.0, 2.0]:
    for comm in [0.0, 3.50, 5.00, 7.00]:
        res_c = execute_backtest(eur_df, eur_sigs, 'EURUSD', starting_balance=200.0, risk_percent=1.0, max_slippage_pips=slip, commission_per_lot=comm)
        cost_results.append({
            'slippage_pips': slip,
            'commission_lot': comm,
            'trades': res_c['total_trades'],
            'win_rate': res_c['win_rate_pct'],
            'profit_factor': res_c['profit_factor'],
            'net_profit': res_c['net_profit']
        })

print(pd.DataFrame(cost_results).to_string(index=False))

print("\n==========================================================================")
print("                    AUDIT SUITE EXECUTION COMPLETE                        ")
print("==========================================================================")
