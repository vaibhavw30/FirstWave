# CLAUDE.md — FirstWave Project Context

# READ THIS BEFORE DOING ANYTHING ELSE IN THIS REPO

---

## What This Project Is

**FirstWave** is a predictive ambulance staging dashboard for NYC EMS dispatchers.
It forecasts where 911 calls will cluster over the next hour using historical incident
patterns, weather, and temporal demand signals — then recommends optimal staging
locations for idle ambulances before those calls arrive.

**Hackathon:** GT Hacklytics 2026
**Tracks:** Healthcare (primary) + SafetyKit: Best AI for Human Safety (secondary)
**Submission deadline:** Sunday February 22, 9:00 AM EST
**Demo format:** 5-minute live pitch + 2-minute Q&A at expo

---

## Team + Module Ownership

| Person  | Role                        | Tool                | Module                            | DO NOT TOUCH                     |
| ------- | --------------------------- | ------------------- | --------------------------------- | -------------------------------- |
| Vaibhav | Frontend Lead + Integration | Claude Max          | `frontend/`                       | backend/, databricks_notebooks/  |
| Ashwin  | Backend Lead                | Claude Pro + GitHub | `backend/`                        | frontend/, databricks_notebooks/ |
| Praneel | Pipeline Lead               | Claude Pro + GitHub | `databricks_notebooks/`           | frontend/, backend/ source files |
| Ansh    | PM + Demo                   | Non-technical       | `data/ems_stations.json`, Devpost | All code                         |

**Rule:** Never edit another person's module. If you need something from another module,
post in group chat and ask. Do not edit it yourself.

**Shared files (one designated writer each):**

- `data/mock_api_responses.json` → Ashwin writes in Hour 0, FROZEN after that
- `data/ems_stations.json` → Ansh writes manually, everyone reads
- `data/zone_centroids.json` → generated from constants in this file
- `CLAUDE.md` → anyone can ADD to it, never delete from it

---

## Repo Structure

