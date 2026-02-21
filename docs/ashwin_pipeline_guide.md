# Ashwin — Pipeline Run + Backend Update Guide

## What Changed

The pipeline now trains a **21-feature** XGBoost model (was 15). Six new features were added:

| Feature | Type | Source | Default for inference |
|---------|------|--------|----------------------|
| `is_holiday` | binary | Federal + NYC holidays (hardcoded) | `0` |
| `is_major_event` | binary | NYC Permitted Events CSV (downloaded) | `0` |
| `is_school_day` | binary | NYC DOE calendar (hardcoded) | `1` |
| `is_heat_emergency` | binary | Derived from `temperature_2m >= 35.0` | `int(temp >= 35.0)` |
| `is_extreme_heat` | binary | Derived from `temperature_2m >= 35.0` | `int(temp >= 35.0)` |
| `subway_disruption_idx` | float 0-1 | MTA Major Incidents CSV (downloaded) | `0.5` |

---

## Part 1: Run the Pipeline

### Prerequisites

- Raw EMS CSV (~2GB) already downloaded
- Internet access (Script 02 downloads weather, NYC events, MTA data)
- Python 3.11 with: `duckdb`, `pandas`, `requests`, `xgboost`, `scikit-learn`, `joblib`, `numpy`

### Pull latest code

```bash
git fetch origin feat/frontend
git checkout feat/frontend
# or merge feat/frontend into your branch
```

### Run in order

```bash
python pipeline/01_ingest_clean.py --csv ~/Downloads/ems_raw.csv
python pipeline/02_weather_merge.py
python pipeline/03_spatial_join.py
python pipeline/04_aggregate.py
python pipeline/05_train_demand_model.py
python pipeline/08_counterfactual_precompute.py
```

Script 06 and 07 are unchanged — run them if `drive_time_matrix.pkl` isn't already built.

### What to check after each script

**Script 02** — validation output at the end:
- Holiday rows: 2-4%
- School day rows: 45-60%
- Major event rows: 5-15% (0% is OK if NYC events download fails — non-fatal)
- Heat emergency rows: 3-10%
- MTA mean: 0.3-0.7

**Script 04** — check enrichment columns present:
- All 7 enrichment columns should show "OK" at validation
- `zone_baselines.parquet` should have <= 5,208 rows
- `zone_stats.parquet` should have exactly 31 rows

**Script 05** — model training results:
- RMSE < 4.0 (target met)
- `zone_baseline_avg` in top 3 features
- New features should not all have near-zero importance
- Sanity checks A-E should all pass

**Script 08** — counterfactual:
- Should NOT crash (this proves the 21-feature model works end-to-end)
- Static within 8 min: ~61%
- Staged within 8 min: ~83%
- Improvement should be > 5 percentage points

### Output artifacts (all written to `backend/artifacts/`)

| File | From Script |
|------|-------------|
| `demand_model.pkl` | 05 |
| `zone_baselines.parquet` | 04 |
| `zone_stats.parquet` | 04 |
| `counterfactual_summary.parquet` | 08 |
| `counterfactual_raw.parquet` | 08 |

---

## Part 2: Update Backend Inference

After pipeline runs, `demand_model.pkl` expects 21 features. Your backend currently builds 15.

### File to update: `backend/models/demand_forecaster.py`

**1. Update FEATURE_COLS** — add these 6 at the end (order matters):

```python
FEATURE_COLS = [
    # ── Original 15 (unchanged) ──
    "hour_sin","hour_cos","dow_sin","dow_cos","month_sin","month_cos",
    "is_weekend","temperature_2m","precipitation","windspeed_10m",
    "is_severe_weather","svi_score","zone_baseline_avg",
    "high_acuity_ratio","held_ratio",
    # ── New 6 ──
    "is_holiday",
    "is_major_event",
    "is_school_day",
    "is_heat_emergency",
    "is_extreme_heat",
    "subway_disruption_idx",
]
```

**2. Update `build_prediction_df()` (or wherever you build the feature row dict)** — add these fields to each zone's row:

```python
"is_holiday":            0,
"is_major_event":        0,
"is_school_day":         1,   # conservative default: school in session
"is_heat_emergency":     int(temperature_2m >= 35.0),
"is_extreme_heat":       int(temperature_2m >= 35.0),
"subway_disruption_idx": 0.5,  # median (unknown)
```

The heat flags are derived from the `temperature_2m` query parameter that already exists in the API.

**3. Test it:**

```bash
uvicorn main:app --reload --port 8000
curl "http://localhost:8000/api/heatmap?hour=20&dow=4&month=10&temperature=15&precipitation=0&windspeed=10&ambulances=5"
```

Should return 200 with 31 zone predictions. If you get a feature mismatch error, the FEATURE_COLS order doesn't match the model.

---

## Quick Reference: New Feature Columns Order

Position 15-20 in the feature array (0-indexed):

```
[15] is_holiday
[16] is_major_event
[17] is_school_day
[18] is_heat_emergency
[19] is_extreme_heat
[20] subway_disruption_idx
```

This order is frozen after training. Do not rearrange.
