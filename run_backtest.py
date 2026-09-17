import sys
import os
import json
import argparse
from typing import List, Dict, Any

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from backend.engine.data_loader import load_pair_data, resample_candles
from backend.engine.strategy_setups import get_all_setup_signals
from backend.engine.backtester import execute_backtest

def main():
    parser = argparse.ArgumentParser(description="ICT 10-Setup Multi-Pair Backtesting Engine")
    parser.add_argument("--pairs", nargs="+", default=["GBPUSD", "EURUSD", "USDJPY", "USDCAD", "AUDUSD", "USDCHF"], help="Pairs to backtest")
    parser.add_argument("--capital", type=float, default=200.0, help="Starting capital ($)")
    parser.add_argument("--risk", type=float, default=1.0, help="Account risk per trade (%%)")
    parser.add_argument("--rr", type=float, default=2.0, help="Minimum Risk-to-Reward ratio")
    parser.add_argument("--slippage", type=float, default=0.5, help="Max slippage buffer in pips")
    parser.add_argument("--commission", type=float, default=3.50, help="Broker round-turn commission per lot ($)")
    parser.add_argument("--timeframe", type=str, default="5m", help="Candle timeframe (5m, 15m, 1h)")
    parser.add_argument("--sample", type=float, default=0.1, help="Data sample ratio (0.1 to 1.0)")
    
    args = parser.parse_args()
    
    config_path = os.path.join(os.path.dirname(__file__), "config", "config.json")
    data_dir = r"C:\Users\Vijayakumar R\Documents"
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            cfg = json.load(f)
            data_dir = cfg.get("data_dir", data_dir)
            
    print("==========================================================================")
    print("         ICT 10-SETUP MULTI-ASSET BACKTESTING ENGINE            ")
    print("==========================================================================")
    print(f"Starting Capital:       ${args.capital:.2f}")
    print(f"Fixed Risk Per Trade:   {args.risk:.1f}% (${args.capital * (args.risk/100):.2f})")
    print(f"Target Risk-to-Reward:  1:{args.rr:.1f} Minimum RR")
    print(f"Max Slippage Buffer:    {args.slippage} Pips")
    print(f"Round-Turn Commission:  ${args.commission:.2f} / Lot")
    print(f"Timeframe:              {args.timeframe}")
    print(f"Instruments Monitored:  {', '.join(args.pairs)}")
    print("==========================================================================")
    
    all_results = {}
    aggregated_trades = []
    
    for pair in args.pairs:
        print(f"\n[+] Processing data for {pair}...")
        try:
            df = load_pair_data(data_dir, pair, sample_ratio=args.sample)
            df_res = resample_candles(df, args.timeframe)
            print(f"    Resampled {len(df_res)} candles ({args.timeframe}). Generating setup signals...")
            
            signals = get_all_setup_signals(df_res, pair, min_rr=args.rr)
            print(f"    Total ICT Setup Signals Found: {len(signals)}")
            
            res = execute_backtest(
                df_res,
                signals,
                pair,
                starting_balance=args.capital,
                risk_percent=args.risk,
                max_slippage_pips=args.slippage,
                commission_per_lot=args.commission
            )
            all_results[pair] = res
            aggregated_trades.extend(res['trades'])
            
            print(f"    -> Trades Executed: {res['total_trades']} | Win Rate: {res['win_rate_pct']}% ({res['winning_trades']}W / {res['losing_trades']}L)")
            print(f"    -> Profit Factor: {res['profit_factor']} | Max DD: {res['max_drawdown_pct']}% (${res['max_drawdown_dollars']:.2f})")
            print(f"    -> Final Pair Balance: ${res['ending_balance']:.2f} ({res['net_return_pct']:+.2f}%)")
            
        except Exception as e:
            print(f"    [!] Skipping {pair}: {e}")
            
    print("\n==========================================================================")
    print("                     PORTFOLIO SUMMARY METRICS                         ")
    print("==========================================================================")
    
    total_trades = len(aggregated_trades)
    winning_trades = [t for t in aggregated_trades if t['outcome'] == 'WIN']
    losing_trades = [t for t in aggregated_trades if t['outcome'] == 'LOSS']
    win_rate = (len(winning_trades) / total_trades * 100.0) if total_trades > 0 else 0.0
    
    net_pnl = sum(t['net_pnl'] for t in aggregated_trades)
    ending_capital = args.capital + net_pnl
    ret_pct = (net_pnl / args.capital) * 100.0 if args.capital > 0 else 0.0
    
    print(f"Total Portfolio Trades:   {total_trades}")
    print(f"Overall Win Rate:         {win_rate:.2f}% ({len(winning_trades)} Wins / {len(losing_trades)} Losses)")
    print(f"Net Portfolio Profit:     ${net_pnl:+.2f} ({ret_pct:+.2f}% Return)")
    print(f"Final Account Balance:    ${ending_capital:.2f}")
    
    # 10 Setup Breakdown Table
    print("\n----------------------------------------------------------------------------------------")
    print("Setup #  Setup Name                                    Trades   Win Rate %   Net PnL ($)")
    print("----------------------------------------------------------------------------------------")
    
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
    
    for s_id in range(1, 11):
        if s_id in [7, 8]: continue
        s_trades = [t for t in aggregated_trades if t['setup_id'] == s_id]
        s_wins = [t for t in s_trades if t['outcome'] == 'WIN']
        s_wr = (len(s_wins) / len(s_trades) * 100.0) if s_trades else 0.0
        s_pnl = sum(t['net_pnl'] for t in s_trades)
        print(f"  #{s_id:<2}   {setup_names[s_id]:<42} {len(s_trades):<8} {s_wr:>8.1f}%   ${s_pnl:>10.2f}")
        
    print("================================================================------------------------\n")

if __name__ == "__main__":
    main()