```
firstwave/
├── CLAUDE.md                        ← this file
├── PRD_v2.md                        ← full technical spec
├── HACKATHON_STRATEGY.md            ← demo script, submission checklist
├── VAIBHAV_GUIDE.md                 ← Vaibhav's personal step-by-step guide
├── ASHWIN_GUIDE.md                  ← Ashwin's personal step-by-step guide
├── PRANEEL_GUIDE.md                 ← Praneel's personal step-by-step guide
├── ANSH_GUIDE.md                    ← Ansh's personal step-by-step guide
│
├── frontend/                        ← React 18 + Mapbox GL JS (Vaibhav)
│   ├── src/
│   │   ├── App.jsx
│   │   ├── constants.js             ← MAPBOX_TOKEN, API_BASE_URL, USE_MOCK_DATA
│   │   ├── components/
│   │   │   ├── Map/
│   │   │   │   ├── MapContainer.jsx
│   │   │   │   ├── ZoneChoropleth.jsx
│   │   │   │   ├── StagingPins.jsx
│   │   │   │   ├── ZoneTooltip.jsx
│   │   │   │   └── ZoneDetailPanel.jsx
│   │   │   ├── Controls/
│   │   │   │   ├── ControlPanel.jsx
│   │   │   │   ├── TimeSlider.jsx
│   │   │   │   ├── DayPicker.jsx
│   │   │   │   ├── WeatherSelector.jsx
│   │   │   │   ├── AmbulanceCount.jsx
│   │   │   │   └── LayerToggle.jsx
│   │   │   ├── Impact/
│   │   │   │   ├── ImpactPanel.jsx
│   │   │   │   ├── CoverageBars.jsx
│   │   │   │   ├── ResponseHistogram.jsx
│   │   │   │   └── EquityChart.jsx
│   │   │   └── Header.jsx
│   │   ├── hooks/
│   │   │   ├── useHeatmap.js
│   │   │   ├── useStaging.js
│   │   │   ├── useCounterfactual.js
│   │   │   └── useZoneHistory.js
│   │   └── utils/
│   │       ├── colorScale.js
│   │       └── formatters.js        ← seconds → "X min Y sec"
│   ├── .env                         ← VITE_MAPBOX_TOKEN, VITE_API_BASE_URL
│   ├── package.json
│   └── vite.config.js
│
├── backend/                         ← FastAPI Python (Ashwin)
│   ├── main.py                      ← app, CORS, startup artifact loading
│   ├── routers/
│   │   ├── heatmap.py
│   │   ├── staging.py
│   │   ├── counterfactual.py
│   │   ├── historical.py
│   │   └── breakdown.py
│   ├── models/
│   │   ├── demand_forecaster.py     ← XGBoost inference wrapper
│   │   └── staging_optimizer.py    ← weighted K-Means
│   ├── scripts/
│   │   └── seed_zone_boundaries.py ← populates PostGIS with zone polygons
│   ├── artifacts/                   ← populated by Praneel during hackathon
│   │   ├── demand_model.pkl         ← arrives ~Hour 10
│   │   ├── drive_time_matrix.pkl    ← pre-computed before hackathon
│   │   ├── zone_baselines.parquet   ← arrives ~Hour 10
│   │   ├── zone_stats.parquet       ← arrives ~Hour 10
│   │   └── counterfactual_summary.parquet ← arrives ~Hour 20
│   ├── requirements.txt
│   └── .env
│
├── databricks_notebooks/            ← Spark pipeline (Praneel)
│   ├── 01_ingest_clean.py
│   ├── 02_weather_merge.py
│   ├── 03_spatial_join.py
│   ├── 04_aggregate.py
│   ├── 05_train_demand_model.py
│   ├── 06_osmnx_matrix.py           ← RUN PRE-HACKATHON (30-60 min compute)
│   ├── 07_staging_optimizer.py
│   └── 08_counterfactual_precompute.py
│
└── data/                            ← static files, read-only for code
    ├── mock_api_responses.json      ← Ashwin writes Hour 0, FROZEN
    ├── ems_stations.json            ← Ansh compiles manually (~36 FDNY stations)
    ├── zone_centroids.json          ← generated from ZONE_CENTROIDS below
    └── zone_svi_lookup.json         ← generated from ZONE_SVI below
```

---

## API Contract

### Base URL: http://localhost:8000

### Frontend: http://localhost:3000

These field names are FROZEN after Hour 0. Never rename a field without
notifying both Vaibhav and Praneel simultaneously and updating this file.

---

### GET /api/heatmap

**Query params:**

```
hour          int   0–23       required
dow           int   0–6        required  (0=Monday, 6=Sunday)
month         int   1–12       required
temperature   float default 15.0
precipitation float default 0.0
windspeed     float default 10.0
ambulances    int   1–10       default 5
```

**Response: GeoJSON FeatureCollection**

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

---

### GET /api/staging

**Query params:** same as /api/heatmap (uses ambulances=K for cluster count)

**Response: GeoJSON FeatureCollection**

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
      "geometry": { "type": "Point", "coordinates": [-73.9196, 40.8448] }
    }
  ]
}
```

Note: GeoJSON Point coordinates are ALWAYS [longitude, latitude] — never reversed.

---

### GET /api/counterfactual

**Query params:** `hour` (0–23), `dow` (0–6)

**Response:**

```json
{
  "hour": 20,
  "dayofweek": 4,
  "median_seconds_saved": 147,
  "pct_within_8min_static": 61.2,
  "pct_within_8min_staged": 83.7,
  "by_borough": {
    "BRONX": { "static": 48.2, "staged": 74.6, "median_saved_sec": 213 },
    "BROOKLYN": { "static": 58.4, "staged": 81.2, "median_saved_sec": 159 },
    "MANHATTAN": { "static": 71.3, "staged": 89.1, "median_saved_sec": 118 },
    "QUEENS": { "static": 63.1, "staged": 84.9, "median_saved_sec": 141 },
    "RICHMOND / STATEN ISLAND": {
      "static": 75.0,
      "staged": 88.3,
      "median_saved_sec": 89
    }
  },
  "by_svi_quartile": {
    "Q1": { "median_saved_sec": 89 },
    "Q2": { "median_saved_sec": 118 },
    "Q3": { "median_saved_sec": 159 },
    "Q4": { "median_saved_sec": 213 }
  },
  "histogram_baseline_seconds": [320, 480, 520, 610, 390, 720, 445, 510],
  "histogram_staged_seconds": [210, 310, 380, 440, 290, 510, 335, 390]
}
```

Note: borough keys are EXACT strings — including "RICHMOND / STATEN ISLAND" with slash and spaces.

---

### GET /api/historical/{zone}

**Path param:** zone code string (e.g. "B2")

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
  "hourly_avg": [
    3.1, 2.4, 1.9, 1.6, 1.8, 2.3, 3.8, 6.1, 8.4, 9.2, 9.8, 10.1, 10.4, 10.7,
    11.2, 11.8, 12.4, 13.1, 14.8, 16.2, 15.9, 14.3, 11.8, 7.4
  ]
}
```

