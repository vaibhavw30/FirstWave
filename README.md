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

**Key capabilities:**

- **Demand forecasting** — 20-feature XGBoost model predicts incident count per dispatch zone per hour
- **Borough-fair staging** — weighted K-Means guarantees minimum coverage per borough before demand-proportional allocation
- **Counterfactual engine** — weather-adjusted comparison of static vs. staged response times across all 31 zones
- **AI Dispatcher** — GPT-4o-mini natural language interface for scenario exploration ("What about a Friday night storm?")
- **Equity analysis** — SVI overlay and quartile breakdown showing impact on NYC's most vulnerable communities
- **Watch the Wave** — animated 24-hour playback of demand patterns across the city

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
We ingested 28.7M rows of NYC EMS dispatch data (Socrata Open Data), applied 9 quality filters to get 5.6M clean training incidents (2019, 2021, 2022) and 1.5M holdout incidents (2023). We excluded 2020 due to COVID anomalies. Weather data comes from the Open-Meteo historical archive API. The pipeline runs locally via DuckDB.

### 2. Demand Forecasting (XGBoost)
An XGBoost regressor predicts **incident count per dispatch zone per hour**. Features include cyclical time encodings (sine/cosine for hour, day-of-week, month), weather conditions, CDC Social Vulnerability Index scores, zone-level historical baselines, heat emergency flags, and infrastructure disruption indices.

**20 features. Most important: `zone_baseline_avg` (47% feature importance)**

- Training RMSE: 6.0 incidents/zone/hour on 2023 holdout
- Model sees Friday 8PM Bronx at ~59 predicted incidents — correctly identifying it as peak demand

### 3. Borough-Fair Staging Optimizer (Weighted K-Means)
Takes the demand forecast for all 31 zones and runs a two-phase allocation: first guarantees 1 staging point per borough, then distributes extras proportionally to demand. Within each borough, demand-weighted K-Means finds optimal staging coordinates. Each staged location covers a ~3,500m radius (8-minute urban drive).

### 4. Counterfactual Engine
Compares actual historical response times against simulated drive times from optimally staged zones — with weather adjustment (precipitation and wind increase travel times). This gives an honest, data-backed answer to: *"How much faster would we have gotten there if we'd pre-staged?"*

Weather travel factor: `1.0 + 0.012 * precipitation_mm + 0.002 * max(0, windspeed - 15)`

### 5. Live Dashboard
Dispatchers see a live choropleth map of predicted demand intensity, staging pin locations, EMS station overlay, and an impact panel showing coverage improvement and time saved — all updating in real time as they adjust the hour, day, weather, and ambulance count.

### 6. AI Dispatcher
A GPT-4o-mini-powered chat interface lets dispatchers explore scenarios in natural language. "What happens during a Friday night Yankees game?" — the AI generates a situational briefing and can adjust the map controls automatically. Includes auto-briefing that updates whenever the demand forecast changes.

### 7. Equity Analysis
A ZIP-level Social Vulnerability Index overlay visualizes community vulnerability across NYC with a purple gradient. The impact panel breaks down response time savings by SVI quartile, showing that the most vulnerable communities (Q4) receive the largest benefit — 299 seconds saved.

---

## The Demo Flow (for pitch)

**Start on Monday 4AM** — map is dark teal/green, quiet across all boroughs.

**Hit "Watch the Wave"** — the hour slider auto-plays 0→23 at 1.5-second intervals. Watch demand build through the day. By 8PM, Bronx and Brooklyn burst red.

**Pause on Friday 8PM** — point to the staging pins. 5 ambulances pre-positioned at the mathematical center of predicted demand, covering 22+ zones with overlapping 8-minute radiuses.

**Show the impact panel** — 64.7% → 86.0%, 3 min 19 sec saved.

**Toggle the equity layer** — purple SVI overlay shows vulnerability distribution. Q4 (most vulnerable) gets the most benefit. The algorithm isn't just faster, it's fairer.

**Toggle FDNY stations** — note the gap between fixed station placement and actual demand clustering.

**Open the AI Dispatcher** — ask "Heavy storm Tuesday evening?" Watch the AI brief and adjust the map. Ask "Quiet Monday 4AM" — map shifts automatically.

**Switch to storm weather** — response times increase, more zones turn orange/red. FirstWave accounts for weather in both forecasting and response time estimation.

**Click a zone** — show zone detail with 24-hour demand curve, before/after response times, SVI score.

**The closing line:** *"The Bronx at 10.6 minutes average isn't a resource problem. It's a placement problem. FirstWave solves the placement problem."*

