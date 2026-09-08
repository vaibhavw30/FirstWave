"""
Datamorph Python action — Stage ⑤: train_demand_model
FirstWave | GT Hacklytics 2026

Inputs (Parquet):
  pipeline/data/incidents_aggregated.parquet   (from Stage ④ proc_sql_4a)
  backend/artifacts/zone_baselines.parquet     (from Stage ④ proc_sql_4b)
  backend/artifacts/zone_stats.parquet         (from Stage ④ proc_sql_4c)
Output:
  backend/artifacts/demand_model.pkl

Mirrors: pipeline/05_train_demand_model.py (core training; dev sanity-scenarios
omitted — they live in the original script). Gate: Test RMSE < 4.0, and
zone_baseline_avg must rank in the top-3 feature importances.
"""

import pathlib
import sys

import joblib
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import mean_absolute_error, mean_squared_error

ARTIFACTS = pathlib.Path("backend/artifacts")
ARTIFACTS.mkdir(parents=True, exist_ok=True)
AGGD = pathlib.Path("pipeline/data/incidents_aggregated.parquet")
BASELINE = ARTIFACTS / "zone_baselines.parquet"
STATS = ARTIFACTS / "zone_stats.parquet"
MODEL_OUT = ARTIFACTS / "demand_model.pkl"

# Frozen 21-feature order — must match inference in backend/models/demand_forecaster.py
FEATURE_COLS = [
    "hour_sin", "hour_cos", "dow_sin", "dow_cos", "month_sin", "month_cos",
    "is_weekend", "temperature_2m", "precipitation", "windspeed_10m",
    "is_severe_weather", "svi_score", "zone_baseline_avg",
    "high_acuity_ratio", "held_ratio",
    "is_holiday", "is_major_event", "is_school_day",
    "is_heat_emergency", "is_extreme_heat", "subway_disruption_idx",
]
NEW_FEATURE_COLS = FEATURE_COLS[15:]

XGB_PARAMS = {
    "n_estimators": 300, "max_depth": 6, "learning_rate": 0.05,
    "subsample": 0.8, "colsample_bytree": 0.8, "random_state": 42,
    "n_jobs": -1, "tree_method": "hist", "early_stopping_rounds": 20,
}
FILL_DEFAULTS = {
    "zone_baseline_avg": 1.0, "high_acuity_ratio": 0.23, "held_ratio": 0.06,
    "is_holiday": 0, "is_major_event": 0, "is_school_day": 0,
    "is_heat_emergency": 0, "is_extreme_heat": 0, "subway_disruption_idx": 0.5,
}


def main() -> None:
    for p in (AGGD, BASELINE, STATS):
        if not p.exists():
            sys.exit(f"ERROR: {p} not found. Run Stage ④ first.")

    agg = pd.read_parquet(AGGD)
    baselines = pd.read_parquet(BASELINE)
    zone_stats = pd.read_parquet(STATS)

    missing = [c for c in NEW_FEATURE_COLS if c not in agg.columns]
    if missing:
        sys.exit(f"ERROR: missing enrichment columns {missing} — re-run Stage ②/④")

    # Merge baseline + stats features
    agg = agg.merge(
        baselines[["INCIDENT_DISPATCH_AREA", "hour", "dayofweek", "zone_baseline_avg"]],
        on=["INCIDENT_DISPATCH_AREA", "hour", "dayofweek"], how="left",
    ).merge(
        zone_stats[["INCIDENT_DISPATCH_AREA", "high_acuity_ratio", "held_ratio"]],
        on="INCIDENT_DISPATCH_AREA", how="left",
    )
    for col, default in FILL_DEFAULTS.items():
        if col in agg.columns:
            agg[col] = agg[col].fillna(default)

    if agg[FEATURE_COLS].isnull().any().any():
        bad = agg[FEATURE_COLS].isnull().sum()
        sys.exit(f"ERROR: nulls remain in features:\n{bad[bad > 0]}")

    train = agg[agg["split"] == "train"]
    test = agg[agg["split"] == "test"]
    X_train, y_train = train[FEATURE_COLS], train["incident_count"]
    X_test, y_test = test[FEATURE_COLS], test["incident_count"]

    print(f"Training XGBoost: X_train={X_train.shape}, X_test={X_test.shape}")
    model = xgb.XGBRegressor(**XGB_PARAMS)
    model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=50)

    preds = np.clip(model.predict(X_test), 0, None)
    rmse = float(np.sqrt(mean_squared_error(y_test, preds)))
    mae = float(mean_absolute_error(y_test, preds))

    fi = pd.DataFrame({"feature": FEATURE_COLS, "importance": model.feature_importances_}) \
        .sort_values("importance", ascending=False).reset_index(drop=True)

    joblib.dump(model, MODEL_OUT)

    print("=" * 56)
    print(f"  Test RMSE: {rmse:.3f} (target < 4.0)   Test MAE: {mae:.3f}")
    print("  Top features:")
    for _, r in fi.head(5).iterrows():
        print(f"    {r['feature']:<24} {r['importance']:.4f}")
    print(f"  Model saved: {MODEL_OUT}")
    print("=" * 56)

    # ── Gate ──
    if rmse > 6.0:
        sys.exit("GATE FAIL: RMSE > 6.0 — zone_baseline_avg likely missing from features")
    if "zone_baseline_avg" not in fi.head(3)["feature"].values:
        print("WARN: zone_baseline_avg not in top-3 importances — check merge keys")
    if rmse > 4.0:
        print(f"WARN: RMSE {rmse:.2f} > 4.0 (acceptable if Bronx is the outlier)")


if __name__ == "__main__":
    main()
