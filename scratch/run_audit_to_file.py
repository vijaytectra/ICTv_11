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

out_file = r"C:\personal\ICT_v11\scratch\audit_output.txt"
with open(out_file, "w", encoding="utf-8") as out:
    def p(text=""):
        print(text)
        out.write(str(text) + "\n")

    p("==========================================================================")
    p("             STARTING COMPREHENSIVE ICT BACKTEST AUDIT SUITE               ")
    p("==========================================================================")

    data_dir = r"C:\Users\Vijayakumar R\Documents"
    pairs = ["GBPUSD", "EURUSD", "USDJPY", "USDCAD", "AUDUSD", "USDCHF"]

    # 1. Data Inventory Audit
    data_stats = []
    all_dfs_res = {}
    all_dfs_raw = {}

    for pair in pairs:
        bid_files = sorted(glob.glob(os.path.join(data_dir, f"{pair}_1 Min_Bid_*.csv")))
        ask_files = sorted(glob.glob(os.path.join(data_dir, f"{pair}_1 Min_Ask_*.csv")))
        
        total_raw = 0
        bid_dfs = []
        for f in bid_files:
            df_f = pd.read_csv(f)
            total_raw += len(df_f)
            cols_map = {c: c.strip().lower() for c in df_f.columns}
            df_f.rename(columns=cols_map, inplace=True)
            time_col = [c for c in df_f.columns if 'time' in c.lower()][0]
            df_f.rename(columns={time_col: 'time'}, inplace=True)
            df_f['time'] = pd.to_datetime(df_f['time'], format='%Y.%m.%d %H:%M:%S', errors='coerce')
            df_f.dropna(subset=['time'], inplace=True)
            bid_dfs.append(df_f[['time']])
            
        full_bid = pd.concat(bid_dfs, ignore_index=True)
        dup_ts = full_bid.duplicated(subset=['time']).sum()
        unique_ts = full_bid['time'].nunique()
        
        df_raw = load_pair_data(data_dir, pair, sample_ratio=0.1)
        df_res = resample_candles(df_raw, "5m")
        all_dfs_res[pair] = df_res
        all_dfs_raw[pair] = df_raw
        
        full_idx = pd.date_range(start=df_res.index[0], end=df_res.index[-1], freq='5min')
        full_idx_no_wknd = full_idx[full_idx.dayofweek < 5]
        missing_intervals = len(full_idx_no_wknd.difference(df_res.index))
        
        data_stats.append({
            'pair': pair,
            'raw_rows': total_raw,
            'unique_ts': unique_ts,
            'dup_ts': dup_ts,
            'resampled_5m': len(df_res),
            'start_date': str(df_res.index[0]),
            'end_date': str(df_res.index[-1]),
            'missing_5m_intervals': missing_intervals,
            'mean_spread': round(df_raw['spread_pips'].mean(), 2)
        })

    p("\n--- DATA INTEGRITY TABLE ---")
    p(pd.DataFrame(data_stats).to_string(index=False))

    # 2. Reproduction of backtest (0.1 sample)
    p("\n--- RUNNING BACKTEST REPRODUCTION (0.1 SAMPLE DATA) ---")
    all_trades = []
    for pair in pairs:
        df_res = all_dfs_res[pair]
        signals = get_all_setup_signals(df_res, pair, min_rr=2.0)
        res = execute_backtest(df_res, signals, pair, starting_balance=200.0, risk_percent=1.0, max_slippage_pips=0.5, commission_per_lot=3.50)
        all_trades.extend(res['trades'])
        p(f"  {pair}: Resampled 5m candles={len(df_res)}, Signals={len(signals)}, Trades Executed={res['total_trades']}, Win Rate={res['win_rate_pct']}%, Net Profit=${res['net_profit']:.2f}")

    p(f"\nTotal Executed Portfolio Trades across 6 Pairs: {len(all_trades)}")

    # 3. Setup Breakdown Table & Wilson 95% Confidence Intervals
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
    sum_setup_trades = 0
    for s_id in range(1, 11):
        if s_id in [7, 8]: continue
        s_tr = [t for t in all_trades if t['setup_id'] == s_id]
        s_w = [t for t in s_tr if t['outcome'] == 'WIN']
        s_l = [t for t in s_tr if t['outcome'] == 'LOSS']
        sum_setup_trades += len(s_tr)
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

    p("\n--- WIN RATE AUDIT TABLE ---")
    p(pd.DataFrame(setup_rows).to_string(index=False))
    p(f"Sum of Setup Trades: {sum_setup_trades}")

    # 4. Intrabar Ambiguity Check
    ambig_cnt = 0
    for pair in pairs:
        df_res = all_dfs_res[pair]
        highs = df_res['high'].values
        lows = df_res['low'].values
        df_times = list(df_res.index)
        t_map = {t.strftime('%Y-%m-%d %H:%M:%S'): i for i, t in enumerate(df_times)}
        for tr in [t for t in all_trades if t['pair'] == pair]:
            if tr['timestamp_exit'] in t_map:
                idx = t_map[tr['timestamp_exit']]
                sl_p, tp_p = tr['sl_price'], tr['tp_price']
                if tr['direction'] == 'BUY' and lows[idx] <= sl_p and highs[idx] >= tp_p:
                    ambig_cnt += 1
                elif tr['direction'] == 'SELL' and highs[idx] >= sl_p and lows[idx] <= tp_p:
                    ambig_cnt += 1

    p(f"\nIntrabar Ambiguous Trades (both SL and TP hit in same exit candle): {ambig_cnt} ({ambig_cnt/max(1, len(all_trades))*100:.2f}%)")

    # 5. Out-of-sample Split
    df_tr_all = pd.DataFrame(all_trades)
    df_tr_all['dt'] = pd.to_datetime(df_tr_all['timestamp_entry'])

    train_df = df_tr_all[df_tr_all['dt'] < '2025-01-01']
    val_df = df_tr_all[(df_tr_all['dt'] >= '2025-01-01') & (df_tr_all['dt'] < '2026-01-01')]
    oos_df = df_tr_all[df_tr_all['dt'] >= '2026-01-01']

    def metrics_for_subset(df_sub, label):
        n = len(df_sub)
        if n == 0: return {'period': label, 'trades': 0, 'wr': 0, 'pf': 0, 'net_pnl': 0}
        w = len(df_sub[df_sub['outcome'] == 'WIN'])
        wr = w / n * 100.0
        gp = df_sub[df_sub['net_pnl'] > 0]['net_pnl'].sum()
        gl = abs(df_sub[df_sub['net_pnl'] < 0]['net_pnl'].sum())
        pf = (gp / gl) if gl > 0 else 99.0
        return {'period': label, 'trades': n, 'wr': round(wr, 2), 'pf': round(pf, 2), 'net_pnl': round(df_sub['net_pnl'].sum(), 2)}

    p("\n--- CHRONOLOGICAL OUT-OF-SAMPLE RESULTS ---")
    p(pd.DataFrame([
        metrics_for_subset(train_df, "Train (2024)"),
        metrics_for_subset(val_df, "Val (2025)"),
        metrics_for_subset(oos_df, "OOS (2026 YTD)")
    ]).to_string(index=False))

    # 6. Monte Carlo 10,000 simulations
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

    p("\n--- MONTE CARLO 10,000 SIMULATIONS ---")
    p(f"  5th Percentile Ending Balance:  ${np.percentile(final_bals, 5):,.2f}")
    p(f"  50th Percentile Ending Balance: ${np.percentile(final_bals, 50):,.2f}")
    p(f"  95th Percentile Ending Balance: ${np.percentile(final_bals, 95):,.2f}")
    p(f"  Median Max Drawdown:           {np.median(max_dds):.2f}%")
    p(f"  95th Percentile Max Drawdown:  {np.percentile(max_dds, 95):.2f}%")

    # 7. Cost Sensitivity
    p("\n--- COST SENSITIVITY AUDIT (EURUSD) ---")
    eur_df = all_dfs_res['EURUSD']
    eur_sigs = get_all_setup_signals(eur_df, 'EURUSD', min_rr=2.0)

    cost_rows = []
    for slip in [0.0, 0.25, 0.5, 1.0, 2.0]:
        for comm in [0.0, 3.50, 5.00, 7.00]:
            res_c = execute_backtest(eur_df, eur_sigs, 'EURUSD', starting_balance=200.0, risk_percent=1.0, max_slippage_pips=slip, commission_per_lot=comm)
            cost_rows.append({
                'slippage_pips': slip,
                'commission_lot': comm,
                'trades': res_c['total_trades'],
                'win_rate': res_c['win_rate_pct'],
                'profit_factor': res_c['profit_factor'],
                'net_profit': res_c['net_profit']
            })

    p(pd.DataFrame(cost_rows).to_string(index=False))

    p("\n==========================================================================")
    p("                    AUDIT SUITE COMPLETE                                  ")
    p("==========================================================================")