Note: hourly_avg is always exactly 24 values, index = hour of day (0=midnight).

---

### GET /api/breakdown

**Response: array of 5 borough objects**

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

### GET /health

**Response:**

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

Reloads all artifacts from `backend/artifacts/` without restarting the server.
Use this when Praneel drops a new .pkl or .parquet file.

---

## Validated Data Facts

_These are confirmed from live Socrata queries against the real NYC EMS dataset._

| Fact                          | Value                               | Source     |
| ----------------------------- | ----------------------------------- | ---------- |
| Total dataset rows            | 28,697,411                          | Live query |
| Valid response time flag rate | 96.2% (27.6M rows)                  | Live query |
| Annual volume 2019            | 1,536,396                           | Live query |
| Annual volume 2020            | 1,424,727 (COVID anomaly — EXCLUDE) | Live query |
| Annual volume 2021            | 1,495,772                           | Live query |
| Annual volume 2022            | 1,589,517                           | Live query |
| Annual volume 2023            | 1,591,256 (holdout)                 | Live query |
| Bronx mean response           | 638.3 sec (10.6 min)                | Live query |
| Manhattan mean response       | 630.2 sec (10.5 min)                | Live query |
| Brooklyn mean response        | 563.9 sec (9.4 min)                 | Live query |
| Queens mean response          | 538.3 sec (9.0 min)                 | Live query |
| Staten Island mean response   | 482.0 sec (8.0 min)                 | Live query |
| Clean dispatch zones          | 31                                  | Live query |
| High-acuity (codes 1+2) share | 23.1%                               | Live query |
| Severity code 1 count         | 569,117                             | Live query |
| Severity code 2 count         | 6,061,477                           | Live query |

**8-minute clinical threshold = 480 seconds.** Every borough except Staten Island is already above this on average.

**Training split:** years 2019, 2021, 2022 (~5.6M rows after filters)
**Holdout split:** year 2023 (~1.5M rows after filters)
**Excluded:** year 2020 (COVID anomaly), mismatched borough/zone codes, UNKNOWN borough

---

## Data Filtering Rules

Apply ALL of the following filters when reading `incidents_cleaned`:

```python
VALID_ZONES = [
    'B1','B2','B3','B4','B5',
    'K1','K2','K3','K4','K5','K6','K7',
    'M1','M2','M3','M4','M5','M6','M7','M8','M9',
    'Q1','Q2','Q3','Q4','Q5','Q6','Q7',
    'S1','S2','S3'
]

ZONE_BOROUGH_PREFIX = {
    'B': 'BRONX',
    'K': 'BROOKLYN',
    'M': 'MANHATTAN',
    'Q': 'QUEENS',
    'S': 'RICHMOND / STATEN ISLAND'
}

# Quality filters
VALID_INCIDENT_RSPNS_TIME_INDC == 'Y'
VALID_DISPATCH_RSPNS_TIME_INDC == 'Y'
REOPEN_INDICATOR == 'N'
TRANSFER_INDICATOR == 'N'
STANDBY_INDICATOR == 'N'
INCIDENT_RESPONSE_SECONDS_QY between 1 and 7200
BOROUGH != 'UNKNOWN'
INCIDENT_DISPATCH_AREA in VALID_ZONES
zone_prefix(INCIDENT_DISPATCH_AREA) matches BOROUGH  # B→BRONX, K→BROOKLYN etc.

# Training split: exclude 2020
year NOT IN (2020)
```

