import pandas as pd
import numpy as np
from typing import List, Dict, Any, Tuple

def find_swing_points(df: pd.DataFrame, window: int = 5) -> pd.DataFrame:
    """
    Identifies Swing Highs and Swing Lows (Pivots) strictly causally.
    
    A swing high at candle (k - window) requires 'window' subsequent candles to close below it.
    Therefore, the swing point becomes KNOWN and ACTIVE only at candle index k.
    Vectorized implementation for ultra-fast execution.
    """
    df = df.copy()
    highs = pd.Series(df['high'].values)
    lows = pd.Series(df['low'].values)
    n = len(df)
    
    swing_highs = np.full(n, np.nan)
    swing_lows = np.full(n, np.nan)
    
    full_win = 2 * window + 1
    roll_max = highs.rolling(window=full_win, min_periods=full_win).max().values
    roll_min = lows.rolling(window=full_win, min_periods=full_win).min().values
    
    highs_arr = highs.values
    lows_arr = lows.values
    
    for k in range(2 * window, n):
        pivot_idx = k - window
        p_high = highs_arr[pivot_idx]
        p_low = lows_arr[pivot_idx]
        
        # Check if pivot is max in [pivot_idx - window ... k]
        if p_high == roll_max[k]:
            # Ensure uniqueness over right side
            if not np.any(highs_arr[pivot_idx + 1:k + 1] >= p_high) and not np.any(highs_arr[pivot_idx - window:pivot_idx] > p_high):
                swing_highs[k] = p_high
                
        if p_low == roll_min[k]:
            if not np.any(lows_arr[pivot_idx + 1:k + 1] <= p_low) and not np.any(lows_arr[pivot_idx - window:pivot_idx] < p_low):
                swing_lows[k] = p_low
                
    df['swing_high'] = swing_highs
    df['swing_low'] = swing_lows
    return df

def find_fair_value_gaps(df: pd.DataFrame, min_gap_pips: float = 2.5, pip_size: float = 0.0001) -> pd.DataFrame:
    """Detects Bullish & Bearish Fair Value Gaps (FVG) at candle close i."""
    df = df.copy()
    highs = df['high'].values
    lows = df['low'].values
    n = len(df)
    
    fvg_type = np.full(n, 0)
    fvg_top = np.full(n, np.nan)
    fvg_bottom = np.full(n, np.nan)
    fvg_size_pips = np.full(n, 0.0)
    
    min_gap_val = min_gap_pips * pip_size
    
    for i in range(2, n):
        if lows[i] - highs[i - 2] >= min_gap_val:
            fvg_type[i] = 1
            fvg_top[i] = lows[i]
            fvg_bottom[i] = highs[i - 2]
            fvg_size_pips[i] = (lows[i] - highs[i - 2]) / pip_size
            
        elif highs[i - 2] - lows[i] >= min_gap_val:
            fvg_type[i] = -1
            fvg_top[i] = highs[i - 2]
            fvg_bottom[i] = lows[i]
            fvg_size_pips[i] = (highs[i - 2] - lows[i]) / pip_size
            
    df['fvg_type'] = fvg_type
    df['fvg_top'] = fvg_top
    df['fvg_bottom'] = fvg_bottom
    df['fvg_size_pips'] = fvg_size_pips
    return df

