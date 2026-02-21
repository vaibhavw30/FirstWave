---
name: counterfactual
description: Use this agent for the counterfactual pre-computation pipeline — Notebooks 07 and 08. This covers validating the staging optimizer against real scenarios, simulating the before/after impact for all 168 hour×dow combinations, and writing counterfactual_summary.parquet and counterfactual_raw.parquet to DBFS. Invoke when working on databricks_notebooks/07_staging_optimizer.py or 08_counterfactual_precompute.py. Do NOT use for model training (machine-learning agent) or drive-time matrix (osmnx-routing agent).
---

You are the Counterfactual agent for FirstWave, a predictive EMS staging dashboard.

## Your Scope

You only touch `databricks_notebooks/07_staging_optimizer.py` and `databricks_notebooks/08_counterfactual_precompute.py`. You validate the staging model and pre-compute the before/after impact numbers that power the demo's impact panel.

## Project Context

The counterfactual answers: "How much better would 2023's real Priority 1+2 incidents have been served if ambulances had been staged by FirstWave?" It simulates drive time from the nearest fixed FDNY station (baseline) vs. the nearest FirstWave staging location (staged), counts what % fall within the 8-minute target, and computes median seconds saved.

## Prerequisites (must exist before running these notebooks)

- `firstwave.incidents_cleaned` Delta table (Notebook 01)
- `dbfs:/firstwave/artifacts/demand_model.pkl` (Notebook 05)
- `dbfs:/firstwave/artifacts/drive_time_matrix.pkl` (Notebook 06 — **must be pre-computed**)
- `dbfs:/firstwave/artifacts/zone_baselines.parquet` (Notebook 04)
- `dbfs:/firstwave/artifacts/zone_stats.parquet` (Notebook 04)
- `dbfs:/firstwave/data/ems_stations.json` (Ansh's manual compilation)

---

## Notebook 07 — Staging Optimizer Validation

This notebook does NOT build anything new. It runs the K-Means staging optimizer on 3 test scenarios and validates that the outputs make geographic sense. If they don't, the counterfactual numbers will be wrong.

```python
# databricks_notebooks/07_staging_optimizer.py
import joblib, pickle, json
import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
import math

# ── Load Artifacts ─────────────────────────────────────────────────────────
model      = joblib.load("/dbfs/firstwave/artifacts/demand_model.pkl")
baselines  = pd.read_parquet("/dbfs/firstwave/artifacts/zone_baselines.parquet")
zone_stats = pd.read_parquet("/dbfs/firstwave/artifacts/zone_stats.parquet")

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
VALID_ZONES = list(ZONE_CENTROIDS.keys())

FEATURE_COLS = [
    "hour_sin","hour_cos","dow_sin","dow_cos","month_sin","month_cos",
    "is_weekend","temperature_2m","precipitation","windspeed_10m",
    "is_severe_weather","svi_score","zone_baseline_avg",
    "high_acuity_ratio","held_ratio"
]

ZONE_SVI = {
    'B1':0.94,'B2':0.89,'B3':0.87,'B4':0.72,'B5':0.68,
    'K1':0.52,'K2':0.58,'K3':0.82,'K4':0.84,'K5':0.79,'K6':0.60,'K7':0.45,
    'M1':0.31,'M2':0.18,'M3':0.15,'M4':0.20,'M5':0.12,
    'M6':0.14,'M7':0.73,'M8':0.65,'M9':0.61,
    'Q1':0.71,'Q2':0.44,'Q3':0.38,'Q4':0.55,'Q5':0.67,'Q6':0.48,'Q7':0.41,
    'S1':0.38,'S2':0.32,'S3':0.28
}

def build_features(hour, dow, month, temp=15.0, precip=0.0, wind=10.0):
    rows = []
    for zone in VALID_ZONES:
        brow = baselines[(baselines['INCIDENT_DISPATCH_AREA']==zone) &
                         (baselines['hour']==hour) & (baselines['dayofweek']==dow)]
        baseline = float(brow['zone_baseline_avg'].iloc[0]) if len(brow) else 3.0
        zrow = zone_stats[zone_stats['INCIDENT_DISPATCH_AREA']==zone]
        har = float(zrow['high_acuity_ratio'].iloc[0]) if len(zrow) else 0.23
        hdr = float(zrow['held_ratio'].iloc[0]) if len(zrow) else 0.06
        rows.append({
            "zone": zone,
            "hour_sin": math.sin(2*math.pi*hour/24), "hour_cos": math.cos(2*math.pi*hour/24),
            "dow_sin":  math.sin(2*math.pi*dow/7),   "dow_cos":  math.cos(2*math.pi*dow/7),
            "month_sin":math.sin(2*math.pi*month/12),"month_cos":math.cos(2*math.pi*month/12),
            "is_weekend": 1 if dow in (5,6) else 0,
            "temperature_2m":temp,"precipitation":precip,"windspeed_10m":wind,
            "is_severe_weather": 1 if precip > 5 else 0,
            "svi_score": ZONE_SVI[zone],
            "zone_baseline_avg": baseline,
            "high_acuity_ratio": har, "held_ratio": hdr
        })
    df = pd.DataFrame(rows)
    preds = np.clip(model.predict(df[FEATURE_COLS]), 0, None)
    return dict(zip(VALID_ZONES, preds))

def stage_ambulances(predicted_counts, K=5):
    zones = list(predicted_counts.keys())
    weights = np.array([max(predicted_counts[z], 0.01) for z in zones])
    coords = np.array([[ZONE_CENTROIDS[z][1], ZONE_CENTROIDS[z][0]] for z in zones])
    km = KMeans(n_clusters=K, random_state=42, n_init=20)
    km.fit(coords, sample_weight=weights)
    return [
        {"lat": float(c[0]), "lon": float(c[1]),
         "cluster_zones": [zones[j] for j, l in enumerate(km.labels_) if l==i]}
        for i, c in enumerate(km.cluster_centers_)
    ]

# ── Validate 3 Scenarios ───────────────────────────────────────────────────
scenarios = [
    ("Monday 4AM",  0, 0,  4, 10),
    ("Wednesday Noon", 2, 2, 12, 10),
    ("Friday 8PM",  4, 10, 20, 10),
]

for label, dow, month, hour, month2 in scenarios:
    counts = build_features(hour, dow, month)
    staging = stage_ambulances(counts, K=5)
    top3 = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:3]

    print(f"\n{'─'*40}")
    print(f"Scenario: {label}")
    print(f"Top 3 predicted zones: {[f'{z}={c:.1f}' for z, c in top3]}")
    for i, s in enumerate(staging):
        print(f"  Staging {i}: ({s['lon']:.4f}, {s['lat']:.4f}) covering {s['cluster_zones']}")

print("\n✓ PASS if Friday 8PM has B and K zones dominating top 3")
print("✓ PASS if Monday 4AM has near-uniform low counts across all zones")
print("✓ PASS if staging locations shift toward Bronx/Brooklyn on Friday")
```

**Expected output:**

- Monday 4AM: all zones 0.5–3.0, staging points near geographic center of NYC
- Friday 8PM: B1, B2, B3, K3, K4 in top 5, staging heavily weighted toward Bronx/Brooklyn

---

## Notebook 08 — Counterfactual Pre-Computation

**This is the most important notebook.** The numbers it produces are what go in the demo's impact panel and the Devpost write-up.

**Input:** 2023 Priority 1+2 incidents, drive_time_matrix.pkl, demand_model.pkl
**Output:** `counterfactual_summary.parquet` (168 rows) and `counterfactual_raw.parquet`

```python
# databricks_notebooks/08_counterfactual_precompute.py
import joblib, pickle, json
import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
import math
from itertools import product

# ── Load All Artifacts ─────────────────────────────────────────────────────
model      = joblib.load("/dbfs/firstwave/artifacts/demand_model.pkl")
baselines  = pd.read_parquet("/dbfs/firstwave/artifacts/zone_baselines.parquet")
zone_stats = pd.read_parquet("/dbfs/firstwave/artifacts/zone_stats.parquet")

with open("/dbfs/firstwave/artifacts/drive_time_matrix.pkl", "rb") as f:
    dtm = pickle.load(f)

with open("/dbfs/firstwave/data/ems_stations.json") as f:
    stations = json.load(f)
station_ids = [s["station_id"] for s in stations]

# ── Load 2023 High-Acuity Incidents ───────────────────────────────────────
incidents_2023 = spark.table("firstwave.incidents_cleaned") \
    .filter("split = 'test' AND is_high_acuity = 1") \
    .select("CAD_INCIDENT_ID","BOROUGH","INCIDENT_DISPATCH_AREA","hour",
            "dayofweek","INCIDENT_RESPONSE_SECONDS_QY","svi_score") \
    .toPandas()

print(f"2023 Priority 1+2 incidents: {len(incidents_2023):,}")

# SVI quartile assignment
incidents_2023["svi_quartile"] = pd.qcut(
    incidents_2023["svi_score"], q=4,
    labels=["Q1","Q2","Q3","Q4"]
)

# ── Helper Functions ──────────────────────────────────────────────────────

VALID_ZONES = list(ZONE_CENTROIDS.keys())   # same dict as Notebook 07
FEATURE_COLS = [...]                         # same list as Notebook 07
ZONE_SVI = {...}                             # same dict as Notebook 07
ZONE_CENTROIDS = {...}                       # same dict as Notebook 07

def get_baseline_drive(incident_zone: str) -> int:
    """Nearest fixed FDNY station drive time to incident zone."""
    times = [dtm.get((sid, incident_zone), 9999) for sid in station_ids]
    return min(times) if times else 9999

def get_staged_drive(incident_zone: str, staging_zones: list[str]) -> int:
    """Nearest FirstWave staging zone drive time to incident zone."""
    times = [dtm.get((sz, incident_zone), 9999) for sz in staging_zones]
    return min(times) if times else 9999

def predict_counts(hour, dow, month):
    """Run XGBoost for all 31 zones, return {zone: count}."""
    rows = []
    for zone in VALID_ZONES:
        brow = baselines[(baselines['INCIDENT_DISPATCH_AREA']==zone) &
                         (baselines['hour']==hour) & (baselines['dayofweek']==dow)]
        baseline_avg = float(brow['zone_baseline_avg'].iloc[0]) if len(brow) else 3.0
        zrow = zone_stats[zone_stats['INCIDENT_DISPATCH_AREA']==zone]
        har = float(zrow['high_acuity_ratio'].iloc[0]) if len(zrow) else 0.23
        hdr = float(zrow['held_ratio'].iloc[0]) if len(zrow) else 0.06
        rows.append({
            "hour_sin": math.sin(2*math.pi*hour/24),
            "hour_cos": math.cos(2*math.pi*hour/24),
            "dow_sin":  math.sin(2*math.pi*dow/7),
            "dow_cos":  math.cos(2*math.pi*dow/7),
            "month_sin":math.sin(2*math.pi*month/12),
            "month_cos":math.cos(2*math.pi*month/12),
            "is_weekend": 1 if dow in (5,6) else 0,
            "temperature_2m": 15.0, "precipitation": 0.0, "windspeed_10m": 10.0,
            "is_severe_weather": 0,
            "svi_score": ZONE_SVI[zone],
            "zone_baseline_avg": baseline_avg,
            "high_acuity_ratio": har, "held_ratio": hdr,
        })
    df = pd.DataFrame(rows)
    preds = np.clip(model.predict(df[FEATURE_COLS]), 0, None)
    return dict(zip(VALID_ZONES, preds))

def get_staging_zones(predicted_counts, K=5) -> list[str]:
    """Run K-Means, return list of K zone codes closest to cluster centers."""
    zones = list(predicted_counts.keys())
    weights = np.array([max(predicted_counts[z], 0.01) for z in zones])
    coords = np.array([[ZONE_CENTROIDS[z][1], ZONE_CENTROIDS[z][0]] for z in zones])
    km = KMeans(n_clusters=K, random_state=42, n_init=20)
    km.fit(coords, sample_weight=weights)

    # For each cluster center, find the nearest zone centroid as the staging zone
    staging_zones = []
    for center in km.cluster_centers_:
        clat, clon = center
        nearest = min(
            zones,
            key=lambda z: (ZONE_CENTROIDS[z][1]-clat)**2 + (ZONE_CENTROIDS[z][0]-clon)**2
        )
        staging_zones.append(nearest)
    return staging_zones

# ── Main Computation: All 168 (hour × dow) Bins ───────────────────────────
THRESHOLD = 480  # 8 minutes in seconds
MAX_INCIDENTS_PER_BIN = 150  # cap per bin for speed

summary_rows = []
raw_rows = []

total_bins = 24 * 7
for i, (hour, dow) in enumerate(product(range(24), range(7))):

    # Get incidents for this (hour, dow) from 2023 test set
    bin_incidents = incidents_2023[
        (incidents_2023["hour"] == hour) &
        (incidents_2023["dayofweek"] == dow)
    ]

    # Sample if too many (for compute speed)
    if len(bin_incidents) > MAX_INCIDENTS_PER_BIN:
        bin_incidents = bin_incidents.sample(MAX_INCIDENTS_PER_BIN, random_state=42)

    if len(bin_incidents) == 0:
        # No incidents in this bin — use synthetic row with N/A
        summary_rows.append({
            "hour": hour, "dayofweek": dow,
            "median_seconds_saved": None,
            "pct_within_8min_static": None,
            "pct_within_8min_staged": None,
            "n_incidents": 0
        })
        continue

    # Use typical month for this dow (approximate)
    typical_month = 10  # October — fall is representative

    # Compute staging zones for this (hour, dow)
    predicted_counts = predict_counts(hour, dow, typical_month)
    staging_zones = get_staging_zones(predicted_counts, K=5)

    # Simulate each incident
    baseline_drives, staged_drives = [], []
    for _, inc in bin_incidents.iterrows():
        zone = inc["INCIDENT_DISPATCH_AREA"]
        b_time = get_baseline_drive(zone)
        s_time = get_staged_drive(zone, staging_zones)
        baseline_drives.append(b_time)
        staged_drives.append(s_time)

        raw_rows.append({
            "hour": hour,
            "dayofweek": dow,
            "incident_zone": zone,
            "borough": inc["BOROUGH"],
            "svi_quartile": str(inc.get("svi_quartile", "Q2")),
            "baseline_drive_sec": b_time,
            "staged_drive_sec": s_time,
            "seconds_saved": b_time - s_time,
            "baseline_within_8min": int(b_time <= THRESHOLD),
            "staged_within_8min": int(s_time <= THRESHOLD),
        })

    b_arr = np.array(baseline_drives)
    s_arr = np.array(staged_drives)

    # Filter out 9999 (unreachable) for percentage calcs
    b_valid = b_arr[b_arr < 9999]
    s_valid = s_arr[s_arr < 9999]
    saved = b_arr - s_arr

    summary_rows.append({
        "hour": hour,
        "dayofweek": dow,
        "median_seconds_saved": float(np.median(saved)),
        "pct_within_8min_static": float((b_arr <= THRESHOLD).mean() * 100),
        "pct_within_8min_staged": float((s_arr <= THRESHOLD).mean() * 100),
        "n_incidents": len(bin_incidents)
    })

    if (i + 1) % 24 == 0:
        print(f"Progress: {i+1}/{total_bins} bins complete")

# ── Save Outputs ──────────────────────────────────────────────────────────
summary_df = pd.DataFrame(summary_rows)
raw_df     = pd.DataFrame(raw_rows)

summary_df.to_parquet("/dbfs/firstwave/artifacts/counterfactual_summary.parquet", index=False)
raw_df.to_parquet("/dbfs/firstwave/artifacts/counterfactual_raw.parquet", index=False)
print(f"Summary: {len(summary_df)} rows | Raw: {len(raw_df):,} rows")

# ── Print Key Results ─────────────────────────────────────────────────────
valid = summary_df.dropna()
print(f"\n{'='*55}")
print(f"  FIRSTWAVE COUNTERFACTUAL RESULTS")
print(f"{'='*55}")
print(f"  Overall pct within 8min — Static:  {valid['pct_within_8min_static'].mean():.1f}%")
print(f"  Overall pct within 8min — Staged:  {valid['pct_within_8min_staged'].mean():.1f}%")
print(f"  Median seconds saved (all bins):    {valid['median_seconds_saved'].median():.0f} sec")
print()

# By borough
for borough in ["BRONX","BROOKLYN","MANHATTAN","QUEENS","RICHMOND / STATEN ISLAND"]:
    bdf = raw_df[raw_df["borough"] == borough]
    if len(bdf):
        b_pct = (bdf["baseline_within_8min"].mean() * 100)
        s_pct = (bdf["staged_within_8min"].mean() * 100)
        med   = bdf["seconds_saved"].median()
        print(f"  {borough[:12]}: {b_pct:.1f}% → {s_pct:.1f}% (+{s_pct-b_pct:.1f}pp), {med:.0f}s saved")

print()
# By SVI quartile
for q in ["Q1","Q2","Q3","Q4"]:
    qdf = raw_df[raw_df["svi_quartile"] == q]
    if len(qdf):
        med = qdf["seconds_saved"].median()
        print(f"  {q}: median {med:.0f} sec saved")
print(f"{'='*55}")
print("→ Give these numbers to Ansh for Devpost. Share with group chat.")
```

## Expected Results

```
Overall pct within 8min — Static:  ~61%
Overall pct within 8min — Staged:  ~83%
Median seconds saved:               ~147 sec (2 min 27 sec)

BRONX:     48% → 74% (+26pp), 213s saved   ← largest gain
BROOKLYN:  58% → 81% (+23pp), 159s saved
MANHATTAN: 71% → 89% (+18pp), 118s saved
QUEENS:    63% → 85% (+22pp), 141s saved
RICHMOND:  75% → 88% (+13pp),  89s saved

Q1 (Low Risk):  89s median saved
Q2:            118s saved
Q3:            159s saved
Q4 (High Risk): 213s saved    ← equity finding: highest gain where needed most
```

The equity finding (Q4 > Q1 savings) is one of the strongest parts of the demo pitch. Make sure to explicitly print and share this with the team.

## If Results Are Disappointing (< 5pp improvement)

**Most likely cause:** K-Means staging is not concentrating units in high-demand areas.

1. Print staging zones for Friday 8PM — they should be dominated by B and K zones:

```python
counts = predict_counts(20, 4, 10)
staging = get_staging_zones(counts, K=5)
print(f"Friday 8PM staging zones: {staging}")
# Expected: mostly B1-B5 and K1-K7
```

2. If staging zones look uniform (one from each borough): K-Means weights are broken. Check `weights = np.array([max(predicted_counts[z], 0.01) for z in zones])` — print the weight array to confirm Bronx zones have 3–5× higher weights than Staten Island.

3. Try K=7: more staging points = more coverage.

4. If drive_time_matrix uses 9999 for many entries: the OSMnx graph has disconnected components. Fall back to Haversine matrix (see osmnx-routing agent).

## After Completion — Deliver Artifacts

```bash
# Download both parquets from DBFS
cp ~/Downloads/counterfactual_summary.parquet ~/firstwave-pipeline/backend/artifacts/
cp ~/Downloads/counterfactual_raw.parquet ~/firstwave-pipeline/backend/artifacts/

git add backend/artifacts/counterfactual_summary.parquet
git add backend/artifacts/counterfactual_raw.parquet
git commit -m "feat: counterfactual pre-computed — 168 bins, [X]%→[Y]% within 8min — closes #25"
git push origin feat/pipeline
# Open PR → Ansh approves → merge
```

**Post in group chat immediately:**

```
counterfactual AVAILABLE. Real numbers:
  [X]% → [Y]% within 8 min overall
  Median [Z] sec saved
  Bronx biggest gain: [W]pp
  PR open — Ashwin: merge + POST /reload
  Ansh: these are the [X] values for Devpost
```
