import sys
import os
import glob
import pandas as pd
import numpy as np

sys.path.insert(0, r"C:\personal\ICT_v11")

from backend.engine.data_loader import get_pip_size, resample_candles
from backend.engine.strategy_setups import get_all_setup_signals
from backend.engine.backtester import execute_backtest

data_dir = r"C:\Users\Vijayakumar R\Documents"
user_pairs = ["EURUSD", "GBPUSD", "USDCAD", "USDJPY", "AUDUSD"]

out_path = r"C:\personal\ICT_v11\scratch\recent_output.txt"
with open(out_path, "w", encoding="utf-8") as out:
    def p(text=""):
        print(text, flush=True)
        out.write(str(text) + "\n")
        out.flush()

    p("==========================================================================")
    p("     BACKTEST RUNNER — SPECIFIC DATASET (2026.09.05 to 2026.09.17)        ")
    p("==========================================================================")
    p("Codebase Status: UNCHANGED AS-IS")
    p("Target Pairs:   " + ", ".join(user_pairs))
    p("==========================================================================")

    def load_specific_recent_data(data_dir: str, pair: str) -> pd.DataFrame:
        bid_pattern = os.path.join(data_dir, f"{pair}_1 Min_Bid_2026.09.05_2026.09.17.csv")
        ask_pattern = os.path.join(data_dir, f"{pair}_1 Min_Ask_2026.09.05_2026.09.17.csv")
        
        bid_files = glob.glob(bid_pattern)
        ask_files = glob.glob(ask_pattern)
        
        if not bid_files:
            raise FileNotFoundError(f"Bid file not found: {bid_pattern}")
            
        df_bid = pd.read_csv(bid_files[0])
        cols_map = {c: c.strip().lower() for c in df_bid.columns}
        df_bid.rename(columns=cols_map, inplace=True)
        time_col = [c for c in df_bid.columns if 'time' in c.lower()][0]
        df_bid.rename(columns={time_col: 'time'}, inplace=True)
        if 'volume' not in df_bid.columns:
            df_bid['volume'] = 1.0
            
        df_bid['time'] = pd.to_datetime(df_bid['time'], format='%Y.%m.%d %H:%M:%S', errors='coerce')
        df_bid.dropna(subset=['time'], inplace=True)
        df_bid = df_bid[['time', 'open', 'high', 'low', 'close', 'volume']].sort_values('time').drop_duplicates('time').reset_index(drop=True)
        
        pip_size = get_pip_size(pair)
        spread_pips = 1.0
        
        if ask_files:
            df_ask = pd.read_csv(ask_files[0])
            cols_map_ask = {c: c.strip().lower() for c in df_ask.columns}
            df_ask.rename(columns=cols_map_ask, inplace=True)
            time_col_ask = [c for c in df_ask.columns if 'time' in c.lower()][0]
            df_ask.rename(columns={time_col_ask: 'time', 'close': 'ask_close'}, inplace=True)
            df_ask['time'] = pd.to_datetime(df_ask['time'], format='%Y.%m.%d %H:%M:%S', errors='coerce')
            df_ask.dropna(subset=['time'], inplace=True)
            df_ask = df_ask[['time', 'ask_close']].sort_values('time').drop_duplicates('time')
            
            merged = pd.merge(df_bid, df_ask, on='time', how='left')
            merged['ask_close'] = merged['ask_close'].fillna(merged['close'] + (spread_pips * pip_size))
            merged['spread_pips'] = ((merged['ask_close'] - merged['close']) / pip_size).clip(lower=0.1, upper=50.0)
            final_df = merged
        else:
            df_bid['spread_pips'] = spread_pips
            final_df = df_bid
            
        final_df.set_index('time', inplace=True)
        return final_df

    all_pair_results = {}
    aggregated_trades = []
    pair_summaries = []

    for pair in user_pairs:
        p(f"\n[+] Loading & Processing {pair} (2026.09.05 - 2026.09.17)...")
        try:
            df_raw = load_specific_recent_data(data_dir, pair)
            df_5m = resample_candles(df_raw, "5m")
            
            p(f"    Raw 1m rows: {len(df_raw)} | Resampled 5m candles: {len(df_5m)}")
            p(f"    Date Range: {df_5m.index[0]} to {df_5m.index[-1]}")
            
            signals = get_all_setup_signals(df_5m, pair, min_rr=2.0)
            p(f"    Signals Generated: {len(signals)}")
            
            res = execute_backtest(
                df_5m,
                signals,
                pair,
                starting_balance=200.0,
                risk_percent=1.0,
                max_slippage_pips=0.5,
                commission_per_lot=3.50
            )
            
            all_pair_results[pair] = res
            aggregated_trades.extend(res['trades'])
            
            pair_summaries.append({
                'Pair': pair,
                '1m Rows': len(df_raw),
                '5m Candles': len(df_5m),
                'Signals': len(signals),
                'Trades': res['total_trades'],
                'Wins': res['winning_trades'],
                'Losses': res['losing_trades'],
                'Win Rate %': f"{res['win_rate_pct']:.2f}%",
                'Profit Factor': f"{res['profit_factor']:.2f}",
                'Max DD %': f"{res['max_drawdown_pct']:.2f}%",
                'Net Profit ($)': f"${res['net_profit']:+.2f}",
                'Final Balance ($)': f"${res['ending_balance']:.2f}"
            })
            
        except Exception as e:
            p(f"    [!] Error processing {pair}: {e}")

    p("\n==========================================================================")
    p("                   PAIR PERFORMANCE SUMMARY TABLE                         ")
    p("==========================================================================")
    df_pairs_report = pd.DataFrame(pair_summaries)
    p(df_pairs_report.to_string(index=False))

    p("\n==========================================================================")
    p("                 PORTFOLIO OVERALL BACKTEST SUMMARY                       ")
    p("==========================================================================")

    total_trades = len(aggregated_trades)
    winning_trades = [t for t in aggregated_trades if t['outcome'] == 'WIN']
    losing_trades = [t for t in aggregated_trades if t['outcome'] == 'LOSS']

    num_wins = len(winning_trades)
    num_losses = len(losing_trades)
    win_rate = (num_wins / total_trades * 100.0) if total_trades > 0 else 0.0

    total_gross_profit = sum(t['net_pnl'] for t in winning_trades)
    total_gross_loss = abs(sum(t['net_pnl'] for t in losing_trades))
    profit_factor = (total_gross_profit / total_gross_loss) if total_gross_loss > 0 else (99.0 if total_gross_profit > 0 else 0.0)

    net_pnl = sum(t['net_pnl'] for t in aggregated_trades)
    ending_capital = 200.0 + net_pnl
    return_pct = (net_pnl / 200.0) * 100.0

    p(f"Total Portfolio Trades Executed: {total_trades}")
    p(f"Overall Portfolio Win Rate:     {win_rate:.2f}% ({num_wins} Wins / {num_losses} Losses)")
    p(f"Portfolio Profit Factor:        {profit_factor:.2f}")
    p(f"Net Portfolio Profit:           ${net_pnl:+.2f} ({return_pct:+.2f}% Return)")
    p(f"Final Combined Balance:         ${ending_capital:.2f}")

    p("\n----------------------------------------------------------------------------------------")
    p("Setup #  Setup Name                                    Trades   Wins   Losses   Win Rate %   Net PnL ($)")
    p("----------------------------------------------------------------------------------------")

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

    setup_report = []
    for s_id in range(1, 11):
        if s_id in [7, 8]: continue
        s_tr = [t for t in aggregated_trades if t['setup_id'] == s_id]
        s_w = [t for t in s_tr if t['outcome'] == 'WIN']
        s_l = [t for t in s_tr if t['outcome'] == 'LOSS']
        s_wr = (len(s_w) / len(s_tr) * 100.0) if s_tr else 0.0
        s_pnl = sum(t['net_pnl'] for t in s_tr)
        setup_report.append({
            'Setup #': f"#{s_id}",
            'Setup Name': setup_names[s_id],
            'Trades': len(s_tr),
            'Wins': len(s_w),
            'Losses': len(s_l),
            'Win Rate %': f"{s_wr:.2f}%",
            'Net PnL ($)': f"${s_pnl:+.2f}"
        })

    p(pd.DataFrame(setup_report).to_string(index=False))
    p("================================================================------------------------\n")
