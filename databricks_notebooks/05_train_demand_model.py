# Databricks notebook source
# MAGIC %md
# MAGIC # Notebook 05 — XGBoost Demand Forecaster
# MAGIC **FirstWave | GT Hacklytics 2026**
# MAGIC
# MAGIC Input: `firstwave.incidents_aggregated` + zone_baselines.parquet + zone_stats.parquet
# MAGIC Output: `dbfs:/firstwave/artifacts/demand_model.pkl`
# MAGIC MLflow experiment: `/firstwave/demand_forecasting`

# COMMAND ----------

# MAGIC %md ## Setup

# COMMAND ----------

import mlflow
import mlflow.xgboost
import xgboost as xgb
import pandas as pd
import numpy as np
import joblib
from sklearn.metrics import mean_squared_error, mean_absolute_error

# Serverless: use dbfs:/ for Spark operations, /tmp/ for local Python I/O
DBFS_ARTIFACTS = "dbfs:/firstwave/artifacts"
TMP_ARTIFACTS  = "/tmp/firstwave/artifacts"

import os
os.makedirs(TMP_ARTIFACTS, exist_ok=True)

# COMMAND ----------

# MAGIC %md ## Feature Columns (order matters — must match inference exactly)

# COMMAND ----------

FEATURE_COLS = [
    "hour_sin",           # sin(2π × hour / 24)
    "hour_cos",           # cos(2π × hour / 24)
    "dow_sin",            # sin(2π × dayofweek / 7)
    "dow_cos",            # cos(2π × dayofweek / 7)
    "month_sin",          # sin(2π × month / 12)
    "month_cos",          # cos(2π × month / 12)
    "is_weekend",         # 1 if dow in (5,6) else 0
    "temperature_2m",     # °C from Open-Meteo
    "precipitation",      # mm/hr from Open-Meteo
    "windspeed_10m",      # km/h from Open-Meteo
    "is_severe_weather",  # 1 if WMO weathercode in severe set else 0
    "svi_score",          # CDC SVI RPL_THEMES 0–1 per zone
    "zone_baseline_avg",  # ← MOST IMPORTANT: rolling avg incidents per (zone, hour, dow)
    "high_acuity_ratio",  # historical % of codes 1+2 for this zone
    "held_ratio",         # historical % of held calls for this zone
]

print(f"Feature columns: {len(FEATURE_COLS)}")
for i, f in enumerate(FEATURE_COLS):
    print(f"  [{i:02d}] {f}")

# COMMAND ----------

# MAGIC %md ## Step 1: Load Data

# COMMAND ----------

print("Loading incidents_aggregated from Delta...")
agg_pd = spark.table("firstwave.incidents_aggregated").toPandas()
print(f"  Loaded {len(agg_pd):,} rows")

# On Serverless, read parquets via Spark (not pd.read_parquet on /dbfs/ path)
print("\nLoading zone_baselines.parquet...")
baselines = spark.read.parquet(f"{DBFS_ARTIFACTS}/zone_baselines.parquet").toPandas()
print(f"  {len(baselines)} rows, columns: {list(baselines.columns)}")

print("\nLoading zone_stats.parquet...")
zone_stats = spark.read.parquet(f"{DBFS_ARTIFACTS}/zone_stats.parquet").toPandas()
print(f"  {len(zone_stats)} rows, columns: {list(zone_stats.columns)}")

# COMMAND ----------

# MAGIC %md ## Step 2: Merge Baseline Features

# COMMAND ----------

# Merge zone_baseline_avg: (INCIDENT_DISPATCH_AREA, hour, dayofweek)
agg_pd = agg_pd.merge(
    baselines[["INCIDENT_DISPATCH_AREA", "hour", "dayofweek", "zone_baseline_avg"]],
    on=["INCIDENT_DISPATCH_AREA", "hour", "dayofweek"],
    how="left"
)

# Merge high_acuity_ratio and held_ratio from zone_stats
agg_pd = agg_pd.merge(
    zone_stats[["INCIDENT_DISPATCH_AREA", "high_acuity_ratio", "held_ratio"]],
    on="INCIDENT_DISPATCH_AREA",
    how="left"
)

