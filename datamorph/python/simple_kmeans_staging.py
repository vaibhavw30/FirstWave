"""
Datamorph Python action — SIMPLIFIED Step 5: simple_kmeans_staging
FirstWave | GT Hacklytics 2026

Uses the trained XGBoost model to predict demand across all 31 zones for one
scenario, then runs weighted K-Means over the zone centroids to place K ambulance
staging points in the mathematical center of predicted demand.

Inputs:
  backend/artifacts/simple_demand_model.pkl
  backend/artifacts/simple_zone_baselines.parquet
Outputs:
  backend/artifacts/simple_staging.parquet
  backend/artifacts/simple_staging.json     (staging points: lat/lon/zone/demand)

Scenario defaults to Friday 8PM, October (the FirstWave demo peak). Override with
env vars HOUR, DOW, MONTH, TEMP, PRECIP if your datamorph action supports them.

Mirrors pipeline/07_staging_optimizer.py (the staging core), trimmed to 11 features.
"""

import json
import math
import os
import pathlib
import sys

import joblib
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans

ARTIFACTS = pathlib.Path("backend/artifacts")
MODEL_PKL = ARTIFACTS / "simple_demand_model.pkl"
BASELINE_PQ = ARTIFACTS / "simple_zone_baselines.parquet"
STAGING_PARQUET = ARTIFACTS / "simple_staging.parquet"
STAGING_JSON = ARTIFACTS / "simple_staging.json"

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
VALID_ZONES = list(ZONE_CENTROIDS.keys())

FEATURE_COLS = [
    "hour_sin", "hour_cos", "dow_sin", "dow_cos", "month_sin", "month_cos",
    "is_weekend", "temperature_2m", "precipitation", "is_severe_weather",
    "zone_baseline_avg",
]

# ── Scenario (env-overridable) ──────────────────────────────────────────────────
HOUR = int(os.environ.get("HOUR", 20))     # Friday 8PM
DOW = int(os.environ.get("DOW", 4))        # 0=Mon..6=Sun -> 4=Fri
MONTH = int(os.environ.get("MONTH", 10))
TEMP = float(os.environ.get("TEMP", 15.0))
PRECIP = float(os.environ.get("PRECIP", 0.0))
K = int(os.environ.get("K", 5))            # number of ambulances to stage


def predict_demand(model, baselines) -> dict:
    """Run inference for all 31 zones for the chosen scenario."""
    rows = []
    for z in VALID_ZONES:
        brow = baselines[(baselines["zone"] == z) &
                         (baselines["hour"] == HOUR) &
                         (baselines["dayofweek"] == DOW)]
        baseline_avg = float(brow["zone_baseline_avg"].iloc[0]) if len(brow) else 1.0
        rows.append({
            "zone": z,
            "hour_sin": math.sin(2 * math.pi * HOUR / 24),
            "hour_cos": math.cos(2 * math.pi * HOUR / 24),
            "dow_sin": math.sin(2 * math.pi * DOW / 7),
            "dow_cos": math.cos(2 * math.pi * DOW / 7),
            "month_sin": math.sin(2 * math.pi * MONTH / 12),
            "month_cos": math.cos(2 * math.pi * MONTH / 12),
            "is_weekend": 1 if DOW in (5, 6) else 0,
            "temperature_2m": TEMP,
            "precipitation": PRECIP,
            "is_severe_weather": 1 if PRECIP > 5 else 0,
            "zone_baseline_avg": baseline_avg,
        })
    df = pd.DataFrame(rows)
    df["predicted"] = np.clip(model.predict(df[FEATURE_COLS]), 0, None)
    return dict(zip(df["zone"], df["predicted"]))


def stage(predicted_counts: dict, k: int) -> list:
    """Weighted K-Means over zone centroids; weight = predicted demand."""
    zones = list(predicted_counts)
    weights = np.array([max(predicted_counts[z], 0.01) for z in zones])
    coords = np.array([[ZONE_CENTROIDS[z][1], ZONE_CENTROIDS[z][0]] for z in zones])  # [lat, lon]
    km = KMeans(n_clusters=k, random_state=42, n_init=20).fit(coords, sample_weight=weights)

    staging = []
    for i, center in enumerate(km.cluster_centers_):
        clat, clon = float(center[0]), float(center[1])
        cluster_zones = [zones[j] for j, lab in enumerate(km.labels_) if lab == i]
        nearest = min(cluster_zones,
                      key=lambda z: (ZONE_CENTROIDS[z][1] - clat) ** 2 + (ZONE_CENTROIDS[z][0] - clon) ** 2)
        staging.append({
            "staging_index": i,
            "lat": round(clat, 5),
            "lon": round(clon, 5),
            "nearest_zone": nearest,
            "cluster_zones": cluster_zones,
            "zone_count": len(cluster_zones),
            "total_demand": round(sum(predicted_counts[z] for z in cluster_zones), 1),
        })
    return staging


def main() -> None:
    for p in (MODEL_PKL, BASELINE_PQ):
        if not p.exists():
            sys.exit(f"ERROR: {p} not found. Run simple_train_xgboost.py first.")

    model = joblib.load(MODEL_PKL)
    baselines = pd.read_parquet(BASELINE_PQ)

    counts = predict_demand(model, baselines)
    staging = stage(counts, K)

    pd.DataFrame(staging).to_parquet(STAGING_PARQUET, index=False)
    STAGING_JSON.write_text(json.dumps(staging, indent=2))

    top5 = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:5]
    print("=" * 56)
    print(f"  Scenario: hour={HOUR} dow={DOW} month={MONTH} temp={TEMP} precip={PRECIP}  K={K}")
    print(f"  Total predicted city demand: {sum(counts.values()):.1f} incidents/hr")
    print("  Top-5 demand zones:")
    for z, c in top5:
        print(f"    {z}: {c:.1f}")
    print(f"  {K} staging points:")
    for s in staging:
        print(f"    [{s['staging_index']}] {s['nearest_zone']} "
              f"(lon={s['lon']}, lat={s['lat']}) — {s['zone_count']} zones, demand {s['total_demand']}")
    print(f"  Saved: {STAGING_PARQUET}  &  {STAGING_JSON}")
    print("=" * 56)
    print("  Sanity: on Friday 8PM, B/K (Bronx/Brooklyn) zones should top the demand list.")


if __name__ == "__main__":
    main()