**High-acuity filter** (for counterfactual only):

```python
FINAL_SEVERITY_LEVEL_CODE IN (1, 2)
```

---

## Model A — XGBoost Demand Forecaster

**Target:** `incident_count` (incidents per zone per hour)
**Training data:** split == 'train' (2019, 2021, 2022)
**Holdout:** split == 'test' (2023)

### FEATURE_COLS (order matters — must match training exactly)

```python
FEATURE_COLS = [
    "hour_sin",          # sin(2π × hour / 24)
    "hour_cos",          # cos(2π × hour / 24)
    "dow_sin",           # sin(2π × dayofweek / 7)
    "dow_cos",           # cos(2π × dayofweek / 7)
    "month_sin",         # sin(2π × month / 12)
    "month_cos",         # cos(2π × month / 12)
    "is_weekend",        # 1 if dow in (5,6) else 0
    "temperature_2m",    # °C from Open-Meteo
    "precipitation",     # mm/hr from Open-Meteo
    "windspeed_10m",     # km/h from Open-Meteo
    "is_severe_weather", # 1 if WMO weathercode in severe_codes else 0
    "svi_score",         # CDC SVI RPL_THEMES 0–1 per zone
    "zone_baseline_avg", # rolling avg incidents for (zone, hour, dow) — most important feature
    "high_acuity_ratio", # historical % of codes 1+2 for that zone
    "held_ratio"         # historical % of held calls for that zone
]
```

### XGBoost Hyperparameters

```python
XGBRegressor(
    n_estimators=300,
    max_depth=6,
    learning_rate=0.05,
    subsample=0.8,
    colsample_bytree=0.8,
    random_state=42,
    n_jobs=-1,
    tree_method="hist"   # fast on Databricks
)
```

### MLflow Experiment

```
experiment_name: /firstwave/demand_forecasting
run_name: xgboost_v1_dispatch_zones
```

### Target Metrics

- Overall RMSE: < 4.0 incidents/zone/hour on 2023 holdout
- If RMSE > 6: zone_baseline_avg is probably not being included — check merge

---

## Model B — Weighted K-Means Staging Optimizer

```python
from sklearn.cluster import KMeans

# Weight each zone centroid by predicted demand
weights = np.array([max(predicted_counts[z], 0.01) for z in zones])
coords = np.array([[ZONE_CENTROIDS[z][1], ZONE_CENTROIDS[z][0]] for z in zones])  # [lat, lon]

kmeans = KMeans(n_clusters=K, random_state=42, n_init=20)
kmeans.fit(coords, sample_weight=weights)

# Coverage radius: 8-minute drive at ~25 km/h urban speed
coverage_radius_m = 3500
```

---

## Zone Data

### VALID_ZONES (31 clean dispatch zones)

```
Bronx:      B1 B2 B3 B4 B5
Brooklyn:   K1 K2 K3 K4 K5 K6 K7
Manhattan:  M1 M2 M3 M4 M5 M6 M7 M8 M9
Queens:     Q1 Q2 Q3 Q4 Q5 Q6 Q7
Staten Is:  S1 S2 S3
```

### ZONE_CENTROIDS (longitude, latitude)