# Fill nulls with sensible defaults (should be 0 if merge worked correctly)
agg_pd["zone_baseline_avg"] = agg_pd["zone_baseline_avg"].fillna(1.0)
agg_pd["high_acuity_ratio"] = agg_pd["high_acuity_ratio"].fillna(0.23)
agg_pd["held_ratio"]        = agg_pd["held_ratio"].fillna(0.06)

print(f"After merge: {len(agg_pd):,} rows")
print(f"Training rows: {(agg_pd['split']=='train').sum():,}")
print(f"Test rows:     {(agg_pd['split']=='test').sum():,}")

print("\nNull counts in FEATURE_COLS (should all be 0):")
null_counts = agg_pd[FEATURE_COLS].isnull().sum()
print(null_counts.to_string())

# Critical check: if zone_baseline_avg has nulls, the merge failed
if null_counts.get("zone_baseline_avg", 0) > 0:
    print("\n⚠️  ERROR: zone_baseline_avg has nulls — merge failed!")
    print("⚠️  Check that column is 'INCIDENT_DISPATCH_AREA' not 'zone_code'")
    raise ValueError("zone_baseline_avg merge failed — cannot continue training")

# COMMAND ----------

# MAGIC %md ## Step 3: Train/Test Split

# COMMAND ----------

train = agg_pd[agg_pd["split"] == "train"].copy()
test  = agg_pd[agg_pd["split"] == "test"].copy()

X_train, y_train = train[FEATURE_COLS], train["incident_count"]
X_test,  y_test  = test[FEATURE_COLS],  test["incident_count"]

print(f"X_train: {X_train.shape}")
print(f"X_test:  {X_test.shape}")
print(f"\ny_train stats:")
print(y_train.describe().to_string())

# COMMAND ----------

# MAGIC %md ## Step 4: Train with MLflow Tracking

# COMMAND ----------

mlflow.set_experiment("/firstwave/demand_forecasting")

PARAMS = {
    "n_estimators": 300,
    "max_depth": 6,
    "learning_rate": 0.05,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "random_state": 42,
    "n_jobs": -1,
    "tree_method": "hist",  # fast on Databricks
}

with mlflow.start_run(run_name="xgboost_v1_dispatch_zones") as run:

    mlflow.log_params({
        **PARAMS,
        "training_years": "2019,2021,2022",
        "holdout_year": "2023",
        "n_zones": 31,
        "n_features": len(FEATURE_COLS),
        "spatial_unit": "incident_dispatch_area",
        "excluded_years": "2020 (COVID anomaly)",
        "target": "incident_count",
    })

    # ── Train Model ──────────────────────────────────────────────────────────
    model = xgb.XGBRegressor(**PARAMS)
    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        early_stopping_rounds=20,
        verbose=50,
    )

    # ── Overall Metrics ──────────────────────────────────────────────────────
    preds = np.clip(model.predict(X_test), 0, None)
    rmse = np.sqrt(mean_squared_error(y_test, preds))
    mae  = mean_absolute_error(y_test, preds)

    mlflow.log_metrics({"test_rmse": round(rmse, 3), "test_mae": round(mae, 3)})

    # ── Per-Borough RMSE ─────────────────────────────────────────────────────
    test_eval = test.copy()
    test_eval["predicted"] = preds
    test_eval["sq_err"] = (test_eval["incident_count"] - test_eval["predicted"]) ** 2

    borough_rmse = {}
    for borough in test_eval["BOROUGH"].unique():
        b_mask = test_eval["BOROUGH"] == borough
        b_rmse = np.sqrt(test_eval.loc[b_mask, "sq_err"].mean())
        key = f"rmse_{borough.lower().replace(' ','_').replace('/','')[:12]}"
        borough_rmse[key] = round(b_rmse, 3)

    mlflow.log_metrics(borough_rmse)

    # ── Feature Importance ───────────────────────────────────────────────────
    fi = pd.DataFrame({
        "feature": FEATURE_COLS,
        "importance": model.feature_importances_
    }).sort_values("importance", ascending=False)

    fi_path = "/tmp/feature_importance.csv"
    fi.to_csv(fi_path, index=False)
    mlflow.log_artifact(fi_path, "feature_importance")

    # ── Log Model ─────────────────────────────────────────────────────────────
    mlflow.xgboost.log_model(model, "demand_model")

    # ── Save PKL: write to /tmp/ then copy to DBFS (Serverless has no /dbfs/ mount)
    _model_tmp = f"{TMP_ARTIFACTS}/demand_model.pkl"
    joblib.dump(model, _model_tmp)
    dbutils.fs.cp(f"file:{_model_tmp}", f"{DBFS_ARTIFACTS}/demand_model.pkl")

    # ── Print Results ─────────────────────────────────────────────────────────
    print(f"\n{'='*55}")
    print(f"  FIRSTWAVE DEMAND MODEL — TRAINING COMPLETE")
    print(f"{'='*55}")
    print(f"  Test RMSE:  {rmse:.3f} incidents/zone/hour   ← target < 4.0")
    print(f"  Test MAE:   {mae:.3f}")
    print()
    print(f"  Per-Borough RMSE:")
    for k, v in sorted(borough_rmse.items()):
        print(f"    {k}: {v}")
    print()
    print(f"  Top 5 Features (zone_baseline_avg should be #1 or #2):")
    for _, row in fi.head(5).iterrows():
        print(f"    {row['feature']}: {row['importance']:.4f}")
    print()
    print(f"  MLflow run ID: {run.info.run_id}")
    print(f"  Model saved:   {DBFS_ARTIFACTS}/demand_model.pkl")
    print(f"{'='*55}")

    if rmse > 6.0:
        print("  ⚠️  RMSE > 6 — zone_baseline_avg is likely missing from features")
        print("  ⚠️  Run rolling average fallback below if needed")
    elif rmse > 4.0:
        print("  ⚠️  RMSE > 4 — acceptable but not ideal. Check residuals by borough.")
    else:
        print("  ✓ RMSE < 4.0 — target met!")

