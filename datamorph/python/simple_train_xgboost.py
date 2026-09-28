"""
Datamorph Python action — SIMPLIFIED Step 4: simple_train_xgboost
FirstWave | GT Hacklytics 2026

Reads the model-input table (from simple_03_model_input.sql) and trains a small
XGBoost regressor that predicts EMS incident_count from time + weather + the
per-zone baseline. Saves the model AND a per-zone baseline lookup that the next
step (K-Means staging) uses for inference.

Input:
  pipeline/data/incidents_model_input.parquet
Outputs:
  backend/artifacts/simple_demand_model.pkl
  backend/artifacts/simple_zone_baselines.parquet   (zone, hour, dayofweek, zone_baseline_avg)

Mirrors the idea of pipeline/05_train_demand_model.py, trimmed to 11 features and
one year of data so it trains in well under a minute.
"""

import pathlib
import sys

import joblib
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import train_test_split

IN = pathlib.Path("pipeline/data/incidents_model_input.parquet")
ARTIFACTS = pathlib.Path("backend/artifacts")
ARTIFACTS.mkdir(parents=True, exist_ok=True)
MODEL_OUT = ARTIFACTS / "simple_demand_model.pkl"
BASELINE_OUT = ARTIFACTS / "simple_zone_baselines.parquet"

# 11 features — same spirit as the full model, minus the 6 extra calendar/MTA flags.
FEATURE_COLS = [
    "hour_sin", "hour_cos", "dow_sin", "dow_cos", "month_sin", "month_cos",
    "is_weekend", "temperature_2m", "precipitation", "is_severe_weather",
    "zone_baseline_avg",          # ← strongest feature: per-zone demand prior
]


def add_cyclical(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24)
    df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24)
    df["dow_sin"] = np.sin(2 * np.pi * df["dayofweek"] / 7)
    df["dow_cos"] = np.cos(2 * np.pi * df["dayofweek"] / 7)
    df["month_sin"] = np.sin(2 * np.pi * df["month"] / 12)
    df["month_cos"] = np.cos(2 * np.pi * df["month"] / 12)
    return df


def main() -> None:
    if not IN.exists():
        sys.exit(f"ERROR: {IN} not found. Run the simple_ems_weather DuckDB pipeline first.")

    df = pd.read_parquet(IN)
    print(f"Loaded {len(df):,} rows")
    df = add_cyclical(df).fillna({"temperature_2m": 15.0, "precipitation": 0.0,
                                  "is_severe_weather": 0, "zone_baseline_avg": 1.0})

    X = df[FEATURE_COLS]
    y = df["incident_count"]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    model = xgb.XGBRegressor(
        n_estimators=200, max_depth=5, learning_rate=0.07,
        subsample=0.8, colsample_bytree=0.8, random_state=42,
        n_jobs=-1, tree_method="hist",
    )
    model.fit(X_train, y_train)

    preds = np.clip(model.predict(X_test), 0, None)
    rmse = float(np.sqrt(mean_squared_error(y_test, preds)))
    mae = float(mean_absolute_error(y_test, preds))

    joblib.dump(model, MODEL_OUT)

    # Save the per-zone baseline lookup for inference in the staging step.
    baselines = (df[["zone", "hour", "dayofweek", "zone_baseline_avg"]]
                 .drop_duplicates(subset=["zone", "hour", "dayofweek"])
                 .reset_index(drop=True))
    baselines.to_parquet(BASELINE_OUT, index=False)

    fi = (pd.DataFrame({"feature": FEATURE_COLS, "importance": model.feature_importances_})
          .sort_values("importance", ascending=False))

    print("=" * 56)
    print(f"  Test RMSE: {rmse:.3f}   MAE: {mae:.3f}")
    print("  Top features:")
    for _, r in fi.head(5).iterrows():
        print(f"    {r['feature']:<20} {r['importance']:.4f}")
    print(f"  Saved model:     {MODEL_OUT}")
    print(f"  Saved baselines: {BASELINE_OUT}  ({len(baselines)} zone-hour-dow rows)")
    print("=" * 56)
    print("  Next: python datamorph/python/simple_kmeans_staging.py")


if __name__ == "__main__":
    main()
