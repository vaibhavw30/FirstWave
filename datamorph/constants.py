"""
Shared constants for the FirstWave datamorph rebuild.
FirstWave | GT Hacklytics 2026

These mirror the values inlined across pipeline/01..08_*.py and CLAUDE.md.
The datamorph Python actions are self-contained and do NOT import this module —
it exists for reference / DRY reuse if your datamorph project supports shared modules.
"""

# 31 clean dispatch zones
VALID_ZONES = [
    'B1', 'B2', 'B3', 'B4', 'B5',
    'K1', 'K2', 'K3', 'K4', 'K5', 'K6', 'K7',
    'M1', 'M2', 'M3', 'M4', 'M5', 'M6', 'M7', 'M8', 'M9',
    'Q1', 'Q2', 'Q3', 'Q4', 'Q5', 'Q6', 'Q7',
    'S1', 'S2', 'S3',
]

# zone -> (longitude, latitude)
ZONE_CENTROIDS = {
    'B1': (-73.9101, 40.8116), 'B2': (-73.9196, 40.8448), 'B3': (-73.8784, 40.8189),
    'B4': (-73.8600, 40.8784), 'B5': (-73.9056, 40.8651),
    'K1': (-73.9857, 40.5995), 'K2': (-73.9442, 40.6501), 'K3': (-73.9075, 40.6929),
    'K4': (-73.9015, 40.6501), 'K5': (-73.9283, 40.6801), 'K6': (-73.9645, 40.6401),
    'K7': (-73.9573, 40.7201),
    'M1': (-74.0060, 40.7128), 'M2': (-74.0000, 40.7484), 'M3': (-73.9857, 40.7580),
    'M4': (-73.9784, 40.7484), 'M5': (-73.9584, 40.7701), 'M6': (-73.9484, 40.7884),
    'M7': (-73.9428, 40.8048), 'M8': (-73.9373, 40.8284), 'M9': (-73.9312, 40.8484),
    'Q1': (-73.7840, 40.6001), 'Q2': (-73.8284, 40.7501), 'Q3': (-73.8784, 40.7201),
    'Q4': (-73.9073, 40.7101), 'Q5': (-73.8073, 40.6901), 'Q6': (-73.9173, 40.7701),
    'Q7': (-73.8373, 40.7701),
    'S1': (-74.1115, 40.6401), 'S2': (-74.1515, 40.5901), 'S3': (-74.1915, 40.5301),
}

# CDC SVI RPL_THEMES (0-1, higher = more vulnerable)
ZONE_SVI = {
    'B1': 0.94, 'B2': 0.89, 'B3': 0.87, 'B4': 0.72, 'B5': 0.68,
    'K1': 0.52, 'K2': 0.58, 'K3': 0.82, 'K4': 0.84, 'K5': 0.79, 'K6': 0.60, 'K7': 0.45,
    'M1': 0.31, 'M2': 0.18, 'M3': 0.15, 'M4': 0.20, 'M5': 0.12,
    'M6': 0.14, 'M7': 0.73, 'M8': 0.65, 'M9': 0.61,
    'Q1': 0.71, 'Q2': 0.44, 'Q3': 0.38, 'Q4': 0.55, 'Q5': 0.67, 'Q6': 0.48, 'Q7': 0.41,
    'S1': 0.38, 'S2': 0.32, 'S3': 0.28,
}

# WMO weathercodes that flag is_severe_weather = 1
SEVERE_WEATHER_CODES = {51, 53, 55, 61, 63, 65, 71, 73, 75, 77, 80, 81, 82, 85, 86, 95, 96, 99}

# Model feature order — FROZEN. Must match demand_model.pkl training order exactly.
FEATURE_COLS = [
    # original 15
    "hour_sin", "hour_cos", "dow_sin", "dow_cos", "month_sin", "month_cos",
    "is_weekend", "temperature_2m", "precipitation", "windspeed_10m",
    "is_severe_weather", "svi_score", "zone_baseline_avg",
    "high_acuity_ratio", "held_ratio",
    # +6 enrichment
    "is_holiday", "is_major_event", "is_school_day",
    "is_heat_emergency", "is_extreme_heat", "subway_disruption_idx",
]

# XGBoost hyperparameters (Script 05)
XGB_PARAMS = {
    "n_estimators": 300,
    "max_depth": 6,
    "learning_rate": 0.05,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "random_state": 42,
    "n_jobs": -1,
    "tree_method": "hist",
    "early_stopping_rounds": 20,
}

# 8-minute clinical target, in seconds
THRESHOLD_SECONDS = 480

# Borough display order
BOROUGHS = ["BRONX", "BROOKLYN", "MANHATTAN", "QUEENS", "RICHMOND / STATEN ISLAND"]