```python
ZONE_CENTROIDS = {
    # Bronx
    'B1': (-73.9101, 40.8116),  # South Bronx, Hunts Point
    'B2': (-73.9196, 40.8448),  # West/Central Bronx
    'B3': (-73.8784, 40.8189),  # East Bronx, Soundview
    'B4': (-73.8600, 40.8784),  # North Bronx, Pelham
    'B5': (-73.9056, 40.8651),  # Riverdale, Fordham
    # Brooklyn
    'K1': (-73.9857, 40.5995),  # Southern Brooklyn, Coney Island
    'K2': (-73.9442, 40.6501),  # Park Slope, Crown Heights
    'K3': (-73.9075, 40.6929),  # Bushwick, Brownsville
    'K4': (-73.9015, 40.6501),  # East New York, Flatbush
    'K5': (-73.9283, 40.6801),  # Bed-Stuy, Ocean Hill
    'K6': (-73.9645, 40.6401),  # Borough Park, Flatbush
    'K7': (-73.9573, 40.7201),  # North Brooklyn, Williamsburg
    # Manhattan
    'M1': (-74.0060, 40.7128),  # Lower Manhattan, Financial District
    'M2': (-74.0000, 40.7484),  # Midtown South, Chelsea
    'M3': (-73.9857, 40.7580),  # Midtown, Hell's Kitchen
    'M4': (-73.9784, 40.7484),  # Murray Hill, Gramercy
    'M5': (-73.9584, 40.7701),  # Upper East Side South
    'M6': (-73.9484, 40.7884),  # Upper East Side North
    'M7': (-73.9428, 40.8048),  # Harlem, East Harlem
    'M8': (-73.9373, 40.8284),  # Washington Heights South
    'M9': (-73.9312, 40.8484),  # Washington Heights North, Inwood
    # Queens
    'Q1': (-73.7840, 40.6001),  # Far Rockaway, Jamaica
    'Q2': (-73.8284, 40.7501),  # Flushing, Bayside
    'Q3': (-73.8784, 40.7201),  # Forest Hills, Rego Park
    'Q4': (-73.9073, 40.7101),  # Ridgewood, Maspeth
    'Q5': (-73.8073, 40.6901),  # Jamaica, Hollis
    'Q6': (-73.9173, 40.7701),  # Astoria, Long Island City
    'Q7': (-73.8373, 40.7701),  # Flushing North, Whitestone
    # Staten Island
    'S1': (-74.1115, 40.6401),  # North Shore
    'S2': (-74.1515, 40.5901),  # Mid-Island
    'S3': (-74.1915, 40.5301),  # South Shore
}
```

### ZONE_NAMES (for display labels)

```python
ZONE_NAMES = {
    'B1':'South Bronx', 'B2':'West/Central Bronx', 'B3':'East Bronx',
    'B4':'North Bronx', 'B5':'Riverdale',
    'K1':'Southern Brooklyn', 'K2':'Park Slope', 'K3':'Bushwick',
    'K4':'East New York', 'K5':'Bed-Stuy', 'K6':'Borough Park', 'K7':'Williamsburg',
    'M1':'Lower Manhattan', 'M2':'Midtown South', 'M3':'Midtown',
    'M4':'Murray Hill', 'M5':'Upper East Side S', 'M6':'Upper East Side N',
    'M7':'Harlem', 'M8':'Washington Heights S', 'M9':'Washington Heights N',
    'Q1':'Far Rockaway', 'Q2':'Flushing', 'Q3':'Forest Hills',
    'Q4':'Ridgewood', 'Q5':'Jamaica', 'Q6':'Astoria', 'Q7':'Whitestone',
    'S1':'North Shore SI', 'S2':'Mid-Island SI', 'S3':'South Shore SI'
}
```

### ZONE_SVI (CDC Social Vulnerability Index, 0–1, higher = more vulnerable)

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

### SEVERE_WEATHER_CODES (WMO codes → is_severe_weather = 1)

```python
SEVERE_WEATHER_CODES = {51,53,55,61,63,65,71,73,75,77,80,81,82,85,86,95,96,99}
```

---

## Artifacts Reference

All artifacts live in `backend/artifacts/`. Praneel produces them on Databricks
and commits them via PR. Ashwin's server loads them at startup.

