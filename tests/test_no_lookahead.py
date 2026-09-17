import pytest
import pandas as pd
import numpy as np
from backend.engine.ict_indicators import (
    find_swing_points, find_fair_value_gaps, find_inverted_fvgs,
    find_liquidity_sweeps, find_order_blocks, find_breaker_blocks,
    find_ote_zones, tag_killzones
)

def create_dummy_ohlc(num_candles: int = 200) -> pd.DataFrame:
    """Generates synthetic OHLC market data for causality testing."""
    np.random.seed(123)
    times = pd.date_range(start='2026-01-01 00:00:00', periods=num_candles, freq='5min')
    close_prices = 1.1000 + np.cumsum(np.random.randn(num_candles) * 0.0005)
    
    opens = close_prices + np.random.randn(num_candles) * 0.0002
    highs = np.maximum(opens, close_prices) + np.abs(np.random.randn(num_candles) * 0.0004)
    lows = np.minimum(opens, close_prices) - np.abs(np.random.randn(num_candles) * 0.0004)
    
    df = pd.DataFrame({
        'open': opens,
        'high': highs,
        'low': lows,
        'close': close_prices,
        'volume': 100.0,
        'spread_pips': 1.0
    }, index=times)
    return df

def run_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Executes the complete pipeline of indicator computations."""
    df = find_swing_points(df, window=5)
    df = find_fair_value_gaps(df, min_gap_pips=2.5)
    df = find_inverted_fvgs(df)
    df = find_liquidity_sweeps(df, lookback=50)
    df = find_order_blocks(df, lookback=8)
    df = find_breaker_blocks(df, lookback=30)
    df = find_ote_zones(df, lookback=30)
    df = tag_killzones(df)
    return df

def test_causality_strict():
    """
    MASTERCARD CAUSALITY TEST:
    Given a dataset up to timestamp T:
    Altering any candles AFTER T MUST NOT change any calculated indicator or signal value <= T.
    """
    df_original = create_dummy_ohlc(200)
    
    # Choose a cutoff timestamp T (e.g. index 100)
    cutoff_idx = 100
    
    # Dataset A: Full original dataset
    df_A_ind = run_all_indicators(df_original.copy())
    
    # Dataset B: Identical candles <= cutoff_idx, but RANDOMIZED candles > cutoff_idx
    df_B = df_original.copy()
    np.random.seed(999)
    num_future = len(df_B) - (cutoff_idx + 1)
    df_B.iloc[cutoff_idx + 1:, df_B.columns.get_loc('close')] += np.random.randn(num_future) * 0.05
    df_B.iloc[cutoff_idx + 1:, df_B.columns.get_loc('high')] += np.abs(np.random.randn(num_future) * 0.05)
    df_B.iloc[cutoff_idx + 1:, df_B.columns.get_loc('low')] -= np.abs(np.random.randn(num_future) * 0.05)
    
    df_B_ind = run_all_indicators(df_B)
    
    # Verify that all calculated columns for candles 0..cutoff_idx are 100% IDENTICAL
    check_cols = [c for c in df_A_ind.columns if c not in ['open', 'high', 'low', 'close', 'volume', 'spread_pips']]
    
    for col in check_cols:
        val_A = df_A_ind[col].iloc[:cutoff_idx + 1].values
        val_B = df_B_ind[col].iloc[:cutoff_idx + 1].values
        
        # Compare NaN or values
        mask_nan = np.isnan(val_A.astype(float)) if np.issubdtype(val_A.dtype, np.number) else pd.isna(val_A)
        np.testing.assert_array_equal(
            val_A, val_B,
            err_msg=f"Causality violation detected in indicator '{col}' at or before cutoff index {cutoff_idx}!"
        )

if __name__ == '__main__':
    test_causality_strict()
    print("ALL CAUSALITY TESTS PASSED 100%!")
