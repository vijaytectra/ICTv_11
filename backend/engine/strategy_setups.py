import pandas as pd
import numpy as np
from typing import List, Dict, Any
from backend.engine.ict_indicators import (
    find_swing_points, find_htf_structure_and_bias, find_institutional_liquidity_pools,
    find_displacement_and_expansion, find_premium_discount_zones,
    find_fair_value_gaps, find_inverted_fvgs, find_liquidity_sweeps,
    find_order_blocks, find_breaker_blocks, find_ote_zones, tag_killzones
)
from backend.engine.data_loader import get_pip_size

def add_master_htf_confluence(df: pd.DataFrame) -> pd.DataFrame:
    """Master HTF Trend Confluence Filter (combines 1H Market Structure & EMA trend)."""
    df = df.copy()
    if 'htf_bias' not in df.columns:
        df = find_htf_structure_and_bias(df)
        
    df['ema_fast'] = df['close'].ewm(span=50, adjust=False).mean()
    df['ema_slow'] = df['close'].ewm(span=200, adjust=False).mean()
    ema_bias = np.where(
        (df['close'] > df['ema_fast']) & (df['ema_fast'] > df['ema_slow']), 1,
        np.where((df['close'] < df['ema_fast']) & (df['ema_fast'] < df['ema_slow']), -1, 0)
    )
    
    df['master_bias'] = np.where(df['htf_bias'] != 0, df['htf_bias'], ema_bias)
    return df

def run_all_indicators(df: pd.DataFrame, pair: str) -> pd.DataFrame:
    """Pre-calculates all 12 ICT technical indicators with institutional precision filters."""
    pip_size = get_pip_size(pair)
    df = find_swing_points(df, window=5)
    df = find_htf_structure_and_bias(df)
    df = find_institutional_liquidity_pools(df, pip_size=pip_size)
    df = find_displacement_and_expansion(df, atr_period=20)
    df = find_premium_discount_zones(df, lookback=40)
    df = find_fair_value_gaps(df, min_gap_pips=2.0, pip_size=pip_size)
    df = find_inverted_fvgs(df)
    df = find_liquidity_sweeps(df, lookback=50)
    df = find_order_blocks(df, lookback=8)
    df = find_breaker_blocks(df, lookback=30)
    df = find_ote_zones(df, lookback=30)
    df = tag_killzones(df)
    df = add_master_htf_confluence(df)
    return df

# Helper to filter active KZ indices
def get_kz_indices(df: pd.DataFrame) -> np.ndarray:
    kz_mask = df['is_london_kz'] | df['is_ny_kz'] | df['is_silver_bullet']
    indices = np.where(kz_mask)[0]
    return indices[indices >= 5]

# Setup 1: Liquidity Sweep + FVG (High Quality: Major Pool + Discount/Premium)
def generate_signals_setup_1(df: pd.DataFrame, pair: str, min_rr: float = 2.0) -> List[Dict[str, Any]]:
    pip_size = get_pip_size(pair)
    signals = []
    kz_indices = get_kz_indices(df)
    
    for i in kz_indices:
        if df['master_bias'].iloc[i] == 0: continue
        recent_sweeps = df['sweep_type'].iloc[max(0, i-4):i+1]
        has_sweep = not (recent_sweeps == 0).all()
        last_sweep_idx = recent_sweeps[recent_sweeps != 0].index[-1] if has_sweep else i
        sweep_dir = df.loc[last_sweep_idx, 'sweep_type'] if has_sweep else 0
        
        ftype = df['fvg_type'].iloc[i]
        bias = df['master_bias'].iloc[i]
        is_disc = df['is_discount'].iloc[i]
        is_prem = df['is_premium'].iloc[i]

        if sweep_dir == 1 and ftype == 1 and bias == 1 and is_disc:
            fvg_b = df['fvg_bottom'].iloc[i]
            if not np.isnan(fvg_b):
                entry = (df['fvg_top'].iloc[i] + fvg_b) / 2.0
                ob_b = df['ob_bottom'].iloc[i] if 'ob_bottom' in df.columns and not np.isnan(df['ob_bottom'].iloc[i]) else df['low'].iloc[max(0, i-4):i+1].min()
                sl = ob_b - (3.5 * pip_size)
                risk = entry - sl
                if risk > (2.0 * pip_size):
                    signals.append({'timestamp': df.index[i].strftime('%Y-%m-%d %H:%M:%S'), 'pair': pair, 'setup_id': 1, 'setup_name': 'Liquidity Sweep + FVG', 'direction': 'BUY', 'entry': round(entry, 5), 'sl': round(sl, 5), 'tp': round(entry + min_rr*risk, 5), 'rr': min_rr, 'sl_pips': round(risk/pip_size, 1), 'spread_pips': round(df['spread_pips'].iloc[i], 1)})
        elif sweep_dir == -1 and ftype == -1 and bias == -1 and is_prem:
            fvg_t_val = df['fvg_top'].iloc[i]
            if not np.isnan(fvg_t_val):
                entry = (df['fvg_bottom'].iloc[i] + fvg_t_val) / 2.0
                ob_t_val = df['ob_top'].iloc[i] if 'ob_top' in df.columns and not np.isnan(df['ob_top'].iloc[i]) else df['high'].iloc[max(0, i-4):i+1].max()
                sl = ob_t_val + (3.5 * pip_size)
                risk = sl - entry
                if risk > (2.0 * pip_size):
                    signals.append({'timestamp': df.index[i].strftime('%Y-%m-%d %H:%M:%S'), 'pair': pair, 'setup_id': 1, 'setup_name': 'Liquidity Sweep + FVG', 'direction': 'SELL', 'entry': round(entry, 5), 'sl': round(sl, 5), 'tp': round(entry - min_rr*risk, 5), 'rr': min_rr, 'sl_pips': round(risk/pip_size, 1), 'spread_pips': round(df['spread_pips'].iloc[i], 1)})
    return signals

