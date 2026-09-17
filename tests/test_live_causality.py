import pytest
import pandas as pd
import numpy as np
from backend.engine.event_simulation_engine import EventDrivenLiveSimulator

def create_synthetic_market(num_candles_1m: int = 1000) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Generates synthetic 1m and 5m market data for live causality verification."""
    np.random.seed(42)
    times_1m = pd.date_range('2026-01-01 00:00:00', periods=num_candles_1m, freq='1min')
    
    close_prices = 1.1500 + np.cumsum(np.random.randn(num_candles_1m) * 0.0002)
    opens = close_prices + np.random.randn(num_candles_1m) * 0.0001
    highs = np.maximum(opens, close_prices) + np.abs(np.random.randn(num_candles_1m) * 0.0002)
    lows = np.minimum(opens, close_prices) - np.abs(np.random.randn(num_candles_1m) * 0.0002)
    
    df_1m = pd.DataFrame({
        'open': opens,
        'high': highs,
        'low': lows,
        'close': close_prices,
        'volume': 100.0,
        'spread_pips': 1.0
    }, index=times_1m)
    
    # Resample 5m
    df_5m = df_1m.resample('5min').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'spread_pips': 'mean',
        'volume': 'sum'
    }).dropna()
    
    return df_1m, df_5m

def test_live_causality_strict():
    """
    STRICT LIVE SIMULATION CAUSALITY TEST:
    Given cutoff timestamp T:
    Modifying any future candles > T MUST NOT alter any decision or signal <= T.
    """
    df_1m_orig, df_5m_orig = create_synthetic_market(1000)
    
    # Cutoff timestamp T (e.g. index 500 in 1m)
    cutoff_1m_idx = 500
    cutoff_time = df_1m_orig.index[cutoff_1m_idx]
    
    sim_A = EventDrivenLiveSimulator(pair="EURUSD", confluence_threshold=3)
    res_A = sim_A.run_simulation(df_1m_orig.copy(), df_5m_orig.copy())
    
    # Dataset B: Identical candles <= cutoff_time, but RANDOMIZED candles > cutoff_time
    df_1m_B = df_1m_orig.copy()
    np.random.seed(888)
    n_fut_1m = len(df_1m_B) - (cutoff_1m_idx + 1)
    
    df_1m_B.iloc[cutoff_1m_idx + 1:, df_1m_B.columns.get_loc('close')] += np.random.randn(n_fut_1m) * 0.05
    df_1m_B.iloc[cutoff_1m_idx + 1:, df_1m_B.columns.get_loc('high')] += np.abs(np.random.randn(n_fut_1m) * 0.05)
    df_1m_B.iloc[cutoff_1m_idx + 1:, df_1m_B.columns.get_loc('low')] -= np.abs(np.random.randn(n_fut_1m) * 0.05)
    
    df_5m_B = df_1m_B.resample('5min').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'spread_pips': 'mean',
        'volume': 'sum'
    }).dropna()
    
    sim_B = EventDrivenLiveSimulator(pair="EURUSD", confluence_threshold=3)
    res_B = sim_B.run_simulation(df_1m_B, df_5m_B)
    
    # Filter trades entered at or before cutoff_time
    trades_A_before_T = [t for t in res_A['trades'] if pd.to_datetime(t['timestamp_entry']) <= cutoff_time]
    trades_B_before_T = [t for t in res_B['trades'] if pd.to_datetime(t['timestamp_entry']) <= cutoff_time]
    
    assert len(trades_A_before_T) == len(trades_B_before_T), (
        f"Trade count mismatch before cutoff T! Dataset A: {len(trades_A_before_T)}, Dataset B: {len(trades_B_before_T)}"
    )
    
    for tr_a, tr_b in zip(trades_A_before_T, trades_B_before_T):
        assert tr_a['timestamp_entry'] == tr_b['timestamp_entry']
        assert tr_a['direction'] == tr_b['direction']
        assert tr_a['entry_price'] == tr_b['entry_price']
        assert tr_a['sl_price'] == tr_b['sl_price']
        assert tr_a['tp_price'] == tr_b['tp_price']
        assert tr_a['lot_size'] == tr_b['lot_size']

if __name__ == '__main__':
    test_live_causality_strict()
    print("LIVE SIMULATION CAUSALITY TEST PASSED 100%!")
