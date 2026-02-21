# Praneel's Personal Guide — PulsePoint

## Role: Pipeline Lead + Databricks Owner

## Tool: Claude Pro + GitHub Integration (`cd ~/pulsepoint-pipeline && claude`)

---

## Your Job in One Sentence

You run the entire data science pipeline on Databricks — cleaning 28.7M rows, training the XGBoost model, computing the counterfactual, and delivering the model artifacts that Ashwin's API needs to serve real predictions.

## What You Own

- `databricks_notebooks/` — entirely yours, nobody else touches it
- All 8 pipeline notebooks (run on Databricks)
- Every artifact in `backend/artifacts/` (you produce them all)

## What You Do NOT Touch

- `frontend/` — that's Vaibhav's
- `backend/` — that's Ashwin's (you only write to `backend/artifacts/`, never to `backend/` source files)
- `data/ems_stations.json` — that's Ansh's

## Your Two Most Important Moments

1. **Hour ~10:** `demand_model.pkl` delivered to `backend/artifacts/`. This unblocks Ashwin's real inference.
2. **Hour ~20:** `counterfactual_summary.parquet` delivered to `backend/artifacts/`. This unblocks the impact panel with real numbers.

Both of these are hard dependencies for the whole team. Protect these deadlines above everything else.

---

## Pre-Hackathon Checklist (CRITICAL — Must Be Done Before You Arrive)

- [ ] **Run Notebook 06 (OSMnx drive-time matrix) — this is 30–60 minutes of compute. Cannot be done during the hackathon.**
  - Sign up at `community.cloud.databricks.com` (free)
  - Create cluster: ML Runtime 14.x, terminate after 120 min
  - Upload NYC EMS CSV to DBFS (see Step 1 below for the download URL)
  - Run Notebook 06 — verify `drive_time_matrix.pkl` is written to `dbfs:/pulsepoint/artifacts/`
- [ ] Download NYC EMS CSV (~2GB):
      `https://data.cityofnewyork.us/api/views/76xm-jjuj/rows.csv?accessType=DOWNLOAD`
      Get a free API token first: sign up at `data.cityofnewyork.us`
- [ ] Upload CSV to DBFS: in Databricks UI → Data → Add Data → Upload File → `dbfs:/pulsepoint/data/ems_raw.csv`
- [ ] Verify Databricks Community Edition cluster is accessible and running
- [ ] Connect Claude Pro to GitHub: in Claude Code, Settings → Integrations → GitHub → Authorize
- [ ] Clone the repo:

```bash
git clone https://github.com/yourteam/pulsepoint.git
git checkout feat/pipeline
```

---

## Databricks Setup

### Cluster Configuration

```
Name: pulsepoint-cluster
Runtime: Databricks ML Runtime 14.x (includes XGBoost, MLflow, scikit-learn pre-installed)
Terminate after: 120 minutes idle (set this so you don't accidentally leave it running)
```

### DBFS File Structure

```
dbfs:/pulsepoint/
├── data/
│   ├── ems_raw.csv              ← upload before hackathon
│   ├── ems_stations.json        ← commit from Ansh's data/ folder
│   └── svi_2022_nyc.csv         ← CDC SVI data (download separately)
├── delta/
│   ├── incidents_cleaned/       ← created by Notebook 01
│   └── incidents_aggregated/    ← created by Notebook 04
└── artifacts/
    ├── nyc_graph.pkl            ← created by Notebook 06 (PRE-HACKATHON)
    ├── drive_time_matrix.pkl    ← created by Notebook 06 (PRE-HACKATHON)
    ├── zone_nodes.pkl           ← created by Notebook 06 (PRE-HACKATHON)
    ├── zone_baselines.parquet   ← created by Notebook 04
    ├── zone_stats.parquet       ← created by Notebook 04
    ├── demand_model.pkl         ← created by Notebook 05
    └── counterfactual_summary.parquet ← created by Notebook 08
```

### Install Dependencies at Notebook Start

Add this to the first cell of any notebook that needs non-built-in libraries:

```python
%pip install osmnx geopandas
dbutils.library.restartPython()
```

---

## Your Claude Code Setup

```bash
cd ~/pulsepoint-pipeline
claude
```

First session:

```
/init
Read CLAUDE.md for full project context. I'm building the Databricks pipeline
for PulsePoint. My module is databricks_notebooks/. Create the notebook files
as Python files (they'll be imported into Databricks as notebooks):
01_ingest_clean.py
02_weather_merge.py
03_spatial_join.py
04_aggregate.py
05_train_demand_model.py
06_osmnx_matrix.py   (already run pre-hackathon — for reference only)
07_staging_optimizer.py
08_counterfactual_precompute.py
```

---

## Phase 1: Data Ingestion (Hours 0–8)

### Notebook 01 — Ingest & Clean (Hours 0–3)

This is the most important notebook. Everything downstream depends on clean data.

Ask Claude Code:

```
Write databricks_notebooks/01_ingest_clean.py as a Databricks notebook.

Input: dbfs:/pulsepoint/data/ems_raw.csv (~28.7M rows)
Output: Delta table pulsepoint.incidents_cleaned

Steps:
1. Read CSV with Spark inferSchema=True
2. Parse INCIDENT_DATETIME: to_timestamp with format "MM/dd/yyyy hh:mm:ss a"
3. Extract: year, month, dayofweek (0=Mon, adjust from Spark's 1=Sun),
   hour, date_hour (truncated to hour), is_weekend (dow in 5,6)

4. Quality filters (all must pass):
   - VALID_INCIDENT_RSPNS_TIME_INDC == 'Y'
   - VALID_DISPATCH_RSPNS_TIME_INDC == 'Y'
   - REOPEN_INDICATOR == 'N'
   - TRANSFER_INDICATOR == 'N'
   - STANDBY_INDICATOR == 'N'
   - INCIDENT_RESPONSE_SECONDS_QY between 1 and 7200
   - BOROUGH != 'UNKNOWN'
   - INCIDENT_DISPATCH_AREA in VALID_ZONES (list below)
   - Zone-borough prefix match (B→BRONX, K→BROOKLYN, M→MANHATTAN,
     Q→QUEENS, S→RICHMOND / STATEN ISLAND)

VALID_ZONES = ['B1','B2','B3','B4','B5','K1','K2','K3','K4','K5','K6','K7',
               'M1','M2','M3','M4','M5','M6','M7','M8','M9',
               'Q1','Q2','Q3','Q4','Q5','Q6','Q7','S1','S2','S3']

5. Feature engineering:
   - is_high_acuity: FINAL_SEVERITY_LEVEL_CODE in (1,2) → 1 else 0
   - is_held: HELD_INDICATOR == 'Y' → 1 else 0
   - is_covid_year: year == 2020 → 1 else 0
   - split: year==2023 → 'test', year==2020 → 'exclude',
     year in (2019,2021,2022) → 'train', else → 'exclude'

6. Write to Delta:
   incidents_cleaned.write.format("delta").mode("overwrite")
     .save("dbfs:/pulsepoint/delta/incidents_cleaned")

   CREATE TABLE IF NOT EXISTS pulsepoint.incidents_cleaned
   USING DELTA LOCATION 'dbfs:/pulsepoint/delta/incidents_cleaned'

7. Print validation counts:
   - Total rows after filter
   - Training rows (split='train')
   - Test rows (split='test')
   - Excluded rows
   Expected: ~5.6M training rows, ~1.5M test rows
```

**Expected validation output:**

```
Total rows after filter: ~7.2M
Training rows (2019,2021,2022): ~5.6M
Test rows (2023): ~1.5M
2020 excluded: ~1.1M
```

If training rows is below 4M, something is wrong with the filters. The most common issue is the datetime parse format — if it fails, use `to_timestamp("INCIDENT_DATETIME")` without a format string and let Spark infer it.

### Notebook 02 — Weather Merge (Hours 3–5)

Ask Claude Code:

```
Write databricks_notebooks/02_weather_merge.py.

1. Fetch Open-Meteo historical weather for NYC 2019-2023:
   URL: https://archive-api.open-meteo.com/v1/archive
   Params: latitude=40.7128, longitude=-74.0060,
           start_date=2019-01-01, end_date=2023-12-31,
           hourly=temperature_2m,precipitation,windspeed_10m,weathercode,
           timezone=America/New_York
   This is a single API call — it returns all 5 years at once.

2. Convert to Spark DataFrame. date_hour column is the join key (hourly timestamps).

3. Add is_severe_weather flag:
   severe_codes = {51,53,55,61,63,65,71,73,75,77,80,81,82,85,86,95,96,99}
   is_severe_weather = 1 if weathercode in severe_codes else 0

4. Left join incidents_cleaned to weather on date_hour.
   Fill nulls: temperature_2m=15.0, precipitation=0.0, windspeed_10m=10.0,
   is_severe_weather=0

5. Overwrite Delta table pulsepoint.incidents_cleaned with weather columns added.

6. Validation: print null count for temperature_2m. Should be < 0.1% of rows.
```

### Notebook 03 — SVI Join (Hours 5–6)

The SVI data needs to be joined at the dispatch zone level. Since getting census-tract-to-dispatch-zone crosswalk data is complex, use a pre-built lookup table.

Ask Claude Code:

```
Write databricks_notebooks/03_spatial_join.py.

Use a static zone→SVI lookup (hardcoded in the notebook — no external data needed):

ZONE_SVI = {
  'B1':0.94, 'B2':0.89, 'B3':0.87, 'B4':0.72, 'B5':0.68,
  'K1':0.52, 'K2':0.58, 'K3':0.82, 'K4':0.84, 'K5':0.79, 'K6':0.60, 'K7':0.45,
  'M1':0.31, 'M2':0.18, 'M3':0.15, 'M4':0.20, 'M5':0.12,
  'M6':0.14, 'M7':0.73, 'M8':0.65, 'M9':0.61,
  'Q1':0.71, 'Q2':0.44, 'Q3':0.38, 'Q4':0.55, 'Q5':0.67, 'Q6':0.48, 'Q7':0.41,
  'S1':0.38, 'S2':0.32, 'S3':0.28
}

1. Create a Spark DataFrame from ZONE_SVI dict: columns zone_code, svi_score
2. Join to incidents_cleaned on INCIDENT_DISPATCH_AREA == zone_code (left join)
3. Fill nulls in svi_score with 0.5
4. Overwrite Delta table incidents_cleaned

Print: distinct zone counts, null SVI count (should be 0).
```

---

## Phase 2: Modeling (Hours 8–16)

### Notebook 04 — Aggregation (Hours 8–11)

Ask Claude Code:

