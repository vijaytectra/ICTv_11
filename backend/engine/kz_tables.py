"""
ICT killzone / session clock profiles (America/New_York hours).

Default law: mentorship_2017 (Gap Closure H lock KZ=C).
"""
from __future__ import annotations

from typing import Dict, Tuple

# Windows are [start_hour, end_hour) in NY local decimal hours.
# SB windows are OR-ed into is_silver_bullet.

KZ_TABLES: Dict[str, Dict] = {
    "mentorship_2017": {
        "asian": (20.0, 24.0),  # 20:00–00:00 (wraps midnight)
        "asian_wrap": True,
        "london_kz": (1.0, 5.0),
        "ny_kz": (7.0, 10.0),
        "sb": [(3.0, 4.0), (10.0, 11.0), (14.0, 15.0)],
        "london_pool": (1.0, 5.0),
    },
    "public_2016_2022": {
        "asian": (20.0, 24.0),
        "asian_wrap": True,
        "london_kz": (2.0, 5.0),
        "ny_kz": (7.0, 10.0),
        "sb": [(10.0, 11.0), (14.0, 15.0)],
        "london_pool": (2.0, 5.0),
    },
    "legacy_hybrid": {
        "asian": (0.0, 6.0),
        "asian_wrap": False,
        "london_kz": (2.0, 5.0),
        "ny_kz": (7.0, 10.0),
        "sb": [(3.0, 4.0), (10.0, 11.0), (15.0, 16.0)],
        "london_pool": (7.0, 10.0),  # historical LSH/LSL window in prior code
    },
}

DEFAULT_KZ_TABLE = "mentorship_2017"
GEOMETRY_LOCK_VERSION = "H-2026-09-21"


def in_window(hours: "object", start: float, end: float, wrap: bool = False):
    """Vectorized hour membership; wrap=True for 20–00 style ranges."""
    import numpy as np

    h = np.asarray(hours, dtype=float)
    if wrap and end >= 24.0:
        # e.g. 20–24 means hour >= 20
        return h >= start
    if wrap and start > end:
        return (h >= start) | (h < end)
    return (h >= start) & (h < end)


def resolve_kz_table(name: str | None) -> str:
    if not name or name not in KZ_TABLES:
        return DEFAULT_KZ_TABLE
    return name