# COMMAND ----------

# MAGIC %md ## Step 5: Friday 8PM Sanity Check (Bronx should dominate)

# COMMAND ----------

import math

ZONE_CENTROIDS = {
    'B1':(-73.9101,40.8116),'B2':(-73.9196,40.8448),'B3':(-73.8784,40.8189),
    'B4':(-73.8600,40.8784),'B5':(-73.9056,40.8651),
    'K1':(-73.9857,40.5995),'K2':(-73.9442,40.6501),'K3':(-73.9075,40.6929),
    'K4':(-73.9015,40.6501),'K5':(-73.9283,40.6801),'K6':(-73.9645,40.6401),
    'K7':(-73.9573,40.7201),
    'M1':(-74.0060,40.7128),'M2':(-74.0000,40.7484),'M3':(-73.9857,40.7580),
    'M4':(-73.9784,40.7484),'M5':(-73.9584,40.7701),'M6':(-73.9484,40.7884),
    'M7':(-73.9428,40.8048),'M8':(-73.9373,40.8284),'M9':(-73.9312,40.8484),
    'Q1':(-73.7840,40.6001),'Q2':(-73.8284,40.7501),'Q3':(-73.8784,40.7201),
    'Q4':(-73.9073,40.7101),'Q5':(-73.8073,40.6901),'Q6':(-73.9173,40.7701),
    'Q7':(-73.8373,40.7701),
    'S1':(-74.1115,40.6401),'S2':(-74.1515,40.5901),'S3':(-74.1915,40.5301),
}

ZONE_SVI = {
    'B1':0.94,'B2':0.89,'B3':0.87,'B4':0.72,'B5':0.68,
    'K1':0.52,'K2':0.58,'K3':0.82,'K4':0.84,'K5':0.79,'K6':0.60,'K7':0.45,
    'M1':0.31,'M2':0.18,'M3':0.15,'M4':0.20,'M5':0.12,
    'M6':0.14,'M7':0.73,'M8':0.65,'M9':0.61,
    'Q1':0.71,'Q2':0.44,'Q3':0.38,'Q4':0.55,'Q5':0.67,'Q6':0.48,'Q7':0.41,
    'S1':0.38,'S2':0.32,'S3':0.28
}

VALID_ZONES = list(ZONE_CENTROIDS.keys())

