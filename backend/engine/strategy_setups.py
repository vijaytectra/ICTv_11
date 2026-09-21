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

def run_all_indicators(
    df: pd.DataFrame,
    pair: str,
    kz_table: str = "mentorship_2017",
    fvg_require_displacement_candle: bool = True,
    liquidity_model: str = "session_pools",
) -> pd.DataFrame:
    """Pre-calculates all ICT technical indicators with institutional precision filters."""
    pip_size = get_pip_size(pair)
    df = find_swing_points(df, window=5)
    df = find_htf_structure_and_bias(df)
    df = find_institutional_liquidity_pools(df, pip_size=pip_size, kz_table=kz_table)
    df = find_displacement_and_expansion(df, atr_period=20)
    df = find_premium_discount_zones(df, lookback=40)
    df = find_fair_value_gaps(
        df,
        min_gap_pips=2.0,
        pip_size=pip_size,
        fvg_require_displacement_candle=fvg_require_displacement_candle,
    )
    df = find_inverted_fvgs(df)
    df = find_liquidity_sweeps(df, lookback=50)
    df = find_order_blocks(df, lookback=8)
    df = find_breaker_blocks(df, lookback=30)
    df = find_ote_zones(df, lookback=30)
    df = tag_killzones(df, kz_table=kz_table)
    df = add_master_htf_confluence(df)
    df.attrs["liquidity_model"] = liquidity_model or "session_pools"
    df.attrs["kz_table"] = kz_table
    return df

# Helper to filter active KZ indices
def get_kz_indices(df: pd.DataFrame) -> np.ndarray:
    kz_mask = df['is_london_kz'] | df['is_ny_kz'] | df['is_silver_bullet']
    indices = np.where(kz_mask)[0]
    return indices[indices >= 5]


def _last_sweep_info(df: pd.DataFrame, i: int, lookback: int = 4):
    """Return (sweep_dir, sweep_level, sweep_extreme, sweep_quality) from latest sweep in window."""
    start = max(0, i - lookback)
    st = df["sweep_type"].iloc[start : i + 1]
    nonzero = st[st != 0]
    if nonzero.empty:
        return 0, np.nan, np.nan, 0
    idx = nonzero.index[-1]
    extreme = df.loc[idx, "sweep_extreme"] if "sweep_extreme" in df.columns else df.loc[idx, "sweep_level"]
    quality = int(df.loc[idx, "sweep_quality"]) if "sweep_quality" in df.columns else 1
    return int(df.loc[idx, "sweep_type"]), float(df.loc[idx, "sweep_level"]), float(extreme), quality


def _has_displacement(df: pd.DataFrame, i: int, direction: str, lookback: int = 5) -> bool:
    if "has_displacement" not in df.columns:
        return True
    start = max(0, i - lookback)
    win = df.iloc[start : i + 1]
    disp = win[win["has_displacement"] == True]
    if disp.empty:
        return False
    # Displacement candle body must align with trade direction
    if direction == "BUY":
        return bool((disp["close"] > disp["open"]).any())
    return bool((disp["close"] < disp["open"]).any())


def _fvg_still_valid(df: pd.DataFrame, i: int, direction: str) -> bool:
    """Reject if close has already invalidated the FVG on the signal bar."""
    top = df["fvg_top"].iloc[i]
    bot = df["fvg_bottom"].iloc[i]
    close = df["close"].iloc[i]
    if np.isnan(top) or np.isnan(bot):
        return False
    if direction == "BUY":
        return close >= bot  # still above / inside bullish FVG
    return close <= top

