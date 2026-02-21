# Pipeline Guide — Local DuckDB + Pandas
## FirstWave | GT Hacklytics 2026

**Pipeline runs on: Ashwin's machine** (Praneel's Databricks connection failed)
**All artifact outputs, schemas, and field names are IDENTICAL to the original plan.**

---

## What Changed

| Was (Databricks)               | Now (Local)                                  |
|-------------------------------|----------------------------------------------|
| PySpark DataFrames            | DuckDB SQL + pandas                          |
| Delta Lake tables             | Intermediate parquets in `pipeline/data/`    |
| `dbfs:/firstwave/artifacts/`  | `backend/artifacts/` directly                |
| `dbutils.fs.cp()`             | plain file operations                        |
| MLflow tracking               | Print-only results                           |
| `python databricks_notebooks/`| `python pipeline/` (same scripts, rewritten) |

**What does NOT change:**
- All 5 artifact files and their schemas
- FEATURE_COLS order, XGBoost hyperparameters
- API contract (CLAUDE.md frozen fields)
- `backend/`, `frontend/` — untouched

---

## Setup (Ashwin runs this)

```bash
# From repo root (feat/pipeline branch)
git checkout feat/pipeline
git pull origin feat/pipeline

pip install -r pipeline/requirements.txt
```

**Download the EMS CSV (~2GB) — do this first:**
```
https://data.cityofnewyork.us/api/views/76xm-jjuj/rows.csv?accessType=DOWNLOAD
```
Save it anywhere (e.g. `~/Downloads/ems_raw.csv`).

---

## Run Order

**Start Script 06 FIRST** in a background terminal (30-60 min for OSMnx):
```bash
python pipeline/06_osmnx_matrix.py --stations data/ems_stations.json &
```

Then run the main pipeline sequentially:
```bash
# ~5-10 min (28.7M rows via DuckDB)
python pipeline/01_ingest_clean.py --csv ~/Downloads/ems_raw.csv

# ~2 min (Open-Meteo API fetch + join)
python pipeline/02_weather_merge.py

# ~1 min (hardcoded SVI lookup join)
python pipeline/03_spatial_join.py

# ~2 min (aggregate + write zone_baselines + zone_stats to backend/artifacts/)
python pipeline/04_aggregate.py

# ~5-10 min (XGBoost training, writes demand_model.pkl to backend/artifacts/)
python pipeline/05_train_demand_model.py

# After 05 + 06 both complete:
python pipeline/07_staging_optimizer.py   # validation only (pass/fail checks)
python pipeline/08_counterfactual_precompute.py  # ~10 min (writes counterfactual parquets)
```

---

## Intermediate Files (pipeline/data/ — NOT committed)

```
pipeline/data/
├── incidents_cleaned.parquet      (~7.1M rows, ~800MB — do NOT commit)
└── incidents_aggregated.parquet   (~500MB — do NOT commit)
```

These are excluded from git via `.gitignore`. Only `backend/artifacts/` is committed.

---

## Artifact Delivery

Artifacts are written **directly** to `backend/artifacts/` — no download step needed.

### Hour ~10 delivery (after Scripts 04 + 05):
```bash
git add backend/artifacts/demand_model.pkl \
        backend/artifacts/zone_baselines.parquet \
        backend/artifacts/zone_stats.parquet
git commit -m "feat: ML artifacts — demand_model.pkl (RMSE=[X]), zone_baselines, zone_stats"
git push origin feat/pipeline
# Open PR → Ansh approves → Ashwin merges → POST /reload
```
Post in group chat: `demand_model.pkl AVAILABLE. RMSE=[X]. PR open — Ashwin merge and POST /reload.`

### Hour ~20 delivery (after Script 08):
```bash
git add backend/artifacts/counterfactual_summary.parquet \
        backend/artifacts/counterfactual_raw.parquet
git commit -m "feat: counterfactual pre-computed — 168 bins, [X]%-->[Y]% within 8min"
git push origin feat/pipeline
# Open PR → Ansh approves → Ashwin merges → POST /reload
```
Post in group chat: `counterfactual AVAILABLE. [X]%-->[Y]% within 8min, [Z]s saved. PR open.`

---

## Verification Checklist

| Script | What to check |
|--------|---------------|
| 01 | Prints ~5.6M train rows, ~1.5M test rows, 31 zones |
| 02 | Null weather < 0.1% |
| 03 | Null SVI = 0, distinct zones = 31 |
| 04 | zone_baselines <= 5,208 rows; zone_stats = 31 rows |
| 05 | RMSE < 4.0; Friday 8PM Bronx zones dominate |
| 06 | B1->B2 drive time ~300-500 sec (or Haversine fallback used) |
| 07 | Friday 8PM: Bronx/Brooklyn dominate; Monday 4AM: all zones low |
| 08 | ~61%->~83% within 8min; 5 boroughs + 4 SVI quartiles in output |

---

## Troubleshooting

**Script 01 produces < 3M training rows:**
- Check that `INCIDENT_DATETIME` column name is correct (case-sensitive in CSV)
- Inspect a sample: `head -2 ~/Downloads/ems_raw.csv` to verify datetime format
- If format differs from `%m/%d/%Y %I:%M:%S %p`, update the `strptime` call in Script 01

**XGBoost RMSE > 8:**
- `zone_baseline_avg` merge probably failed — check Script 04 output shows `zone_baselines.parquet: N rows (expect <= 5208)`
- Verify column is named `INCIDENT_DISPATCH_AREA` (not `zone_code`) in both parquets

**Script 06 OSMnx download fails:**
- Script automatically falls back to Haversine approximation — let it run
- Haversine is ~15% less accurate but fully functional
- Tell team: "Using Haversine fallback — counterfactual numbers slightly conservative"

**Script 08 improvement < 5%:**
- Try increasing K from 5 to 7 in `get_staging_zones()` in Script 08
- Also increase `MAX_INCIDENTS_PER_BIN` to 300 for more statistical stability

---

## Group Chat Communication

| When                  | Message                                                                    |
|-----------------------|----------------------------------------------------------------------------|
| Script 01 done        | `pipeline: incidents_cleaned ready. 5.6M train rows, 1.5M test rows.`    |
| Script 04 done        | `pipeline: zone_baselines + zone_stats written to backend/artifacts/.`   |
| Script 05 done        | `demand_model.pkl AVAILABLE. RMSE=[X]. PR open — Ashwin merge + /reload.` |
| Script 08 done        | `counterfactual AVAILABLE. [X]%-->[Y]% within 8min, [Z]s saved. PR open.`|
| Need Ansh's JSON      | `BLOCKED: Ansh — need data/ems_stations.json committed`                   |
