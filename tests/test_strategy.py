import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.engine.data_loader import load_pair_data, resample_candles
from backend.engine.strategy_setups import get_all_setup_signals
from backend.engine.backtester import execute_backtest

def main():
    print("Testing Strategy Setups & Backtester on GBPUSD...")
    df = load_pair_data(r"C:\Users\Vijayakumar R\Documents", "GBPUSD", sample_ratio=0.1) # Fast 10% sample
    df5m = resample_candles(df, "5m")
    
    print(f"Resampled candles count: {len(df5m)}")
    signals = get_all_setup_signals(df5m, "GBPUSD", min_rr=2.0)
    print(f"Total Signals Generated: {len(signals)}")
    
    if signals:
        print("Sample Signal:", signals[0])
        results = execute_backtest(df5m, signals, "GBPUSD", starting_balance=200.0, risk_percent=1.0)
        print("\n=== Backtest Summary ===")
        print(f"Pair: {results['pair']}")
        print(f"Starting Capital: ${results['starting_balance']}")
        print(f"Ending Capital: ${results['ending_balance']}")
        print(f"Net Return: {results['net_return_pct']}% (${results['net_profit']})")
        print(f"Total Trades: {results['total_trades']}")
        print(f"Win Rate: {results['win_rate_pct']}% ({results['winning_trades']} Wins / {results['losing_trades']} Losses)")
        print(f"Profit Factor: {results['profit_factor']}")
        print(f"Max Drawdown: {results['max_drawdown_pct']}% (${results['max_drawdown_dollars']})")
        print(f"Trades/Week: {results['trades_per_week']}")
        print(f"Trades/Month: {results['trades_per_month']}")

if __name__ == "__main__":
    main()
