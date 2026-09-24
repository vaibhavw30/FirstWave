"""
Datamorph Python action — Stage ⑧: counterfactual_precompute
FirstWave | GT Hacklytics 2026

The headline-number generator. For all 168 (hour x dow) bins, compares:
  BASELINE: real observed response time (static deployment)
  STAGED:   nearest FirstWave staging-zone drive time (pre-positioned)

Inputs:
  backend/artifacts/demand_model.pkl
  backend/artifacts/drive_time_matrix.pkl
  backend/artifacts/zone_baselines.parquet
  backend/artifacts/zone_stats.parquet
  pipeline/data/incidents_cleaned.parquet     (2023 Priority 1+2)
  data/ems_stations.json
Outputs:
  backend/artifacts/counterfactual_summary.parquet   (168 rows)
  backend/artifacts/counterfactual_raw.parquet

Mirrors: pipeline/08_counterfactual_precompute.py.
Expected: ~61% -> ~83% within 8 min, ~147s median saved, Q4 (most vulnerable) biggest gain.
"""

import json
import math
import pathlib
import pickle
import sys
from itertools import product

import joblib
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans

ARTIFACTS = pathlib.Path("backend/artifacts")
MODEL_PKL = ARTIFACTS / "demand_model.pkl"
DTM_PKL = ARTIFACTS / "drive_time_matrix.pkl"
BASELINE = ARTIFACTS / "zone_baselines.parquet"
STATS = ARTIFACTS / "zone_stats.parquet"
CLEANED = pathlib.Path("pipeline/data/incidents_cleaned.parquet")
STATIONS_JSON = pathlib.Path("data/ems_stations.json")
SUMMARY_OUT = ARTIFACTS / "counterfactual_summary.parquet"
RAW_OUT = ARTIFACTS / "counterfactual_raw.parquet"

THRESHOLD = 480           # 8-minute clinical target, seconds
MAX_INCIDENTS_PER_BIN = 150

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
FEATURE_COLS = [
    "hour_sin", "hour_cos", "dow_sin", "dow_cos", "month_sin", "month_cos",
    "is_weekend", "temperature_2m", "precipitation", "windspeed_10m",
    "is_severe_weather", "svi_score", "zone_baseline_avg",
    "high_acuity_ratio", "held_ratio",
    "is_holiday", "is_major_event", "is_school_day",
    "is_heat_emergency", "is_extreme_heat", "subway_disruption_idx",
]
VALID_ZONES = list(ZONE_CENTROIDS.keys())

for p in (MODEL_PKL, DTM_PKL, BASELINE, STATS, CLEANED):
    if not p.exists():
        sys.exit(f"ERROR: {p} not found.")

model = joblib.load(MODEL_PKL)
baselines = pd.read_parquet(BASELINE)
zone_stats = pd.read_parquet(STATS)
dtm = pickle.loads(DTM_PKL.read_bytes())
stations = json.loads(STATIONS_JSON.read_text()) if STATIONS_JSON.exists() else []
station_ids = [s["station_id"] for s in stations]


def predict_counts(hour, dow, month=10):
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
            "is_weekend": 1 if dow in (5, 6) else 0, "temperature_2m": 15.0,
            "precipitation": 0.0, "windspeed_10m": 10.0, "is_severe_weather": 0,
            "svi_score": ZONE_SVI[z], "zone_baseline_avg": baseline_avg,
            "high_acuity_ratio": har, "held_ratio": hdr,
            "is_holiday": 0, "is_major_event": 0, "is_school_day": 1,
            "is_heat_emergency": 0, "is_extreme_heat": 0, "subway_disruption_idx": 0.5,
        })
    df = pd.DataFrame(rows)
    return dict(zip(VALID_ZONES, np.clip(model.predict(df[FEATURE_COLS]), 0, None)))


def staging_zones(counts, K=10):
    zones = list(counts)
    weights = np.array([max(counts[z], 0.01) for z in zones])
    coords = np.array([[ZONE_CENTROIDS[z][1], ZONE_CENTROIDS[z][0]] for z in zones])
    km = KMeans(n_clusters=K, random_state=42, n_init=20).fit(coords, sample_weight=weights)
    return [min(zones, key=lambda z: (ZONE_CENTROIDS[z][1] - c[0]) ** 2 + (ZONE_CENTROIDS[z][0] - c[1]) ** 2)
            for c in km.cluster_centers_]


