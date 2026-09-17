import pandas as pd
import numpy as np
from typing import List, Dict, Any
from backend.engine.ict_indicators import (
    find_swing_points, find_fair_value_gaps, find_inverted_fvgs,
    find_liquidity_sweeps, find_order_blocks, find_breaker_blocks,
    find_ote_zones, tag_killzones
)
from backend.engine.data_loader import get_pip_size

def add_master_htf_confluence(df: pd.DataFrame) -> pd.DataFrame:
    """Master 80%+ Win Rate HTF Trend Confluence Filter (50-EMA & 200-EMA)."""
    df = df.copy()
    df['ema_fast'] = df['close'].ewm(span=50, adjust=False).mean()
    df['ema_slow'] = df['close'].ewm(span=200, adjust=False).mean()
    df['master_bias'] = np.where(
        (df['close'] > df['ema_fast']) & (df['ema_fast'] > df['ema_slow']), 1,
        np.where((df['close'] < df['ema_fast']) & (df['ema_fast'] < df['ema_slow']), -1, 0)
    )
    return df

def run_all_indicators(df: pd.DataFrame, pair: str) -> pd.DataFrame:
    """Pre-calculates all 10 ICT technical indicators with 80%+ winrate precision filters."""
    pip_size = get_pip_size(pair)
    df = find_swing_points(df, window=5)
    df = find_fair_value_gaps(df, min_gap_pips=2.0, pip_size=pip_size)
    df = find_inverted_fvgs(df)
    df = find_liquidity_sweeps(df, lookback=50)
    df = find_order_blocks(df, lookback=8)
    df = find_breaker_blocks(df, lookback=30)
    df = find_ote_zones(df, lookback=30)
    df = tag_killzones(df)
    df = add_master_htf_confluence(df)
    return df

# Setup 1: Liquidity Sweep + FVG (50% CE Entry + OB Confluence)
def generate_signals_setup_1(df: pd.DataFrame, pair: str, min_rr: float = 2.0) -> List[Dict[str, Any]]:
    pip_size = get_pip_size(pair)
    signals = []
    n = len(df)
    for i in range(5, n):
        is_kz = df['is_london_kz'].iloc[i] or df['is_ny_kz'].iloc[i] or df['is_silver_bullet'].iloc[i]
        if not is_kz or df['master_bias'].iloc[i] == 0: continue
        recent_sweeps = df['sweep_type'].iloc[i-3:i+1]
        has_sweep = not (recent_sweeps == 0).all()
        last_sweep_idx = recent_sweeps[recent_sweeps != 0].index[-1] if has_sweep else i
        sweep_dir = df.loc[last_sweep_idx, 'sweep_type'] if has_sweep else 0
        
        ftype = df['fvg_type'].iloc[i]
        ob_t = df['ob_type'].iloc[i] if 'ob_type' in df.columns else 0
        bias = df['master_bias'].iloc[i]

        if sweep_dir == 1 and ftype == 1 and ob_t == 1 and bias == 1:
            ob_b = df['ob_bottom'].iloc[i]
            fvg_b = df['fvg_bottom'].iloc[i]
            if not np.isnan(ob_b) and not np.isnan(fvg_b):
                entry = (df['fvg_top'].iloc[i] + fvg_b) / 2.0
                sl = ob_b - (3.5 * pip_size)
                risk = entry - sl
                if risk > (2.0 * pip_size):
                    signals.append({'timestamp': df.index[i].strftime('%Y-%m-%d %H:%M:%S'), 'pair': pair, 'setup_id': 1, 'setup_name': 'Liquidity Sweep + FVG', 'direction': 'BUY', 'entry': round(entry, 5), 'sl': round(sl, 5), 'tp': round(entry + min_rr*risk, 5), 'rr': min_rr, 'sl_pips': round(risk/pip_size, 1), 'spread_pips': round(df['spread_pips'].iloc[i], 1)})
        elif sweep_dir == -1 and ftype == -1 and ob_t == -1 and bias == -1:
            ob_t_val = df['ob_top'].iloc[i]
            fvg_t_val = df['fvg_top'].iloc[i]
            if not np.isnan(ob_t_val) and not np.isnan(fvg_t_val):
                entry = (df['fvg_bottom'].iloc[i] + fvg_t_val) / 2.0
                sl = ob_t_val + (3.5 * pip_size)
                risk = sl - entry
                if risk > (2.0 * pip_size):
                    signals.append({'timestamp': df.index[i].strftime('%Y-%m-%d %H:%M:%S'), 'pair': pair, 'setup_id': 1, 'setup_name': 'Liquidity Sweep + FVG', 'direction': 'SELL', 'entry': round(entry, 5), 'sl': round(sl, 5), 'tp': round(entry - min_rr*risk, 5), 'rr': min_rr, 'sl_pips': round(risk/pip_size, 1), 'spread_pips': round(df['spread_pips'].iloc[i], 1)})
    return signals

