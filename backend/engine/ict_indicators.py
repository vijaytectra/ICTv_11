import pandas as pd
import numpy as np
from typing import List, Dict, Any, Tuple, Optional

from backend.engine.kz_tables import (
    KZ_TABLES,
    DEFAULT_KZ_TABLE,
    GEOMETRY_LOCK_VERSION,
    in_window,
    resolve_kz_table,
)

def find_swing_points(df: pd.DataFrame, window: int = 5) -> pd.DataFrame:
    """
    Identifies Swing Highs and Swing Lows (Pivots) strictly causally in 100% vectorized pandas.
    A swing high at candle (k - window) requires 'window' subsequent candles to close below it.
    Therefore, the swing point becomes KNOWN and ACTIVE only at candle index k.
    """
    df = df.copy()
    highs = df['high']
    lows = df['low']
    
    full_win = 2 * window + 1
    roll_max = highs.rolling(window=full_win, min_periods=full_win).max()
    roll_min = lows.rolling(window=full_win, min_periods=full_win).min()
    
    p_high_shifted = highs.shift(window)
    p_low_shifted = lows.shift(window)
    
    is_sh = (p_high_shifted == roll_max) & (p_high_shifted > highs.shift(1))
    is_sl = (p_low_shifted == roll_min) & (p_low_shifted < lows.shift(1))
    
    df['swing_high'] = np.where(is_sh, p_high_shifted, np.nan)
    df['swing_low'] = np.where(is_sl, p_low_shifted, np.nan)
    return df

def find_htf_structure_and_bias(df: pd.DataFrame) -> pd.DataFrame:
    """
    Computes 1H Higher Timeframe Market Structure (HTF Swings, HTF BOS/MSS) causally.
    Aggregates 5m data into completed 1H candles and projects HTF bias down to 5m.
    1 = Bullish HTF Bias, -1 = Bearish HTF Bias, 0 = Neutral
    """
    df = df.copy()
    if 'swing_high' not in df.columns:
        df = find_swing_points(df, window=5)
        
    df_1h = df.resample('1h').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last'
    }).dropna()
    
    if len(df_1h) < 20:
        df['htf_bias'] = 0
        return df
        
    df_1h = find_swing_points(df_1h, window=3)
    
    sh_1h = df_1h['swing_high'].ffill()
    sl_1h = df_1h['swing_low'].ffill()
    h_closes = df_1h['close']
    
    bias_series = np.where(h_closes > sh_1h, 1, np.where(h_closes < sl_1h, -1, 0))
    df_1h['htf_bias_1h'] = pd.Series(bias_series, index=df_1h.index).replace(0, np.nan).ffill().fillna(0).astype(int)
    
    df_1h_shifted = df_1h[['htf_bias_1h']].shift(1)
    df = df.join(df_1h_shifted, how='left')
    df['htf_bias'] = df['htf_bias_1h'].ffill().fillna(0).astype(int)
    df.drop(columns=['htf_bias_1h'], inplace=True, errors='ignore')
    return df