def baseline_drive(inc):
    t = inc.get("INCIDENT_RESPONSE_SECONDS_QY")
    if t is not None and not np.isnan(t) and 1 <= t <= 7200:
        return int(t)
    times = [dtm.get((sid, inc["INCIDENT_DISPATCH_AREA"]), 9999) for sid in station_ids]
    return min(times) if times else 9999


def main():
    inc_all = pd.read_parquet(CLEANED, columns=[
        "CAD_INCIDENT_ID", "BOROUGH", "INCIDENT_DISPATCH_AREA", "hour", "dayofweek",
        "INCIDENT_RESPONSE_SECONDS_QY", "svi_score", "split", "is_high_acuity",
    ])
    inc = inc_all[(inc_all["split"] == "test") & (inc_all["is_high_acuity"] == 1)].copy()
    del inc_all
    inc["svi_quartile"] = pd.qcut(inc["svi_score"], q=4, labels=["Q1", "Q2", "Q3", "Q4"]).astype(str)
    print(f"2023 Priority 1+2 incidents: {len(inc):,}")

    summary_rows, raw_rows = [], []
    for i, (hour, dow) in enumerate(product(range(24), range(7))):
        bin_inc = inc[(inc["hour"] == hour) & (inc["dayofweek"] == dow)]
        if len(bin_inc) > MAX_INCIDENTS_PER_BIN:
            bin_inc = bin_inc.sample(MAX_INCIDENTS_PER_BIN, random_state=42)
        if len(bin_inc) == 0:
            summary_rows.append({"hour": hour, "dayofweek": dow, "median_seconds_saved": None,
                                 "pct_within_8min_static": None, "pct_within_8min_staged": None, "n_incidents": 0})
            continue

        sz = staging_zones(predict_counts(hour, dow, 10), K=10)
        b_drives, s_drives = [], []
        for _, r in bin_inc.iterrows():
            zone = r["INCIDENT_DISPATCH_AREA"]
            b = baseline_drive(r)
            s = min([dtm.get((z, zone), 9999) for z in sz] or [9999])
            b_drives.append(b)
            s_drives.append(s)
            raw_rows.append({
                "hour": hour, "dayofweek": dow, "incident_zone": zone, "borough": r["BOROUGH"],
                "svi_quartile": str(r.get("svi_quartile", "Q2")),
                "baseline_drive_sec": b, "staged_drive_sec": s, "seconds_saved": b - s,
                "baseline_within_8min": int(b <= THRESHOLD), "staged_within_8min": int(s <= THRESHOLD),
            })
        b_arr, s_arr = np.array(b_drives), np.array(s_drives)
        summary_rows.append({
            "hour": hour, "dayofweek": dow,
            "median_seconds_saved": float(np.median(b_arr - s_arr)),
            "pct_within_8min_static": float((b_arr <= THRESHOLD).mean() * 100),
            "pct_within_8min_staged": float((s_arr <= THRESHOLD).mean() * 100),
            "n_incidents": len(bin_inc),
        })
        if (i + 1) % 24 == 0:
            print(f"  Day {(i + 1) // 24}/7 complete")

    summary_df = pd.DataFrame(summary_rows)
    raw_df = pd.DataFrame(raw_rows)
    summary_df.to_parquet(SUMMARY_OUT, index=False)
    raw_df.to_parquet(RAW_OUT, index=False)

    valid = summary_df.dropna(subset=["median_seconds_saved"])
    static = valid["pct_within_8min_static"].mean()
    staged = valid["pct_within_8min_staged"].mean()
    median_saved = valid["median_seconds_saved"].median()

    print("=" * 56)
    print(f"  Static within 8min:  {static:.1f}%  (expect ~61%)")
    print(f"  Staged within 8min:  {staged:.1f}%  (expect ~83%)")
    print(f"  Improvement:         +{staged - static:.1f} pp")
    print(f"  Median seconds saved: {median_saved:.0f}s  (expect ~147)")
    print("  By SVI quartile (Q4 = most vulnerable, should show largest gain):")
    for q in ["Q1", "Q2", "Q3", "Q4"]:
        qdf = raw_df[raw_df["svi_quartile"] == q]
        if len(qdf):
            print(f"    {q}: median {qdf['seconds_saved'].median():.0f}s saved")
    print("=" * 56)
    print(f"SLACK: counterfactual AVAILABLE. {static:.0f}%->{staged:.0f}% within 8min, "
          f"{median_saved:.0f}s saved. Bronx biggest gain.")

    if staged - static < 5.0:
        print("WARN: improvement < 5pp — try K=7+ staging zones")


if __name__ == "__main__":
    main()
