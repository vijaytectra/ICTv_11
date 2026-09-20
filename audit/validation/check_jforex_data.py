"""
JForex 1m Bid/Ask coverage and integrity checks for the quality ladder study.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd

DEFAULT_PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "USDCAD", "AUDUSD", "USDCHF"]
TIME_FORMAT = "%Y.%m.%d %H:%M:%S"


def _parse_csv_times(path: str) -> pd.Series:
    # Read only the time column for speed on multi-GB exports
    header = pd.read_csv(path, nrows=0)
    cols = list(header.columns)
    time_col = None
    for c in cols:
        if "time" in c.strip().lower():
            time_col = c
            break
    if time_col is None:
        raise ValueError(f"No time column in {path}")
    s = pd.read_csv(path, usecols=[time_col])[time_col]
    times = pd.to_datetime(s, format=TIME_FORMAT, errors="coerce")
    return times.dropna()


def _pair_files(data_dir: str, pair: str, side: str) -> List[str]:
    pattern = os.path.join(data_dir, f"{pair}_1 Min_{side}_*.csv")
    return sorted(glob.glob(pattern))


def _load_side_times(data_dir: str, pair: str, side: str) -> Optional[pd.DatetimeIndex]:
    files = _pair_files(data_dir, pair, side)
    if not files:
        return None
    series_list = []
    for f in files:
        series_list.append(_parse_csv_times(f))
    if not series_list:
        return None
    all_t = pd.concat(series_list, ignore_index=True).drop_duplicates().sort_values()
    return pd.DatetimeIndex(all_t)


def check_data_coverage(
    data_dir: str,
    pairs: Optional[List[str]] = None,
    start: str = "2020-01-01",
    end: str = "2026-12-31",
    min_weekday_coverage: float = 0.80,
) -> Dict[str, Any]:
    """
    Verify Bid+Ask 1m CSVs exist and span [start, end] with adequate weekday coverage.

    Weekday coverage heuristic: expected minutes ≈ weekdays in range * 24 * 60
    (continuous FX; slightly loose vs true session hours — flags gross holes only).
    """
    pairs = pairs or list(DEFAULT_PAIRS)
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    errors: List[str] = []
    pair_reports: Dict[str, Any] = {}

    weekdays = pd.bdate_range(start_ts, end_ts, freq="C")
    expected_minutes = max(1, len(weekdays) * 24 * 60)

    for pair in pairs:
        bid_times = _load_side_times(data_dir, pair, "Bid")
        ask_times = _load_side_times(data_dir, pair, "Ask")
        report: Dict[str, Any] = {
            "bid_files": len(_pair_files(data_dir, pair, "Bid")),
            "ask_files": len(_pair_files(data_dir, pair, "Ask")),
            "ok": False,
        }

        if bid_times is None or len(bid_times) == 0:
            errors.append(f"{pair}: missing Bid CSV ({pair}_1 Min_Bid_*.csv)")
            pair_reports[pair] = report
            continue
        if ask_times is None or len(ask_times) == 0:
            errors.append(f"{pair}: missing Ask CSV ({pair}_1 Min_Ask_*.csv)")
            pair_reports[pair] = report
            continue

        bid_in = bid_times[(bid_times >= start_ts) & (bid_times <= end_ts)]
        ask_in = ask_times[(ask_times >= start_ts) & (ask_times <= end_ts)]
        report["bid_rows_in_range"] = int(len(bid_in))
        report["ask_rows_in_range"] = int(len(ask_in))
        report["bid_min"] = str(bid_times.min())
        report["bid_max"] = str(bid_times.max())
        report["ask_min"] = str(ask_times.min())
        report["ask_max"] = str(ask_times.max())

        if len(bid_in) == 0:
            errors.append(f"{pair}: no Bid rows inside {start} → {end}")
            pair_reports[pair] = report
            continue

        if bid_times.min() > start_ts + pd.Timedelta(days=7):
            errors.append(
                f"{pair}: Bid starts too late ({bid_times.min()}); need near {start}"
            )
        if bid_times.max() < end_ts - pd.Timedelta(days=7):
            # end may be "present"; only warn if clearly short of requested end by >7d
            # and requested end is not far in the future relative to today
            today = pd.Timestamp(datetime.utcnow().date())
            effective_end = min(end_ts, today)
            if bid_times.max() < effective_end - pd.Timedelta(days=7):
                errors.append(
                    f"{pair}: Bid ends too early ({bid_times.max()}); need near {effective_end.date()}"
                )

        coverage = len(bid_in) / float(expected_minutes)
        report["weekday_coverage"] = round(coverage, 4)
        if coverage < min_weekday_coverage:
            errors.append(
                f"{pair}: Bid weekday coverage {coverage:.2%} < {min_weekday_coverage:.0%} "
                f"({len(bid_in)} / ~{expected_minutes} mins)"
            )

        # Ask alignment: fraction of Bid timestamps that have Ask
        bid_set = set(bid_in.astype("int64"))
        ask_set = set(ask_in.astype("int64"))
        if bid_set:
            align = len(bid_set & ask_set) / float(len(bid_set))
        else:
            align = 0.0
        report["ask_alignment"] = round(align, 4)
        if align < 0.95:
            errors.append(f"{pair}: Ask alignment {align:.2%} < 95%")

        if len(bid_in) >= 2:
            deltas = bid_in.to_series().diff().dropna().dt.total_seconds()
            report["median_delta_sec"] = float(deltas.median())
        else:
            report["median_delta_sec"] = None

        report["ok"] = not any(e.startswith(f"{pair}:") for e in errors)
        pair_reports[pair] = report

    return {
        "ok": len(errors) == 0,
        "pairs": pair_reports,
        "errors": errors,
        "start": start,
        "end": end,
        "data_dir": data_dir,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Check JForex 1m Bid/Ask coverage")
    parser.add_argument(
        "--data-dir",
        default=r"C:\Users\Vijayakumar R\Documents",
    )
    parser.add_argument("--start", default="2020-01-01")
    parser.add_argument("--end", default=datetime.utcnow().strftime("%Y-%m-%d"))
    parser.add_argument(
        "--pairs",
        default=",".join(DEFAULT_PAIRS),
        help="Comma-separated pairs",
    )
    args = parser.parse_args()
    pairs = [p.strip().upper() for p in args.pairs.split(",") if p.strip()]
    result = check_data_coverage(args.data_dir, pairs, args.start, args.end)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
