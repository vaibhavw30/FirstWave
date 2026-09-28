"""Deterministic synthetic incidents for grid / lag tests."""
import datetime as dt

import numpy as np
import pandas as pd


def count_at(zone_idx: int, hour_idx: int) -> int:
    """Incidents in zone `zone_idx` during hour `hour_idx` (0 = start). Includes zeros."""
    return (hour_idx * 7 + zone_idx * 3) % 5


def write_incidents(path, zones: list[str], start: dt.date, end: dt.date) -> None:
    """One parquet row per incident with INCIDENT_DISPATCH_AREA and date_hour."""
    hours = pd.date_range(pd.Timestamp(start), pd.Timestamp(end) + pd.Timedelta(hours=23), freq="h")
    zone_col, ts_col = [], []
    for zi, zone in enumerate(zones):
        n = np.array([count_at(zi, hi) for hi in range(len(hours))])
        zone_col.extend([zone] * int(n.sum()))
        ts_col.extend(np.repeat(hours.values, n))
    pd.DataFrame({"INCIDENT_DISPATCH_AREA": zone_col, "date_hour": ts_col}).to_parquet(path, index=False)