| File                             | Produced by                 | Available at | Used by                                           |
| -------------------------------- | --------------------------- | ------------ | ------------------------------------------------- |
| `demand_model.pkl`               | Notebook 05                 | ~Hour 10     | /api/heatmap, /api/staging                        |
| `drive_time_matrix.pkl`          | Notebook 06 (PRE-HACKATHON) | Before start | /api/counterfactual                               |
| `zone_baselines.parquet`         | Notebook 04                 | ~Hour 10     | /api/heatmap (zone_baseline_avg feature)          |
| `zone_stats.parquet`             | Notebook 04                 | ~Hour 10     | /api/historical, /api/breakdown                   |
| `counterfactual_summary.parquet` | Notebook 08                 | ~Hour 20     | /api/counterfactual                               |
| `counterfactual_raw.parquet`     | Notebook 08                 | ~Hour 20     | /api/counterfactual (by_borough, by_svi_quartile) |

**drive_time_matrix.pkl schema:**

```python
# dict with keys: (origin_key, destination_zone)
# origin_key is either a zone_code (e.g. 'B2') or station_id (e.g. 'EMS_M01')
# value is drive time in seconds
drive_time_matrix[('B2', 'B1')] = 312   # seconds
drive_time_matrix[('EMS_M01', 'M3')] = 180
```

**zone_baselines.parquet schema:**

```
columns: INCIDENT_DISPATCH_AREA, hour, dayofweek, zone_baseline_avg
```

**zone_stats.parquet schema:**

```
columns: INCIDENT_DISPATCH_AREA, BOROUGH, svi_score, avg_response_seconds,
         avg_travel_seconds, avg_dispatch_seconds, high_acuity_ratio,
         held_ratio, total_incidents
```

**counterfactual_summary.parquet schema:**

```
columns: hour, dayofweek, median_seconds_saved, pct_within_8min_static,
         pct_within_8min_staged, n_incidents
168 rows total (24 hours × 7 days)
```

---

## Environment Setup

### Backend

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env   # fill in DB credentials
uvicorn main:app --reload --port 8000
```

**backend/.env:**

```
DATABASE_URL=postgresql://pp_user:pp_pass@localhost:5432/firstwave
ARTIFACTS_DIR=./artifacts
```

### PostGIS (zone boundary geometries)

```bash
docker run --name firstwave-db \
  -e POSTGRES_DB=firstwave \
  -e POSTGRES_USER=pp_user \
  -e POSTGRES_PASSWORD=pp_pass \
  -p 5432:5432 \
  -d postgis/postgis:15-3.4

# Seed zone boundaries (run once):
python backend/scripts/seed_zone_boundaries.py
```

### Frontend

```bash
cd frontend
npm install
npm run dev   # runs on localhost:3000
```

**frontend/.env:**

```
VITE_MAPBOX_TOKEN=pk.eyJ1IjoiLi4u...   ← your token (public scopes only)
VITE_API_BASE_URL=http://localhost:8000
```

**Mapbox token scopes needed:** STYLES:TILES, STYLES:READ, FONTS:READ,
DATASETS:READ, VISION:READ. No secret scopes needed.

### Pipeline (local — runs on Ashwin's machine)

```bash
git checkout feat/pipeline
pip install -r pipeline/requirements.txt

# Download EMS CSV (~2GB):
# https://data.cityofnewyork.us/api/views/76xm-jjuj/rows.csv?accessType=DOWNLOAD