# Setup 2: Liquidity Sweep + IFVG (Discount/Premium + HTF Bias)
def generate_signals_setup_2(df: pd.DataFrame, pair: str, min_rr: float = 2.0) -> List[Dict[str, Any]]:
    pip_size = get_pip_size(pair)
    signals = []
    kz_indices = get_kz_indices(df)
    
    for i in kz_indices:
        if df['master_bias'].iloc[i] == 0: continue
        ifvg_t = df['ifvg_type'].iloc[i] if 'ifvg_type' in df.columns else 0
        bias = df['master_bias'].iloc[i]
        is_disc = df['is_discount'].iloc[i]
        is_prem = df['is_premium'].iloc[i]

        if ifvg_t == 1 and bias == 1 and is_disc:
            entry = (df['ifvg_top'].iloc[i] + df['ifvg_bottom'].iloc[i]) / 2.0
            sl = df['ob_bottom'].iloc[i] - (3.5 * pip_size) if not np.isnan(df['ob_bottom'].iloc[i]) else df['low'].iloc[max(0, i-4):i+1].min() - (3.5 * pip_size)
            risk = entry - sl
            if risk > (2.0 * pip_size):
                signals.append({'timestamp': df.index[i].strftime('%Y-%m-%d %H:%M:%S'), 'pair': pair, 'setup_id': 2, 'setup_name': 'Liquidity Sweep + IFVG', 'direction': 'BUY', 'entry': round(entry, 5), 'sl': round(sl, 5), 'tp': round(entry + min_rr*risk, 5), 'rr': min_rr, 'sl_pips': round(risk/pip_size, 1), 'spread_pips': round(df['spread_pips'].iloc[i], 1)})
        elif ifvg_t == -1 and bias == -1 and is_prem:
            entry = (df['ifvg_top'].iloc[i] + df['ifvg_bottom'].iloc[i]) / 2.0
            sl = df['ob_top'].iloc[i] + (3.5 * pip_size) if not np.isnan(df['ob_top'].iloc[i]) else df['high'].iloc[max(0, i-4):i+1].max() + (3.5 * pip_size)
            risk = sl - entry
            if risk > (2.0 * pip_size):
                signals.append({'timestamp': df.index[i].strftime('%Y-%m-%d %H:%M:%S'), 'pair': pair, 'setup_id': 2, 'setup_name': 'Liquidity Sweep + IFVG', 'direction': 'SELL', 'entry': round(entry, 5), 'sl': round(sl, 5), 'tp': round(entry - min_rr*risk, 5), 'rr': min_rr, 'sl_pips': round(risk/pip_size, 1), 'spread_pips': round(df['spread_pips'].iloc[i], 1)})
    return signals