# Setup 1: Liquidity Sweep + FVG (High Quality: Major Pool + Discount/Premium)
def generate_signals_setup_1(df: pd.DataFrame, pair: str, min_rr: float = 2.0) -> List[Dict[str, Any]]:
    pip_size = get_pip_size(pair)
    signals = []
    kz_indices = get_kz_indices(df)
    
    for i in kz_indices:
        if df['master_bias'].iloc[i] == 0: continue
        sweep_dir, _lvl, sweep_ext, sweep_q = _last_sweep_info(df, i, lookback=4)
        if sweep_dir == 0 or np.isnan(sweep_ext) or sweep_q < 2:
            continue
        
        ftype = df['fvg_type'].iloc[i]
        bias = df['master_bias'].iloc[i]
        is_disc = df['is_discount'].iloc[i]
        is_prem = df['is_premium'].iloc[i]

        if sweep_dir == 1 and ftype == 1 and bias == 1 and is_disc:
            if not _has_displacement(df, i, "BUY") or not _fvg_still_valid(df, i, "BUY"):
                continue
            fvg_b = df['fvg_bottom'].iloc[i]
            if not np.isnan(fvg_b):
                entry = (df['fvg_top'].iloc[i] + fvg_b) / 2.0
                # SL beyond sweep wick (NOT pool level / random OB — pool already traded through)
                sl = sweep_ext - (3.5 * pip_size)
                risk = entry - sl
                if risk > (2.0 * pip_size) and risk < (40.0 * pip_size):
                    signals.append({'timestamp': df.index[i].strftime('%Y-%m-%d %H:%M:%S'), 'pair': pair, 'setup_id': 1, 'setup_name': 'Liquidity Sweep + FVG', 'direction': 'BUY', 'entry': round(entry, 5), 'sl': round(sl, 5), 'tp': round(entry + min_rr*risk, 5), 'rr': min_rr, 'sl_pips': round(risk/pip_size, 1), 'spread_pips': round(df['spread_pips'].iloc[i], 1)})
        elif sweep_dir == -1 and ftype == -1 and bias == -1 and is_prem:
            if not _has_displacement(df, i, "SELL") or not _fvg_still_valid(df, i, "SELL"):
                continue
            fvg_t_val = df['fvg_top'].iloc[i]
            if not np.isnan(fvg_t_val):
                entry = (df['fvg_bottom'].iloc[i] + fvg_t_val) / 2.0
                sl = sweep_ext + (3.5 * pip_size)
                risk = sl - entry
                if risk > (2.0 * pip_size) and risk < (40.0 * pip_size):
                    signals.append({'timestamp': df.index[i].strftime('%Y-%m-%d %H:%M:%S'), 'pair': pair, 'setup_id': 1, 'setup_name': 'Liquidity Sweep + FVG', 'direction': 'SELL', 'entry': round(entry, 5), 'sl': round(sl, 5), 'tp': round(entry - min_rr*risk, 5), 'rr': min_rr, 'sl_pips': round(risk/pip_size, 1), 'spread_pips': round(df['spread_pips'].iloc[i], 1)})
    return signals