def find_institutional_liquidity_pools(
    df: pd.DataFrame,
    pip_size: float = 0.0001,
    kz_table: Optional[str] = None,
) -> pd.DataFrame:
    """
    Identifies Major Institutional Liquidity Pools causally in ultra-fast vectorized pandas:
    - Previous Day High (PDH) & Previous Day Low (PDL)
    - Asian Session High (ASH) & Asian Session Low (ASL)
    - London Session High (LSH) & London Session Low (LSL)
    - Equal Highs (EQH) & Equal Lows (EQL) within 1.5 pips

    Asian / London pool windows follow active kz_table (default mentorship_2017).
    """
    df = df.copy()
    times = df.index
    table_name = resolve_kz_table(kz_table)
    profile = KZ_TABLES[table_name]
    df.attrs["kz_table"] = table_name
    df.attrs["geometry_lock_version"] = GEOMETRY_LOCK_VERSION

    if getattr(times, "tz", None) is not None:
        ny = times.tz_convert("America/New_York")
        hours = ny.hour + (ny.minute / 60.0)
    else:
        hours = times.hour + (times.minute / 60.0)

    daily_df = df.resample('1D').agg({'high': 'max', 'low': 'min'}).shift(1)
    df['pdh'] = df.index.normalize().map(daily_df['high']).astype(float)
    df['pdl'] = df.index.normalize().map(daily_df['low']).astype(float)

    a_start, a_end = profile["asian"]
    is_asian = in_window(hours, a_start, a_end, wrap=bool(profile.get("asian_wrap")))
    # For wrap ranges like 20–24, also include 00:00–00:00 edge of next calendar day
    # already covered by hour>=20. Mentorship Asia ends at midnight.
    lp_start, lp_end = profile["london_pool"]
    is_london = in_window(hours, lp_start, lp_end, wrap=False)

    # Causal expanding session pools via groupby.cummax/cummin (no future leak)
    # For Asia 20–00, pool day key = session start date (if hour>=20 use today, else prior day)
    if profile.get("asian_wrap") and a_start >= 12:
        # session date: before a_start → previous calendar day
        ny_dates = pd.Series(
            (times.tz_convert("America/New_York").date if getattr(times, "tz", None) else times.date),
            index=times,
        )
        # bars in wrap Asia after midnight (hour < a_end if wrap end < start) — mentorship ends at 24
        session_dates = ny_dates
        if a_end < 24 and profile.get("asian_wrap"):
            # midnight continuation would use prior day — not used for mentorship 20–24
            pass
    else:
        session_dates = pd.Series(
            (times.tz_convert("America/New_York").date if getattr(times, "tz", None) else times.date),
            index=times,
        )
    dates = session_dates
    high_s = pd.Series(df["high"].values, index=times)
    low_s = pd.Series(df["low"].values, index=times)
    ash_raw = high_s.where(is_asian)
    asl_raw = low_s.where(is_asian)
    lsh_raw = high_s.where(is_london)
    lsl_raw = low_s.where(is_london)
    df["ash"] = ash_raw.groupby(dates).cummax().groupby(dates).ffill()
    df["asl"] = asl_raw.groupby(dates).cummin().groupby(dates).ffill()
    df["lsh"] = lsh_raw.groupby(dates).cummax().groupby(dates).ffill()
    df["lsl"] = lsl_raw.groupby(dates).cummin().groupby(dates).ffill()
    eq_tol = 1.5 * pip_size
    sh_s = df['swing_high'] if 'swing_high' in df.columns else pd.Series(np.nan, index=times)
    sl_s = df['swing_low'] if 'swing_low' in df.columns else pd.Series(np.nan, index=times)
    
    sh_valid = sh_s.dropna()
    sl_valid = sl_s.dropna()
    
    if len(sh_valid) >= 2:
        sh_diff = (sh_valid - sh_valid.shift(1)).abs()
        is_eqh = sh_diff <= eq_tol
        df['eqh'] = sh_valid.where(is_eqh)
    else:
        df['eqh'] = np.nan
        
    if len(sl_valid) >= 2:
        sl_diff = (sl_valid - sl_valid.shift(1)).abs()
        is_eql = sl_diff <= eq_tol
        df['eql'] = sl_valid.where(is_eql)
    else:
        df['eql'] = np.nan

    return df

def find_displacement_and_expansion(df: pd.DataFrame, atr_period: int = 20) -> pd.DataFrame:
    """Computes Displacement & Energetic Expansion metrics causally."""
    df = df.copy()
    opens = df['open'].values
    highs = df['high'].values
    lows = df['low'].values
    closes = df['close'].values
    
    body = np.abs(closes - opens)
    rng = np.maximum(highs - lows, 1e-6)
    
    body_ratio = body / rng
    
    tr = np.maximum(highs - lows, np.maximum(np.abs(highs - np.roll(closes, 1)), np.abs(lows - np.roll(closes, 1))))
    tr[0] = highs[0] - lows[0]
    atr = pd.Series(tr).rolling(window=atr_period, min_periods=atr_period).mean().values
    atr = np.where(np.isnan(atr) | (atr == 0), 1e-5, atr)
    
    rel_body_size = body / atr
    has_displacement = (body_ratio >= 0.60) & (rel_body_size >= 1.5)
    
    df['body_ratio'] = body_ratio
    df['rel_body_size'] = rel_body_size
    df['has_displacement'] = has_displacement
    return df

def find_premium_discount_zones(df: pd.DataFrame, lookback: int = 40) -> pd.DataFrame:
    """Calculates Premium vs Discount dealing range causally."""
    df = df.copy()
    highs = df['high'].values
    lows = df['low'].values
    closes = df['close'].values
    
    h_max = pd.Series(highs).rolling(window=lookback, min_periods=lookback).max().shift(1).values
    l_min = pd.Series(lows).rolling(window=lookback, min_periods=lookback).min().shift(1).values
    eq = (h_max + l_min) / 2.0
    
    df['eq_level'] = eq
    df['is_discount'] = closes < eq
    df['is_premium'] = closes > eq
    return df

