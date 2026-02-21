"""
Script 07 — Staging Optimizer Validation
FirstWave | GT Hacklytics 2026

Validates the weighted K-Means staging optimizer against 3 scenarios.
This is a confidence check -- NOT an artifact producer.

Prerequisites:
  backend/artifacts/demand_model.pkl
  backend/artifacts/zone_baselines.parquet
  backend/artifacts/zone_stats.parquet

Run: python pipeline/07_staging_optimizer.py
"""

import math
import pathlib
import sys
import joblib
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans

# ── Paths ──────────────────────────────────────────────────────────────────────
ARTIFACTS_DIR = pathlib.Path("backend/artifacts")

MODEL_PKL   = ARTIFACTS_DIR / "demand_model.pkl"
BASELINE_PQ = ARTIFACTS_DIR / "zone_baselines.parquet"
STATS_PQ    = ARTIFACTS_DIR / "zone_stats.parquet"

for p in [MODEL_PKL, BASELINE_PQ, STATS_PQ]:
    if not p.exists():
        print(f"ERROR: {p} not found. Run Scripts 04 and 05 first.", file=sys.stderr)
        sys.exit(1)

# ── Constants ──────────────────────────────────────────────────────────────────
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
    'B1':0.94,'B2':0.89,'B3':0.87,'B4':0.72,'B5':0.68,
    'K1':0.52,'K2':0.58,'K3':0.82,'K4':0.84,'K5':0.79,'K6':0.60,'K7':0.45,
    'M1':0.31,'M2':0.18,'M3':0.15,'M4':0.20,'M5':0.12,
    'M6':0.14,'M7':0.73,'M8':0.65,'M9':0.61,
    'Q1':0.71,'Q2':0.44,'Q3':0.38,'Q4':0.55,'Q5':0.67,'Q6':0.48,'Q7':0.41,
    'S1':0.38,'S2':0.32,'S3':0.28,
}
FEATURE_COLS = [
    "hour_sin","hour_cos","dow_sin","dow_cos","month_sin","month_cos",
    "is_weekend","temperature_2m","precipitation","windspeed_10m",
    "is_severe_weather","svi_score","zone_baseline_avg",
    "high_acuity_ratio","held_ratio",
]
VALID_ZONES = list(ZONE_CENTROIDS.keys())

# ── Step 1: Load artifacts ─────────────────────────────────────────────────────
print("Loading artifacts...")
model      = joblib.load(MODEL_PKL)
baselines  = pd.read_parquet(BASELINE_PQ)
zone_stats = pd.read_parquet(STATS_PQ)

print(f"  demand_model.pkl loaded")
print(f"  zone_baselines: {len(baselines)} rows")
print(f"  zone_stats: {len(zone_stats)} rows")

# ── Helper functions ───────────────────────────────────────────────────────────
def build_features(hour, dow, month, temp=15.0, precip=0.0, wind=10.0):
    """Build 31-zone feature DataFrame and run model inference."""
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
            "is_severe_weather": 1 if precip > 5 else 0,
            "svi_score": ZONE_SVI[zone],
            "zone_baseline_avg": baseline_avg,
            "high_acuity_ratio": har,
            "held_ratio": hdr,
        })
    df = pd.DataFrame(rows)
    preds = np.clip(model.predict(df[FEATURE_COLS]), 0, None)
    return dict(zip(VALID_ZONES, preds))


def stage_ambulances(predicted_counts, K=5):
    """Run weighted K-Means, return K staging points."""
    zones   = list(predicted_counts.keys())
    weights = np.array([max(predicted_counts[z], 0.01) for z in zones])
    coords  = np.array([[ZONE_CENTROIDS[z][1], ZONE_CENTROIDS[z][0]] for z in zones])
    km = KMeans(n_clusters=K, random_state=42, n_init=20)
    km.fit(coords, sample_weight=weights)
    staging = []
    for i, center in enumerate(km.cluster_centers_):
        clat, clon = center
        cluster_zones = [zones[j] for j, label in enumerate(km.labels_) if label == i]
        nearest_zone = min(
            cluster_zones,
            key=lambda z: (ZONE_CENTROIDS[z][1]-clat)**2 + (ZONE_CENTROIDS[z][0]-clon)**2
        )
        staging.append({
            "staging_index": i,
            "lat": float(clat),
            "lon": float(clon),
            "nearest_zone": nearest_zone,
            "cluster_zones": cluster_zones,
            "zone_count": len(cluster_zones),
            "total_demand": sum(predicted_counts[z] for z in cluster_zones),
        })
    return staging


