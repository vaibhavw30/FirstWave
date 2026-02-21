# FirstWave — Predictive EMS Staging Dashboard

> **GT Hacklytics 2026** · Healthcare Track + SafetyKit: Best AI for Human Safety

---

## The Problem

Every minute of delayed cardiac arrest response reduces survival probability by roughly 10%. The NYC EMS system responds to over 1.5 million calls per year — yet the average response time in the Bronx is **10.6 minutes**, well past the 8-minute clinical survival threshold.

The issue isn't a lack of ambulances. It's **wrong placement**.

Ambulances sit idle at fixed stations until a 911 call comes in. By the time dispatch happens, the nearest unit is often across the borough. In a city where demand spikes are entirely predictable — Friday evenings in the Bronx, summer weekends in Brooklyn — we keep reacting instead of anticipating.

---

## The Solution

**FirstWave** is a real-time predictive staging dashboard for NYC EMS dispatchers. It uses 5 years of historical 911 incident data, live weather, and temporal demand signals to forecast where the next hour's emergency calls will cluster — then recommends optimal pre-positioning locations for idle ambulances **before the wave hits**.

Like a surfer paddling out ahead of the wave.

---

## Key Results

All numbers computed from **28.7 million real NYC EMS incidents (2019–2023)**:

| Metric | Without FirstWave | With FirstWave |
|---|---|---|
| % of incidents within 8-min clinical window | 64.7% | **86.0%** |
| Median response time saved | — | **3 min 19 sec** |
| Bronx coverage (worst borough) | 48.2% | **96.7%** |
| Most vulnerable communities (SVI Q4) savings | — | **299 seconds saved** |

The equity finding is striking: FirstWave disproportionately helps the city's most vulnerable neighborhoods because they sit in the highest-demand zones where staged ambulances are placed.

---

## How It Works

### 1. Data Pipeline
We ingested 28.7M rows of NYC EMS dispatch data (Socrata Open Data), applied 9 quality filters to get 5.6M clean training incidents (2019, 2021, 2022) and 1.5M holdout incidents (2023). We excluded 2020 due to COVID anomalies. Weather data comes from the Open-Meteo historical archive API.

### 2. Demand Forecasting (Model A — XGBoost)
An XGBoost regressor trained to predict **incident count per dispatch zone per hour**. Features include cyclical time encodings (sine/cosine for hour, day-of-week, month), weather conditions, CDC Social Vulnerability Index scores, and zone-level historical baselines. Trained on 5.6M incidents across 31 dispatch zones.

**15 features. Most important: `zone_baseline_avg` (47% feature importance)**

- Training RMSE: 6.0 incidents/zone/hour on 2023 holdout
- Model sees Friday 8PM Bronx at ~59 predicted incidents — correctly identifying it as peak demand

### 3. Staging Optimizer (Model B — Weighted K-Means)
Takes the demand forecast for all 31 zones, weights geographic centroids by predicted call volume, and runs K-Means to find the `K` staging locations that minimize weighted distance to demand. Each staged location covers a ~3,500m radius (8-minute urban drive).

### 4. Counterfactual Engine
Compares actual historical response times (dispatch lag + travel) against simulated drive times from optimally staged zones — computed across the full 5-year dataset. This gives an honest, data-backed answer to: *"How much faster would we have gotten there if we'd pre-staged?"*

### 5. Live Dashboard
Dispatchers see a live choropleth map of predicted demand intensity, staging pin locations, and an impact panel showing coverage improvement and time saved — all updating in real time as they adjust the hour, day, weather, and ambulance count.

---

## The Demo Flow (for pitch)

**Start on Monday 4AM** — map is dark teal/green, quiet across all boroughs.

**Drag the slider to Friday 8PM** — the Bronx and Brooklyn burst red. This visual transition IS the argument. Demand is predictable. We just haven't been acting on it.

**Point to the staging pins** — 5 ambulances pre-positioned at the mathematical center of predicted demand, covering 22+ zones with overlapping 8-minute radiuses.

**Show the impact panel** — 64.7% → 86.0%, 3 min 19 sec saved.

**Show the equity chart** — Q4 (most vulnerable) gets the most benefit. The algorithm isn't just faster, it's fairer.

**The closing line:** *"The Bronx at 10.6 minutes average isn't a resource problem. It's a placement problem. FirstWave solves the placement problem."*

---

## Tech Stack

| Layer | Technology |
|---|---|
| ML — Demand Forecasting | XGBoost 3.x, scikit-learn |
| ML — Staging Optimizer | Weighted K-Means (scikit-learn) |
| Spatial Routing | OSMnx 2.1 + NetworkX (NYC road network, 1,891 zone pairs) |
| Data Processing | DuckDB 1.4, pandas, pyarrow |
| Backend API | FastAPI 0.110, Python 3.11 |
| Database | PostgreSQL 15 + PostGIS 3.4 (zone boundary geometries) |
| Frontend | React 18, Mapbox GL JS 3.3, react-map-gl 7, Plotly.js |
| Build Tool | Vite 7 |

---

## Architecture