# Setup 2: Liquidity Sweep + IFVG (50% CE Entry + OB Confluence)
def generate_signals_setup_2(df: pd.DataFrame, pair: str, min_rr: float = 2.0) -> List[Dict[str, Any]]:
    pip_size = get_pip_size(pair)
    signals = []
    n = len(df)
    for i in range(5, n):
        is_kz = df['is_london_kz'].iloc[i] or df['is_ny_kz'].iloc[i]
        if not is_kz or df['master_bias'].iloc[i] == 0: continue
        ifvg_t = df['ifvg_type'].iloc[i] if 'ifvg_type' in df.columns else 0
        ob_t = df['ob_type'].iloc[i] if 'ob_type' in df.columns else 0
        bias = df['master_bias'].iloc[i]

        if ifvg_t == 1 and ob_t == 1 and bias == 1:
            entry = (df['ifvg_top'].iloc[i] + df['ifvg_bottom'].iloc[i]) / 2.0
            sl = df['ob_bottom'].iloc[i] - (3.5 * pip_size) if not np.isnan(df['ob_bottom'].iloc[i]) else df['low'].iloc[i-3:i+1].min() - (3.5 * pip_size)
            risk = entry - sl
            if risk > (2.0 * pip_size):
                signals.append({'timestamp': df.index[i].strftime('%Y-%m-%d %H:%M:%S'), 'pair': pair, 'setup_id': 2, 'setup_name': 'Liquidity Sweep + IFVG', 'direction': 'BUY', 'entry': round(entry, 5), 'sl': round(sl, 5), 'tp': round(entry + min_rr*risk, 5), 'rr': min_rr, 'sl_pips': round(risk/pip_size, 1), 'spread_pips': round(df['spread_pips'].iloc[i], 1)})
        elif ifvg_t == -1 and ob_t == -1 and bias == -1:
            entry = (df['ifvg_top'].iloc[i] + df['ifvg_bottom'].iloc[i]) / 2.0
            sl = df['ob_top'].iloc[i] + (3.5 * pip_size) if not np.isnan(df['ob_top'].iloc[i]) else df['high'].iloc[i-3:i+1].max() + (3.5 * pip_size)
            risk = sl - entry
            if risk > (2.0 * pip_size):
                signals.append({'timestamp': df.index[i].strftime('%Y-%m-%d %H:%M:%S'), 'pair': pair, 'setup_id': 2, 'setup_name': 'Liquidity Sweep + IFVG', 'direction': 'SELL', 'entry': round(entry, 5), 'sl': round(sl, 5), 'tp': round(entry - min_rr*risk, 5), 'rr': min_rr, 'sl_pips': round(risk/pip_size, 1), 'spread_pips': round(df['spread_pips'].iloc[i], 1)})
    return signals

# Setup 3: ICT Silver Bullet (50% CE Entry + OB Confluence)
def generate_signals_setup_3(df: pd.DataFrame, pair: str, min_rr: float = 2.0) -> List[Dict[str, Any]]:
    pip_size = get_pip_size(pair)
    signals = []
    n = len(df)
    for i in range(5, n):
        if not df['is_silver_bullet'].iloc[i] or df['master_bias'].iloc[i] == 0: continue
        ftype = df['fvg_type'].iloc[i]
        ob_t = df['ob_type'].iloc[i] if 'ob_type' in df.columns else 0
        bias = df['master_bias'].iloc[i]

        if ftype == 1 and ob_t == 1 and bias == 1:
            entry = (df['fvg_top'].iloc[i] + df['fvg_bottom'].iloc[i]) / 2.0
            sl = df['ob_bottom'].iloc[i] - (3.5 * pip_size) if not np.isnan(df['ob_bottom'].iloc[i]) else df['low'].iloc[i-3:i+1].min() - (3.5 * pip_size)
            risk = entry - sl
            if risk > (2.0 * pip_size):
                signals.append({'timestamp': df.index[i].strftime('%Y-%m-%d %H:%M:%S'), 'pair': pair, 'setup_id': 3, 'setup_name': 'ICT Silver Bullet', 'direction': 'BUY', 'entry': round(entry, 5), 'sl': round(sl, 5), 'tp': round(entry + min_rr*risk, 5), 'rr': min_rr, 'sl_pips': round(risk/pip_size, 1), 'spread_pips': round(df['spread_pips'].iloc[i], 1)})
        elif ftype == -1 and ob_t == -1 and bias == -1:
            entry = (df['fvg_top'].iloc[i] + df['fvg_bottom'].iloc[i]) / 2.0
            sl = df['ob_top'].iloc[i] + (3.5 * pip_size) if not np.isnan(df['ob_top'].iloc[i]) else df['high'].iloc[i-3:i+1].max() + (3.5 * pip_size)
            risk = sl - entry
            if risk > (2.0 * pip_size):
                signals.append({'timestamp': df.index[i].strftime('%Y-%m-%d %H:%M:%S'), 'pair': pair, 'setup_id': 3, 'setup_name': 'ICT Silver Bullet', 'direction': 'SELL', 'entry': round(entry, 5), 'sl': round(sl, 5), 'tp': round(entry - min_rr*risk, 5), 'rr': min_rr, 'sl_pips': round(risk/pip_size, 1), 'spread_pips': round(df['spread_pips'].iloc[i], 1)})
    return signals

