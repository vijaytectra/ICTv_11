import sys
import os
import pytest
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.engine.data_loader import get_pip_size, resample_candles
from backend.engine.ict_indicators import (
    find_swing_points, find_fair_value_gaps, find_inverted_fvgs,
    find_liquidity_sweeps, find_order_blocks, tag_killzones
)
from backend.engine.strategy_setups import get_all_setup_signals
from backend.engine.backtester import execute_backtest

def create_synthetic_candles(n: int = 100) -> pd.DataFrame:
    """Generates synthetic OHLCV DataFrame for testing."""
    times = pd.date_range("2026-01-01 08:00:00", periods=n, freq="5min")
    np.random.seed(42)
    base_price = 1.2500
    returns = np.random.normal(0, 0.0005, n)
    prices = base_price + np.cumsum(returns)
    
    opens = prices
    highs = prices + np.abs(np.random.normal(0.0002, 0.0001, n))
    lows = prices - np.abs(np.random.normal(0.0002, 0.0001, n))
    closes = prices + np.random.normal(0, 0.0001, n)
    
    df = pd.DataFrame({
        'open': opens,
        'high': highs,
        'low': lows,
        'close': closes,
        'volume': np.random.randint(10, 500, n),
        'spread_pips': np.random.uniform(0.5, 1.5, n)
    }, index=times)
    return df

def test_pip_size():
    assert get_pip_size("EURUSD") == 0.0001
    assert get_pip_size("USDJPY") == 0.01
    assert get_pip_size("XAUUSD") == 0.1

def test_indicators():
    df = create_synthetic_candles(100)
    df_swings = find_swing_points(df)
    assert 'swing_high' in df_swings.columns
    assert 'swing_low' in df_swings.columns
    
    df_fvg = find_fair_value_gaps(df)
    assert 'fvg_type' in df_fvg.columns
    
    df_ifvg = find_inverted_fvgs(df)
    assert 'ifvg_type' in df_ifvg.columns
    
    df_sweeps = find_liquidity_sweeps(df)
    assert 'sweep_type' in df_sweeps.columns
    
    df_ob = find_order_blocks(df)
    assert 'ob_type' in df_ob.columns
    
    df_kz = tag_killzones(df)
    assert 'is_silver_bullet' in df_kz.columns

def test_backtester_math():
    df = create_synthetic_candles(200)
    signals = [{
        'timestamp': df.index[10].strftime('%Y-%m-%d %H:%M:%S'),
        'pair': 'EURUSD',
        'setup_id': 1,
        'setup_name': 'Liquidity Sweep + FVG',
        'direction': 'BUY',
        'entry': df['close'].iloc[10],
        'sl': df['close'].iloc[10] - 0.0010,
        'tp': df['close'].iloc[10] + 0.0020,
        'rr': 2.0,
        'sl_pips': 10.0,
        'spread_pips': 1.0
    }]
    
    res = execute_backtest(df, signals, "EURUSD", starting_balance=200.0, risk_percent=1.0)
    assert res['starting_balance'] == 200.0
    assert 'ending_balance' in res
    assert 'true_win_rate_pct' in res
    assert len(res['trades']) <= 1