def find_fair_value_gaps(
    df: pd.DataFrame,
    min_gap_pips: float = 2.0,
    pip_size: float = 0.0001,
    fvg_require_displacement_candle: bool = True,
) -> pd.DataFrame:
    """Detects Bullish & Bearish Fair Value Gaps (FVG) at candle close i (Vectorized).

    Locked FVG=B (geometry lock H):
      3-candle wick gap (bar i = candle 3):
        Bullish: low[i] > high[i-2]  → gap [high[i-2], low[i]]
        Bearish: high[i] < low[i-2]  → gap [high[i], low[i-2]]
      Middle candle (i-1) must be displacement when fvg_require_displacement_candle=True.
      fvg_ce = (top + bottom) / 2
    """
    df = df.copy()
    highs = df['high'].values
    lows = df['low'].values
    n = len(df)

    fvg_type = np.zeros(n, dtype=int)
    fvg_top = np.full(n, np.nan)
    fvg_bottom = np.full(n, np.nan)
    fvg_size_pips = np.zeros(n)
    fvg_ce = np.full(n, np.nan)

    min_gap_val = min_gap_pips * pip_size
    high_i2 = np.roll(highs, 2)
    low_i2 = np.roll(lows, 2)

    bull_gap = lows - high_i2
    bull_mask = bull_gap >= min_gap_val
    bull_mask[:2] = False

    bear_gap = low_i2 - highs
    bear_mask = bear_gap >= min_gap_val
    bear_mask[:2] = False

    if fvg_require_displacement_candle:
        if "has_displacement" in df.columns:
            mid_disp = np.roll(df["has_displacement"].astype(bool).values, 1)
            mid_disp[0] = False
        else:
            # fallback: middle candle body ≥ 60% of range
            opens = df["open"].values
            closes = df["close"].values
            body = np.abs(closes - opens)
            rng = np.maximum(highs - lows, 1e-12)
            mid_ok = np.roll(body / rng >= 0.60, 1)
            mid_ok[0] = False
            mid_disp = mid_ok
        bull_mask = bull_mask & mid_disp
        bear_mask = bear_mask & mid_disp

    fvg_type[bull_mask] = 1
    fvg_top[bull_mask] = lows[bull_mask]
    fvg_bottom[bull_mask] = high_i2[bull_mask]
    fvg_size_pips[bull_mask] = bull_gap[bull_mask] / pip_size

    fvg_type[bear_mask] = -1
    fvg_top[bear_mask] = low_i2[bear_mask]
    fvg_bottom[bear_mask] = highs[bear_mask]
    fvg_size_pips[bear_mask] = bear_gap[bear_mask] / pip_size

    created = fvg_type != 0
    fvg_ce[created] = (fvg_top[created] + fvg_bottom[created]) / 2.0

    df['fvg_type'] = fvg_type
    df['fvg_top'] = fvg_top
    df['fvg_bottom'] = fvg_bottom
    df['fvg_size_pips'] = fvg_size_pips
    df['fvg_ce'] = fvg_ce
    df.attrs["fvg_require_displacement_candle"] = fvg_require_displacement_candle
    return annotate_fvg_lifecycle(df)