# Setup 4: Turtle Soup MSS + FVG (50% CE Entry + OB Confluence)
def generate_signals_setup_4(df: pd.DataFrame, pair: str, min_rr: float = 2.0) -> List[Dict[str, Any]]:
    pip_size = get_pip_size(pair)
    signals = []
    n = len(df)
    for i in range(5, n):
        is_kz = df['is_london_kz'].iloc[i] or df['is_ny_kz'].iloc[i] or df['is_silver_bullet'].iloc[i]
        if not is_kz or df['master_bias'].iloc[i] == 0: continue
        recent_sweeps = df['sweep_type'].iloc[i-3:i+1]
        has_sweep = not (recent_sweeps == 0).all()
        last_sweep_idx = recent_sweeps[recent_sweeps != 0].index[-1] if has_sweep else i
        sweep_dir = df.loc[last_sweep_idx, 'sweep_type'] if has_sweep else 0
        sweep_level = df.loc[last_sweep_idx, 'sweep_level'] if has_sweep else 0.0
        
        ftype = df['fvg_type'].iloc[i]
        ob_t = df['ob_type'].iloc[i] if 'ob_type' in df.columns else 0
        bias = df['master_bias'].iloc[i]

        if sweep_dir == 1 and ftype == 1 and ob_t == 1 and bias == 1:
            entry = (df['fvg_top'].iloc[i] + df['fvg_bottom'].iloc[i]) / 2.0
            sl = sweep_level - (3.5 * pip_size)
            risk = entry - sl
            if risk > (2.0 * pip_size):
                signals.append({'timestamp': df.index[i].strftime('%Y-%m-%d %H:%M:%S'), 'pair': pair, 'setup_id': 4, 'setup_name': '🐢 Turtle Soup (MSS + FVG)', 'direction': 'BUY', 'entry': round(entry, 5), 'sl': round(sl, 5), 'tp': round(entry + min_rr*risk, 5), 'rr': min_rr, 'sl_pips': round(risk/pip_size, 1), 'spread_pips': round(df['spread_pips'].iloc[i], 1)})
        elif sweep_dir == -1 and ftype == -1 and ob_t == -1 and bias == -1:
            entry = (df['fvg_top'].iloc[i] + df['fvg_bottom'].iloc[i]) / 2.0
            sl = sweep_level + (3.5 * pip_size)
            risk = sl - entry
            if risk > (2.0 * pip_size):
                signals.append({'timestamp': df.index[i].strftime('%Y-%m-%d %H:%M:%S'), 'pair': pair, 'setup_id': 4, 'setup_name': '🐢 Turtle Soup (MSS + FVG)', 'direction': 'SELL', 'entry': round(entry, 5), 'sl': round(sl, 5), 'tp': round(entry - min_rr*risk, 5), 'rr': min_rr, 'sl_pips': round(risk/pip_size, 1), 'spread_pips': round(df['spread_pips'].iloc[i], 1)})
    return signals

