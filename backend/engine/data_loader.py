import os
import glob
import pandas as pd
import numpy as np

PIP_SIZES = {
    "EURUSD": 0.0001,
    "GBPUSD": 0.0001,
    "USDJPY": 0.01,
    "USDCAD": 0.0001,
    "AUDUSD": 0.0001,
    "USDCHF": 0.0001,
    "XAUUSD": 0.1,
    "DOLLARIDXUSD": 0.01,
    "USATECHIDXUSD": 1.0,
    "USA500IDXUSD": 0.25,
    "USA30IDXUSD": 1.0
}

# Broker CSV header is "Time (EET)" — Eastern European Time with DST (Europe/Bucharest).
SOURCE_TZ = "Europe/Bucharest"
ICT_TZ = "America/New_York"


def get_pip_size(pair: str) -> float:
    return PIP_SIZES.get(pair.upper(), 0.0001)


def _localize_eet_to_ny(series: pd.Series) -> pd.DatetimeIndex:
    """Naive EET timestamps → Europe/Bucharest → America/New_York (tz-aware)."""
    dt = pd.to_datetime(series, errors="coerce")
    localized = dt.dt.tz_localize(SOURCE_TZ, ambiguous="infer", nonexistent="shift_forward")
    return pd.DatetimeIndex(localized.dt.tz_convert(ICT_TZ))


def load_pair_data(data_dir: str, pair: str, sample_ratio: float = 1.0) -> pd.DataFrame:
    """
    Loads 1-Min Bid and Ask CSV files for a given pair, merges time ranges,
    and returns a clean DataFrame indexed in America/New_York (from EET source).
    """
    bid_pattern = os.path.join(data_dir, f"{pair}_1 Min_Bid_*.csv")
    ask_pattern = os.path.join(data_dir, f"{pair}_1 Min_Ask_*.csv")

    bid_files = sorted(glob.glob(bid_pattern))
    ask_files = sorted(glob.glob(ask_pattern))

    if not bid_files:
        raise FileNotFoundError(f"No Bid CSV files found for pair '{pair}' in directory {data_dir}")

    bid_dfs = []
    for f in bid_files:
        df = pd.read_csv(f)
        cols_map = {c: c.strip().lower() for c in df.columns}
        df.rename(columns=cols_map, inplace=True)
        time_col = [c for c in df.columns if "time" in c.lower()][0]
        df.rename(columns={time_col: "time"}, inplace=True)
        if "volume" not in df.columns:
            df["volume"] = 1.0
        df["time"] = pd.to_datetime(df["time"], format="%Y.%m.%d %H:%M:%S", errors="coerce")
        df.dropna(subset=["time"], inplace=True)
        bid_dfs.append(df[["time", "open", "high", "low", "close", "volume"]])

    bid_df = (
        pd.concat(bid_dfs, ignore_index=True)
        .sort_values("time")
        .drop_duplicates("time")
        .reset_index(drop=True)
    )

    spread_pips = 1.0
    pip_size = get_pip_size(pair)

    if ask_files:
        ask_dfs = []
        for f in ask_files:
            df = pd.read_csv(f)
            cols_map = {c: c.strip().lower() for c in df.columns}
            df.rename(columns=cols_map, inplace=True)
            time_col = [c for c in df.columns if "time" in c.lower()][0]
            df.rename(columns={time_col: "time", "close": "ask_close"}, inplace=True)
            df["time"] = pd.to_datetime(df["time"], format="%Y.%m.%d %H:%M:%S", errors="coerce")
            df.dropna(subset=["time"], inplace=True)
            ask_dfs.append(df[["time", "ask_close"]])

        ask_df = pd.concat(ask_dfs, ignore_index=True).sort_values("time").drop_duplicates("time")
        merged = pd.merge(bid_df, ask_df, on="time", how="left")
        merged["ask_close"] = merged["ask_close"].fillna(merged["close"] + (spread_pips * pip_size))
        merged["spread_pips"] = ((merged["ask_close"] - merged["close"]) / pip_size).clip(
            lower=0.1, upper=50.0
        )
        final_df = merged
    else:
        bid_df["spread_pips"] = spread_pips
        final_df = bid_df

    if sample_ratio < 1.0:
        step = int(1.0 / sample_ratio)
        final_df = final_df.iloc[::step].reset_index(drop=True)

    # Convert EET naive → NY for all ICT session logic
    ny_index = _localize_eet_to_ny(final_df["time"])
    final_df = final_df.drop(columns=["time"])
    final_df.index = ny_index
    final_df.index.name = "time"
    final_df = final_df[~final_df.index.duplicated(keep="last")].sort_index()
    return final_df


def resample_candles(df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    """
    Resamples 1m candles into 5m, 15m, 1h, 4h, or 1D timeframes.
    Preserves timezone of the index.
    """
    tf_map = {
        "5m": "5min",
        "15m": "15min",
        "1h": "1h",
        "4h": "4h",
        "1D": "1D",
        "1d": "1D",
    }
    alias = tf_map.get(timeframe, timeframe)

    agg_dict = {
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "spread_pips": "mean",
    }
    if "volume" in df.columns:
        agg_dict["volume"] = "sum"

    resampled = df.resample(alias).agg(agg_dict).dropna()
    return resampled