# Setup 2: Liquidity Sweep + IFVG (Discount/Premium + HTF Bias)
def generate_signals_setup_2(df: pd.DataFrame, pair: str, min_rr: float = 2.0) -> List[Dict[str, Any]]:
    pip_size = get_pip_size(pair)
    signals = []
    kz_indices = get_kz_indices(df)
    
    for i in kz_indices:
        if df['master_bias'].iloc[i] == 0: continue
        sweep_dir, _lvl, sweep_ext, sweep_q = _last_sweep_info(df, i, lookback=6)
        ifvg_t = df['ifvg_type'].iloc[i] if 'ifvg_type' in df.columns else 0
        bias = df['master_bias'].iloc[i]
        is_disc = df['is_discount'].iloc[i]
        is_prem = df['is_premium'].iloc[i]

        if sweep_dir == 1 and sweep_q >= 1 and ifvg_t == 1 and bias == 1 and is_disc and not np.isnan(sweep_ext):
            if not _has_displacement(df, i, "BUY"):
                continue
            entry = (df['ifvg_top'].iloc[i] + df['ifvg_bottom'].iloc[i]) / 2.0
            sl = sweep_ext - (3.5 * pip_size)
            risk = entry - sl
            if risk > (2.0 * pip_size) and risk < (40.0 * pip_size):
                signals.append({'timestamp': df.index[i].strftime('%Y-%m-%d %H:%M:%S'), 'pair': pair, 'setup_id': 2, 'setup_name': 'Liquidity Sweep + IFVG', 'direction': 'BUY', 'entry': round(entry, 5), 'sl': round(sl, 5), 'tp': round(entry + min_rr*risk, 5), 'rr': min_rr, 'sl_pips': round(risk/pip_size, 1), 'spread_pips': round(df['spread_pips'].iloc[i], 1)})
        elif sweep_dir == -1 and sweep_q >= 1 and ifvg_t == -1 and bias == -1 and is_prem and not np.isnan(sweep_ext):
            if not _has_displacement(df, i, "SELL"):
                continue
            entry = (df['ifvg_top'].iloc[i] + df['ifvg_bottom'].iloc[i]) / 2.0
            sl = sweep_ext + (3.5 * pip_size)
            risk = sl - entry
            if risk > (2.0 * pip_size) and risk < (40.0 * pip_size):
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
        sweep_dir, _lvl, sweep_ext, _sq = _last_sweep_info(df, i, lookback=8)

        if ftype == 1 and bias == 1 and is_disc:
            if not _has_displacement(df, i, "BUY") or not _fvg_still_valid(df, i, "BUY"):
                continue
            entry = (df['fvg_top'].iloc[i] + df['fvg_bottom'].iloc[i]) / 2.0
            # Prefer sweep wick; else structural low of SB window
            if sweep_dir == 1 and not np.isnan(sweep_ext):
                sl = sweep_ext - (3.5 * pip_size)
            else:
                sl = df['low'].iloc[max(0, i - 6) : i + 1].min() - (3.5 * pip_size)
            risk = entry - sl
            if risk > (2.0 * pip_size) and risk < (40.0 * pip_size):
                signals.append({'timestamp': df.index[i].strftime('%Y-%m-%d %H:%M:%S'), 'pair': pair, 'setup_id': 3, 'setup_name': 'ICT Silver Bullet', 'direction': 'BUY', 'entry': round(entry, 5), 'sl': round(sl, 5), 'tp': round(entry + min_rr*risk, 5), 'rr': min_rr, 'sl_pips': round(risk/pip_size, 1), 'spread_pips': round(df['spread_pips'].iloc[i], 1)})
        elif ftype == -1 and bias == -1 and is_prem:
            if not _has_displacement(df, i, "SELL") or not _fvg_still_valid(df, i, "SELL"):
                continue
            entry = (df['fvg_top'].iloc[i] + df['fvg_bottom'].iloc[i]) / 2.0
            if sweep_dir == -1 and not np.isnan(sweep_ext):
                sl = sweep_ext + (3.5 * pip_size)
            else:
                sl = df['high'].iloc[max(0, i - 6) : i + 1].max() + (3.5 * pip_size)
            risk = sl - entry
            if risk > (2.0 * pip_size) and risk < (40.0 * pip_size):
                signals.append({'timestamp': df.index[i].strftime('%Y-%m-%d %H:%M:%S'), 'pair': pair, 'setup_id': 3, 'setup_name': 'ICT Silver Bullet', 'direction': 'SELL', 'entry': round(entry, 5), 'sl': round(sl, 5), 'tp': round(entry - min_rr*risk, 5), 'rr': min_rr, 'sl_pips': round(risk/pip_size, 1), 'spread_pips': round(df['spread_pips'].iloc[i], 1)})
    return signals