---

## Tech Stack

| Layer | Technology |
|---|---|
| ML — Demand Forecasting | XGBoost 2.0, scikit-learn 1.4 |
| ML — Staging Optimizer | Borough-Fair Weighted K-Means (scikit-learn) |
| ML — AI Dispatcher | OpenAI GPT-4o-mini |
| Spatial Routing | OSMnx 1.9 + NetworkX (NYC road network, 1,891 zone pairs) |
| Data Processing | DuckDB, pandas 2.2, pyarrow 16 |
| Backend API | FastAPI 0.110, Python 3.11 |
| Database | PostgreSQL 15 + PostGIS 3.4 (zone boundary geometries) |
| Frontend | React 19.2, Mapbox GL JS 3.18, react-map-gl 7.1 |
| Data Fetching | TanStack React Query 5.90 |
| Charts | Plotly.js 3.4 |
| Styling | Tailwind CSS 4.2 |
| Build Tool | Vite 7.3 |

---

## Architecture

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
         |
         v
[ FastAPI Backend ]  <-- artifacts loaded at startup, <300ms per request
    GET  /api/heatmap          -> 31-zone demand forecast GeoJSON
    GET  /api/staging          -> K optimal staging locations GeoJSON
    GET  /api/counterfactual   -> coverage + time saved + weather-adjusted
    GET  /api/historical/:zone -> per-zone response time history
    GET  /api/breakdown        -> borough-level performance breakdown
    GET  /api/stations         -> FDNY EMS station locations GeoJSON
    POST /api/ai               -> GPT-4o-mini dispatcher briefing/chat
         |
         v
[ React 19 + Mapbox GL JS 3.18 Dashboard ]
    Choropleth demand heatmap (31 dispatch zones)
    Staging pins with 8-min coverage circles
    EMS station markers overlay
    Equity/SVI ZIP-level overlay
    AI Dispatcher chat panel
    Watch the Wave 24-hour animation
    Zone detail panels + impact metrics
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
cd backend
pip install -r requirements.txt
```

Create `backend/.env`:
```
DATABASE_URL=postgresql://pp_user:pp_pass@localhost:5432/firstwave
ARTIFACTS_DIR=./artifacts
OPENAI_API_KEY=sk-...  # optional, for AI Dispatcher
```

Start the server:
```bash
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

Verify: `curl http://127.0.0.1:8000/health`

### 3. Start the Frontend
```bash
cd frontend
npm install
```

Create `frontend/.env`:
```
VITE_MAPBOX_TOKEN=pk.eyJ1IjoiLi4u...
VITE_API_BASE_URL=http://localhost:8000
```

Start the dev server:
```bash
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
| **Storm** | 6 PM | Wednesday | Weather amplifies demand + response times. More zones turn orange/red. Weather travel factor increases staged/static times. |

---

## Repo Structure

```
firstwave/
├── backend/               FastAPI server + ML inference
│   ├── main.py            App startup, artifact loading, CORS
│   ├── routers/           7 API endpoints (heatmap, staging, counterfactual,
│   │                      historical, breakdown, stations, ai)
│   ├── models/            XGBoost inference + borough-fair K-Means staging
│   ├── artifacts/         Pre-computed ML artifacts (committed)
│   └── scripts/           PostGIS seeding
├── frontend/              React 19 + Mapbox GL JS 3.18
│   └── src/
│       ├── components/
│       │   ├── Map/       MapContainer, Choropleth, StagingPins, StationLayer,
│       │   │              EquityLayer, ZoneTooltip, ZoneDetailPanel
│       │   ├── Controls/  ControlPanel, TimeSlider, DayPicker, WeatherSelector,
│       │   │              AmbulanceCount, LayerToggle
│       │   ├── Impact/    ImpactPanel, CoverageBars, ResponseHistogram,
│       │   │              EquityChart, OverlayPanel
│       │   └── Chat/      AiPanel (AI Dispatcher)
│       └── hooks/         useHeatmap, useStaging, useCounterfactual,
│                          useZoneHistory, useStations
├── pipeline/              DuckDB + pandas ML pipeline (8 scripts)
│   └── test_artifacts.py  41-check artifact validation suite
├── data/
│   ├── ems_stations.json  FDNY EMS station locations
│   └── zone_centroids.json 31 dispatch zone centroids
├── CLAUDE.md              Full technical spec and data dictionary
├── PRD_v3.md              Product Requirements Document
└── devpost_strategy.md    Devpost submission content
```