def annotate_fvg_lifecycle(df: pd.DataFrame, max_lookforward: int = 200) -> pd.DataFrame:
    """
    Causal FVG lifecycle after creation (bar close only):
      mitigated  = first touch of CE (wick or body)
      invalidated = body close through far side (not mitigation)
    Marks events on the bar where they first occur.
    """
    df = df.copy()
    n = len(df)
    highs = df["high"].values
    lows = df["low"].values
    closes = df["close"].values
    fvg_type = df["fvg_type"].values.astype(int)
    fvg_top = df["fvg_top"].values
    fvg_bottom = df["fvg_bottom"].values
    fvg_ce = df["fvg_ce"].values if "fvg_ce" in df.columns else (fvg_top + fvg_bottom) / 2.0

    mit = np.zeros(n, dtype=bool)
    inv = np.zeros(n, dtype=bool)
    # state columns on creation bar: eventually filled when known (causal forward scan only)
    state = np.array([""] * n, dtype=object)

    open_fvgs: List[Dict[str, Any]] = []
    for i in range(n):
        if fvg_type[i] != 0 and not np.isnan(fvg_ce[i]):
            open_fvgs.append(
                {
                    "idx": i,
                    "dir": int(fvg_type[i]),
                    "top": float(fvg_top[i]),
                    "bot": float(fvg_bottom[i]),
                    "ce": float(fvg_ce[i]),
                    "done": False,
                }
            )
        still = []
        for fv in open_fvgs:
            if fv["done"] or i <= fv["idx"]:
                if not fv["done"]:
                    still.append(fv)
                continue
            if i - fv["idx"] > max_lookforward:
                still.append(fv)
                continue
            d = fv["dir"]
            ce = fv["ce"]
            # mitigation: first CE touch
            if (lows[i] <= ce <= highs[i]) and state[fv["idx"]] == "":
                mit[i] = True
                state[fv["idx"]] = "mitigated"
                fv["done"] = True
                still.append(fv)
                continue
            # invalidation: far-side body close
            if d == 1 and closes[i] < fv["bot"]:
                inv[i] = True
                if state[fv["idx"]] == "":
                    state[fv["idx"]] = "invalidated"
                fv["done"] = True
                still.append(fv)
                continue
            if d == -1 and closes[i] > fv["top"]:
                inv[i] = True
                if state[fv["idx"]] == "":
                    state[fv["idx"]] = "invalidated"
                fv["done"] = True
                still.append(fv)
                continue
            still.append(fv)
        open_fvgs = [f for f in still if not f["done"]]

    df["fvg_mitigated"] = mit
    df["fvg_invalidated"] = inv
    df["fvg_lifecycle_state"] = state
    return df

def find_inverted_fvgs(df: pd.DataFrame, fvg_history_lookback: int = 50) -> pd.DataFrame:
    """Identifies Inverted Fair Value Gaps (IFVG) causally."""
    df = df.copy()
    if 'fvg_type' not in df.columns:
        df = find_fair_value_gaps(df)
        
    closes = df['close'].values
    n = len(df)
    
    ifvg_type = np.zeros(n, dtype=int)
    ifvg_top = np.full(n, np.nan)
    ifvg_bottom = np.full(n, np.nan)
    
    fvg_indices = np.where(df['fvg_type'].values != 0)[0]
    
    for i in fvg_indices:
        ftype = df['fvg_type'].iloc[i]
        ftop = df['fvg_top'].iloc[i]
        fbot = df['fvg_bottom'].iloc[i]
        
        for j in range(i + 1, min(n, i + fvg_history_lookback)):
            c = closes[j]
            if ftype == -1 and c > ftop:
                ifvg_type[j] = 1
                ifvg_top[j] = ftop
                ifvg_bottom[j] = fbot
                break
            elif ftype == 1 and c < fbot:
                ifvg_type[j] = -1
                ifvg_top[j] = ftop
                ifvg_bottom[j] = fbot
                break
                
    df['ifvg_type'] = ifvg_type
    df['ifvg_top'] = ifvg_top
    df['ifvg_bottom'] = ifvg_bottom
    return df