# Setup 4: Turtle Soup MSS + FVG (Deep Sweep + 50% CE Entry)
def generate_signals_setup_4(df: pd.DataFrame, pair: str, min_rr: float = 2.0) -> List[Dict[str, Any]]:
    pip_size = get_pip_size(pair)
    signals = []
    kz_indices = get_kz_indices(df)
    
    for i in kz_indices:
        if df['master_bias'].iloc[i] == 0: continue
        sweep_dir, _lvl, sweep_ext, sweep_q = _last_sweep_info(df, i, lookback=4)
        if sweep_dir == 0 or np.isnan(sweep_ext) or sweep_q < 2:
            continue
        
        ftype = df['fvg_type'].iloc[i]
        bias = df['master_bias'].iloc[i]

        if sweep_dir == 1 and ftype == 1 and bias == 1:
            if not _has_displacement(df, i, "BUY") or not _fvg_still_valid(df, i, "BUY"):
                continue
            entry = (df['fvg_top'].iloc[i] + df['fvg_bottom'].iloc[i]) / 2.0
            sl = sweep_ext - (3.5 * pip_size)
            risk = entry - sl
            if risk > (2.0 * pip_size) and risk < (40.0 * pip_size):
                signals.append({'timestamp': df.index[i].strftime('%Y-%m-%d %H:%M:%S'), 'pair': pair, 'setup_id': 4, 'setup_name': '🐢 Turtle Soup (MSS + FVG)', 'direction': 'BUY', 'entry': round(entry, 5), 'sl': round(sl, 5), 'tp': round(entry + min_rr*risk, 5), 'rr': min_rr, 'sl_pips': round(risk/pip_size, 1), 'spread_pips': round(df['spread_pips'].iloc[i], 1)})
        elif sweep_dir == -1 and ftype == -1 and bias == -1:
            if not _has_displacement(df, i, "SELL") or not _fvg_still_valid(df, i, "SELL"):
                continue
            entry = (df['fvg_top'].iloc[i] + df['fvg_bottom'].iloc[i]) / 2.0
            sl = sweep_ext + (3.5 * pip_size)
            risk = sl - entry
            if risk > (2.0 * pip_size) and risk < (40.0 * pip_size):
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
            if not _has_displacement(df, i, "BUY") or not _fvg_still_valid(df, i, "BUY"):
                continue
            ob_bot = df['ob_bottom'].iloc[i]
            fvg_bot = df['fvg_bottom'].iloc[i]
            if not np.isnan(ob_bot) and not np.isnan(fvg_bot):
                entry = (df['ob_top'].iloc[i] + fvg_bot) / 2.0
                sl = ob_bot - (3.5 * pip_size)
                risk = entry - sl
                if risk > (2.0 * pip_size) and risk < (40.0 * pip_size):
                    signals.append({'timestamp': df.index[i].strftime('%Y-%m-%d %H:%M:%S'), 'pair': pair, 'setup_id': 5, 'setup_name': 'OB + FVG Confluence', 'direction': 'BUY', 'entry': round(entry, 5), 'sl': round(sl, 5), 'tp': round(entry + min_rr*risk, 5), 'rr': min_rr, 'sl_pips': round(risk/pip_size, 1), 'spread_pips': round(df['spread_pips'].iloc[i], 1)})
        elif ob_t == -1 and ftype == -1 and bias == -1 and is_prem:
            if not _has_displacement(df, i, "SELL") or not _fvg_still_valid(df, i, "SELL"):
                continue
            ob_top = df['ob_top'].iloc[i]
            fvg_top = df['fvg_top'].iloc[i]
            if not np.isnan(ob_top) and not np.isnan(fvg_top):
                entry = (df['ob_bottom'].iloc[i] + fvg_top) / 2.0
                sl = ob_top + (3.5 * pip_size)
                risk = sl - entry
                if risk > (2.0 * pip_size) and risk < (40.0 * pip_size):
                    signals.append({'timestamp': df.index[i].strftime('%Y-%m-%d %H:%M:%S'), 'pair': pair, 'setup_id': 5, 'setup_name': 'OB + FVG Confluence', 'direction': 'SELL', 'entry': round(entry, 5), 'sl': round(sl, 5), 'tp': round(entry - min_rr*risk, 5), 'rr': min_rr, 'sl_pips': round(risk/pip_size, 1), 'spread_pips': round(df['spread_pips'].iloc[i], 1)})
    return signals