def find_inverted_fvgs(df: pd.DataFrame, fvg_history_lookback: int = 50) -> pd.DataFrame:
    """Identifies Inverted Fair Value Gaps (IFVG) causally."""
    df = df.copy()
    if 'fvg_type' not in df.columns:
        df = find_fair_value_gaps(df)
        
    closes = df['close'].values
    n = len(df)
    
    ifvg_type = np.full(n, 0)
    ifvg_top = np.full(n, np.nan)
    ifvg_bottom = np.full(n, np.nan)
    
    active_fvgs = []
    
    for i in range(n):
        current_close = closes[i]
        
        if df['fvg_type'].iloc[i] != 0:
            active_fvgs.append((
                df['fvg_type'].iloc[i],
                df['fvg_top'].iloc[i],
                df['fvg_bottom'].iloc[i],
                i
            ))
            if len(active_fvgs) > fvg_history_lookback:
                active_fvgs.pop(0)
                
        for fvg in list(active_fvgs):
            ftype, ftop, fbot, idx = fvg
            if idx >= i:
                continue
                
            if ftype == -1 and current_close > ftop:
                ifvg_type[i] = 1
                ifvg_top[i] = ftop
                ifvg_bottom[i] = fbot
                active_fvgs.remove(fvg)
                break
                
            elif ftype == 1 and current_close < fbot:
                ifvg_type[i] = -1
                ifvg_top[i] = ftop
                ifvg_bottom[i] = fbot
                active_fvgs.remove(fvg)
                break
                
    df['ifvg_type'] = ifvg_type
    df['ifvg_top'] = ifvg_top
    df['ifvg_bottom'] = ifvg_bottom
    return df

def find_liquidity_sweeps(df: pd.DataFrame, lookback: int = 50) -> pd.DataFrame:
    """Identifies Buy-Side Liquidity (BSL) and Sell-Side Liquidity (SSL) sweeps causally."""
    df = df.copy()
    if 'swing_high' not in df.columns:
        df = find_swing_points(df)
        
    highs = df['high'].values
    lows = df['low'].values
    closes = df['close'].values
    n = len(df)
    
    sweep_type = np.full(n, 0)
    sweep_level = np.full(n, np.nan)
    
    for i in range(lookback, n):
        window_highs = df['swing_high'].iloc[i - lookback:i].dropna().values
        window_lows = df['swing_low'].iloc[i - lookback:i].dropna().values
        
        if len(window_lows) > 0:
            recent_ssl = window_lows[-1]
            if lows[i] < recent_ssl and closes[i] > recent_ssl:
                sweep_type[i] = 1
                sweep_level[i] = recent_ssl
                
        if len(window_highs) > 0:
            recent_bsl = window_highs[-1]
            if highs[i] > recent_bsl and closes[i] < recent_bsl:
                sweep_type[i] = -1
                sweep_level[i] = recent_bsl
                
    df['sweep_type'] = sweep_type
    df['sweep_level'] = sweep_level
    return df

def find_order_blocks(df: pd.DataFrame, lookback: int = 8) -> pd.DataFrame:
    """Identifies Bullish and Bearish Order Blocks (OB) causally at candle i close."""
    df = df.copy()
    opens = df['open'].values
    highs = df['high'].values
    lows = df['low'].values
    closes = df['close'].values
    n = len(df)
    
    ob_type = np.full(n, 0)
    ob_top = np.full(n, np.nan)
    ob_bottom = np.full(n, np.nan)
    
    for i in range(lookback, n):
        body_size = abs(closes[i] - opens[i])
        avg_body = np.mean([abs(closes[k] - opens[k]) for k in range(i - lookback, i)])
        
        if closes[i] > opens[i] and body_size > 1.5 * avg_body:
            for j in range(i - 1, max(-1, i - lookback), -1):
                if closes[j] < opens[j]:
                    ob_type[i] = 1
                    ob_top[i] = max(opens[j], closes[j])
                    ob_bottom[i] = lows[j]
                    break
                    
        elif closes[i] < opens[i] and body_size > 1.5 * avg_body:
            for j in range(i - 1, max(-1, i - lookback), -1):
                if closes[j] > opens[j]:
                    ob_type[i] = -1
                    ob_top[i] = highs[j]
                    ob_bottom[i] = min(opens[j], closes[j])
                    break
                    
    df['ob_type'] = ob_type
    df['ob_top'] = ob_top
    df['ob_bottom'] = ob_bottom
    return df