# Setup 3: ICT Silver Bullet (Window FVG + Discount/Premium)
def generate_signals_setup_3(df: pd.DataFrame, pair: str, min_rr: float = 2.0) -> List[Dict[str, Any]]:
    pip_size = get_pip_size(pair)
    signals = []
    sb_indices = np.where(df['is_silver_bullet'])[0]
    sb_indices = sb_indices[sb_indices >= 5]
    
    for i in sb_indices:
        if df['master_bias'].iloc[i] == 0: continue
        ftype = df['fvg_type'].iloc[i]
        bias = df['master_bias'].iloc[i]
        is_disc = df['is_discount'].iloc[i]
        is_prem = df['is_premium'].iloc[i]

        if ftype == 1 and bias == 1 and is_disc:
            entry = (df['fvg_top'].iloc[i] + df['fvg_bottom'].iloc[i]) / 2.0
            sl = df['ob_bottom'].iloc[i] - (3.5 * pip_size) if not np.isnan(df['ob_bottom'].iloc[i]) else df['low'].iloc[max(0, i-4):i+1].min() - (3.5 * pip_size)
            risk = entry - sl
            if risk > (2.0 * pip_size):
                signals.append({'timestamp': df.index[i].strftime('%Y-%m-%d %H:%M:%S'), 'pair': pair, 'setup_id': 3, 'setup_name': 'ICT Silver Bullet', 'direction': 'BUY', 'entry': round(entry, 5), 'sl': round(sl, 5), 'tp': round(entry + min_rr*risk, 5), 'rr': min_rr, 'sl_pips': round(risk/pip_size, 1), 'spread_pips': round(df['spread_pips'].iloc[i], 1)})
        elif ftype == -1 and bias == -1 and is_prem:
            entry = (df['fvg_top'].iloc[i] + df['fvg_bottom'].iloc[i]) / 2.0
            sl = df['ob_top'].iloc[i] + (3.5 * pip_size) if not np.isnan(df['ob_top'].iloc[i]) else df['high'].iloc[max(0, i-4):i+1].max() + (3.5 * pip_size)
            risk = sl - entry
            if risk > (2.0 * pip_size):
                signals.append({'timestamp': df.index[i].strftime('%Y-%m-%d %H:%M:%S'), 'pair': pair, 'setup_id': 3, 'setup_name': 'ICT Silver Bullet', 'direction': 'SELL', 'entry': round(entry, 5), 'sl': round(sl, 5), 'tp': round(entry - min_rr*risk, 5), 'rr': min_rr, 'sl_pips': round(risk/pip_size, 1), 'spread_pips': round(df['spread_pips'].iloc[i], 1)})
    return signals

# Setup 4: Turtle Soup MSS + FVG (Deep Sweep + 50% CE Entry)
def generate_signals_setup_4(df: pd.DataFrame, pair: str, min_rr: float = 2.0) -> List[Dict[str, Any]]:
    pip_size = get_pip_size(pair)
    signals = []
    kz_indices = get_kz_indices(df)
    
    for i in kz_indices:
        if df['master_bias'].iloc[i] == 0: continue
        recent_sweeps = df['sweep_type'].iloc[max(0, i-4):i+1]
        has_sweep = not (recent_sweeps == 0).all()
        last_sweep_idx = recent_sweeps[recent_sweeps != 0].index[-1] if has_sweep else i
        sweep_dir = df.loc[last_sweep_idx, 'sweep_type'] if has_sweep else 0
        sweep_level = df.loc[last_sweep_idx, 'sweep_level'] if has_sweep else 0.0
        
        ftype = df['fvg_type'].iloc[i]
        bias = df['master_bias'].iloc[i]

        if sweep_dir == 1 and ftype == 1 and bias == 1:
            entry = (df['fvg_top'].iloc[i] + df['fvg_bottom'].iloc[i]) / 2.0
            sl = sweep_level - (3.5 * pip_size)
            risk = entry - sl
            if risk > (2.0 * pip_size):
                signals.append({'timestamp': df.index[i].strftime('%Y-%m-%d %H:%M:%S'), 'pair': pair, 'setup_id': 4, 'setup_name': '🐢 Turtle Soup (MSS + FVG)', 'direction': 'BUY', 'entry': round(entry, 5), 'sl': round(sl, 5), 'tp': round(entry + min_rr*risk, 5), 'rr': min_rr, 'sl_pips': round(risk/pip_size, 1), 'spread_pips': round(df['spread_pips'].iloc[i], 1)})
        elif sweep_dir == -1 and ftype == -1 and bias == -1:
            entry = (df['fvg_top'].iloc[i] + df['fvg_bottom'].iloc[i]) / 2.0
            sl = sweep_level + (3.5 * pip_size)
            risk = sl - entry
            if risk > (2.0 * pip_size):
                signals.append({'timestamp': df.index[i].strftime('%Y-%m-%d %H:%M:%S'), 'pair': pair, 'setup_id': 4, 'setup_name': '🐢 Turtle Soup (MSS + FVG)', 'direction': 'SELL', 'entry': round(entry, 5), 'sl': round(sl, 5), 'tp': round(entry - min_rr*risk, 5), 'rr': min_rr, 'sl_pips': round(risk/pip_size, 1), 'spread_pips': round(df['spread_pips'].iloc[i], 1)})
    return signals

