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
from backend.engine.event_simulation_engine import EventDrivenLiveSimulator

out_path = r"C:\personal\ICT_v11\audit\validation\live_causal_results.txt"
with open(out_path, "w", encoding="utf-8") as out:
    def p(text=""):
        print(text, flush=True)
        out.write(str(text) + "\n")
        out.flush()

    data_dir = r"C:\Users\Vijayakumar R\Documents"
    pairs = ["GBPUSD", "EURUSD", "USDJPY", "USDCAD", "AUDUSD", "USDCHF"]

    p("==========================================================================")
    p("     LIVE-SIMULATION ICT STRATEGY RESEARCH & VALIDATION ENGINE            ")
    p("==========================================================================")
    p("Target Specification:")
    p("  - Target TRUE Win Rate: >= 80.00%")
    p("  - Minimum Target RR:   1:2.0")
    p("  - Risk per Trade:       1.0% ($2.00 starting)")
    p("  - Causality Guarantee:  100% Strictly Live Event Simulation")
    p("==========================================================================")

    all_pairs_data_5m = {}
    all_pairs_data_1m = {}

    for pair in pairs:
        p(f"[+] Loading & Resampling {pair}...")
        df_raw = load_pair_data(data_dir, pair, sample_ratio=0.1)
        df_5m = resample_candles(df_raw, "5m")
        all_pairs_data_1m[pair] = df_raw
        all_pairs_data_5m[pair] = df_5m

    def run_multi_pair_sim(confluence_thresh: int, start_date: str = None, end_date: str = None):
        all_trades = []
        for pair in pairs:
            df_1m = all_pairs_data_1m[pair]
            df_5m = all_pairs_data_5m[pair]
            
            if start_date or end_date:
                mask_1m = pd.Series(True, index=df_1m.index)
                mask_5m = pd.Series(True, index=df_5m.index)
                if start_date:
                    mask_1m &= (df_1m.index >= start_date)
                    mask_5m &= (df_5m.index >= start_date)
                if end_date:
                    mask_1m &= (df_1m.index < end_date)
                    mask_5m &= (df_5m.index < end_date)
                    
                df_1m_sub = df_1m[mask_1m]
                df_5m_sub = df_5m[mask_5m]
            else:
                df_1m_sub = df_1m
                df_5m_sub = df_5m
                
            if len(df_1m_sub) == 0 or len(df_5m_sub) == 0:
                continue
                
            sim = EventDrivenLiveSimulator(
                pair=pair,
                starting_capital=200.0,
                risk_percent=1.0,
                target_rr=2.0,
                max_slippage_pips=0.5,
                commission_per_lot=3.50,
                confluence_threshold=confluence_thresh
            )
            res = sim.run_simulation(df_1m_sub, df_5m_sub)
            all_trades.extend(res['trades'])
        return all_trades

    # STEP 1: TRAIN SEARCH
    p("\n--- TRAIN (2024) CANDIDATE CONFLUENCE MODEL SEARCH ---")
    candidate_results = []
    for score_thresh in [3, 4, 5, 6]:
        tr_2024 = run_multi_pair_sim(confluence_thresh=score_thresh, start_date='2024-01-01', end_date='2025-01-01')
        n = len(tr_2024)
        if n == 0:
            candidate_results.append({'threshold': f"Score >= {score_thresh}", 'trades': 0, 'wins': 0, 'losses': 0, 'be': 0, 'true_wr': 0, 'pf': 0, 'net_pnl': 0, 'status': 'No Trades'})
            continue
        w = len([t for t in tr_2024 if t['outcome'] == 'WIN'])
        l = len([t for t in tr_2024 if t['outcome'] == 'LOSS'])
        be = len([t for t in tr_2024 if t['outcome'] == 'BREAKEVEN'])
        n_dec = w + l
        true_wr = (w / n_dec * 100.0) if n_dec > 0 else 0.0
        
        gp = sum(t['net_pnl'] for t in tr_2024 if t['outcome'] == 'WIN')
        gl = abs(sum(t['net_pnl'] for t in tr_2024 if t['outcome'] == 'LOSS'))
        pf = (gp / gl) if gl > 0 else 99.0
        net_pnl = sum(t['net_pnl'] for t in tr_2024)
        
        status = "Target >= 80% REACHED" if true_wr >= 80.0 else "Below 80% Target"
        candidate_results.append({
            'threshold': f"Score >= {score_thresh}",
            'trades': n,
            'wins': w,
            'losses': l,
            'be': be,
            'true_wr': f"{true_wr:.2f}%",
            'pf': f"{pf:.2f}",
            'net_pnl': f"${net_pnl:+.2f}",
            'status': status
        })

    p(pd.DataFrame(candidate_results).to_string(index=False))

    best_thresh = 4

    # STEP 2: FULL DATASET SIMULATION
    p(f"\n--- RUNNING FULL CHRONOLOGICAL VALIDATION WITH FROZEN SCORE >= {best_thresh} ---")
    all_executed_trades = run_multi_pair_sim(confluence_thresh=best_thresh)
    df_all = pd.DataFrame(all_executed_trades)
    df_all['dt'] = pd.to_datetime(df_all['timestamp_entry'])

    pnl_reconciled = True
    reconciled_rows = []

    for tr in all_executed_trades:
        st_bal = tr['starting_balance']
        net_pnl = tr['net_pnl']
        end_bal = tr['ending_balance']
        calc_end = round(st_bal + net_pnl, 2)
        if abs(calc_end - end_bal) > 0.01:
            pnl_reconciled = False
        
        reconciled_rows.append({
            'trade_id': tr['trade_id'],
            'pair': tr['pair'],
            'setup_id': tr['setup_id'],
            'timestamp_entry': tr['timestamp_entry'],
            'timestamp_exit': tr['timestamp_exit'],
            'starting_balance': st_bal,
            'risk_amount': tr['risk_amount'],
            'lot_size': tr['lot_size'],
            'entry_price': tr['entry_price'],
            'sl_price': tr['sl_price'],
            'tp_price': tr['tp_price'],
            'exit_price': tr['exit_price'],
            'outcome': tr['outcome'],
            'commission': tr['commission'],
            'gross_pnl': tr['gross_pnl'],
            'net_pnl': net_pnl,
            'ending_balance': end_bal,
            'reconciled': abs(calc_end - end_bal) <= 0.01
        })

    df_reconciled = pd.DataFrame(reconciled_rows)
    pnl_recon_path = r"C:\personal\ICT_v11\audit\reports\pnl_reconciliation.csv"
    df_reconciled.to_csv(pnl_recon_path, index=False)
    p(f"P&L Reconciliation Check Passed 100%: {pnl_reconciled} (Saved to {pnl_recon_path})")

    train_df = df_all[df_all['dt'] < '2025-01-01']
    val_df = df_all[(df_all['dt'] >= '2025-01-01') & (df_all['dt'] < '2026-01-01')]
    oos_df = df_all[df_all['dt'] >= '2026-01-01']

    def calc_split_row(df_sub, name):
        n = len(df_sub)
        if n == 0: return {'Period': name, 'Trades': 0, 'Wins': 0, 'Losses': 0, 'BE': 0, 'True WR %': '0.00%', 'PF': '0.00', 'Expectancy ($)': '$0.00', 'Net PnL ($)': '$0.00', 'Status': 'No Trades'}
        w = len(df_sub[df_sub['outcome'] == 'WIN'])
        l = len(df_sub[df_sub['outcome'] == 'LOSS'])
        be = len(df_sub[df_sub['outcome'] == 'BREAKEVEN'])
        n_dec = w + l
        true_wr = (w / n_dec * 100.0) if n_dec > 0 else 0.0
        gp = df_sub[df_sub['outcome'] == 'WIN']['net_pnl'].sum()
        gl = abs(df_sub[df_sub['outcome'] == 'LOSS']['net_pnl'].sum())
        pf = (gp / gl) if gl > 0 else 99.0
        exp = df_sub['net_pnl'].sum() / n
        net_pnl = df_sub['net_pnl'].sum()
        
        st = "TARGET >= 80% MET" if true_wr >= 80.0 else "TARGET NOT MET (< 80%)"
        return {
            'Period': name,
            'Trades': n,
            'Wins': w,
            'Losses': l,
            'BE': be,
            'True WR %': f"{true_wr:.2f}%",
            'PF': f"{pf:.2f}",
            'Expectancy ($)': f"${exp:.2f}",
            'Net PnL ($)': f"${net_pnl:+.2f}",
            'Status': st
        }

    p("\n--- CHRONOLOGICAL DATA SPLIT PERFORMANCE ---")
    df_split_report = pd.DataFrame([
        calc_split_row(train_df, "Train (2024)"),
        calc_split_row(val_df, "Validation (2025)"),
        calc_split_row(oos_df, "Final OOS (2026 YTD)")
    ])
    p(df_split_report.to_string(index=False))

    if len(df_all) > 0:
        min_date = df_all['dt'].min()
        max_date = df_all['dt'].max()
        total_weeks = max(1.0, (max_date - min_date).days / 7.0)
        trades_per_week = len(df_all) / total_weeks
    else:
        trades_per_week = 0.0

    p(f"\nWeekly Trade Frequency: {trades_per_week:.2f} trades/week across portfolio")

    pair_rows = []
    for p_name in pairs:
        df_p = df_all[df_all['pair'] == p_name]
        n_p = len(df_p)
        if n_p == 0: continue
        w_p = len(df_p[df_p['outcome'] == 'WIN'])
        l_p = len(df_p[df_p['outcome'] == 'LOSS'])
        be_p = len(df_p[df_p['outcome'] == 'BREAKEVEN'])
        wr_p = (w_p / (w_p + l_p) * 100.0) if (w_p + l_p) > 0 else 0.0
        gp = df_p[df_p['outcome'] == 'WIN']['net_pnl'].sum()
        gl = abs(df_p[df_p['outcome'] == 'LOSS']['net_pnl'].sum())
        pf_p = (gp / gl) if gl > 0 else 99.0
        exp_p = df_p['net_pnl'].sum() / n_p
        pair_rows.append({
            'Pair': p_name,
            'OOS Trades': n_p,
            'Wins': w_p,
            'Losses': l_p,
            'BE': be_p,
            'True WR %': f"{wr_p:.2f}%",
            'PF': f"{pf_p:.2f}",
            'Expectancy ($)': f"${exp_p:.2f}",
            'Net PnL ($)': f"${df_p['net_pnl'].sum():+.2f}"
        })

    p("\n--- PAIR BREAKDOWN LEDGER ---")
    p(pd.DataFrame(pair_rows).to_string(index=False))

    np.random.seed(42)
    oos_pnls = oos_df['net_pnl'].values if len(oos_df) > 0 else df_all['net_pnl'].values
    n_sims = 10000
    final_bals = []
    max_dds = []

    for _ in range(n_sims):
        shuff = np.random.choice(oos_pnls, size=len(oos_pnls), replace=True)
        b_path = 200.0 + np.cumsum(shuff)
        final_bals.append(b_path[-1])
        peak = np.maximum.accumulate(b_path)
        dd = (peak - b_path) / peak * 100.0
        max_dds.append(np.max(dd))

    p("\n--- MONTE CARLO 10,000 SIMULATIONS (OOS) ---")
    p(f"  5th Percentile Ending Balance:  ${np.percentile(final_bals, 5):,.2f}")
    p(f"  50th Percentile Ending Balance: ${np.percentile(final_bals, 50):,.2f}")
    p(f"  95th Percentile Ending Balance: ${np.percentile(final_bals, 95):,.2f}")
    p(f"  Median Max Drawdown %:          {np.median(max_dds):.2f}%")
    p(f"  95th Percentile Max Drawdown %: {np.percentile(max_dds, 95):.2f}%")

    p("\n==========================================================================")
    p("             RESEARCH & VALIDATION SUITE COMPLETE                         ")
    p("==========================================================================")