# Run in order:
python pipeline/06_osmnx_matrix.py &           # start first (30-60 min background)
python pipeline/01_ingest_clean.py --csv ~/Downloads/ems_raw.csv
python pipeline/02_weather_merge.py
python pipeline/03_spatial_join.py
python pipeline/04_aggregate.py
python pipeline/05_train_demand_model.py
python pipeline/07_staging_optimizer.py        # validation only
python pipeline/08_counterfactual_precompute.py
```

Intermediate parquets go to `pipeline/data/` (gitignored, ~500MB).
Artifacts are written directly to `backend/artifacts/`.

---

## Frontend Key Constants

### Mock Data Flag (frontend/src/constants.js)

```javascript
export const USE_MOCK_DATA = true; // ← flip to false at Hour 22 integration sprint
```

When `USE_MOCK_DATA = true`, all hooks return from `data/mock_api_responses.json`.
When `false`, all hooks call the real FastAPI endpoints.
**Never hard-code mock data inside components — always go through the hook.**

### Demo Presets

```javascript
export const DEMO_SCENARIOS = {
  friday_peak: { hour: 20, dow: 4, month: 10, weather: "none", ambulances: 5 },
  monday_quiet: { hour: 4, dow: 0, month: 10, weather: "none", ambulances: 5 },
  storm: { hour: 18, dow: 2, month: 11, weather: "heavy", ambulances: 7 },
};
```

### Choropleth Color Scale

```javascript
// normalized_intensity 0–1 → color
0.0 → '#00897B'   // teal    (low demand)
0.3 → '#FDD835'   // yellow
0.6 → '#FB8C00'   // orange
1.0 → '#C62828'   // red     (critical demand)
```

### Staging Coverage Circle

```javascript
coverage_radius_m = 3500; // ~8-minute drive in NYC urban conditions
fill_color = "rgba(66, 165, 245, 0.15)";
stroke_color = "rgba(66, 165, 245, 0.6)";
```

---

## Backend Key Constants

### SVI Defaults (fallback if zone_stats artifact not loaded)

```python
SVI_DEFAULTS = {
    'B1':0.94,'B2':0.89,'B3':0.87,'B4':0.72,'B5':0.68,
    'K1':0.52,'K2':0.58,'K3':0.82,'K4':0.84,'K5':0.79,'K6':0.60,'K7':0.45,
    'M1':0.31,'M2':0.18,'M3':0.15,'M4':0.20,'M5':0.12,
    'M6':0.14,'M7':0.73,'M8':0.65,'M9':0.61,
    'Q1':0.71,'Q2':0.44,'Q3':0.38,'Q4':0.55,'Q5':0.67,'Q6':0.48,'Q7':0.41,
    'S1':0.38,'S2':0.32,'S3':0.28
}
```

### API Response Time Budget

```
/api/heatmap        < 300ms   (XGBoost + PostGIS geometry query)
/api/staging        < 400ms   (includes heatmap + K-Means)
/api/counterfactual < 20ms    (Parquet DataFrame lookup)
/api/historical     < 20ms    (DataFrame lookup)
/api/breakdown      < 10ms    (pre-computed at startup)
```

### Fallback Behavior

If any artifact is missing at startup: endpoint returns mock data with
response header `X-Data-Source: mock`. Never crash — always serve something.

---

## Git Workflow

### Branches

```
main              → always demo-ready, branch-protected, require 1 PR approval
feat/frontend     → Vaibhav's branch
feat/backend      → Ashwin's branch
feat/pipeline     → Praneel's branch
```

### Worktrees (separate directories — no shared working tree)

```bash
~/firstwave-frontend/   ← Vaibhav
~/firstwave-backend/    ← Ashwin
~/firstwave-pipeline/   ← Praneel
~/firstwave/            ← main branch (read-only reference)
```

### Commit Message Format

```
feat: [description] — closes #[issue]
fix:  [description] — refs #[issue]
wip:  [description] — working on #[issue]
```

### PR Approval

Ansh is required reviewer on all PRs to main.
Ansh approves within 10 minutes — no code review needed, just process gate.

### Claude Code Automated PR Command

```
"Feature complete: [description]. Commit all changes in [module]/ with
message '[type]: [description] — closes #[issue]'. Push to feat/[branch].
Open a PR to main titled '[title]' with the [label] label."
```

---

## Group Chat Message Protocol

| Type           | Format                                                           |
| -------------- | ---------------------------------------------------------------- |
| Artifact ready | `[artifact] AVAILABLE: backend/artifacts/[filename]`             |
| Module ready   | `[module] READY: [what works]`                                   |
| Blocker        | `BLOCKED: [person] — [specific thing needed]`                    |
| Merge          | `MERGING feat/[branch] → main, PR #[N] open`                     |
| Board update   | `BOARD UPDATE (Hour [N]): ✓[closed] ⏳[in progress] ⚠️[blocked]` |