# Setup 5: OB + FVG Confluence (Discount/Premium + OB/FVG Alignment)
def generate_signals_setup_5(df: pd.DataFrame, pair: str, min_rr: float = 2.0) -> List[Dict[str, Any]]:
    pip_size = get_pip_size(pair)
    signals = []
    kz_indices = get_kz_indices(df)
    
    for i in kz_indices:
        if df['master_bias'].iloc[i] == 0: continue
        ob_t = df['ob_type'].iloc[i] if 'ob_type' in df.columns else 0
        ftype = df['fvg_type'].iloc[i]
        bias = df['master_bias'].iloc[i]
        is_disc = df['is_discount'].iloc[i]
        is_prem = df['is_premium'].iloc[i]

        if ob_t == 1 and ftype == 1 and bias == 1 and is_disc:
            ob_bot = df['ob_bottom'].iloc[i]
            fvg_bot = df['fvg_bottom'].iloc[i]
            if not np.isnan(ob_bot) and not np.isnan(fvg_bot):
                entry = (df['ob_top'].iloc[i] + fvg_bot) / 2.0
                sl = ob_bot - (3.5 * pip_size)
                risk = entry - sl
                if risk > (2.0 * pip_size):
                    signals.append({'timestamp': df.index[i].strftime('%Y-%m-%d %H:%M:%S'), 'pair': pair, 'setup_id': 5, 'setup_name': 'OB + FVG Confluence', 'direction': 'BUY', 'entry': round(entry, 5), 'sl': round(sl, 5), 'tp': round(entry + min_rr*risk, 5), 'rr': min_rr, 'sl_pips': round(risk/pip_size, 1), 'spread_pips': round(df['spread_pips'].iloc[i], 1)})
        elif ob_t == -1 and ftype == -1 and bias == -1 and is_prem:
            ob_top = df['ob_top'].iloc[i]
            fvg_top = df['fvg_top'].iloc[i]
            if not np.isnan(ob_top) and not np.isnan(fvg_top):
                entry = (df['ob_bottom'].iloc[i] + fvg_top) / 2.0
                sl = ob_top + (3.5 * pip_size)
                risk = sl - entry
                if risk > (2.0 * pip_size):
                    signals.append({'timestamp': df.index[i].strftime('%Y-%m-%d %H:%M:%S'), 'pair': pair, 'setup_id': 5, 'setup_name': 'OB + FVG Confluence', 'direction': 'SELL', 'entry': round(entry, 5), 'sl': round(sl, 5), 'tp': round(entry - min_rr*risk, 5), 'rr': min_rr, 'sl_pips': round(risk/pip_size, 1), 'spread_pips': round(df['spread_pips'].iloc[i], 1)})
    return signals