# ── Step 2: Validate 3 scenarios ──────────────────────────────────────────────
# dow: 0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri, 5=Sat, 6=Sun
scenarios = [
    ("Monday 4AM (quiet)",   0, 10,  4),
    ("Wednesday Noon",       2, 10, 12),
    ("Friday 8PM (peak)",    4, 10, 20),
]

results = {}
for label, dow, month, hour in scenarios:
    counts  = build_features(hour, dow, month)
    staging = stage_ambulances(counts, K=5)
    top5    = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:5]
    results[label] = {"counts": counts, "staging": staging, "top5": top5}

    print(f"\n{'─'*50}")
    print(f"Scenario: {label}")
    print(f"  Top 5 zones by predicted demand:")
    for zone, count in top5:
        bar = "#" * min(int(count), 30)
        print(f"    {zone}: {count:.1f} {bar}")
    print(f"  Total city demand: {sum(counts.values()):.1f} incidents/hr")
    print(f"  Staging points (K=5):")
    for s in staging:
        print(f"    [{s['staging_index']}] lon={s['lon']:.4f}, lat={s['lat']:.4f} "
              f"-> nearest zone: {s['nearest_zone']} "
              f"({s['zone_count']} zones, {s['total_demand']:.1f} demand)")

# ── Step 3: Pass/Fail checks ──────────────────────────────────────────────────
print("\n" + "=" * 55)
print("  SCRIPT 07 -- VALIDATION CHECKS")
print("=" * 55)

# Check 1: Friday 8PM -- Bronx/Brooklyn should dominate top 5
fri_top5_zones = [z for z, _ in results["Friday 8PM (peak)"]["top5"]]
bk_in_top5 = sum(1 for z in fri_top5_zones if z.startswith(("B","K")))
print(f"\n  Check 1: Friday 8PM top-5 = {fri_top5_zones}")
if bk_in_top5 >= 3:
    print(f"  PASS: {bk_in_top5}/5 are B/K zones (Bronx/Brooklyn)")
else:
    print(f"  FAIL: Only {bk_in_top5}/5 are B/K zones -- check zone_baseline_avg merge")

# Check 2: Monday 4AM -- all zones should be low
mon_counts = results["Monday 4AM (quiet)"]["counts"]
mon_max  = max(mon_counts.values())
mon_mean = sum(mon_counts.values()) / len(mon_counts)
print(f"\n  Check 2: Monday 4AM -- max={mon_max:.2f}, mean={mon_mean:.2f}")
if mon_max < 8.0:
    print(f"  PASS: Monday 4AM max demand < 8 (quiet period)")
else:
    print(f"  WARNING: Monday 4AM max = {mon_max:.1f} -- seems high for quiet period")

# Check 3: Friday >> Monday
fri_total = sum(results["Friday 8PM (peak)"]["counts"].values())
mon_total = sum(results["Monday 4AM (quiet)"]["counts"].values())
ratio = fri_total / mon_total if mon_total > 0 else 0
print(f"\n  Check 3: Demand ratio Friday 8PM / Monday 4AM = {ratio:.1f}x")
if ratio > 2.0:
    print(f"  PASS: Friday peak is {ratio:.1f}x Monday quiet")
else:
    print(f"  FAIL: Ratio < 2x -- model not capturing temporal patterns")

# Check 4: Staging shifts toward Bronx on Friday
fri_staging_zones = [s["nearest_zone"] for s in results["Friday 8PM (peak)"]["staging"]]
mon_staging_zones = [s["nearest_zone"] for s in results["Monday 4AM (quiet)"]["staging"]]
fri_bronx = sum(1 for z in fri_staging_zones if z.startswith("B"))
print(f"\n  Check 4: Friday staging = {fri_staging_zones}")
print(f"           Monday staging  = {mon_staging_zones}")
if fri_bronx >= 1:
    print(f"  PASS: {fri_bronx} Friday staging point(s) in Bronx zones")
else:
    print(f"  WARNING: No Friday staging in Bronx despite high demand")

print("\n" + "=" * 55)
print("  -> If all checks pass: run python pipeline/08_counterfactual_precompute.py")
print("  -> If checks fail: debug model merge (see CLAUDE.md troubleshooting)")
print("=" * 55)