---

## Key Integration Checkpoints

| Hour   | Event                                  | Who          | Verifies                                       |
| ------ | -------------------------------------- | ------------ | ---------------------------------------------- |
| 0      | mock_api_responses.json committed      | Ashwin       | Vaibhav confirms field names match             |
| 0      | ems_stations.json committed            | Ansh         | Praneel copies to DBFS                         |
| 4      | All 5 mock endpoints live on :8000     | Ashwin       | `curl localhost:8000/api/heatmap` → 200        |
| 12     | Checkpoint 1: map renders on mock data | Vaibhav      | All 5 endpoints + choropleth visible           |
| ~10    | demand_model.pkl + parquets → PR       | Praneel      | Ashwin merges, hits POST /reload               |
| ~20    | counterfactual parquets → PR           | Praneel      | Ashwin merges, real impact panel numbers       |
| 22     | Checkpoint 2: integration sprint       | All          | USE_MOCK_DATA=false, all 5 endpoints real      |
| 22     | Endpoint test all pass                 | Praneel runs | All < 500ms, correct shapes                    |
| 26     | Demo video recorded                    | Vaibhav/Ansh | Clean take, < 2 minutes                        |
| 30     | Full pitch rehearsal                   | All          | Timed run, 5 minutes flat                      |
| 8:30AM | Final submission check                 | Ansh         | GitHub public, video public, Devpost published |

---

## Demo Narrative Reference

**The single most important stat:** Bronx average EMS response = 638 seconds (10.6 min).
Clinical target = 8 min (480 seconds). Gap = 158 seconds = 2.6 minutes over threshold.

**The pitch core:**
"Not a lack of ambulances — wrong placement. We pre-position idle units in the
mathematical center of predicted demand, before the wave hits."

**Key transition in demo:**
Monday 4AM (calm map, light colors) → Friday 8PM (Bronx + Brooklyn go red).
This is the visual that makes the pitch — the slider movement IS the argument.

**SafetyKit framing:**
"Prevents harm, reduces risk, helps people respond safely in the moments that
matter most." Every minute of delayed cardiac arrest response = ~10% drop in
survival probability. Bronx at 10.6 min average means patients are already past
the point where survival probability drops ~65% vs a 4-minute response.

---

## External Services & Keys

| Service       | Purpose                | Sign up                                   |
| ------------- | ---------------------- | ----------------------------------------- |
| Mapbox        | Map tiles + styles     | mapbox.com (free tier: 50k loads/month)   |
| NYC Open Data | EMS dataset            | data.cityofnewyork.us (free app token)    |
| Open-Meteo    | Historical weather API | archive-api.open-meteo.com (free, no key) |
| Databricks CE | Spark + MLflow         | community.cloud.databricks.com (free)     |

---

## Full Tech Stack

| Layer    | Technology            | Version            |
| -------- | --------------------- | ------------------ |
| ML       | XGBoost               | 2.0.3              |
| ML       | scikit-learn          | 1.4.1              |
| Spatial  | geopandas             | 0.14.3             |
| Spatial  | OSMnx                 | 1.9.1              |
| Spatial  | shapely               | 2.0.3              |
| Backend  | FastAPI               | 0.110.0            |
| Backend  | Python                | 3.11               |
| Database | PostgreSQL + PostGIS  | 15 + 3.4           |
| Frontend | React                 | 18.2.0             |
| Frontend | react-map-gl          | 7.1.7              |
| Frontend | Mapbox GL JS          | 3.3.0              |
| Frontend | Plotly.js             | 2.30.0             |
| Pipeline | DuckDB                | 0.10+              |
| Pipeline | Python (local)        | 3.11               |

---

_This file is read by Claude Code at the start of every session via /init._
_It is also read by GitHub Copilot as an open tab in VS Code._
_Keep it accurate. When in doubt, add to it — never delete from it._