# Setup 6: Unicorn (Breaker + FVG + 3-Bar Confluence Window)
def generate_signals_setup_6(df: pd.DataFrame, pair: str, min_rr: float = 2.0) -> List[Dict[str, Any]]:
    pip_size = get_pip_size(pair)
    signals = []
    kz_indices = get_kz_indices(df)
    
    for i in kz_indices:
        if df['master_bias'].iloc[i] == 0: continue
        
        breaker_types = df['breaker_type'].iloc[max(0, i-3):i+1] if 'breaker_type' in df.columns else pd.Series([0])
        has_bull_breaker = (breaker_types == 1).any()
        has_bear_breaker = (breaker_types == -1).any()
        
        ftype = df['fvg_type'].iloc[i]
        bias = df['master_bias'].iloc[i]

        if has_bull_breaker and ftype == 1 and bias == 1:
            b_bot = df['breaker_bottom'].iloc[i] if not np.isnan(df['breaker_bottom'].iloc[i]) else df['low'].iloc[max(0, i-3):i+1].min()
            entry = (df['fvg_top'].iloc[i] + df['fvg_bottom'].iloc[i]) / 2.0
            sl = b_bot - (3.5 * pip_size)
            risk = entry - sl
            if risk > (2.0 * pip_size):
                signals.append({'timestamp': df.index[i].strftime('%Y-%m-%d %H:%M:%S'), 'pair': pair, 'setup_id': 6, 'setup_name': '🦄 Unicorn (Breaker + FVG)', 'direction': 'BUY', 'entry': round(entry, 5), 'sl': round(sl, 5), 'tp': round(entry + min_rr*risk, 5), 'rr': min_rr, 'sl_pips': round(risk/pip_size, 1), 'spread_pips': round(df['spread_pips'].iloc[i], 1)})
        elif has_bear_breaker and ftype == -1 and bias == -1:
            b_top = df['breaker_top'].iloc[i] if not np.isnan(df['breaker_top'].iloc[i]) else df['high'].iloc[max(0, i-3):i+1].max()
            entry = (df['fvg_top'].iloc[i] + df['fvg_bottom'].iloc[i]) / 2.0
            sl = b_top + (3.5 * pip_size)
            risk = sl - entry
            if risk > (2.0 * pip_size):
                signals.append({'timestamp': df.index[i].strftime('%Y-%m-%d %H:%M:%S'), 'pair': pair, 'setup_id': 6, 'setup_name': '🦄 Unicorn (Breaker + FVG)', 'direction': 'SELL', 'entry': round(entry, 5), 'sl': round(sl, 5), 'tp': round(entry - min_rr*risk, 5), 'rr': min_rr, 'sl_pips': round(risk/pip_size, 1), 'spread_pips': round(df['spread_pips'].iloc[i], 1)})
    return signals

# Setup 7: Removed by user request
def generate_signals_setup_7(df: pd.DataFrame, pair: str, min_rr: float = 2.0) -> List[Dict[str, Any]]:
    return []

# Setup 8: Removed by user request
def generate_signals_setup_8(df: pd.DataFrame, pair: str, min_rr: float = 2.0) -> List[Dict[str, Any]]:
    return []

# Setup 9: Breaker Block Retest + OB/FVG
def generate_signals_setup_9(df: pd.DataFrame, pair: str, min_rr: float = 2.0) -> List[Dict[str, Any]]:
    pip_size = get_pip_size(pair)
    signals = []
    kz_indices = get_kz_indices(df)
    
    for i in kz_indices:
        if df['master_bias'].iloc[i] == 0: continue
        btype = df['breaker_type'].iloc[i] if 'breaker_type' in df.columns else 0
        ftype = df['fvg_type'].iloc[i]
        ob_t = df['ob_type'].iloc[i] if 'ob_type' in df.columns else 0
        bias = df['master_bias'].iloc[i]

        if btype == 1 and (ob_t == 1 or ftype == 1) and bias == 1:
            entry = (df['breaker_top'].iloc[i] + df['breaker_bottom'].iloc[i]) / 2.0
            sl = df['breaker_bottom'].iloc[i] - (3.5 * pip_size)
            risk = entry - sl
            if risk > (2.0 * pip_size):
                signals.append({'timestamp': df.index[i].strftime('%Y-%m-%d %H:%M:%S'), 'pair': pair, 'setup_id': 9, 'setup_name': '🔄 Breaker Block Retest', 'direction': 'BUY', 'entry': round(entry, 5), 'sl': round(sl, 5), 'tp': round(entry + min_rr*risk, 5), 'rr': min_rr, 'sl_pips': round(risk/pip_size, 1), 'spread_pips': round(df['spread_pips'].iloc[i], 1)})
        elif btype == -1 and (ob_t == -1 or ftype == -1) and bias == -1:
            entry = (df['breaker_top'].iloc[i] + df['breaker_bottom'].iloc[i]) / 2.0
            sl = df['breaker_top'].iloc[i] + (3.5 * pip_size)
            risk = sl - entry
            if risk > (2.0 * pip_size):
                signals.append({'timestamp': df.index[i].strftime('%Y-%m-%d %H:%M:%S'), 'pair': pair, 'setup_id': 9, 'setup_name': '🔄 Breaker Block Retest', 'direction': 'SELL', 'entry': round(entry, 5), 'sl': round(sl, 5), 'tp': round(entry - min_rr*risk, 5), 'rr': min_rr, 'sl_pips': round(risk/pip_size, 1), 'spread_pips': round(df['spread_pips'].iloc[i], 1)})
    return signals