```
Write databricks_notebooks/04_aggregate.py.

Input: Delta table pulsepoint.incidents_cleaned (split in train, test)
Output:
  - Delta table pulsepoint.incidents_aggregated
  - Parquet file dbfs:/pulsepoint/artifacts/zone_baselines.parquet
  - Parquet file dbfs:/pulsepoint/artifacts/zone_stats.parquet

Step 1: Aggregate raw incidents to hourly dispatch-zone level.
GROUP BY: INCIDENT_DISPATCH_AREA, BOROUGH, year, month, dayofweek, hour,
          is_weekend, temperature_2m, precipitation, windspeed_10m,
          is_severe_weather, svi_score, split

AGGREGATIONS:
  incident_count = count(CAD_INCIDENT_ID)
  avg_response_seconds = mean(INCIDENT_RESPONSE_SECONDS_QY)
  avg_travel_seconds = mean(INCIDENT_TRAVEL_TM_SECONDS_QY)
  avg_dispatch_seconds = mean(DISPATCH_RESPONSE_SECONDS_QY)
  high_acuity_count = sum(is_high_acuity)
  held_count = sum(is_held)
  median_response_seconds = percentile_approx(INCIDENT_RESPONSE_SECONDS_QY, 0.5)

Step 2: Add cyclical features using PySpark functions:
  hour_sin = sin(2 * pi * hour / 24)   [use F.sin, F.lit(math.pi)]
  hour_cos = cos(2 * pi * hour / 24)
  dow_sin  = sin(2 * pi * dayofweek / 7)
  dow_cos  = cos(2 * pi * dayofweek / 7)
  month_sin = sin(2 * pi * month / 12)
  month_cos = cos(2 * pi * month / 12)

Step 3: Write incidents_aggregated to Delta.

Step 4: Compute zone_baselines — for TRAINING data only:
  For each (INCIDENT_DISPATCH_AREA, hour, dayofweek):
    Get all individual incident rows (not aggregated), count per (zone, date, hour)
    Then average those daily counts → zone_baseline_avg

  Practical approach:
    daily_counts = incidents_cleaned.filter(split='train')
      .withColumn("date", to_date("incident_dt"))
      .groupBy("INCIDENT_DISPATCH_AREA", "hour", "dayofweek", "date")
      .agg(count("*").alias("daily_incident_count"))

    zone_baselines = daily_counts
      .groupBy("INCIDENT_DISPATCH_AREA", "hour", "dayofweek")
      .agg(mean("daily_incident_count").alias("zone_baseline_avg"))

  Save to: /dbfs/pulsepoint/artifacts/zone_baselines.parquet

Step 5: Compute zone_stats — per-zone historical averages from training data:
  zone_stats = incidents_cleaned.filter(split='train')
    .groupBy("INCIDENT_DISPATCH_AREA", "BOROUGH", "svi_score")
    .agg(
      mean(INCIDENT_RESPONSE_SECONDS_QY).alias("avg_response_seconds"),
      mean(INCIDENT_TRAVEL_TM_SECONDS_QY).alias("avg_travel_seconds"),
      mean(DISPATCH_RESPONSE_SECONDS_QY).alias("avg_dispatch_seconds"),
      mean(is_high_acuity).alias("high_acuity_ratio"),
      mean(is_held).alias("held_ratio"),
      count("*").alias("total_incidents")
    )
  Save to: /dbfs/pulsepoint/artifacts/zone_stats.parquet

Print: aggregated row count, zone_baselines row count (should be ~31×24×7 = 5,208 max),
zone_stats row count (should be 31).
```

### Notebook 05 — XGBoost Training (Hours 11–16)

This is the heart of the ML pipeline. Use MLflow for tracking.

Ask Claude Code:

```
Write databricks_notebooks/05_train_demand_model.py.

1. Load incidents_aggregated Delta table → convert to pandas (it's aggregated, much smaller)
2. Load zone_baselines.parquet and zone_stats.parquet from DBFS
3. Merge zone_baseline_avg and high_acuity_ratio, held_ratio into aggregated DataFrame
4. Fill missing zone_baseline_avg with 1.0

FEATURES (from CLAUDE.md):
["hour_sin","hour_cos","dow_sin","dow_cos","month_sin","month_cos",
 "is_weekend","temperature_2m","precipitation","windspeed_10m",
 "is_severe_weather","svi_score","zone_baseline_avg",
 "high_acuity_ratio","held_ratio"]

TARGET: incident_count

SPLIT: split column (train vs test)

5. MLflow experiment tracking:
   mlflow.set_experiment("/pulsepoint/demand_forecasting")

   with mlflow.start_run(run_name="xgboost_v1"):
     Log params: n_estimators=300, max_depth=6, learning_rate=0.05,
                 subsample=0.8, colsample_bytree=0.8, training_years="2019,2021,2022"

     Train XGBRegressor with early stopping on test set (20 rounds)

     Compute and log metrics:
       test_rmse (overall)
       Per-borough RMSE (filter test set by borough, compute separately)

     Log feature importances as a bar chart artifact
     Log model with mlflow.xgboost.log_model

6. Save model:
   joblib.dump(model, "/dbfs/pulsepoint/artifacts/demand_model.pkl")

7. Print final metrics prominently:
   print(f"\n{'='*50}")
   print(f"TEST RMSE:  {rmse:.3f} incidents/zone/hour")
   print(f"TEST MAE:   {mae:.3f}")
   print("Per-borough RMSE:")
   for borough, b_rmse in borough_rmses.items():
       print(f"  {borough}: {b_rmse:.3f}")
   print(f"{'='*50}")
   print("demand_model.pkl written to DBFS")
```

