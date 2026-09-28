"""
Serving-side lag features. Must match pipeline/fw_grid.py LAG_SPECS exactly;
pipeline/tests/test_lag_parity.py compares the two on the same data.

Timestamps are naive local hours (24 per day, DST days included), the same
convention as the training grid, so "t minus N hours" is plain Timedelta math.
"""
import pandas as pd

LAG_FEATURES = [
    "lag_1h",
    "lag_2h",
    "lag_3h",
    "lag_24h",
    "lag_168h",
    "roll_7d_same_hour",
    "roll_4w_same_hour_dow",
]

_OFFSETS = {
    "lag_1h": [1],
    "lag_2h": [2],
    "lag_3h": [3],
    "lag_24h": [24],
    "lag_168h": [168],
    "roll_7d_same_hour": [24 * k for k in range(1, 8)],
    "roll_4w_same_hour_dow": [168 * k for k in range(1, 5)],
}
MAX_LOOKBACK_HOURS = 672


class MissingHistoryError(LookupError):
    """hourly_counts does not cover a timestamp the lags need."""


def to_wide(hourly_counts: pd.DataFrame) -> pd.DataFrame:
    """Long (zone, date_hour, incident_count) -> wide: index date_hour, one column per zone."""
    wide = hourly_counts.pivot(
        index="date_hour", columns="INCIDENT_DISPATCH_AREA", values="incident_count"
    )
    wide.index = pd.DatetimeIndex(wide.index)
    return wide.sort_index().fillna(0).astype(float)


def _row(counts_wide: pd.DataFrame, ts: pd.Timestamp) -> pd.Series:
    if ts not in counts_wide.index:
        raise MissingHistoryError(f"no hourly counts for {ts}")
    return counts_wide.loc[ts]


def build_lag_features(counts_wide: pd.DataFrame, target: pd.Timestamp) -> pd.DataFrame:
    """Lag features for every zone at `target`. Index = zone, columns = LAG_FEATURES."""
    target = pd.Timestamp(target)
    cols = {}
    for name, offsets in _OFFSETS.items():
        rows = [_row(counts_wide, target - pd.Timedelta(hours=h)) for h in offsets]
        cols[name] = sum(rows) / len(rows)
    return pd.DataFrame(cols)[LAG_FEATURES]


def actual_counts(counts_wide: pd.DataFrame, target: pd.Timestamp) -> dict:
    target = pd.Timestamp(target)
    if target not in counts_wide.index:
        return {}
    return {zone: int(v) for zone, v in counts_wide.loc[target].items()}