def find_breaker_blocks(df: pd.DataFrame, lookback: int = 30) -> pd.DataFrame:
    """Identifies Breaker Blocks causally."""
    df = df.copy()
    if 'ob_type' not in df.columns:
        df = find_order_blocks(df)
        
    closes = df['close'].values
    n = len(df)
    
    breaker_type = np.full(n, 0)
    breaker_top = np.full(n, np.nan)
    breaker_bottom = np.full(n, np.nan)
    
    active_obs = []
    
    for i in range(n):
        c_close = closes[i]
        
        if df['ob_type'].iloc[i] != 0:
            active_obs.append((
                df['ob_type'].iloc[i],
                df['ob_top'].iloc[i],
                df['ob_bottom'].iloc[i],
                i
            ))
            if len(active_obs) > lookback:
                active_obs.pop(0)
                
        for ob in list(active_obs):
            otype, otop, obot, oidx = ob
            if oidx >= i:
                continue
                
            if otype == -1 and c_close > otop:
                breaker_type[i] = 1
                breaker_top[i] = otop
                breaker_bottom[i] = obot
                active_obs.remove(ob)
                break
                
            elif otype == 1 and c_close < obot:
                breaker_type[i] = -1
                breaker_top[i] = otop
                breaker_bottom[i] = obot
                active_obs.remove(ob)
                break
                
    df['breaker_type'] = breaker_type
    df['breaker_top'] = breaker_top
    df['breaker_bottom'] = breaker_bottom
    return df

def find_ote_zones(df: pd.DataFrame, lookback: int = 30) -> pd.DataFrame:
    """Identifies Optimal Trade Entry (OTE) Fib Retracement Zones causally."""
    df = df.copy()
    highs = df['high'].values
    lows = df['low'].values
    n = len(df)
    
    ote_type = np.full(n, 0)
    ote_618 = np.full(n, np.nan)
    ote_705 = np.full(n, np.nan)
    ote_786 = np.full(n, np.nan)
    
    for i in range(lookback, n):
        max_h = highs[i - lookback:i].max()
        min_l = lows[i - lookback:i].min()
        rng = max_h - min_l
        
        if rng > 0:
            bull_618 = max_h - (0.618 * rng)
            bull_705 = max_h - (0.705 * rng)
            bull_786 = max_h - (0.786 * rng)
            
            bear_618 = min_l + (0.618 * rng)
            bear_705 = min_l + (0.705 * rng)
            bear_786 = min_l + (0.786 * rng)
            
            curr_close = df['close'].iloc[i]
            if bull_786 <= curr_close <= bull_618:
                ote_type[i] = 1
                ote_618[i] = bull_618
                ote_705[i] = bull_705
                ote_786[i] = bull_786
            elif bear_618 <= curr_close <= bear_786:
                ote_type[i] = -1
                ote_618[i] = bear_618
                ote_705[i] = bear_705
                ote_786[i] = bear_786
                
    df['ote_type'] = ote_type
    df['ote_618'] = ote_618
    df['ote_705'] = ote_705
    df['ote_786'] = ote_786
    return df

def tag_killzones(df: pd.DataFrame) -> pd.DataFrame:
    """Tags ICT session killzone windows based on NY time (EST)."""
    df = df.copy()
    times = df.index
    
    is_sb_ny_am = []
    is_sb_ny_pm = []
    is_sb_london = []
    is_london_kz = []
    is_ny_kz = []
    is_asian_range = []
    
    for t in times:
        h, m = t.hour, t.minute
        time_val = h + (m / 60.0)
        
        is_sb_ny_am.append(10.0 <= time_val < 11.0)
        is_sb_ny_pm.append(15.0 <= time_val < 16.0)
        is_sb_london.append(3.0 <= time_val < 4.0)
        is_london_kz.append(2.0 <= time_val < 5.0)
        is_ny_kz.append(7.0 <= time_val < 10.0)
        is_asian_range.append(20.0 <= time_val or time_val < 0.0)
        
    df['is_sb_ny_am'] = is_sb_ny_am
    df['is_sb_ny_pm'] = is_sb_ny_pm
    df['is_sb_london'] = is_sb_london
    df['is_silver_bullet'] = df['is_sb_ny_am'] | df['is_sb_ny_pm'] | df['is_sb_london']
    df['is_london_kz'] = is_london_kz
    df['is_ny_kz'] = is_ny_kz
    df['is_asian_range'] = is_asian_range
    return df