# Setup 10: AMD / Power of 3 (Asian Range Break + NY Judas + FVG + OB)
def generate_signals_setup_10(df: pd.DataFrame, pair: str, min_rr: float = 2.0) -> List[Dict[str, Any]]:
    pip_size = get_pip_size(pair)
    signals = []
    ny_indices = np.where(df['is_ny_kz'] | (df['is_sb_ny_am'] if 'is_sb_ny_am' in df.columns else False))[0]
    ny_indices = ny_indices[ny_indices >= 5]
    
    for i in ny_indices:
        if df['master_bias'].iloc[i] == 0: continue
        recent_sweeps = df['sweep_type'].iloc[max(0, i-4):i+1]
        has_sweep = not (recent_sweeps == 0).all()
        last_sweep_idx = recent_sweeps[recent_sweeps != 0].index[-1] if has_sweep else i
        sweep_level = df.loc[last_sweep_idx, 'sweep_level'] if has_sweep else 0.0
        
        ftype = df['fvg_type'].iloc[i]
        ob_t = df['ob_type'].iloc[i] if 'ob_type' in df.columns else 0
        bias = df['master_bias'].iloc[i]

        if has_sweep and ftype == 1 and ob_t == 1 and bias == 1:
            entry = (df['fvg_top'].iloc[i] + df['fvg_bottom'].iloc[i]) / 2.0
            sl = sweep_level - (3.5 * pip_size)
            risk = entry - sl
            if risk > (2.0 * pip_size):
                signals.append({'timestamp': df.index[i].strftime('%Y-%m-%d %H:%M:%S'), 'pair': pair, 'setup_id': 10, 'setup_name': '📈 AMD / Power of 3', 'direction': 'BUY', 'entry': round(entry, 5), 'sl': round(sl, 5), 'tp': round(entry + min_rr*risk, 5), 'rr': min_rr, 'sl_pips': round(risk/pip_size, 1), 'spread_pips': round(df['spread_pips'].iloc[i], 1)})
        elif has_sweep and ftype == -1 and ob_t == -1 and bias == -1:
            entry = (df['fvg_top'].iloc[i] + df['fvg_bottom'].iloc[i]) / 2.0
            sl = sweep_level + (3.5 * pip_size)
            risk = sl - entry
            if risk > (2.0 * pip_size):
                signals.append({'timestamp': df.index[i].strftime('%Y-%m-%d %H:%M:%S'), 'pair': pair, 'setup_id': 10, 'setup_name': '📈 AMD / Power of 3', 'direction': 'SELL', 'entry': round(entry, 5), 'sl': round(sl, 5), 'tp': round(entry - min_rr*risk, 5), 'rr': min_rr, 'sl_pips': round(risk/pip_size, 1), 'spread_pips': round(df['spread_pips'].iloc[i], 1)})
    return signals

def get_all_setup_signals(df: pd.DataFrame, pair: str, min_rr: float = 2.0) -> List[Dict[str, Any]]:
    df_ind = run_all_indicators(df, pair)
    s1 = generate_signals_setup_1(df_ind, pair, min_rr)
    s2 = generate_signals_setup_2(df_ind, pair, min_rr)
    s3 = generate_signals_setup_3(df_ind, pair, min_rr)
    s4 = generate_signals_setup_4(df_ind, pair, min_rr)
    s5 = generate_signals_setup_5(df_ind, pair, min_rr)
    s6 = generate_signals_setup_6(df_ind, pair, min_rr)
    s9 = generate_signals_setup_9(df_ind, pair, min_rr)
    s10 = generate_signals_setup_10(df_ind, pair, min_rr)
    
    all_signals = s1 + s2 + s3 + s4 + s5 + s6 + s9 + s10
    all_signals.sort(key=lambda x: x['timestamp'])
    return all_signals
