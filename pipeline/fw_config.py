"""
Shared constants for the FirstWave pipeline.

The numbered scripts run as `python pipeline/0N_*.py`, which puts pipeline/ on
sys.path, so they import this module directly. pipeline/tests does the same via
conftest.py.
"""
import datetime as dt

VALID_ZONES = [
    'B1', 'B2', 'B3', 'B4', 'B5',
    'K1', 'K2', 'K3', 'K4', 'K5', 'K6', 'K7',
    'M1', 'M2', 'M3', 'M4', 'M5', 'M6', 'M7', 'M8', 'M9',
    'Q1', 'Q2', 'Q3', 'Q4', 'Q5', 'Q6', 'Q7',
    'S1', 'S2', 'S3',
]

ZONE_PREFIX_BOROUGH = {
    'B': 'BRONX',
    'K': 'BROOKLYN',
    'M': 'MANHATTAN',
    'Q': 'QUEENS',
    'S': 'RICHMOND / STATEN ISLAND',
}

# ── Data window ────────────────────────────────────────────────────────────────
DATA_START = dt.date(2021, 12, 1)   # Dec 2021 is lag warm-up only
DATA_END = dt.date(2026, 6, 30)     # last day published as of 2026-09-28

HOURLY_COUNTS_START = dt.date(2024, 12, 1)  # 4+ weeks of history before REPLAY_START
REPLAY_START = dt.date(2025, 1, 1)
REPLAY_END = DATA_END

# (split, first day) in time order; each split runs until the next one starts.
SPLIT_STARTS = [
    ("history", dt.date(2021, 12, 1)),
    ("train", dt.date(2022, 1, 1)),
    ("valid", dt.date(2024, 10, 1)),
    ("test", dt.date(2025, 1, 1)),
    ("test_recent", dt.date(2026, 1, 1)),
]
SPLIT_END = DATA_END + dt.timedelta(days=1)   # exclusive


def split_case_sql(ts_col: str) -> str:
    """DuckDB CASE expression mapping a TIMESTAMP expression to its split name."""
    uppers = [start for _, start in SPLIT_STARTS[1:]] + [SPLIT_END]
    whens = [f"WHEN {ts_col} < TIMESTAMP '{SPLIT_STARTS[0][1]} 00:00:00' THEN 'exclude'"]
    for (name, _), upper in zip(SPLIT_STARTS, uppers):
        whens.append(f"WHEN {ts_col} < TIMESTAMP '{upper} 00:00:00' THEN '{name}'")
    return "CASE " + " ".join(whens) + " ELSE 'exclude' END"


# ── Model features ─────────────────────────────────────────────────────────────
# ORDER IS FROZEN. The first 21 match the previous model; lags are appended.
BASE_FEATURE_COLS = [
    "hour_sin", "hour_cos",
    "dow_sin", "dow_cos",
    "month_sin", "month_cos",
    "is_weekend",
    "temperature_2m",
    "precipitation",
    "windspeed_10m",
    "is_severe_weather",
    "svi_score",
    "zone_baseline_avg",
    "high_acuity_ratio",
    "held_ratio",
    "is_holiday",
    "is_major_event",
    "is_school_day",
    "is_heat_emergency",
    "is_extreme_heat",
    "subway_disruption_idx",
]

# Must equal backend/models/lag_features.py LAG_FEATURES (pinned by test_lag_parity.py).
LAG_FEATURE_COLS = [
    "lag_1h",
    "lag_2h",
    "lag_3h",
    "lag_24h",
    "lag_168h",
    "roll_7d_same_hour",
    "roll_4w_same_hour_dow",
]

FEATURE_COLS = BASE_FEATURE_COLS + LAG_FEATURE_COLS