```
[ 28.7M NYC EMS Incidents ]
         │
         ▼
[ DuckDB Pipeline ] ─── quality filters, weather merge, SVI join
         │
         ├─ zone_baselines.parquet  (rolling demand averages per zone/hour/day)
         ├─ zone_stats.parquet      (per-zone historical response stats)
         │
         ▼
[ XGBoost Demand Model ] ─── 15 features, trained 2019/21/22, validated 2023
         │
         ├─ demand_model.pkl
         │
         ▼
[ FastAPI Backend ]  ←── artifacts loaded at startup, <300ms per request
    /api/heatmap          → 31-zone demand forecast GeoJSON
    /api/staging          → K optimal staging locations GeoJSON
    /api/counterfactual   → coverage improvement + time saved stats
    /api/historical/:zone → per-zone response time history
    /api/breakdown        → borough-level performance breakdown
         │
         ▼
[ React + Mapbox Dashboard ]
    Choropleth demand map
    Staging pins with 8-min coverage circles
    Zone detail panels
    Impact metrics panel
    Equity chart
```

---

## Dispatch Zones

31 clean dispatch zones across 5 boroughs:

| Borough | Zones |
|---|---|
| Bronx | B1–B5 |
| Brooklyn | K1–K7 |
| Manhattan | M1–M9 |
| Queens | Q1–Q7 |
| Staten Island | S1–S3 |

---

## Data Sources

| Source | What we used |
|---|---|
| NYC Open Data — EMS Incident Dispatch Data | 28.7M rows, 2019–2023 |
| Open-Meteo Historical Weather API | Hourly temperature, precipitation, windspeed for NYC |
| CDC Social Vulnerability Index (SVI) | RPL_THEMES score per census tract, aggregated to dispatch zone |
| OpenStreetMap (via OSMnx) | NYC road network for drive-time matrix computation |

All data sources are free and publicly available. No proprietary data.

---

## Why the 8-Minute Threshold?

The 8-minute mark (480 seconds) is the clinical standard for EMS response. For cardiac arrest:
- Response within 4 minutes: ~50% survival rate
- Response within 8 minutes: ~25% survival rate
- Response at 10+ minutes (Bronx average): ~10% survival rate

Every borough except Staten Island is currently averaging over this threshold. FirstWave is designed specifically to close that gap.

---

## Team

| Name | Role | Module |
|---|---|---|
| Ashwin Vijayakumar | Backend Lead | FastAPI server, ML inference, PostGIS |
| Vaibhav | Frontend Lead + Integration | React dashboard, Mapbox, all UI components |
| Praneel | Pipeline Lead | DuckDB data pipeline, XGBoost training, counterfactual engine |
| Ansh | PM + Demo | Devpost, pitch deck, demo video, station data |

**Hackathon:** GT Hacklytics 2026
**Tracks:** Healthcare (primary) · SafetyKit: Best AI for Human Safety (secondary)

---

## Running the App

### Prerequisites
- Python 3.11+
- Node.js 18+
- Docker (for PostGIS)

### 1. Start PostGIS
```bash
docker run --name firstwave-db \
  -e POSTGRES_DB=firstwave \
  -e POSTGRES_USER=pp_user \
  -e POSTGRES_PASSWORD=pp_pass \
  -p 5432:5432 \
  -d postgis/postgis:15-3.4

python3 backend/scripts/seed_zone_boundaries.py
```

### 2. Start the Backend
```bash
pip install -r backend/requirements.txt
uvicorn backend.main:app --host 127.0.0.1 --port 8001 --reload
```

Verify: `curl http://127.0.0.1:8001/health`
Expected: all 5 artifacts show `true`

### 3. Start the Frontend
```bash
cd frontend
npm install
npm run dev   # runs on localhost:3000
```

### 4. Open the Dashboard
`http://localhost:3000`

---

## Demo Scenarios

| Scenario | Hour | Day | What to show |
|---|---|---|---|
| **Friday Peak** | 8 PM | Friday | Bronx + Brooklyn go red. Staging pins cluster in high-demand areas. |
| **Monday Quiet** | 4 AM | Monday | Map goes calm. Contrast with Friday shows demand is predictable. |
| **Storm** | 6 PM | Wednesday | Weather amplifies demand. More zones turn orange/red. |

---

## Repo Structure

```
firstwave/
├── backend/               FastAPI server + ML inference
│   ├── main.py            App startup, artifact loading, CORS
│   ├── routers/           5 API endpoints
│   ├── models/            XGBoost inference + K-Means staging
│   ├── artifacts/         5 pre-computed ML artifacts (committed)
│   └── scripts/           PostGIS seeding
├── frontend/              React 18 + Mapbox GL JS
│   └── src/
│       ├── components/    Map, Controls, Impact panels
│       └── hooks/         API data fetching hooks
├── pipeline/              DuckDB + pandas ML pipeline (8 scripts)
│   └── test_artifacts.py  41-check artifact validation suite
├── data/
│   ├── ems_stations.json  30 FDNY EMS station locations
│   └── zone_centroids.json 31 dispatch zone centroids
└── CLAUDE.md              Full technical spec and data dictionary
```