def build_prediction_df(hour, dow, month, temp=15.0, precip=0.0, wind=10.0):
    rows = []
    for zone in VALID_ZONES:
        brow = baselines[
            (baselines['INCIDENT_DISPATCH_AREA'] == zone) &
            (baselines['hour'] == hour) &
            (baselines['dayofweek'] == dow)
        ]
        baseline_avg = float(brow['zone_baseline_avg'].iloc[0]) if len(brow) else 3.0

        zrow = zone_stats[zone_stats['INCIDENT_DISPATCH_AREA'] == zone]
        har = float(zrow['high_acuity_ratio'].iloc[0]) if len(zrow) else 0.23
        hdr = float(zrow['held_ratio'].iloc[0]) if len(zrow) else 0.06

        rows.append({
            "zone": zone,
            "hour_sin":  math.sin(2*math.pi*hour/24),
            "hour_cos":  math.cos(2*math.pi*hour/24),
            "dow_sin":   math.sin(2*math.pi*dow/7),
            "dow_cos":   math.cos(2*math.pi*dow/7),
            "month_sin": math.sin(2*math.pi*month/12),
            "month_cos": math.cos(2*math.pi*month/12),
            "is_weekend": 1 if dow in (5, 6) else 0,
            "temperature_2m": temp,
            "precipitation": precip,
            "windspeed_10m": wind,
            "is_severe_weather": 0,
            "svi_score": ZONE_SVI[zone],
            "zone_baseline_avg": baseline_avg,
            "high_acuity_ratio": har,
            "held_ratio": hdr,
        })
    return pd.DataFrame(rows)

# Friday 8PM (dow=4, month=10, hour=20)
df_fri_pm = build_prediction_df(hour=20, dow=4, month=10)
preds_fri = np.clip(model.predict(df_fri_pm[FEATURE_COLS]), 0, None)
df_fri_pm["predicted"] = preds_fri

print("\nFriday 8PM — Top 10 predicted zones:")
top10 = df_fri_pm.sort_values("predicted", ascending=False).head(10)
for _, row in top10.iterrows():
    print(f"  {row['zone']}: {row['predicted']:.1f} incidents/hr")

# Monday 4AM (dow=0, month=10, hour=4)
df_mon_am = build_prediction_df(hour=4, dow=0, month=10)
preds_mon = np.clip(model.predict(df_mon_am[FEATURE_COLS]), 0, None)

print(f"\nMonday 4AM — Mean predicted: {preds_mon.mean():.2f}, Max: {preds_mon.max():.2f}")
print("  (should be uniformly low)")

print("\n✓ PASS if Friday 8PM has B and K zones in top 5")
print("✓ PASS if Monday 4AM shows all zones < 5 incidents/hr")

# COMMAND ----------

# MAGIC %md ## Step 6: Fallback — Rolling Average Model (use if RMSE > 8)

# COMMAND ----------

# Uncomment and run if XGBoost RMSE > 8
# This simple baseline still clusters demand correctly for staging
"""
baseline_preds = test.merge(
    baselines[["INCIDENT_DISPATCH_AREA","hour","dayofweek","zone_baseline_avg"]],
    on=["INCIDENT_DISPATCH_AREA","hour","dayofweek"],
    how="left"
)["zone_baseline_avg"].fillna(1.0).values

baseline_rmse = np.sqrt(mean_squared_error(y_test, baseline_preds))
print(f"Baseline (rolling avg) RMSE: {baseline_rmse:.3f}")
print("If XGBoost RMSE barely beats this, both are acceptable for staging purposes")
"""

# COMMAND ----------

# MAGIC %md ## Delivery Checklist
# MAGIC
# MAGIC After this notebook completes:
# MAGIC 1. Download `demand_model.pkl` from `dbfs:/firstwave/artifacts/`
# MAGIC 2. Also download `zone_baselines.parquet` and `zone_stats.parquet` (from Notebook 04)
# MAGIC 3. Copy all 3 files to `backend/artifacts/` in the local repo
# MAGIC 4. Commit: `feat: ML artifacts — demand_model.pkl (RMSE=[X]), zone_baselines, zone_stats — closes #23`
# MAGIC 5. Push feat/pipeline branch and open PR to main
# MAGIC 6. Post in group chat: `demand_model.pkl AVAILABLE. RMSE=[X]. Ashwin: merge PR and POST /reload`