# Setup 6: Unicorn (Breaker + FVG + 3-Bar Confluence Window)
def generate_signals_setup_6(df: pd.DataFrame, pair: str, min_rr: float = 2.0) -> List[Dict[str, Any]]:
    pip_size = get_pip_size(pair)
    signals = []
    kz_indices = get_kz_indices(df)
    
    for i in kz_indices:
        if df['master_bias'].iloc[i] == 0: continue
        
        start = max(0, i - 3)
        win = df.iloc[start : i + 1]
        ftype = df['fvg_type'].iloc[i]
        bias = df['master_bias'].iloc[i]

        if 'breaker_type' not in df.columns:
            continue
        bull_rows = win[win['breaker_type'] == 1]
        bear_rows = win[win['breaker_type'] == -1]

        if len(bull_rows) and ftype == 1 and bias == 1:
            if not _has_displacement(df, i, "BUY") or not _fvg_still_valid(df, i, "BUY"):
                continue
            b_top = float(bull_rows['breaker_top'].iloc[-1])
            b_bot = float(bull_rows['breaker_bottom'].iloc[-1])
            if np.isnan(b_bot) or np.isnan(b_top):
                continue
            f_top = float(df['fvg_top'].iloc[i])
            f_bot = float(df['fvg_bottom'].iloc[i])
            # Unicorn: FVG must overlap the breaker block
            if f_bot > b_top or f_top < b_bot:
                continue
            entry = (f_top + f_bot) / 2.0
            sl = b_bot - (3.5 * pip_size)
            risk = entry - sl
            if risk > (2.0 * pip_size) and risk < (40.0 * pip_size):
                signals.append({'timestamp': df.index[i].strftime('%Y-%m-%d %H:%M:%S'), 'pair': pair, 'setup_id': 6, 'setup_name': '🦄 Unicorn (Breaker + FVG)', 'direction': 'BUY', 'entry': round(entry, 5), 'sl': round(sl, 5), 'tp': round(entry + min_rr*risk, 5), 'rr': min_rr, 'sl_pips': round(risk/pip_size, 1), 'spread_pips': round(df['spread_pips'].iloc[i], 1)})
        elif len(bear_rows) and ftype == -1 and bias == -1:
            if not _has_displacement(df, i, "SELL") or not _fvg_still_valid(df, i, "SELL"):
                continue
            b_top = float(bear_rows['breaker_top'].iloc[-1])
            b_bot = float(bear_rows['breaker_bottom'].iloc[-1])
            if np.isnan(b_top) or np.isnan(b_bot):
                continue
            f_top = float(df['fvg_top'].iloc[i])
            f_bot = float(df['fvg_bottom'].iloc[i])
            if f_bot > b_top or f_top < b_bot:
                continue
            entry = (f_top + f_bot) / 2.0
            sl = b_top + (3.5 * pip_size)
            risk = sl - entry
            if risk > (2.0 * pip_size) and risk < (40.0 * pip_size):
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
    retest_tol = 5.0 * pip_size
    
    for i in kz_indices:
        if df['master_bias'].iloc[i] == 0: continue
        if 'breaker_type' not in df.columns:
            continue
        # Retest: breaker formed in prior bars; CURRENT close must be near CE
        start = max(0, i - 12)
        # Exclude current bar from "formation" — retest happens after formation
        formed = df.iloc[start:i]
        if formed.empty:
            continue
        bull_rows = formed[formed['breaker_type'] == 1]
        bear_rows = formed[formed['breaker_type'] == -1]
        ftype = df['fvg_type'].iloc[i]
        ob_t = df['ob_type'].iloc[i] if 'ob_type' in df.columns else 0
        bias = df['master_bias'].iloc[i]
        close = float(df['close'].iloc[i])

        if len(bull_rows) and ftype == 1 and ob_t == 1 and bias == 1:
            if not _has_displacement(df, i, "BUY"):
                continue
            b_top = float(bull_rows['breaker_top'].iloc[-1])
            b_bot = float(bull_rows['breaker_bottom'].iloc[-1])
            if np.isnan(b_top) or np.isnan(b_bot):
                continue
            entry = (b_top + b_bot) / 2.0
            # Must be an actual retest of CE (not just "breaker existed recently")
            if abs(close - entry) > retest_tol and abs(float(df['low'].iloc[i]) - entry) > retest_tol:
                continue
            sl = b_bot - (3.5 * pip_size)
            risk = entry - sl
            if risk > (2.0 * pip_size) and risk < (40.0 * pip_size):
                signals.append({'timestamp': df.index[i].strftime('%Y-%m-%d %H:%M:%S'), 'pair': pair, 'setup_id': 9, 'setup_name': '🔄 Breaker Block Retest', 'direction': 'BUY', 'entry': round(entry, 5), 'sl': round(sl, 5), 'tp': round(entry + min_rr*risk, 5), 'rr': min_rr, 'sl_pips': round(risk/pip_size, 1), 'spread_pips': round(df['spread_pips'].iloc[i], 1)})
        elif len(bear_rows) and ftype == -1 and ob_t == -1 and bias == -1:
            if not _has_displacement(df, i, "SELL"):
                continue
            b_top = float(bear_rows['breaker_top'].iloc[-1])
            b_bot = float(bear_rows['breaker_bottom'].iloc[-1])
            if np.isnan(b_top) or np.isnan(b_bot):
                continue
            entry = (b_top + b_bot) / 2.0
            if abs(close - entry) > retest_tol and abs(float(df['high'].iloc[i]) - entry) > retest_tol:
                continue
            sl = b_top + (3.5 * pip_size)
            risk = sl - entry
            if risk > (2.0 * pip_size) and risk < (40.0 * pip_size):
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
        sweep_dir, _lvl, sweep_ext, sweep_q = _last_sweep_info(df, i, lookback=6)
        if sweep_dir == 0 or np.isnan(sweep_ext) or sweep_q < 2:
            continue
        
        ftype = df['fvg_type'].iloc[i]
        ob_t = df['ob_type'].iloc[i] if 'ob_type' in df.columns else 0
        bias = df['master_bias'].iloc[i]

        if sweep_dir == 1 and ftype == 1 and ob_t == 1 and bias == 1:
            if not _has_displacement(df, i, "BUY") or not _fvg_still_valid(df, i, "BUY"):
                continue
            entry = (df['fvg_top'].iloc[i] + df['fvg_bottom'].iloc[i]) / 2.0
            sl = sweep_ext - (3.5 * pip_size)
            risk = entry - sl
            if risk > (2.0 * pip_size) and risk < (40.0 * pip_size):
                signals.append({'timestamp': df.index[i].strftime('%Y-%m-%d %H:%M:%S'), 'pair': pair, 'setup_id': 10, 'setup_name': '📈 AMD / Power of 3', 'direction': 'BUY', 'entry': round(entry, 5), 'sl': round(sl, 5), 'tp': round(entry + min_rr*risk, 5), 'rr': min_rr, 'sl_pips': round(risk/pip_size, 1), 'spread_pips': round(df['spread_pips'].iloc[i], 1)})
        elif sweep_dir == -1 and ftype == -1 and ob_t == -1 and bias == -1:
            if not _has_displacement(df, i, "SELL") or not _fvg_still_valid(df, i, "SELL"):
                continue
            entry = (df['fvg_top'].iloc[i] + df['fvg_bottom'].iloc[i]) / 2.0
            sl = sweep_ext + (3.5 * pip_size)
            risk = sl - entry
            if risk > (2.0 * pip_size) and risk < (40.0 * pip_size):
                signals.append({'timestamp': df.index[i].strftime('%Y-%m-%d %H:%M:%S'), 'pair': pair, 'setup_id': 10, 'setup_name': '📈 AMD / Power of 3', 'direction': 'SELL', 'entry': round(entry, 5), 'sl': round(sl, 5), 'tp': round(entry - min_rr*risk, 5), 'rr': min_rr, 'sl_pips': round(risk/pip_size, 1), 'spread_pips': round(df['spread_pips'].iloc[i], 1)})
    return signals

