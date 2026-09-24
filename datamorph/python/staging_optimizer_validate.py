"""
Datamorph Python action — Stage ⑦: staging_optimizer_validate  (Branch gate)
FirstWave | GT Hacklytics 2026

Produces NO artifact. Validates the weighted K-Means staging optimizer against
3 scenarios. Exit code 0 = all hard checks pass -> Branch proceeds to Stage ⑧.
Exit code 1 = halt + Slack alert.

Inputs:
  backend/artifacts/demand_model.pkl
  backend/artifacts/zone_baselines.parquet
  backend/artifacts/zone_stats.parquet

Mirrors: pipeline/07_staging_optimizer.py.
"""

import math
import pathlib
import sys

import joblib
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans

ARTIFACTS = pathlib.Path("backend/artifacts")
MODEL_PKL = ARTIFACTS / "demand_model.pkl"
BASELINE = ARTIFACTS / "zone_baselines.parquet"
STATS = ARTIFACTS / "zone_stats.parquet"

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
ZONE_SVI = {
    'B1': 0.94, 'B2': 0.89, 'B3': 0.87, 'B4': 0.72, 'B5': 0.68,
    'K1': 0.52, 'K2': 0.58, 'K3': 0.82, 'K4': 0.84, 'K5': 0.79, 'K6': 0.60, 'K7': 0.45,
    'M1': 0.31, 'M2': 0.18, 'M3': 0.15, 'M4': 0.20, 'M5': 0.12,
    'M6': 0.14, 'M7': 0.73, 'M8': 0.65, 'M9': 0.61,
    'Q1': 0.71, 'Q2': 0.44, 'Q3': 0.38, 'Q4': 0.55, 'Q5': 0.67, 'Q6': 0.48, 'Q7': 0.41,
    'S1': 0.38, 'S2': 0.32, 'S3': 0.28,
}
# Stage ⑦ uses the original 15-feature inference subset (matches pipeline/07)
FEATURE_COLS = [
    "hour_sin", "hour_cos", "dow_sin", "dow_cos", "month_sin", "month_cos",
    "is_weekend", "temperature_2m", "precipitation", "windspeed_10m",
    "is_severe_weather", "svi_score", "zone_baseline_avg",
    "high_acuity_ratio", "held_ratio",
]
VALID_ZONES = list(ZONE_CENTROIDS.keys())

model = joblib.load(MODEL_PKL)
baselines = pd.read_parquet(BASELINE)
zone_stats = pd.read_parquet(STATS)


def build_features(hour, dow, month, temp=15.0, precip=0.0, wind=10.0):
    rows = []
    for z in VALID_ZONES:
        brow = baselines[(baselines["INCIDENT_DISPATCH_AREA"] == z) &
                         (baselines["hour"] == hour) & (baselines["dayofweek"] == dow)]
        baseline_avg = float(brow["zone_baseline_avg"].iloc[0]) if len(brow) else 3.0
        zrow = zone_stats[zone_stats["INCIDENT_DISPATCH_AREA"] == z]
        har = float(zrow["high_acuity_ratio"].iloc[0]) if len(zrow) else 0.23
        hdr = float(zrow["held_ratio"].iloc[0]) if len(zrow) else 0.06
        rows.append({
            "hour_sin": math.sin(2 * math.pi * hour / 24), "hour_cos": math.cos(2 * math.pi * hour / 24),
            "dow_sin": math.sin(2 * math.pi * dow / 7), "dow_cos": math.cos(2 * math.pi * dow / 7),
            "month_sin": math.sin(2 * math.pi * month / 12), "month_cos": math.cos(2 * math.pi * month / 12),
            "is_weekend": 1 if dow in (5, 6) else 0, "temperature_2m": temp,
            "precipitation": precip, "windspeed_10m": wind, "is_severe_weather": 1 if precip > 5 else 0,
            "svi_score": ZONE_SVI[z], "zone_baseline_avg": baseline_avg,
            "high_acuity_ratio": har, "held_ratio": hdr,
        })
    df = pd.DataFrame(rows)
    return dict(zip(VALID_ZONES, np.clip(model.predict(df[FEATURE_COLS]), 0, None)))


def stage(counts, K=5):
    zones = list(counts)
    weights = np.array([max(counts[z], 0.01) for z in zones])
    coords = np.array([[ZONE_CENTROIDS[z][1], ZONE_CENTROIDS[z][0]] for z in zones])
    km = KMeans(n_clusters=K, random_state=42, n_init=20).fit(coords, sample_weight=weights)
    out = []
    for c in km.cluster_centers_:
        nearest = min(zones, key=lambda z: (ZONE_CENTROIDS[z][1] - c[0]) ** 2 + (ZONE_CENTROIDS[z][0] - c[1]) ** 2)
        out.append(nearest)
    return out


def main():
    fri = build_features(20, 4, 10)
    mon = build_features(4, 0, 10)
    fri_top5 = [z for z, _ in sorted(fri.items(), key=lambda x: x[1], reverse=True)[:5]]
    fri_staging = stage(fri, 5)

    bk = sum(1 for z in fri_top5 if z.startswith(("B", "K")))
    mon_max = max(mon.values())
    ratio = sum(fri.values()) / sum(mon.values())
    fri_bronx = sum(1 for z in fri_staging if z.startswith("B"))

    print(f"  Friday top-5: {fri_top5}  ({bk}/5 B/K)")
    print(f"  Monday 4AM max demand: {mon_max:.2f}")
    print(f"  Friday/Monday demand ratio: {ratio:.1f}x")
    print(f"  Friday staging: {fri_staging}  ({fri_bronx} in Bronx)")

    hard_fail = []
    if bk < 3:
        hard_fail.append("Friday top-5 has <3 B/K zones (check zone_baseline_avg merge)")
    if ratio <= 2.0:
        hard_fail.append(f"Friday/Monday ratio {ratio:.1f}x <= 2.0 (no temporal signal)")
    if mon_max >= 8.0:
        print(f"WARN: Monday 4AM max {mon_max:.1f} seems high for a quiet period")
    if fri_bronx < 1:
        print("WARN: no Friday staging point in Bronx despite high demand")

    if hard_fail:
        print("GATE FAIL:")
        for f in hard_fail:
            print(f"  - {f}")
        sys.exit(1)
    print("GATE PASS — proceed to Stage ⑧")


if __name__ == "__main__":
    main()