def find_liquidity_sweeps(df: pd.DataFrame, lookback: int = 50) -> pd.DataFrame:
    """Identifies Buy-Side Liquidity (BSL) and Sell-Side Liquidity (SSL) sweeps causally (Vectorized)."""
    df = df.copy()
    if 'swing_high' not in df.columns:
        df = find_swing_points(df)
        
    highs = df['high'].values
    lows = df['low'].values
    closes = df['close'].values
    n = len(df)
    
    sweep_type = np.zeros(n, dtype=int)
    sweep_level = np.full(n, np.nan)
    sweep_quality = np.zeros(n, dtype=int)
    
    c_pdh = df['pdh'].values if 'pdh' in df.columns else np.full(n, np.nan)
    c_pdl = df['pdl'].values if 'pdl' in df.columns else np.full(n, np.nan)
    # Shift session pools by 1: expanding ash/asl already includes bar i, which
    # makes same-bar sweeps of the session extreme impossible / look-ahead-ish.
    c_ash = pd.Series(df['ash'].values if 'ash' in df.columns else np.full(n, np.nan)).shift(1).values
    c_asl = pd.Series(df['asl'].values if 'asl' in df.columns else np.full(n, np.nan)).shift(1).values
    
    ssl_pd_sweep = (~np.isnan(c_pdl)) & (lows < c_pdl) & (closes > c_pdl)
    ssl_as_sweep = (~np.isnan(c_asl)) & (lows < c_asl) & (closes > c_asl)
    
    bsl_pd_sweep = (~np.isnan(c_pdh)) & (highs > c_pdh) & (closes < c_pdh)
    bsl_as_sweep = (~np.isnan(c_ash)) & (highs > c_ash) & (closes < c_ash)
    
    sweep_extreme = np.full(n, np.nan)  # wick extreme of the sweep candle (for SL)

    sweep_type[ssl_pd_sweep] = 1
    sweep_level[ssl_pd_sweep] = c_pdl[ssl_pd_sweep]
    sweep_extreme[ssl_pd_sweep] = lows[ssl_pd_sweep]
    sweep_quality[ssl_pd_sweep] = 2

    m_ssl_as = ssl_as_sweep & (sweep_type == 0)
    sweep_type[m_ssl_as] = 1
    sweep_level[m_ssl_as] = c_asl[m_ssl_as]
    sweep_extreme[m_ssl_as] = lows[m_ssl_as]
    sweep_quality[m_ssl_as] = 2

    sweep_type[bsl_pd_sweep] = -1
    sweep_level[bsl_pd_sweep] = c_pdh[bsl_pd_sweep]
    sweep_extreme[bsl_pd_sweep] = highs[bsl_pd_sweep]
    sweep_quality[bsl_pd_sweep] = 2

    m_bsl_as = bsl_as_sweep & (sweep_type == 0)
    sweep_type[m_bsl_as] = -1
    sweep_level[m_bsl_as] = c_ash[m_bsl_as]
    sweep_extreme[m_bsl_as] = highs[m_bsl_as]
    sweep_quality[m_bsl_as] = 2
    
    sw_l = pd.Series(df['swing_low'].values).ffill().shift(1).values
    sw_h = pd.Series(df['swing_high'].values).ffill().shift(1).values
    
    minor_ssl = (sweep_type == 0) & (~np.isnan(sw_l)) & (lows < sw_l) & (closes > sw_l)
    minor_bsl = (sweep_type == 0) & (~np.isnan(sw_h)) & (highs > sw_h) & (closes < sw_h)
    
    sweep_type[minor_ssl] = 1
    sweep_level[minor_ssl] = sw_l[minor_ssl]
    sweep_extreme[minor_ssl] = lows[minor_ssl]
    sweep_quality[minor_ssl] = 1
    
    sweep_type[minor_bsl] = -1
    sweep_level[minor_bsl] = sw_h[minor_bsl]
    sweep_extreme[minor_bsl] = highs[minor_bsl]
    sweep_quality[minor_bsl] = 1
    
    df['sweep_type'] = sweep_type
    df['sweep_level'] = sweep_level
    df['sweep_extreme'] = sweep_extreme
    df['sweep_quality'] = sweep_quality
    return df

def find_order_blocks(df: pd.DataFrame, lookback: int = 8) -> pd.DataFrame:
    """Identifies Bullish and Bearish Order Blocks (OB) causally at candle i close (Vectorized)."""
    df = df.copy()
    opens = df['open'].values
    highs = df['high'].values
    lows = df['low'].values
    closes = df['close'].values
    n = len(df)
    
    ob_type = np.zeros(n, dtype=int)
    ob_top = np.full(n, np.nan)
    ob_bottom = np.full(n, np.nan)
    
    body = np.abs(closes - opens)
    avg_body = pd.Series(body).rolling(window=lookback, min_periods=lookback).mean().values
    
    is_bull_expansion = (closes > opens) & (body > 1.5 * avg_body)
    is_bear_expansion = (closes < opens) & (body > 1.5 * avg_body)
    
    is_bear_candle = (closes < opens)
    is_bull_candle = (closes > opens)
    
    for i in np.where(is_bull_expansion)[0]:
        if i < lookback: continue
        for j in range(i - 1, max(-1, i - lookback), -1):
            if is_bear_candle[j]:
                ob_type[i] = 1
                ob_top[i] = max(opens[j], closes[j])
                ob_bottom[i] = lows[j]
                break
                
    for i in np.where(is_bear_expansion)[0]:
        if i < lookback: continue
        for j in range(i - 1, max(-1, i - lookback), -1):
            if is_bull_candle[j]:
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
    
    breaker_type = np.zeros(n, dtype=int)
    breaker_top = np.full(n, np.nan)
    breaker_bottom = np.full(n, np.nan)
    
    ob_indices = np.where(df['ob_type'].values != 0)[0]
    
    for i in ob_indices:
        otype = df['ob_type'].iloc[i]
        otop = df['ob_top'].iloc[i]
        obot = df['ob_bottom'].iloc[i]
        
        for j in range(i + 1, min(n, i + lookback)):
            c_close = closes[j]
            if otype == -1 and c_close > otop:
                breaker_type[j] = 1
                breaker_top[j] = otop
                breaker_bottom[j] = obot
                break
            elif otype == 1 and c_close < obot:
                breaker_type[j] = -1
                breaker_top[j] = otop
                breaker_bottom[j] = obot
                break
                
    df['breaker_type'] = breaker_type
    df['breaker_top'] = breaker_top
    df['breaker_bottom'] = breaker_bottom
    return df