SETUP_GENERATORS = {
    1: generate_signals_setup_1,
    2: generate_signals_setup_2,
    3: generate_signals_setup_3,
    4: generate_signals_setup_4,
    5: generate_signals_setup_5,
    6: generate_signals_setup_6,
    9: generate_signals_setup_9,
    10: generate_signals_setup_10,
}

# Preference when multiple setups share one liquidity event (first wins after sort)
SETUP_PRIORITY = {1: 0, 4: 1, 10: 2, 2: 3, 3: 4, 5: 5, 6: 6, 9: 7}


def get_all_setup_signals(
    df: pd.DataFrame,
    pair: str,
    min_rr: float = 2.0,
    active_setups: List[int] = None,
    return_indicators: bool = False,
    use_narrative: bool = True,
    rejections: List[Dict[str, Any]] = None,
):
    """
    Run indicators and generate signals for active setups.
    When use_narrative=True (default), apply event/narrative 10Q gates and
    one-trade-per-liquidity-event dedupe.
    """
    from backend.engine.event_engine import build_events
    from backend.engine.narrative import validate_trade

    df_ind = run_all_indicators(df, pair)
    if active_setups is None:
        active_setups = [1, 2, 3, 4, 5, 6, 9, 10]

    raw: List[Dict[str, Any]] = []
    for setup_id in active_setups:
        gen = SETUP_GENERATORS.get(int(setup_id))
        if gen is None:
            continue
        raw.extend(gen(df_ind, pair, min_rr))

    raw.sort(
        key=lambda x: (
            x["timestamp"],
            SETUP_PRIORITY.get(int(x["setup_id"]), 99),
        )
    )

    if not use_narrative:
        if return_indicators:
            return raw, df_ind
        return raw

    events = build_events(df_ind, pair=pair)
    pip_size = get_pip_size(pair)
    try:
        labels = df_ind.index.strftime("%Y-%m-%d %H:%M:%S")
        time_to_idx = {t: i for i, t in enumerate(labels)}
    except Exception:
        time_to_idx = {
            t.strftime("%Y-%m-%d %H:%M:%S"): i for i, t in enumerate(df_ind.index)
        }

    used_events: set = set()
    accepted: List[Dict[str, Any]] = []

    for sig in raw:
        ts = sig["timestamp"]
        if ts not in time_to_idx:
            continue
        i = time_to_idx[ts]
        sid = int(sig["setup_id"])
        v = validate_trade(
            df_ind,
            i,
            sig["direction"],
            float(sig["entry"]),
            float(sig["sl"]),
            min_rr=min_rr,
            events=events,
            used_event_ids=used_events,
            require_mss=(sid == 4),
            require_raid_ab=True,
            pip_size=pip_size,
        )
        if not v.ok:
            if rejections is not None:
                rejections.append(
                    {
                        **sig,
                        "rejection_reason": v.reason,
                        "raid_grade": v.narrative.raid_grade if v.narrative else None,
                        "narrative": {
                            "raid_grade": v.narrative.raid_grade if v.narrative else None,
                            "liquidity_event_id": v.narrative.liquidity_event_id
                            if v.narrative
                            else None,
                        },
                    }
                )
            continue
        sig = dict(sig)
        sig["tp"] = round(v.tp, 5)
        sig["rr"] = min_rr
        sig["event_id"] = v.event_id
        sig["raid_grade"] = v.narrative.raid_grade if v.narrative else None
        sig["session"] = v.narrative.session if v.narrative else None
        if v.event_id:
            used_events.add(v.event_id)
        accepted.append(sig)

    if return_indicators:
        return accepted, df_ind
    return accepted
