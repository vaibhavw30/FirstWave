# FirstWave — Predictive EMS Staging Dashboard

## Product Requirements Document (PRD) v3.0

**Hackathon:** GT Hacklytics 2026 — Healthcare Track + SafetyKit Track
**Team:** Praneel, Ansh, Vaibhav, Ashwin
**Timeline:** 36 hours
**Submission Deadline:** Sunday February 22, 9:00 AM EST
**Last Updated:** February 2026
**Supersedes:** PRD v2.0

---

## Changelog from v2.0

| Change | Reason |
|---|---|
| Renamed project from PulsePoint to **FirstWave** | Branding clarity; "like a surfer paddling out ahead of the wave" |
| Compute infrastructure moved from Databricks to **local DuckDB pipeline** | Databricks Community Edition hit memory/cluster limits mid-hackathon; DuckDB runs locally with identical output |
| Feature count expanded from 15 to **20 features** | Added `is_holiday`, `is_major_event`, `is_school_day`, `is_heat_emergency`, `is_extreme_heat`, `subway_disruption_idx` |
| Borough-fair staging optimizer | Guarantees minimum 1 staging point per borough before demand-proportional allocation of extras |
| AI Dispatcher panel added (`POST /api/ai`) | GPT-4o-mini natural language interface for scenario exploration ("What about a Friday night Yankees game?") |
| EMS stations overlay added (`GET /api/stations`) | Displays ~31 FDNY station locations on map for spatial reference |
| Equity/SVI layer added | ZIP-level Social Vulnerability Index overlay with purple color ramp |
| Watch the Wave animation added | Auto-plays hour slider 0→23 at 1.5s intervals, showing demand patterns over a full day |
| Weather-adjusted response times in counterfactual | Travel factor: `1.0 + 0.012×precip + 0.002×max(0, wind-15)` applied to both static and staged times |
| Zone-level counterfactual data | `by_zone` field added to `/api/counterfactual` response with per-zone static/staged/saved times |
| Frontend upgraded to React 19.2 + Mapbox GL JS 3.18 | Latest stable versions for performance and features |

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [Solution Overview](#3-solution-overview)
4. [Goals & Success Metrics](#4-goals--success-metrics)
5. [Dataset Specifications & Validation](#5-dataset-specifications--validation)
6. [Data Pipeline](#6-data-pipeline)
7. [Machine Learning & Optimization](#7-machine-learning--optimization)
8. [System Architecture](#8-system-architecture)
9. [Backend API Specification](#9-backend-api-specification)
10. [Frontend Specification](#10-frontend-specification)
11. [Tech Stack Reference](#11-tech-stack-reference)
12. [Team Division of Labor](#12-team-division-of-labor)
13. [Risk Register & Mitigations](#13-risk-register--mitigations)
14. [Demo Narrative & SafetyKit Framing](#14-demo-narrative--safetykit-framing)
15. [Appendix](#15-appendix)

---

## 1. Executive Summary

**FirstWave** is a predictive ambulance staging dashboard for EMS dispatch operations. Rather than waiting for 911 calls and routing the nearest available unit reactively, FirstWave uses 28.7 million validated NYC EMS incidents, weather overlays, and temporal demand patterns to forecast _where_ emergencies will concentrate over the next hour — then recommends optimal staging locations for idle ambulances _before_ those calls arrive.

The system is a dispatcher-facing web application featuring:

- An interactive Mapbox map with choropleth demand heatmap and staging pin overlays
- A time-of-day slider with "Watch the Wave" animation showing demand patterns across 24 hours
- A counterfactual impact panel quantifying response time savings and 8-minute threshold coverage
- An **AI Dispatcher** panel (GPT-4o-mini) for natural language scenario exploration
- An **equity/SVI layer** showing Social Vulnerability Index distribution across NYC
- An **EMS stations overlay** displaying FDNY station locations for spatial context
- A **borough-fair staging optimizer** guaranteeing coverage equity across all 5 boroughs

**Validated data findings that anchor the demo:**

- Bronx mean response time: **638 seconds (10.6 minutes)** — already 33% above the 8-minute clinical threshold
- Dataset: **28.7M rows, 96.2% response time validity rate**
- **31 clean dispatch zones** (B1–B5, K1–K7, M1–M9, Q1–Q7, S1–S3)
- Severity codes 1 and 2 account for **23% of all incidents** (~6.6M rows)

**Key Results:**

| Metric | Without FirstWave | With FirstWave |
|---|---|---|
| % within 8-min clinical window | 64.7% | **86.0%** |
| Median response time saved | — | **3 min 19 sec** |
| Bronx coverage (worst borough) | 48.2% | **96.7%** |
| Most vulnerable communities (SVI Q4) | — | **299 seconds saved** |

**The pitch:** "Current EMS deployment is reactive. FirstWave is a predictive staging engine that cuts median response time by pre-positioning idle ambulances into forecasted hot zones before the 911 call happens — with the biggest gains in the city's most vulnerable neighborhoods."

---

## 2. Problem Statement

### 2.1 Background

New York City EMS responds to approximately 1.6 million calls per year. Despite this volume, ambulance deployment remains largely static: units are assigned to fixed stations and dispatched reactively when calls arrive. Emergency demand is highly non-uniform — it clusters by dispatch zone, time of day, day of week, weather conditions, and seasonal patterns in ways that are demonstrably predictable from historical data.

### 2.2 Validated Data Evidence

The following findings come from live queries against the actual NYC EMS Incident Dispatch Data (28.7M rows, confirmed February 2026):

**Response time by borough (validated):**

| Borough | Mean Response (sec) | Mean Response (min) | vs 8-min Target |
|---|---|---|---|
| Bronx | 638.3 | 10.6 min | **+33% over threshold** |
| Manhattan | 630.2 | 10.5 min | **+31% over threshold** |
| Brooklyn | 563.9 | 9.4 min | **+17% over threshold** |
| Queens | 538.3 | 9.0 min | **+12% over threshold** |
| Staten Island | 482.0 | 8.0 min | At threshold |

Every single borough except Staten Island is above the 8-minute clinical mean.

**Dataset quality (validated):**

- Total rows: 28,697,411
- Valid response time flag `Y`: 27,614,516 (**96.2%**)
- Annual volume 2019: 1,536,396
- Annual volume 2021: 1,495,772
- Annual volume 2022: 1,589,517
- Annual volume 2023: 1,591,256 (holdout)
- 2020: 1,424,727 (excluded — COVID anomaly)

**Severity distribution (validated):**

| Code | Count | % of Total | Classification |
|---|---|---|---|
| 1 | 569,117 | 2.0% | Life-threatening |
| 2 | 6,061,477 | 21.1% | Critical |
| 3 | 3,995,626 | 13.9% | Serious |
| 4 | 5,663,437 | 19.7% | Moderate |
| 5 | 5,192,966 | 18.1% | Lower urgency |
| 6 | 4,399,837 | 15.3% | Non-urgent |
| 7 | 2,722,507 | 9.5% | Lowest urgency |
| 8 | 92,411 | 0.3% | Administrative |

High-acuity (codes 1+2) = **23.1% of all incidents**.

### 2.3 The Two Failure Modes

**Failure Mode A — Temporal Coverage Gaps:** Demand is highly non-uniform by hour and day. A fixed station optimized for Monday 4 AM baseline demand is not in the right place for Friday 8 PM peak demand.

**Failure Mode B — Equity Gap:** The highest-SVI neighborhoods — concentrated in the Bronx and Central Brooklyn — already experience the longest response times. Static deployment perpetuates this gap; dynamic staging targeted at forecasted demand can close it.

### 2.4 The Response Time Decomposition Opportunity

NYC's dataset uniquely provides three response time components:

- `DISPATCH_RESPONSE_SECONDS_QY`: call creation → first unit assigned (dispatch delay)
- `INCIDENT_TRAVEL_TM_SECONDS_QY`: unit en route → on scene (drive time)
- `INCIDENT_RESPONSE_SECONDS_QY`: total call-to-on-scene

Having the decomposition means FirstWave can prove it targets the _right_ component: staging addresses drive time, not dispatch delay.

---

## 3. Solution Overview

### 3.1 What FirstWave Does

1. **Ingests** 28.7M NYC EMS incidents via DuckDB pipeline, trains XGBoost demand forecasting model on ~5.6M clean rows (2019, 2021–2022 training + 2023 holdout)
2. **Forecasts** incident count per dispatch zone for any user-specified hour, day of week, month, and weather condition using a **20-feature XGBoost model**
3. **Optimizes** staging locations using a **borough-fair weighted K-Means algorithm** that guarantees minimum coverage per borough before demand-proportional allocation
4. **Quantifies** counterfactual impact with **weather-adjusted response times** and **zone-level breakdown** — comparing static station response vs. staged response across all 31 zones
5. **Visualizes** everything in a dispatcher dashboard: choropleth heatmap, staging pins with 8-minute coverage circles, equity overlay, EMS station markers
6. **AI Dispatcher** enables natural language scenario exploration ("What happens during a Friday night storm?") via GPT-4o-mini, with automatic map control updates
7. **Equity Analysis** via ZIP-level SVI overlay showing vulnerability distribution and SVI quartile impact metrics

### 3.2 What FirstWave Does NOT Do

- Does not dispatch ambulances automatically — it is a **decision-support tool** for human dispatchers
- Does not ingest live 911 call streams — demo simulates "live" via historical data with the time slider
- Does not handle hospital routing, turnaround time, or post-scene logistics
- Does not process individual patient data — all analysis is at the dispatch zone level (HIPAA-clean)

### 3.3 Competitive Differentiation

| | Typical Hackathon EMS Project | FirstWave |
|---|---|---|
| **Analytics type** | Descriptive (what happened) | Prescriptive (where to go next) |
| **Spatial unit** | ZIP codes | Operational dispatch zones (31 zones) |
| **Routing** | Straight-line distance | Real road network via OSMnx |
| **Staging** | Static or simple centroid | Borough-fair K-Means with demand weighting |
| **Output** | A map of past incidents | K staging coordinates + coverage circles |
| **Impact measure** | Response time average | % within 8-min threshold, by SVI quartile, by zone |
| **AI integration** | None | GPT-4o-mini dispatcher for natural language queries |
| **Dataset size** | Sample or single year | 28.7M rows, 2005–2024 |

---

## 4. Goals & Success Metrics

### 4.1 Achieved Results

| Goal | Status | Result |
|---|---|---|
| Data pipeline complete | Done | 8-script DuckDB pipeline, all artifacts generated |
| Model A trained | Done | XGBoost 20-feature model, RMSE ~6.0 on 2023 holdout |
| Model B working | Done | Borough-fair K-Means with guaranteed per-borough coverage |
| Counterfactual pre-computed | Done | 168 (hour × dow) combinations + zone-level + weather-adjusted |
| FastAPI running | Done | 7 endpoints, all < 500ms |
| Dashboard working | Done | Full interactive map with Watch the Wave, AI panel, equity layer |
| AI Dispatcher | Done | GPT-4o-mini auto-briefing + interactive chat with map control |

### 4.2 Key Demo Metrics (achieved)

- **Primary:** 64.7% → **86.0%** within 8-minute threshold (staged vs. static)
- **Primary:** Median **3 min 19 sec** saved
- **Equity:** SVI Q4 (most vulnerable) saves **299 seconds** — most benefit goes to most vulnerable
- **Bronx:** 48.2% → **96.7%** coverage improvement

### 4.3 The Single Number That Wins

Bronx coverage improvement from 48.2% to 96.7% within the 8-minute clinical window. Framed against cardiac arrest survival: every minute past 8 minutes drops survival probability by ~10%. This is the number that makes the pitch.

---

## 5. Dataset Specifications & Validation

### 5.1 Primary Dataset — NYC EMS Incident Dispatch Data

**Source:** NYC Open Data / Socrata
**URL:** `https://data.cityofnewyork.us/Public-Safety/EMS-Incident-Dispatch-Data/76xm-jjuj`
**Volume:** 28,697,411 rows (2005–2024), ~2GB raw CSV
**Training window:** 2019, 2021, 2022 (~5.6M rows after quality filters)
**Holdout:** 2023 (~1.5M rows after quality filters)

**Quality filters (9 filters applied in order):**

```python
VALID_DISPATCH_ZONES = {
    'B1','B2','B3','B4','B5',
    'K1','K2','K3','K4','K5','K6','K7',
    'M1','M2','M3','M4','M5','M6','M7','M8','M9',
    'Q1','Q2','Q3','Q4','Q5','Q6','Q7',
    'S1','S2','S3'
}

df = df[
    (df['VALID_INCIDENT_RSPNS_TIME_INDC'] == 'Y') &
    (df['VALID_DISPATCH_RSPNS_TIME_INDC'] == 'Y') &
    (df['REOPEN_INDICATOR'] == 'N') &
    (df['TRANSFER_INDICATOR'] == 'N') &
    (df['STANDBY_INDICATOR'] == 'N') &
    (df['INCIDENT_RESPONSE_SECONDS_QY'].between(1, 7200)) &
    (df['BOROUGH'] != 'UNKNOWN') &
    (df['INCIDENT_DISPATCH_AREA'].isin(VALID_DISPATCH_ZONES)) &
    # Enforce zone matches expected borough prefix (B→BRONX, K→BROOKLYN, etc.)
    (zone_prefix_matches_borough)
]
```

### 5.2 Secondary Dataset — Open-Meteo Historical Weather API

**URL:** `https://archive-api.open-meteo.com/v1/archive`
**Cost:** Free, no API key
**Variables:** `temperature_2m`, `precipitation`, `windspeed_10m`, `weathercode`
**NYC coordinates:** 40.7128°N, 74.0060°W

### 5.3 CDC Social Vulnerability Index (SVI)

**Source:** CDC/ATSDR Social Vulnerability Index
**Metric:** `RPL_THEMES` composite score (0–1), aggregated from census tract to dispatch zone level
**Usage:** Feature in demand model + equity visualization layer + impact quartile analysis

---

## 6. Data Pipeline

### 6.1 Infrastructure

**Runtime:** Local DuckDB (pivoted from Databricks Community Edition mid-hackathon due to cluster memory limits)
**Processing:** 8-script sequential pipeline
**Intermediate storage:** Parquet files in `pipeline/data/` (gitignored, ~500MB)
**Output:** Artifacts written directly to `backend/artifacts/`

### 6.2 Pipeline Scripts

| Script | Purpose | Output |
|---|---|---|
| `01_ingest_clean.py` | Load raw CSV, apply 9 quality filters | `incidents_cleaned.parquet` |
| `02_weather_merge.py` | Join hourly Open-Meteo weather data | `incidents_with_weather.parquet` |
| `03_spatial_join.py` | Attach zone centroids + SVI scores | `incidents_spatial.parquet` |
| `04_aggregate.py` | Compute zone-level baselines and stats | `zone_baselines.parquet`, `zone_stats.parquet` |
| `05_train_demand_model.py` | Train 20-feature XGBoost model | `demand_model.pkl` |
| `06_osmnx_matrix.py` | Compute drive-time matrix via NYC road network | `drive_time_matrix.pkl` |
| `07_staging_optimizer.py` | Validate staging algorithm on test scenarios | Validation output only |
| `08_counterfactual_precompute.py` | Simulate staged vs. static response times | `counterfactual_summary.parquet`, `counterfactual_raw.parquet` |

### 6.3 Artifact Outputs

| Artifact | File | Used By |
|---|---|---|
| Demand model | `demand_model.pkl` | `/api/heatmap`, `/api/staging` |
| Drive-time matrix | `drive_time_matrix.pkl` | `/api/counterfactual` |
| Zone baselines | `zone_baselines.parquet` | `/api/heatmap` (zone_baseline_avg feature) |
| Zone stats | `zone_stats.parquet` | `/api/historical`, `/api/breakdown` |
| Counterfactual summary | `counterfactual_summary.parquet` | `/api/counterfactual` |
| Counterfactual raw | `counterfactual_raw.parquet` | `/api/counterfactual` (by_borough, by_svi) |

---

## 7. Machine Learning & Optimization

### 7.1 Model A — XGBoost Demand Forecaster

**Target:** `incident_count` (incidents per zone per hour)
**Training data:** 2019, 2021, 2022 (~5.6M rows)
**Holdout:** 2023 (~1.5M rows)

**20 Features (order must match training):**

```python
FEATURE_COLS = [
    # Cyclical temporal encodings
    "hour_sin",          # sin(2pi * hour / 24)
    "hour_cos",          # cos(2pi * hour / 24)
    "dow_sin",           # sin(2pi * dayofweek / 7)
    "dow_cos",           # cos(2pi * dayofweek / 7)
    "month_sin",         # sin(2pi * month / 12)
    "month_cos",         # cos(2pi * month / 12)
    # Temporal flags
    "is_weekend",        # 1 if dow in (5,6) else 0
    # Weather features
    "temperature_2m",    # degrees Celsius
    "precipitation",     # mm/hr
    "windspeed_10m",     # km/h
    "is_severe_weather", # 1 if precipitation > 5mm
    # Zone-specific features
    "svi_score",         # CDC SVI RPL_THEMES 0-1
    "zone_baseline_avg", # rolling avg incidents (zone, hour, dow) -- MOST IMPORTANT
    "high_acuity_ratio", # historical % of codes 1+2
    "held_ratio",        # historical % of held calls
    # Extended temporal flags (v3 additions)
    "is_holiday",        # 1 if federal holiday (hardcoded 0 for inference)
    "is_major_event",    # 1 if NYC major event (hardcoded 0)
    "is_school_day",     # 1 if school in session (hardcoded 1)
    # Heat emergency flags
    "is_heat_emergency", # 1 if temperature >= 35C
    "is_extreme_heat",   # 1 if temperature >= 35C
    # Infrastructure
    "subway_disruption_idx",  # 0-1 disruption level (hardcoded 0.5)
]
```

**XGBoost Hyperparameters:**

```python
XGBRegressor(
    n_estimators=300,
    max_depth=6,
    learning_rate=0.05,
    subsample=0.8,
    colsample_bytree=0.8,
    random_state=42,
    n_jobs=-1,
    tree_method="hist"
)
```

**Inference:** Predictions clipped to minimum 0. Returns `{zone_code: predicted_count}` for all 31 zones.

### 7.2 Model B — Borough-Fair Staging Optimizer

The staging optimizer uses a two-phase allocation to guarantee equity across boroughs:

**Phase 1 — Guaranteed allocation:**
- Rank boroughs by total predicted demand (descending)
- Allocate 1 staging point to each borough (if K >= 5)
- Each borough runs demand-weighted centroid placement for its single point

**Phase 2 — Extra allocation:**
- Remaining K-5 ambulances allocated to borough with highest demand-per-cluster ratio
- Formula: `best_borough = argmax(borough_demand / borough_clusters)`
- Each allocation increments that borough's cluster count

**Within-borough clustering:**
- If borough has 1 cluster: demand-weighted centroid
- If borough has N > 1 clusters: K-Means with `sample_weight=demand_weights`, `n_init=10`

**Coverage radius:** 3,500 meters (~8-minute urban drive at ~25 km/h)

**Output per staging point:**
```python
{
    "staging_index": int,     # 0-indexed, sorted by demand coverage descending
    "lat": float,
    "lon": float,
    "coverage_radius_m": 3500,
    "predicted_demand_coverage": float,
    "cluster_zones": [str],
    "zone_count": int
}
```

### 7.3 Counterfactual Engine

The counterfactual engine compares actual historical response times against simulated staged response times.

**Weather travel factor:**
```python
factor = 1.0 + (0.012 * precipitation_mm) + (0.002 * max(0, windspeed - 15))
```
- Adds 1.2% penalty per mm/hr precipitation
- Adds 0.2% penalty per km/h wind above 15 km/h

**Response time calculation per zone:**
```python
static_time = dispatch_sec + (travel_sec * weather_factor)
staged_time = dispatch_sec + min(best_drive_time_from_staging, static_travel_component)
# Staged can never be worse than static
# Minimum drive time floor: 120 seconds
```

**8-minute threshold estimation (lognormal CDF):**
```python
cv = 0.95  # calibrated to real EMS response time distributions
sigma = sqrt(ln(1 + cv^2))
mu = ln(mean_seconds) - sigma^2/2
pct_within_8min = lognorm.cdf(480, s=sigma, scale=exp(mu))
```

**Aggregation:**
- All metrics demand-weighted by predicted incident count
- Borough-level and SVI-quartile breakdowns use same weighting
- Zone-level breakdown provides per-zone static/staged/saved times

---

## 8. System Architecture

```
[ 28.7M NYC EMS Incidents ]
         |
         v
[ DuckDB Pipeline ] --- 9 quality filters, weather merge, SVI join
         |
         +-- zone_baselines.parquet  (rolling demand averages per zone/hour/day)
         +-- zone_stats.parquet      (per-zone historical response stats)
         +-- demand_model.pkl        (20-feature XGBoost)
         +-- drive_time_matrix.pkl   (OSMnx NYC road network)
         +-- counterfactual_*.parquet (precomputed impact metrics)
         |
         v
[ FastAPI Backend ]  <-- artifacts loaded at startup, <300ms per request
    GET  /api/heatmap          -> 31-zone demand forecast GeoJSON
    GET  /api/staging          -> K optimal staging locations GeoJSON
    GET  /api/counterfactual   -> coverage + time saved + by_zone + weather
    GET  /api/historical/:zone -> per-zone response time history
    GET  /api/breakdown        -> borough-level performance breakdown
    GET  /api/stations         -> 31 FDNY EMS station locations GeoJSON
    POST /api/ai               -> GPT-4o-mini dispatcher briefing/chat
    GET  /health               -> artifact status
    POST /reload               -> hot-reload artifacts
         |
         v
[ React 19 + Mapbox GL JS 3.18 Dashboard ]
    Choropleth demand heatmap (31 zones)
    Staging pins with 8-min coverage circles
    EMS station markers overlay
    Equity/SVI ZIP-level overlay (purple ramp)
    Zone detail panels (click any zone)
    Impact metrics panel (coverage bars + histogram)
    AI Dispatcher panel (auto-briefing + chat)
    Watch the Wave animation (24-hour playback)
    Control panel (hour slider, day picker, weather, ambulances)
```

---

## 9. Backend API Specification

**Base URL:** `http://localhost:8000`

### GET /api/heatmap

**Query params:**

| Param | Type | Range | Default | Required |
|---|---|---|---|---|
| hour | int | 0–23 | — | yes |
| dow | int | 0–6 (Mon=0) | — | yes |
| month | int | 1–12 | — | yes |
| temperature | float | — | 15.0 | no |
| precipitation | float | — | 0.0 | no |
| windspeed | float | — | 10.0 | no |
| ambulances | int | 1–10 | 5 | no |

**Response:** GeoJSON FeatureCollection

```json
{
  "type": "FeatureCollection",
  "query_params": {"hour": 20, "dow": 4, "month": 10},
  "features": [
    {
      "type": "Feature",
      "properties": {
        "zone": "B2",
        "borough": "BRONX",
        "zone_name": "West/Central Bronx",
        "predicted_count": 18.4,
        "normalized_intensity": 0.91,
        "svi_score": 0.89,
        "historical_avg_response_sec": 641,
        "high_acuity_ratio": 0.28
      },
      "geometry": {"type": "MultiPolygon", "coordinates": [...]}
    }
  ]
}
```

**Normalization:** `(count - min) / (max - min + 0.001)` across all 31 zones.

**Response header:** `X-Data-Source: "model"` or `"mock"`.

---

### GET /api/staging

**Query params:** Same as `/api/heatmap`.

**Response:** GeoJSON FeatureCollection

```json
{
  "type": "FeatureCollection",
  "ambulance_count": 5,
  "features": [
    {
      "type": "Feature",
      "properties": {
        "staging_index": 0,
        "coverage_radius_m": 3500,
        "predicted_demand_coverage": 31.2,
        "cluster_zones": ["B1", "B2", "B3"],
        "zone_count": 3
      },
      "geometry": {"type": "Point", "coordinates": [-73.9196, 40.8448]}
    }
  ]
}
```

**Caching:** LRU cache with 168 slots (24 hours x 7 days).

---

### GET /api/counterfactual

**Query params:**

| Param | Type | Range | Default | Required |
|---|---|---|---|---|
| hour | int | 0–23 | — | yes |
| dow | int | 0–6 | — | yes |
| month | int | 1–12 | 10 | no |
| temperature | float | — | 15.0 | no |
| precipitation | float | — | 0.0 | no |
| windspeed | float | — | 10.0 | no |
| ambulances | int | 1–10 | 5 | no |

**Response:**

```json
{
  "hour": 20,
  "dayofweek": 4,
  "median_seconds_saved": 147,
  "pct_within_8min_static": 61.2,
  "pct_within_8min_staged": 83.7,
  "by_borough": {
    "BRONX": {"static": 48.2, "staged": 74.6, "median_saved_sec": 213},
    "BROOKLYN": {"static": 58.4, "staged": 81.2, "median_saved_sec": 159},
    "MANHATTAN": {"static": 71.3, "staged": 89.1, "median_saved_sec": 118},
    "QUEENS": {"static": 63.1, "staged": 84.9, "median_saved_sec": 141},
    "RICHMOND / STATEN ISLAND": {"static": 75.0, "staged": 88.3, "median_saved_sec": 89}
  },
  "by_svi_quartile": {
    "Q1": {"median_saved_sec": 89},
    "Q2": {"median_saved_sec": 118},
    "Q3": {"median_saved_sec": 159},
    "Q4": {"median_saved_sec": 213}
  },
  "histogram_baseline_seconds": [320, 480, 520, 610, 390, 720, 445, 510],
  "histogram_staged_seconds": [210, 310, 380, 440, 290, 510, 335, 390],
  "by_zone": {
    "B1": {"static_time": 680, "staged_time": 420, "seconds_saved": 260},
    "B2": {"static_time": 641, "staged_time": 398, "seconds_saved": 243}
  }
}
```

**Weather factor applied:** `1.0 + 0.012*precip + 0.002*max(0, wind-15)` affects both static and staged travel times.

---

### GET /api/historical/{zone_code}

**Path param:** Zone code string (e.g., "B2"). 404 if not in VALID_ZONES.

**Response:**

```json
{
  "zone": "B2",
  "borough": "BRONX",
  "zone_name": "West/Central Bronx",
  "svi_score": 0.89,
  "avg_response_seconds": 641,
  "avg_travel_seconds": 398,
  "avg_dispatch_seconds": 243,
  "high_acuity_ratio": 0.28,
  "held_ratio": 0.09,
  "hourly_avg": [3.1, 2.4, 1.9, ..., 7.4]
}
```

`hourly_avg` is always exactly 24 values (index = hour of day, 0 = midnight).

---

### GET /api/breakdown

**Response:** Array of 5 borough objects.

```json
[
  {
    "name": "BRONX",
    "avg_dispatch_seconds": 243,
    "avg_travel_seconds": 395,
    "avg_total_seconds": 638,
    "pct_held": 9.1,
    "high_acuity_ratio": 0.28,
    "zones": ["B1", "B2", "B3", "B4", "B5"]
  }
]
```

---

### GET /api/stations

**Response:** GeoJSON FeatureCollection of FDNY EMS stations.

```json
{
  "type": "FeatureCollection",
  "count": 31,
  "features": [
    {
      "type": "Feature",
      "properties": {
        "station_id": "EMS_M01",
        "name": "Station 1 - Midtown",
        "borough": "MANHATTAN",
        "address": "123 Main St",
        "dispatch_zone": "M3"
      },
      "geometry": {"type": "Point", "coordinates": [-73.985, 40.758]}
    }
  ]
}
```

**Data source:** `data/ems_stations.json` (static, maintained by Ansh).

---

### POST /api/ai

**Request:**

```json
{
  "message": "What about a Friday night Yankees game?",
  "context": {
    "hour": 20,
    "dow": 4,
    "weather": "none",
    "ambulances": 5,
    "top_zones": [{"zone": "B2", "borough": "BRONX", "count": 18.4}],
    "coverage": {"pct_static": 61.2, "pct_staged": 83.7, "median_saved_sec": 147}
  }
}
```

- `message: null` triggers **auto-briefing mode** (3-sentence operational briefing)
- `message: string` triggers **interactive mode** (2-3 sentence response + optional map control changes)

**Response:**

```json
{
  "reply": "Friday evening in the Bronx shows peak demand at 18.4 predicted incidents in West/Central Bronx...",
  "controls": {"hour": 20, "dow": 4}
}
```

`controls` is `null` when no map state change is recommended.

**AI Configuration:**
- Model: GPT-4o-mini
- Max tokens: 300
- Temperature: 0.7
- System prompt includes zone legend, 8-minute threshold context, and current dashboard snapshot

---

### GET /health

```json
{
  "status": "ok",
  "artifacts": {
    "demand_model": true,
    "drive_time": true,
    "baselines": true,
    "zone_stats": true,
    "counterfactual": true
  }
}
```

### POST /reload

Reloads all artifacts from `backend/artifacts/` without server restart.

---

## 10. Frontend Specification

### 10.1 Technology

- **React 19.2.0** with Vite 7.3.1
- **Mapbox GL JS 3.18.1** via react-map-gl 7.1.9
- **TanStack React Query 5.90** for data fetching and caching
- **Plotly.js 3.4.0** for charts
- **Tailwind CSS 4.2.0** for styling

### 10.2 Component Architecture

```
App.jsx (root state manager)
├── Header.jsx
├── Controls/
│   ├── ControlPanel.jsx
│   ├── TimeSlider.jsx
│   ├── DayPicker.jsx
│   ├── WeatherSelector.jsx
│   ├── AmbulanceCount.jsx
│   └── LayerToggle.jsx
├── Map/
│   ├── MapContainer.jsx (Mapbox wrapper, event handlers)
│   ├── ZoneChoropleth.jsx (zone polygon outlines)
│   ├── StagingPins.jsx (ambulance pins + coverage circles)
│   ├── StationLayer.jsx (FDNY station markers)
│   ├── EquityLayer.jsx (SVI ZIP-level overlay)
│   ├── ZoneTooltip.jsx (hover info)
│   └── ZoneDetailPanel.jsx (click-to-expand zone stats)
├── Impact/
│   ├── ImpactPanel.jsx
│   ├── CoverageBars.jsx
│   ├── ResponseHistogram.jsx
│   ├── EquityChart.jsx
│   └── OverlayPanel.jsx (SVI toggle + legend)
└── Chat/
    └── AiPanel.jsx (AI Dispatcher)
```

### 10.3 Key Features

**Watch the Wave Animation**
- Triggered by play button in control panel
- Increments hour from 0 to 23 at 1.5-second intervals
- Auto-stops at hour 23
- All data hooks re-fetch at each hour step

**AI Dispatcher Panel**
- Collapsed state: pill button at top-right corner
- Expanded state: 340px x 520px chat panel
- Auto-briefing: generates 3-sentence operational summary when heatmap data changes (1.5s debounce)
- Interactive chat: sends user message + dashboard context to GPT-4o-mini
- Map control updates: AI can recommend hour/dow changes, applied via callback
- Undo: captures previous control state, allows one-click revert

**Equity/SVI Layer**
- ZIP-level GeoJSON polygons enriched with zone-mapped SVI scores
- Purple color ramp: transparent (SVI 0.0) to dark purple (SVI 1.0)
- Toggled via OverlayPanel with visual legend
- CDC Social Vulnerability Index explanation text

**EMS Station Layer**
- Circle markers (8px, gray #90A4AE) for each FDNY station
- Hover tooltip: station name, borough, address
- Toggled via layer visibility controls

**Layer Toggles**
- Heatmap (demand choropleth)
- Staging (pins + coverage circles)
- Coverage (circle overlays)
- Stations (FDNY markers)

### 10.4 Color Scales

**Demand choropleth (normalized_intensity 0–1):**
```
0.0 -> #00897B  (teal, low demand)
0.3 -> #FDD835  (yellow)
0.6 -> #FB8C00  (orange)
1.0 -> #C62828  (red, critical demand)
```

**Equity overlay (SVI 0–1):**
```
0.0 -> transparent light purple
1.0 -> rgba(76, 5, 149, 0.95) (dark purple)
```

**Staging coverage circles:**
```
fill:   rgba(66, 165, 245, 0.15)
stroke: rgba(66, 165, 245, 0.6)
```

### 10.5 Map Configuration

```javascript
initialViewState = {
    longitude: -73.97,
    latitude: 40.73,
    zoom: 10.5,
    pitch: 0,
    bearing: 0
}
mapStyle = "mapbox://styles/mapbox/dark-v11"
```

### 10.6 Weather Presets

```javascript
WEATHER_PRESETS = {
    none:  { temperature: 22, precipitation: 0,  windspeed: 8  },
    light: { temperature: 10, precipitation: 4,  windspeed: 20 },
    heavy: { temperature: 4,  precipitation: 12, windspeed: 40 }
}
```

### 10.7 Data Hooks

| Hook | Endpoint | Trigger |
|---|---|---|
| `useHeatmap` | GET /api/heatmap | Controls change (debounced 300ms) |
| `useStaging` | GET /api/staging | Controls change (debounced 300ms) |
| `useCounterfactual` | GET /api/counterfactual | Controls change (debounced 300ms) |
| `useZoneHistory` | GET /api/historical/:zone | Zone selection change |
| `useStations` | GET /api/stations | Component mount (once) |

---

## 11. Tech Stack Reference

| Layer | Technology | Version |
|---|---|---|
| ML — Demand | XGBoost | 2.0.3 |
| ML — Staging | scikit-learn (K-Means) | 1.4.1 |
| ML — AI Dispatcher | OpenAI GPT-4o-mini | latest |
| Spatial Routing | OSMnx + NetworkX | 1.9.1 / 3.3 |
| Data Processing | DuckDB, pandas, pyarrow | 1.4+ / 2.2.1 / 16.0 |
| Backend API | FastAPI + Uvicorn | 0.110.0 / 0.29.0 |
| Database | PostgreSQL + PostGIS | 15 + 3.4 |
| Frontend | React | 19.2.0 |
| Map | Mapbox GL JS + react-map-gl | 3.18.1 / 7.1.9 |
| Charts | Plotly.js + react-plotly.js | 3.4.0 / 2.6.0 |
| Data Fetching | TanStack React Query | 5.90.21 |
| HTTP Client | Axios | 1.13.5 |
| Styling | Tailwind CSS | 4.2.0 |
| Build Tool | Vite | 7.3.1 |
| Testing | Vitest + Testing Library | 4.0.18 |

---

## 12. Team Division of Labor

| Person | Role | Module | Do Not Touch |
|---|---|---|---|
| Vaibhav | Frontend Lead + Integration | `frontend/` | backend/, pipeline/ |
| Ashwin | Backend Lead | `backend/` | frontend/, pipeline/ |
| Praneel | Pipeline Lead | `pipeline/`, `databricks_notebooks/` | frontend/, backend/ source |
| Ansh | PM + Demo | `data/ems_stations.json`, Devpost | All code |

---

## 13. Risk Register & Mitigations

| Risk | Impact | What Happened | Mitigation |
|---|---|---|---|
| Databricks Community Edition cluster limits | Pipeline blocked | Pivoted to local DuckDB in ~2 hours | DuckDB handles 28.7M rows locally without issues |
| CORS port mismatch | Frontend can't reach backend | Backend CORS config initially missed port 3000 | Added all likely dev ports to `allow_origins` |
| XGBoost model RMSE > target | Inaccurate predictions | RMSE ~6.0 vs target <4.0 | zone_baseline_avg is dominant feature; model still produces useful relative rankings |
| PostGIS unavailable | No zone geometries | Falls back to extracting geometries from mock data | Graceful degradation chain: PostGIS -> mock GeoJSON |
| OpenAI API key missing | AI panel non-functional | Returns informative error message | Panel shows "OPENAI_API_KEY not configured" |
| Artifact files not yet generated | Endpoints return empty | Mock data fallback at every endpoint | `X-Data-Source: mock` header signals which mode |

---

## 14. Demo Narrative & SafetyKit Framing

### Demo Flow (5 minutes)

1. **Open on Monday 4 AM** — map shows cool teal/green across all boroughs. Demand is low, evenly distributed.

2. **Watch the Wave** — hit play. The hour slider auto-advances 0→23, showing demand build through the day. By 8 PM, Bronx and Brooklyn burst red.

3. **Pause on Friday 8 PM** — highlight the staging pins. 5 ambulances pre-positioned at the mathematical center of predicted demand, with overlapping 8-minute coverage circles.

4. **Show Impact Panel** — 64.7% → 86.0% within 8-minute window. Median 3 min 19 sec saved.

5. **Show Equity** — toggle SVI layer. Purple overlay shows vulnerability distribution. SVI Q4 (most vulnerable) gets 299 seconds saved — the algorithm isn't just faster, it's fairer.

6. **Toggle Stations** — show FDNY station locations. Note the gap between fixed station placement and where demand actually concentrates.

7. **AI Dispatcher** — ask "What about a Friday night Yankees game?" Watch the AI return a briefing and adjust map controls. Ask "Show me a quiet Monday morning" — map shifts automatically.

8. **Storm scenario** — switch weather to "heavy." Watch response times increase, more zones turn orange/red. FirstWave accounts for weather in both forecasting and response time estimation.

9. **Click a zone** — show zone detail panel with 24-hour demand curve, historical response times, SVI score, before/after response times.

10. **Closing line:** "The Bronx at 10.6 minutes average isn't a resource problem. It's a placement problem. FirstWave solves the placement problem."

### SafetyKit Framing

"Prevents harm, reduces risk, helps people respond safely in the moments that matter most."

Every minute of delayed cardiac arrest response reduces survival probability by ~10%. Bronx at 10.6 min average means patients are already past the point where survival drops ~65% compared to a 4-minute response.

FirstWave directly addresses human safety by:
- Predicting demand before it occurs
- Pre-positioning responders in optimal locations
- Quantifying the equity impact on vulnerable communities
- Providing AI-assisted scenario planning for dispatchers

---

## 15. Appendix

### 15.1 Zone Centroids (longitude, latitude)

```python
ZONE_CENTROIDS = {
    'B1': (-73.9101, 40.8116), 'B2': (-73.9196, 40.8448),
    'B3': (-73.8784, 40.8189), 'B4': (-73.8600, 40.8784),
    'B5': (-73.9056, 40.8651),
    'K1': (-73.9857, 40.5995), 'K2': (-73.9442, 40.6501),
    'K3': (-73.9075, 40.6929), 'K4': (-73.9015, 40.6501),
    'K5': (-73.9283, 40.6801), 'K6': (-73.9645, 40.6401),
    'K7': (-73.9573, 40.7201),
    'M1': (-74.0060, 40.7128), 'M2': (-74.0000, 40.7484),
    'M3': (-73.9857, 40.7580), 'M4': (-73.9784, 40.7484),
    'M5': (-73.9584, 40.7701), 'M6': (-73.9484, 40.7884),
    'M7': (-73.9428, 40.8048), 'M8': (-73.9373, 40.8284),
    'M9': (-73.9312, 40.8484),
    'Q1': (-73.7840, 40.6001), 'Q2': (-73.8284, 40.7501),
    'Q3': (-73.8784, 40.7201), 'Q4': (-73.9073, 40.7101),
    'Q5': (-73.8073, 40.6901), 'Q6': (-73.9173, 40.7701),
    'Q7': (-73.8373, 40.7701),
    'S1': (-74.1115, 40.6401), 'S2': (-74.1515, 40.5901),
    'S3': (-74.1915, 40.5301),
}
```

### 15.2 Zone SVI Scores

```python
ZONE_SVI = {
    'B1':0.94, 'B2':0.89, 'B3':0.87, 'B4':0.72, 'B5':0.68,
    'K1':0.52, 'K2':0.58, 'K3':0.82, 'K4':0.84, 'K5':0.79, 'K6':0.60, 'K7':0.45,
    'M1':0.31, 'M2':0.18, 'M3':0.15, 'M4':0.20, 'M5':0.12,
    'M6':0.14, 'M7':0.73, 'M8':0.65, 'M9':0.61,
    'Q1':0.71, 'Q2':0.44, 'Q3':0.38, 'Q4':0.55, 'Q5':0.67, 'Q6':0.48, 'Q7':0.41,
    'S1':0.38, 'S2':0.32, 'S3':0.28
}
```

### 15.3 Severe Weather Codes (WMO)

```python
SEVERE_WEATHER_CODES = {51,53,55,61,63,65,71,73,75,77,80,81,82,85,86,95,96,99}
```

### 15.4 Drive-Time Matrix Schema

```python
# dict with keys: (origin_key, destination_zone)
# origin_key is zone_code (e.g. 'B2') or station_id (e.g. 'EMS_M01')
# value is drive time in seconds
drive_time_matrix[('B2', 'B1')] = 312
drive_time_matrix[('EMS_M01', 'M3')] = 180
```