**Target metrics:**

- Overall RMSE: < 4.0 incidents/zone/hour
- If RMSE > 6: something is wrong — check that zone_baseline_avg is being included (it's the most important feature). Also check cyclical features are being computed correctly (should range -1 to 1).

**The moment this notebook finishes:**

```bash
# Download from DBFS to local (Databricks provides this via the UI or CLI)
# In Databricks: File → Export → as file → demand_model.pkl
# Then commit to backend/artifacts/:

cp ~/Downloads/demand_model.pkl ~/pulsepoint-pipeline/backend/artifacts/
git add backend/artifacts/demand_model.pkl
git commit -m "feat: demand_model.pkl trained (RMSE: [X]) — closes #23, unblocks #14"
git push origin feat/pipeline
# Open PR. Ashwin will merge it.
```

**Tell the team:** `demand_model.pkl AVAILABLE: backend/artifacts/. RMSE=[X]. Ashwin: merge the PR and POST /reload.`

Also download and commit `zone_baselines.parquet` and `zone_stats.parquet` at the same time:

```bash
# Download both parquets from DBFS → backend/artifacts/
git add backend/artifacts/zone_baselines.parquet backend/artifacts/zone_stats.parquet
git commit -m "feat: zone_baselines + zone_stats parquets — unblocks /api/historical and /api/breakdown"
git push origin feat/pipeline
```

---

## Phase 3: Optimization + Counterfactual (Hours 16–22)

### Notebook 07 — Staging Optimizer Validation (Hour 16–18)

You don't need to rebuild the K-Means optimizer — Ashwin built it in the backend. Notebook 07 is for validating that the staging logic produces sensible results.

Ask Claude Code:

```
Write databricks_notebooks/07_staging_optimizer.py as a validation notebook.

1. Load demand_model.pkl from DBFS
2. Load zone_baselines.parquet and zone_stats.parquet
3. For 3 test scenarios (Monday 4AM, Wednesday Noon, Friday 8PM):
   a. Build feature DataFrame for all 31 zones
   b. Run model.predict()
   c. Run weighted K-Means with K=5
   d. Print: predicted top-3 hottest zones, 5 staging locations (zone name + lat/lon)

4. Validate: staging locations should always be in high-demand zones.
   Friday 8PM: Bronx and Brooklyn zones should dominate predictions.
   Monday 4AM: predictions should be uniformly low across all zones.

This notebook is for your confidence — the model makes geographic sense.
```

### Notebook 08 — Counterfactual Pre-Computation (Hours 18–22)

This is the most complex notebook. It produces the numbers that power the demo's impact panel.

Ask Claude Code:

```
Write databricks_notebooks/08_counterfactual_precompute.py.

Goal: For all 168 (hour × dayofweek) combinations, compute:
- pct_within_8min_static: % of Priority 1+2 calls in 2023 that were within 8 min
  if served from nearest fixed FDNY station
- pct_within_8min_staged: % that would be within 8 min if served from
  PulsePoint-recommended staging locations
- median_seconds_saved: median(baseline_drive_time - staged_drive_time)
- by_borough and by_svi_quartile breakdowns

Inputs:
  - incidents_cleaned Delta table (split='test', is_high_acuity=1)
  - demand_model.pkl
  - drive_time_matrix.pkl: dict {(origin_key, zone): seconds}
    where origin_key is either a zone_code or station_id
  - zone_baselines.parquet, zone_stats.parquet

Load EMS stations from dbfs:/pulsepoint/data/ems_stations.json.
(Ansh will commit this to data/ — copy it to DBFS during setup.)

Algorithm per (hour, dow):
  1. Sample up to 100 Priority 1+2 incidents from 2023 with this (hour, dow)
  2. For each incident (its dispatch zone = zone of origin):

     a. BASELINE (static stations):
        baseline_drive = min over all stations of drive_time_matrix[(station_id, incident_zone)]
        baseline_within_8min = baseline_drive <= 480

     b. STAGED (PulsePoint):
        - Run Model A to get predicted_counts for this (hour, dow)
        - Run weighted K-Means K=5 to get staging zones
        - staged_drive = min over all staging zone codes of drive_time_matrix[(staging_zone, incident_zone)]
        - staged_within_8min = staged_drive <= 480

     c. seconds_saved = baseline_drive - staged_drive

  3. Aggregate results:
     summary row: hour, dayofweek, median_seconds_saved,
                  pct_within_8min_static, pct_within_8min_staged, n_incidents
     raw row per incident: hour, dayofweek, incident_zone, borough, svi_score,
                           baseline_drive, staged_drive, seconds_saved,
                           baseline_within_8min, staged_within_8min

Output:
  /dbfs/pulsepoint/artifacts/counterfactual_summary.parquet (168 rows)
  /dbfs/pulsepoint/artifacts/counterfactual_raw.parquet (all incidents)

Print final stats:
  Overall: pct_within_8min_static, pct_within_8min_staged, median_seconds_saved
  Per borough breakdown
  Per SVI quartile breakdown

Important: if drive_time_matrix is missing an entry, use 9999 (unit not reachable).
Do not skip incidents — a 9999 still counts as not within 8 minutes.
```

**When this finishes, this is your most important deliverable:**

```bash
# Download counterfactual_summary.parquet from DBFS
cp ~/Downloads/counterfactual_summary.parquet ~/pulsepoint-pipeline/backend/artifacts/
# Also download counterfactual_raw.parquet
cp ~/Downloads/counterfactual_raw.parquet ~/pulsepoint-pipeline/backend/artifacts/

git add backend/artifacts/counterfactual_summary.parquet backend/artifacts/counterfactual_raw.parquet
git commit -m "feat: counterfactual pre-computed for all 168 hour×dow bins — closes #25, unblocks #16"
git push origin feat/pipeline
# Open PR
```

**Tell the team:** `counterfactual_summary.parquet AVAILABLE. Real numbers: [X]% → [Y]% within 8 min, [Z] sec median saved. Ashwin: merge the PR. Ansh: fill these numbers into Devpost.`

Give Ansh the exact numbers — he needs them for the Devpost write-up and HACKATHON_STRATEGY.md demo script.

---

## Using Claude Pro + GitHub Integration

### Setup

```bash
# In Claude Code session:
/github connect
```

### Automated artifact delivery PRs

After each artifact is ready, instead of doing git commands manually:

```
demand_model.pkl is written to /dbfs/pulsepoint/artifacts/demand_model.pkl.
I've downloaded it to backend/artifacts/demand_model.pkl.
Also download zone_baselines.parquet and zone_stats.parquet to backend/artifacts/.
Commit all three files with message:
'feat: ML artifacts ready — demand_model.pkl (RMSE 3.8), zone_baselines, zone_stats — closes #23'
Push to feat/pipeline. Open a PR to main titled 'Pipeline: ML artifacts ready (#23)'
with the pipeline label. Tag issue #14 as unblocked.
```

### Commit Schedule

Commit after each notebook completes, even if you're not done with the phase:

```
"Notebook 01 (ingest_clean) is complete and validated: 5.6M training rows,
1.5M test rows. Commit databricks_notebooks/01_ingest_clean.py with
message 'feat: Notebook 01 ingest + clean — closes #19'.
Push to feat/pipeline."
```

---

## Databricks Raffle (Hour 22–24)

This is a free prize entry — 1-minute Loom recording, then submit.

**What to record:**

1. Open your Notebook 05 (XGBoost training) in Databricks
2. Show the notebook structure briefly
3. Click Run All
4. While it runs, narrate: "We're training our XGBoost demand forecasting model on 5.6 million NYC EMS incidents from 2019–2022. The model learns to predict hourly incident counts per dispatch zone using time-of-day, weather, and social vulnerability features."
5. Show the MLflow experiment page with your logged run (metrics visible)
6. Done — 1 minute exactly

Submit the Loom URL to the Databricks raffle form. Ansh can do this submission for you.

---

## Group Chat Communication Rules

| When                   | Message                                                                        |
| ---------------------- | ------------------------------------------------------------------------------ |
| Notebook 01 complete   | `pipeline: incidents_cleaned ready. 5.6M train rows, 1.5M test rows.`          |
| Weather merge done     | `pipeline: weather merge complete, <0.1% null weather rows.`                   |
| Notebook 04 done       | `pipeline: aggregation + zone_baselines + zone_stats parquets written.`        |
| Model training starts  | `pipeline: XGBoost training started. ~20 min ETA.`                             |
| demand_model.pkl ready | `demand_model.pkl AVAILABLE. RMSE=[X]. PR open — Ashwin merge and /reload.`    |
| Counterfactual done    | `counterfactual AVAILABLE. [X]%→[Y]% within 8min, [Z]sec saved. PR open.`      |
| Need from Ansh         | `BLOCKED: Ansh — need ems_stations.json committed to data/ and copied to DBFS` |

---

## If Things Go Wrong

**Notebook 01 produces < 3M training rows:**

1. Check the datetime parse — try `to_timestamp("INCIDENT_DATETIME")` without format string
2. Check VALID_INCIDENT_RSPNS_TIME_INDC filter — make sure it's comparing to string `'Y'` not `1`
3. Check the zone-borough prefix match — print a sample of filtered-out rows to see what's being dropped

**XGBoost RMSE > 8:**

1. Check that `zone_baseline_avg` is included in features — it's the most important feature and a common merge failure
2. Check cyclical features are computing correctly: `hour_sin` for hour=6 should be ~0.707, not 6
3. Fallback: use just `zone_baseline_avg` as the prediction (rolling average). This is still a valid model and will show demand clustering correctly.

**drive_time_matrix.pkl not in DBFS:**
This should have been pre-computed. If it's missing:

1. Run Notebook 06 immediately — it takes 30–60 minutes
2. Tell the team: "Running OSMnx matrix now, ETA 45 min"
3. Fallback: use Haversine distance × 1.35 for drive-time approximation while waiting

**Counterfactual numbers are disappointing (< 5% improvement):**
This usually means K-Means is not converging well. Try:

1. Increase K to 7 or 10 (more staging points)
2. Increase `n_init=50` in KMeans
3. If still bad: check that staging zones are chosen from high-demand areas, not averaged to geographic center

**Databricks cluster terminates mid-run:**
All Delta tables are durable on DBFS — they survive cluster termination. Restart the cluster and re-run only the notebooks that didn't finish.

---

## Your Hour-by-Hour Summary

| Hour          | Task                                                           | Closes   |
| ------------- | -------------------------------------------------------------- | -------- |
| Pre-hackathon | OSMnx matrix (Notebook 06) + CSV upload                        | #24      |
| 0–3           | Notebook 01: ingest + clean, validate ~5.6M rows               | #19      |
| 3–5           | Notebook 02: weather merge                                     | #20      |
| 5–6           | Notebook 03: SVI join                                          | #21      |
| 6–8           | Notebook 04: aggregation, zone_baselines, zone_stats           | #22      |
| 8–11          | Notebook 05: XGBoost training starts                           | —        |
| ~10–11        | demand_model.pkl + parquets committed + PR → unblocks Ashwin   | #23      |
| 11–16         | Notebook 05 complete + validated, commit final artifacts       | —        |
| 16–18         | Notebook 07: staging optimizer validation                      | —        |
| 18–22         | Notebook 08: counterfactual precompute                         | —        |
| ~20           | counterfactual parquets committed + PR → unblocks impact panel | #25, #26 |
| 22–24         | Databricks raffle Loom recorded + submitted                    | #30      |
| 24–30         | Support Ashwin on any pipeline questions, pitch prep           | —        |