def find_ote_zones(df: pd.DataFrame, lookback: int = 30) -> pd.DataFrame:
    """Identifies Optimal Trade Entry (OTE) Fib Retracement Zones causally (Vectorized)."""
    df = df.copy()
    highs = df['high'].values
    lows = df['low'].values
    closes = df['close'].values
    n = len(df)
    
    max_h = pd.Series(highs).rolling(window=lookback, min_periods=lookback).max().shift(1).values
    min_l = pd.Series(lows).rolling(window=lookback, min_periods=lookback).min().shift(1).values
    rng = max_h - min_l
    
    bull_618 = max_h - (0.618 * rng)
    bull_786 = max_h - (0.786 * rng)
    
    bear_618 = min_l + (0.618 * rng)
    bear_786 = min_l + (0.786 * rng)
    
    ote_type = np.zeros(n, dtype=int)
    ote_type[(rng > 0) & (closes >= bull_786) & (closes <= bull_618)] = 1
    ote_type[(rng > 0) & (closes >= bear_618) & (closes <= bear_786)] = -1
    
    df['ote_type'] = ote_type
    df['ote_618'] = np.where(ote_type == 1, bull_618, np.where(ote_type == -1, bear_618, np.nan))
    df['ote_705'] = np.where(ote_type == 1, max_h - (0.705 * rng), np.where(ote_type == -1, min_l + (0.705 * rng), np.nan))
    df['ote_786'] = np.where(ote_type == 1, bull_786, np.where(ote_type == -1, bear_786, np.nan))
    return df

def tag_killzones(df: pd.DataFrame, kz_table: Optional[str] = None) -> pd.DataFrame:
    """Tags ICT session killzone windows on America/New_York clock (index must be NY).

    Default kz_table=mentorship_2017 (Gap Closure H lock).
    """
    df = df.copy()
    times = df.index
    table_name = resolve_kz_table(kz_table or df.attrs.get("kz_table"))
    profile = KZ_TABLES[table_name]
    df.attrs["kz_table"] = table_name

    if getattr(times, "tz", None) is not None:
        hours = times.tz_convert("America/New_York").hour + (
            times.tz_convert("America/New_York").minute / 60.0
        )
    else:
        hours = times.hour + (times.minute / 60.0)

    a_start, a_end = profile["asian"]
    df["is_asian_range"] = in_window(hours, a_start, a_end, wrap=bool(profile.get("asian_wrap")))

    l_start, l_end = profile["london_kz"]
    df["is_london_kz"] = in_window(hours, l_start, l_end, wrap=False)

    n_start, n_end = profile["ny_kz"]
    df["is_ny_kz"] = in_window(hours, n_start, n_end, wrap=False)

    sb_mask = np.zeros(len(df), dtype=bool)
    for s_start, s_end in profile["sb"]:
        sb_mask |= in_window(hours, s_start, s_end, wrap=False)
    # Named SB flags for attribution (first three windows)
    sb_wins = profile["sb"]
    df["is_sb_london"] = in_window(hours, sb_wins[0][0], sb_wins[0][1]) if len(sb_wins) > 0 else False
    df["is_sb_ny_am"] = in_window(hours, sb_wins[1][0], sb_wins[1][1]) if len(sb_wins) > 1 else False
    df["is_sb_ny_pm"] = in_window(hours, sb_wins[2][0], sb_wins[2][1]) if len(sb_wins) > 2 else False
    df["is_silver_bullet"] = sb_mask
    return df
