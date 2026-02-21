import numpy as np
import pandas as pd
import math

VALID_ZONES = [
    'B1', 'B2', 'B3', 'B4', 'B5',
    'K1', 'K2', 'K3', 'K4', 'K5', 'K6', 'K7',
    'M1', 'M2', 'M3', 'M4', 'M5', 'M6', 'M7', 'M8', 'M9',
    'Q1', 'Q2', 'Q3', 'Q4', 'Q5', 'Q6', 'Q7',
    'S1', 'S2', 'S3',
]

SVI_DEFAULTS = {
    'B1': 0.94, 'B2': 0.89, 'B3': 0.87, 'B4': 0.72, 'B5': 0.68,
    'K1': 0.52, 'K2': 0.58, 'K3': 0.82, 'K4': 0.84, 'K5': 0.79, 'K6': 0.60, 'K7': 0.45,
    'M1': 0.31, 'M2': 0.18, 'M3': 0.15, 'M4': 0.20, 'M5': 0.12,
    'M6': 0.14, 'M7': 0.73, 'M8': 0.65, 'M9': 0.61,
    'Q1': 0.71, 'Q2': 0.44, 'Q3': 0.38, 'Q4': 0.55, 'Q5': 0.67, 'Q6': 0.48, 'Q7': 0.41,
    'S1': 0.38, 'S2': 0.32, 'S3': 0.28,
}

HIGH_ACUITY_DEFAULTS = {
    'B1': 0.29, 'B2': 0.28, 'B3': 0.26, 'B4': 0.24, 'B5': 0.22,
    'K1': 0.21, 'K2': 0.23, 'K3': 0.27, 'K4': 0.27, 'K5': 0.25, 'K6': 0.22, 'K7': 0.21,
    'M1': 0.20, 'M2': 0.19, 'M3': 0.20, 'M4': 0.19, 'M5': 0.18,
    'M6': 0.18, 'M7': 0.25, 'M8': 0.24, 'M9': 0.23,
    'Q1': 0.22, 'Q2': 0.21, 'Q3': 0.20, 'Q4': 0.21, 'Q5': 0.22, 'Q6': 0.21, 'Q7': 0.19,
    'S1': 0.19, 'S2': 0.18, 'S3': 0.17,
}

HELD_RATIO_DEFAULTS = {
    'B1': 0.10, 'B2': 0.09, 'B3': 0.09, 'B4': 0.08, 'B5': 0.08,
    'K1': 0.07, 'K2': 0.07, 'K3': 0.08, 'K4': 0.08, 'K5': 0.08, 'K6': 0.07, 'K7': 0.07,
    'M1': 0.06, 'M2': 0.06, 'M3': 0.07, 'M4': 0.06, 'M5': 0.06,
    'M6': 0.06, 'M7': 0.08, 'M8': 0.07, 'M9': 0.07,
    'Q1': 0.07, 'Q2': 0.06, 'Q3': 0.06, 'Q4': 0.06, 'Q5': 0.07, 'Q6': 0.06, 'Q7': 0.06,
    'S1': 0.05, 'S2': 0.05, 'S3': 0.05,
}

FEATURE_COLS = [
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
]

SEVERE_WEATHER_CODES = {51, 53, 55, 61, 63, 65, 71, 73, 75, 77, 80, 81, 82, 85, 86, 95, 96, 99}


class DemandForecaster:
    def __init__(self, model):
        self.model = model

    def predict_all_zones(
        self,
        hour: int,
        dow: int,
        month: int,
        temperature: float,
        precipitation: float,
        windspeed: float,
        zone_stats_df,
        baselines_df,
    ) -> dict:
        """
        Build a 31-row feature DataFrame for all zones and run a single batch predict.
        Returns dict {zone_code: predicted_count}.
        """
        hour_sin = math.sin(2 * math.pi * hour / 24)
        hour_cos = math.cos(2 * math.pi * hour / 24)
        dow_sin = math.sin(2 * math.pi * dow / 7)
        dow_cos = math.cos(2 * math.pi * dow / 7)
        month_sin = math.sin(2 * math.pi * month / 12)
        month_cos = math.cos(2 * math.pi * month / 12)
        is_weekend = 1 if dow in (5, 6) else 0
        is_severe_weather = 1 if precipitation > 5 else 0

        rows = []
        for zone in VALID_ZONES:
            svi = SVI_DEFAULTS[zone]
            high_acuity = HIGH_ACUITY_DEFAULTS[zone]
            held = HELD_RATIO_DEFAULTS[zone]
            baseline = 5.0

            if zone_stats_df is not None:
                row = zone_stats_df[zone_stats_df["INCIDENT_DISPATCH_AREA"] == zone]
                if not row.empty:
                    svi = float(row["svi_score"].iloc[0]) if "svi_score" in row.columns else svi
                    high_acuity = float(row["high_acuity_ratio"].iloc[0]) if "high_acuity_ratio" in row.columns else high_acuity
                    held = float(row["held_ratio"].iloc[0]) if "held_ratio" in row.columns else held

            if baselines_df is not None:
                bl_row = baselines_df[
                    (baselines_df["INCIDENT_DISPATCH_AREA"] == zone) &
                    (baselines_df["hour"] == hour) &
                    (baselines_df["dayofweek"] == dow)
                ]
                if not bl_row.empty:
                    baseline = float(bl_row["zone_baseline_avg"].iloc[0])

            rows.append({
                "zone": zone,
                "hour_sin": hour_sin,
                "hour_cos": hour_cos,
                "dow_sin": dow_sin,
                "dow_cos": dow_cos,
                "month_sin": month_sin,
                "month_cos": month_cos,
                "is_weekend": is_weekend,
                "temperature_2m": temperature,
                "precipitation": precipitation,
                "windspeed_10m": windspeed,
                "is_severe_weather": is_severe_weather,
                "svi_score": svi,
                "zone_baseline_avg": baseline,
                "high_acuity_ratio": high_acuity,
                "held_ratio": held,
            })

        df = pd.DataFrame(rows)
        features = df[FEATURE_COLS]
        preds = self.model.predict(features)
        preds = np.clip(preds, 0, None)

        return {row["zone"]: float(pred) for row, pred in zip(rows, preds)}