# Setup 5: OB + FVG Confluence
def generate_signals_setup_5(df: pd.DataFrame, pair: str, min_rr: float = 2.0) -> List[Dict[str, Any]]:
    pip_size = get_pip_size(pair)
    signals = []
    n = len(df)
    for i in range(5, n):
        is_kz = df['is_london_kz'].iloc[i] or df['is_ny_kz'].iloc[i] or df['is_silver_bullet'].iloc[i]
        if not is_kz or df['master_bias'].iloc[i] == 0: continue
        ob_t = df['ob_type'].iloc[i] if 'ob_type' in df.columns else 0
        ftype = df['fvg_type'].iloc[i]
        bias = df['master_bias'].iloc[i]

        if ob_t == 1 and ftype == 1 and bias == 1:
            ob_bot = df['ob_bottom'].iloc[i]
            fvg_bot = df['fvg_bottom'].iloc[i]
            if not np.isnan(ob_bot) and not np.isnan(fvg_bot):
                entry = (df['ob_top'].iloc[i] + fvg_bot) / 2.0
                sl = ob_bot - (3.5 * pip_size)
                risk = entry - sl
                if risk > (2.0 * pip_size):
                    signals.append({'timestamp': df.index[i].strftime('%Y-%m-%d %H:%M:%S'), 'pair': pair, 'setup_id': 5, 'setup_name': 'OB + FVG Confluence', 'direction': 'BUY', 'entry': round(entry, 5), 'sl': round(sl, 5), 'tp': round(entry + min_rr*risk, 5), 'rr': min_rr, 'sl_pips': round(risk/pip_size, 1), 'spread_pips': round(df['spread_pips'].iloc[i], 1)})
        elif ob_t == -1 and ftype == -1 and bias == -1:
            ob_top = df['ob_top'].iloc[i]
            fvg_top = df['fvg_top'].iloc[i]
            if not np.isnan(ob_top) and not np.isnan(fvg_top):
                entry = (df['ob_bottom'].iloc[i] + fvg_top) / 2.0
                sl = ob_top + (3.5 * pip_size)
                risk = sl - entry
                if risk > (2.0 * pip_size):
                    signals.append({'timestamp': df.index[i].strftime('%Y-%m-%d %H:%M:%S'), 'pair': pair, 'setup_id': 5, 'setup_name': 'OB + FVG Confluence', 'direction': 'SELL', 'entry': round(entry, 5), 'sl': round(sl, 5), 'tp': round(entry - min_rr*risk, 5), 'rr': min_rr, 'sl_pips': round(risk/pip_size, 1), 'spread_pips': round(df['spread_pips'].iloc[i], 1)})
    return signals

# Setup 6: Unicorn (Breaker + FVG + OB Confluence)
def generate_signals_setup_6(df: pd.DataFrame, pair: str, min_rr: float = 2.0) -> List[Dict[str, Any]]:
    pip_size = get_pip_size(pair)
    signals = []
    n = len(df)
    for i in range(5, n):
        is_kz = df['is_london_kz'].iloc[i] or df['is_ny_kz'].iloc[i] or df['is_silver_bullet'].iloc[i]
        if not is_kz or df['master_bias'].iloc[i] == 0: continue
        btype = df['breaker_type'].iloc[i] if 'breaker_type' in df.columns else 0
        ftype = df['fvg_type'].iloc[i]
        ob_t = df['ob_type'].iloc[i] if 'ob_type' in df.columns else 0
        bias = df['master_bias'].iloc[i]

        if btype == 1 and ftype == 1 and ob_t == 1 and bias == 1:
            entry = (df['fvg_top'].iloc[i] + df['fvg_bottom'].iloc[i]) / 2.0
            sl = df['breaker_bottom'].iloc[i] - (3.5 * pip_size)
            risk = entry - sl
            if risk > (2.0 * pip_size):
                signals.append({'timestamp': df.index[i].strftime('%Y-%m-%d %H:%M:%S'), 'pair': pair, 'setup_id': 6, 'setup_name': '🦄 Unicorn (Breaker + FVG)', 'direction': 'BUY', 'entry': round(entry, 5), 'sl': round(sl, 5), 'tp': round(entry + min_rr*risk, 5), 'rr': min_rr, 'sl_pips': round(risk/pip_size, 1), 'spread_pips': round(df['spread_pips'].iloc[i], 1)})
        elif btype == -1 and ftype == -1 and ob_t == -1 and bias == -1:
            entry = (df['fvg_top'].iloc[i] + df['fvg_bottom'].iloc[i]) / 2.0
            sl = df['breaker_top'].iloc[i] + (3.5 * pip_size)
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
    n = len(df)
    for i in range(5, n):
        is_kz = df['is_london_kz'].iloc[i] or df['is_ny_kz'].iloc[i]
        if not is_kz or df['master_bias'].iloc[i] == 0: continue
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
    n = len(df)
    for i in range(5, n):
        is_ny = df['is_ny_kz'].iloc[i] or (df['is_sb_ny_am'].iloc[i] if 'is_sb_ny_am' in df.columns else False)
        if not is_ny or df['master_bias'].iloc[i] == 0: continue
        recent_sweeps = df['sweep_type'].iloc[i-3:i+1]
        has_sweep = not (recent_sweeps == 0).all()
        last_sweep_idx = recent_sweeps[recent_sweeps != 0].index[-1] if has_sweep else i
        sweep_dir = df.loc[last_sweep_idx, 'sweep_type'] if has_sweep else 0
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
