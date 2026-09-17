import os
import sys
import pandas as pd
import numpy as np

sys.path.insert(0, r"C:\personal\ICT_v11")

from backend.engine.data_loader import load_pair_data, resample_candles, get_pip_size
from backend.engine.ict_indicators import (
    find_swing_points, find_fair_value_gaps, find_inverted_fvgs,
    find_liquidity_sweeps, find_order_blocks, find_breaker_blocks,
    find_ote_zones, tag_killzones
)

data_dir = r"C:\Users\Vijayakumar R\Documents"

def add_master_htf_confluence(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df['ema_fast'] = df['close'].ewm(span=50, adjust=False).mean()
    df['ema_slow'] = df['close'].ewm(span=200, adjust=False).mean()
    df['master_bias'] = np.where(
        (df['close'] > df['ema_fast']) & (df['ema_fast'] > df['ema_slow']), 1,
        np.where((df['close'] < df['ema_fast']) & (df['ema_fast'] < df['ema_slow']), -1, 0)
    )
    return df

def run_indicators(df: pd.DataFrame, pair: str) -> pd.DataFrame:
    pip_size = get_pip_size(pair)
    df = find_swing_points(df, window=5)
    df = find_fair_value_gaps(df, min_gap_pips=2.5, pip_size=pip_size)
    df = find_inverted_fvgs(df)
    df = find_liquidity_sweeps(df, lookback=50)
    df = find_order_blocks(df, lookback=8)
    df = find_breaker_blocks(df, lookback=30)
    df = find_ote_zones(df, lookback=30)
    df = tag_killzones(df)
    df = add_master_htf_confluence(df)
    return df

def generate_signals_all_80plus(df: pd.DataFrame, pair: str, min_rr: float = 2.0):
    pip_size = get_pip_size(pair)
    signals = []
    n = len(df)
    
    is_london = df['is_london_kz'].values
    is_ny = df['is_ny_kz'].values
    is_sb = df['is_silver_bullet'].values
    bias_arr = df['master_bias'].values
    sweep_type = df['sweep_type'].values
    sweep_level = df['sweep_level'].values
    fvg_type = df['fvg_type'].values
    fvg_top = df['fvg_top'].values
    fvg_bottom = df['fvg_bottom'].values
    ifvg_type = df['ifvg_type'].values
    ifvg_top = df['ifvg_top'].values
    ifvg_bottom = df['ifvg_bottom'].values
    ob_type = df['ob_type'].values
    ob_top = df['ob_top'].values
    ob_bottom = df['ob_bottom'].values
    breaker_type = df['breaker_type'].values
    breaker_top = df['breaker_top'].values
    breaker_bottom = df['breaker_bottom'].values
    spread = df['spread_pips'].values if 'spread_pips' in df.columns else np.zeros(n)
    low_arr = df['low'].values
    high_arr = df['high'].values
    timestamps = df.index.strftime('%Y-%m-%d %H:%M:%S').values
    
    for i in range(15, n):
        is_kz = is_london[i] or is_ny[i] or is_sb[i]
        bias = bias_arr[i]
        if not is_kz or bias == 0: continue
        
        recent_sweeps = sweep_type[max(0, i-3):i+1]
        has_sweep = (recent_sweeps != 0).any()
        if has_sweep:
            sweep_indices = np.where(recent_sweeps != 0)[0]
            last_sw_idx = max(0, i-3) + sweep_indices[-1]
            s_dir = sweep_type[last_sw_idx]
            s_lvl = sweep_level[last_sw_idx]
        else:
            s_dir, s_lvl = 0, np.nan
            
        ftype = fvg_type[i]
        ifvg_t = ifvg_type[i]
        ob_t = ob_type[i]
        btype = breaker_type[i]
        
        ote_type = df['ote_type'].values
        
        # Setup 1: Sweep + FVG 50% CE + OTE Fib 61.8%+ Confluence
        if s_dir == 1 and ftype == 1 and ote_type[i] == 1 and bias == 1:
            entry = (fvg_top[i] + fvg_bottom[i]) / 2.0
            sl_base = ob_bottom[i] if not np.isnan(ob_bottom[i]) else fvg_bottom[i]
            sl = sl_base - (3.5 * pip_size)
            risk = entry - sl
            if risk > (2.0 * pip_size):
                signals.append({'timestamp': str(timestamps[i]), 'pair': pair, 'setup_id': 1, 'setup_name': 'Liquidity Sweep + FVG', 'direction': 'BUY', 'entry': round(entry, 5), 'sl': round(sl, 5), 'tp': round(entry + min_rr*risk, 5), 'rr': min_rr, 'sl_pips': round(risk/pip_size, 1), 'spread_pips': round(spread[i], 1)})
        elif s_dir == -1 and ftype == -1 and ote_type[i] == -1 and bias == -1:
            entry = (fvg_top[i] + fvg_bottom[i]) / 2.0
            sl_base = ob_top[i] if not np.isnan(ob_top[i]) else fvg_top[i]
            sl = sl_base + (3.5 * pip_size)
            risk = sl - entry
            if risk > (2.0 * pip_size):
                signals.append({'timestamp': str(timestamps[i]), 'pair': pair, 'setup_id': 1, 'setup_name': 'Liquidity Sweep + FVG', 'direction': 'SELL', 'entry': round(entry, 5), 'sl': round(sl, 5), 'tp': round(entry - min_rr*risk, 5), 'rr': min_rr, 'sl_pips': round(risk/pip_size, 1), 'spread_pips': round(spread[i], 1)})

        # Setup 2: Sweep + IFVG 50% CE
        if ifvg_t == 1 and bias == 1:
            entry = (ifvg_top[i] + ifvg_bottom[i]) / 2.0
            sl_base = ob_bottom[i] if not np.isnan(ob_bottom[i]) else ifvg_bottom[i]
            sl = sl_base - (3.5 * pip_size)
            risk = entry - sl
            if risk > (2.0 * pip_size):
                signals.append({'timestamp': str(timestamps[i]), 'pair': pair, 'setup_id': 2, 'setup_name': 'Liquidity Sweep + IFVG', 'direction': 'BUY', 'entry': round(entry, 5), 'sl': round(sl, 5), 'tp': round(entry + min_rr*risk, 5), 'rr': min_rr, 'sl_pips': round(risk/pip_size, 1), 'spread_pips': round(spread[i], 1)})
        elif ifvg_t == -1 and bias == -1:
            entry = (ifvg_top[i] + ifvg_bottom[i]) / 2.0
            sl_base = ob_top[i] if not np.isnan(ob_top[i]) else ifvg_top[i]
            sl = sl_base + (3.5 * pip_size)
            risk = sl - entry
            if risk > (2.0 * pip_size):
                signals.append({'timestamp': str(timestamps[i]), 'pair': pair, 'setup_id': 2, 'setup_name': 'Liquidity Sweep + IFVG', 'direction': 'SELL', 'entry': round(entry, 5), 'sl': round(sl, 5), 'tp': round(entry - min_rr*risk, 5), 'rr': min_rr, 'sl_pips': round(risk/pip_size, 1), 'spread_pips': round(spread[i], 1)})

        # Setup 3: Silver Bullet FVG 50% CE + OTE Fib Confluence
        if is_sb[i] and ftype == 1 and ote_type[i] == 1 and bias == 1:
            entry = (fvg_top[i] + fvg_bottom[i]) / 2.0
            sl_base = ob_bottom[i] if not np.isnan(ob_bottom[i]) else fvg_bottom[i]
            sl = sl_base - (3.5 * pip_size)
            risk = entry - sl
            if risk > (2.0 * pip_size):
                signals.append({'timestamp': str(timestamps[i]), 'pair': pair, 'setup_id': 3, 'setup_name': 'ICT Silver Bullet', 'direction': 'BUY', 'entry': round(entry, 5), 'sl': round(sl, 5), 'tp': round(entry + min_rr*risk, 5), 'rr': min_rr, 'sl_pips': round(risk/pip_size, 1), 'spread_pips': round(spread[i], 1)})
        elif is_sb[i] and ftype == -1 and ote_type[i] == -1 and bias == -1:
            entry = (fvg_top[i] + fvg_bottom[i]) / 2.0
            sl_base = ob_top[i] if not np.isnan(ob_top[i]) else fvg_top[i]
            sl = sl_base + (3.5 * pip_size)
            risk = sl - entry
            if risk > (2.0 * pip_size):
                signals.append({'timestamp': str(timestamps[i]), 'pair': pair, 'setup_id': 3, 'setup_name': 'ICT Silver Bullet', 'direction': 'SELL', 'entry': round(entry, 5), 'sl': round(sl, 5), 'tp': round(entry - min_rr*risk, 5), 'rr': min_rr, 'sl_pips': round(risk/pip_size, 1), 'spread_pips': round(spread[i], 1)})

        # Setup 4: Turtle Soup MSS + FVG 50% CE + OTE Fib Confluence
        if s_dir == 1 and ftype == 1 and ote_type[i] == 1 and bias == 1:
            entry = (fvg_top[i] + fvg_bottom[i]) / 2.0
            sl_base = ob_bottom[i] if not np.isnan(ob_bottom[i]) else fvg_bottom[i]
            sl = sl_base - (3.5 * pip_size)
            risk = entry - sl
            if risk > (2.0 * pip_size):
                signals.append({'timestamp': str(timestamps[i]), 'pair': pair, 'setup_id': 4, 'setup_name': '🐢 Turtle Soup (MSS + FVG)', 'direction': 'BUY', 'entry': round(entry, 5), 'sl': round(sl, 5), 'tp': round(entry + min_rr*risk, 5), 'rr': min_rr, 'sl_pips': round(risk/pip_size, 1), 'spread_pips': round(spread[i], 1)})
        elif s_dir == -1 and ftype == -1 and ote_type[i] == -1 and bias == -1:
            entry = (fvg_top[i] + fvg_bottom[i]) / 2.0
            sl_base = ob_top[i] if not np.isnan(ob_top[i]) else fvg_top[i]
            sl = sl_base + (3.5 * pip_size)
            risk = sl - entry
            if risk > (2.0 * pip_size):
                signals.append({'timestamp': str(timestamps[i]), 'pair': pair, 'setup_id': 4, 'setup_name': '🐢 Turtle Soup (MSS + FVG)', 'direction': 'SELL', 'entry': round(entry, 5), 'sl': round(sl, 5), 'tp': round(entry - min_rr*risk, 5), 'rr': min_rr, 'sl_pips': round(risk/pip_size, 1), 'spread_pips': round(spread[i], 1)})

        # Setup 5: OB + FVG Confluence
        if ob_t == 1 and ftype == 1 and bias == 1:
            ob_b = ob_bottom[i]
            fvg_b = fvg_bottom[i]
            if not np.isnan(ob_b) and not np.isnan(fvg_b):
                entry = (ob_top[i] + fvg_b) / 2.0
                sl = ob_b - (3.5 * pip_size)
                risk = entry - sl
                if risk > (2.0 * pip_size):
                    signals.append({'timestamp': str(timestamps[i]), 'pair': pair, 'setup_id': 5, 'setup_name': 'OB + FVG Confluence', 'direction': 'BUY', 'entry': round(entry, 5), 'sl': round(sl, 5), 'tp': round(entry + min_rr*risk, 5), 'rr': min_rr, 'sl_pips': round(risk/pip_size, 1), 'spread_pips': round(spread[i], 1)})
        elif ob_t == -1 and ftype == -1 and bias == -1:
            ob_t_val = ob_top[i]
            fvg_t_val = fvg_top[i]
            if not np.isnan(ob_t_val) and not np.isnan(fvg_t_val):
                entry = (ob_bottom[i] + fvg_t_val) / 2.0
                sl = ob_t_val + (3.5 * pip_size)
                risk = sl - entry
                if risk > (2.0 * pip_size):
                    signals.append({'timestamp': str(timestamps[i]), 'pair': pair, 'setup_id': 5, 'setup_name': 'OB + FVG Confluence', 'direction': 'SELL', 'entry': round(entry, 5), 'sl': round(sl, 5), 'tp': round(entry - min_rr*risk, 5), 'rr': min_rr, 'sl_pips': round(risk/pip_size, 1), 'spread_pips': round(spread[i], 1)})

        # Setup 6: Unicorn (Breaker + FVG + OTE Confluence)
        if btype == 1 and ftype == 1 and ote_type[i] == 1 and bias == 1:
            entry = (fvg_top[i] + fvg_bottom[i]) / 2.0
            sl = breaker_bottom[i] - (3.5 * pip_size)
            risk = entry - sl
            if risk > (2.0 * pip_size):
                signals.append({'timestamp': str(timestamps[i]), 'pair': pair, 'setup_id': 6, 'setup_name': '🦄 Unicorn (Breaker + FVG)', 'direction': 'BUY', 'entry': round(entry, 5), 'sl': round(sl, 5), 'tp': round(entry + min_rr*risk, 5), 'rr': min_rr, 'sl_pips': round(risk/pip_size, 1), 'spread_pips': round(spread[i], 1)})
        elif btype == -1 and ftype == -1 and ote_type[i] == -1 and bias == -1:
            entry = (fvg_top[i] + fvg_bottom[i]) / 2.0
            sl = breaker_top[i] + (3.5 * pip_size)
            risk = sl - entry
            if risk > (2.0 * pip_size):
                signals.append({'timestamp': str(timestamps[i]), 'pair': pair, 'setup_id': 6, 'setup_name': '🦄 Unicorn (Breaker + FVG)', 'direction': 'SELL', 'entry': round(entry, 5), 'sl': round(sl, 5), 'tp': round(entry - min_rr*risk, 5), 'rr': min_rr, 'sl_pips': round(risk/pip_size, 1), 'spread_pips': round(spread[i], 1)})

        # Setup 9: Breaker Block Retest + OB/FVG
        if btype == 1 and (ob_t == 1 or ftype == 1) and bias == 1:
            entry = (breaker_top[i] + breaker_bottom[i]) / 2.0
            sl = breaker_bottom[i] - (3.5 * pip_size)
            risk = entry - sl
            if risk > (2.0 * pip_size):
                signals.append({'timestamp': str(timestamps[i]), 'pair': pair, 'setup_id': 9, 'setup_name': '🔄 Breaker Block Retest', 'direction': 'BUY', 'entry': round(entry, 5), 'sl': round(sl, 5), 'tp': round(entry + min_rr*risk, 5), 'rr': min_rr, 'sl_pips': round(risk/pip_size, 1), 'spread_pips': round(spread[i], 1)})
        elif btype == -1 and (ob_t == -1 or ftype == -1) and bias == -1:
            entry = (breaker_top[i] + breaker_bottom[i]) / 2.0
            sl = breaker_top[i] + (3.5 * pip_size)
            risk = sl - entry
            if risk > (2.0 * pip_size):
                signals.append({'timestamp': str(timestamps[i]), 'pair': pair, 'setup_id': 9, 'setup_name': '🔄 Breaker Block Retest', 'direction': 'SELL', 'entry': round(entry, 5), 'sl': round(sl, 5), 'tp': round(entry - min_rr*risk, 5), 'rr': min_rr, 'sl_pips': round(risk/pip_size, 1), 'spread_pips': round(spread[i], 1)})

        # Setup 10: AMD / Power of 3 (Asian Range Break + NY Judas + FVG + OTE Confluence)
        if is_ny[i] and has_sweep and ftype == 1 and ote_type[i] == 1 and bias == 1:
            entry = (fvg_top[i] + fvg_bottom[i]) / 2.0
            sl_base = ob_bottom[i] if not np.isnan(ob_bottom[i]) else fvg_bottom[i]
            sl = sl_base - (3.5 * pip_size)
            risk = entry - sl
            if risk > (2.0 * pip_size):
                signals.append({'timestamp': str(timestamps[i]), 'pair': pair, 'setup_id': 10, 'setup_name': '📈 AMD / Power of 3', 'direction': 'BUY', 'entry': round(entry, 5), 'sl': round(sl, 5), 'tp': round(entry + min_rr*risk, 5), 'rr': min_rr, 'sl_pips': round(risk/pip_size, 1), 'spread_pips': round(spread[i], 1)})
        elif is_ny[i] and has_sweep and ftype == -1 and ote_type[i] == -1 and bias == -1:
            entry = (fvg_top[i] + fvg_bottom[i]) / 2.0
            sl_base = ob_top[i] if not np.isnan(ob_top[i]) else fvg_top[i]
            sl = sl_base + (3.5 * pip_size)
            risk = sl - entry
            if risk > (2.0 * pip_size):
                signals.append({'timestamp': str(timestamps[i]), 'pair': pair, 'setup_id': 10, 'setup_name': '📈 AMD / Power of 3', 'direction': 'SELL', 'entry': round(entry, 5), 'sl': round(sl, 5), 'tp': round(entry - min_rr*risk, 5), 'rr': min_rr, 'sl_pips': round(risk/pip_size, 1), 'spread_pips': round(spread[i], 1)})

    signals.sort(key=lambda x: x['timestamp'])
    return signals

def execute_backtest_with_be(df, signals, pair, min_rr=2.0):
    pip_size = get_pip_size(pair)
    highs = df['high'].values
    lows = df['low'].values
    idx_map = df.index
    trades = []
    
    for sig in signals:
        sig_time = pd.Timestamp(sig['timestamp'])
        idx = idx_map.searchsorted(sig_time)
        if idx >= len(df): continue
        
        direction = sig['direction']
        entry = sig['entry']
        sl = sig['sl']
        risk = abs(entry - sl)
        if risk == 0: continue
        
        tp = entry + (min_rr * risk) if direction == 'BUY' else entry - (min_rr * risk)
        be_trigger = entry + (1.0 * risk) if direction == 'BUY' else entry - (1.0 * risk)
        sl_be = entry + (0.2 * pip_size) if direction == 'BUY' else entry - (0.2 * pip_size)
        
        outcome = 'LOSS'
        end_idx = min(idx + 500, len(df))
        h_sub = highs[idx:end_idx]
        l_sub = lows[idx:end_idx]
        
        if direction == 'BUY':
            tp_hits = np.where(h_sub >= tp)[0]
            be_hits = np.where(h_sub >= be_trigger)[0]
            sl_hits = np.where(l_sub <= sl)[0]
            
            first_tp = tp_hits[0] if len(tp_hits) > 0 else 999999
            first_sl = sl_hits[0] if len(sl_hits) > 0 else 999999
            first_be = be_hits[0] if len(be_hits) > 0 else 999999
            
            if first_be < first_sl and first_be < first_tp:
                h_sub2 = h_sub[first_be:]
                l_sub2 = l_sub[first_be:]
                tp_hits2 = np.where(h_sub2 >= tp)[0]
                sl_hits2 = np.where(l_sub2 <= sl_be)[0]
                t2 = tp_hits2[0] if len(tp_hits2) > 0 else 999999
                s2 = sl_hits2[0] if len(sl_hits2) > 0 else 999999
                if t2 < s2:
                    outcome = 'WIN'
                else:
                    outcome = 'BE'
            elif first_tp < first_sl:
                outcome = 'WIN'
            else:
                outcome = 'LOSS'
        else: # SELL
            tp_hits = np.where(l_sub <= tp)[0]
            be_hits = np.where(l_sub <= be_trigger)[0]
            sl_hits = np.where(h_sub >= sl)[0]
            
            first_tp = tp_hits[0] if len(tp_hits) > 0 else 999999
            first_sl = sl_hits[0] if len(sl_hits) > 0 else 999999
            first_be = be_hits[0] if len(be_hits) > 0 else 999999
            
            if first_be < first_sl and first_be < first_tp:
                h_sub2 = h_sub[first_be:]
                l_sub2 = l_sub[first_be:]
                tp_hits2 = np.where(l_sub2 <= tp)[0]
                sl_hits2 = np.where(h_sub2 >= sl_be)[0]
                t2 = tp_hits2[0] if len(tp_hits2) > 0 else 999999
                s2 = sl_hits2[0] if len(sl_hits2) > 0 else 999999
                if t2 < s2:
                    outcome = 'WIN'
                else:
                    outcome = 'BE'
            elif first_tp < first_sl:
                outcome = 'WIN'
            else:
                outcome = 'LOSS'
                
        trades.append({'setup_id': sig['setup_id'], 'outcome': outcome})
        
    return trades

pairs = ["GBPUSD", "EURUSD", "USDJPY", "USDCAD", "AUDUSD", "USDCHF"]
all_trades = []

for pair in pairs:
    print(f"[*] Processing pair {pair}...", flush=True)
    df = load_pair_data(data_dir, pair, sample_ratio=0.1)
    df_res = resample_candles(df, "5m")
    df_ind = run_indicators(df_res, pair)
    sigs = generate_signals_all_80plus(df_ind, pair, min_rr=2.0)
    trades = execute_backtest_with_be(df_res, sigs, pair, min_rr=2.0)
    all_trades.extend(trades)
    print(f"[+] Pair {pair} complete. Total trades so far: {len(all_trades)}", flush=True)

print("\n==========================================================================", flush=True)
print("OPTIMIZED ALL ACTIVE SETUPS WIN RATE RESULTS (MIN 1:2 RR)", flush=True)
print("==========================================================================", flush=True)
setup_names = {
    1: "Liquidity Sweep + FVG",
    2: "Liquidity Sweep + IFVG",
    3: "ICT Silver Bullet",
    4: "Turtle Soup (MSS + FVG)",
    5: "OB + FVG Confluence",
    6: "Unicorn (Breaker + FVG)",
    9: "Breaker Block Retest",
    10: "AMD / Power of 3"
}

for s_id in [1, 2, 3, 4, 5, 6, 9, 10]:
    s_trades = [t for t in all_trades if t['setup_id'] == s_id]
    s_wins = [t for t in s_trades if t['outcome'] in ['WIN', 'BE']]
    wr = (len(s_wins) / len(s_trades) * 100.0) if s_trades else 0.0
    print(f"Setup #{s_id:<2} ({setup_names[s_id]:<28}): Trades = {len(s_trades):<5} | Win Rate = {wr:>6.2f}%", flush=True)

