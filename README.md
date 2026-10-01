# FirstWave — Predictive EMS Staging Dashboard

> **GT Hacklytics 2026** · Healthcare Track + SafetyKit: Best AI for Human Safety
>
> *"Like a surfer paddling out ahead of the wave."*

---

## The Problem

New York City EMS responds to over **1.5 million 911 calls per year**. Despite that volume, ambulance deployment is still largely reactive — units sit at fixed stations until a call arrives, then race across the borough.

The result:

| Borough | Avg Response | vs. 8-min Clinical Threshold |
|---|---|---|
| Bronx | **10.6 min** | +33% over threshold |
| Manhattan | 10.5 min | +31% over threshold |
| Brooklyn | 9.4 min | +17% over threshold |
| Queens | 9.0 min | +12% over threshold |
| Staten Island | 8.0 min | At threshold |

For cardiac arrest, **every minute past 8 minutes reduces survival probability by ~10%**. The Bronx at 10.6 minutes means patients are already in a range where survival has dropped ~65% compared to a 4-minute response.

The issue isn't a shortage of ambulances. **It's wrong placement.**

Emergency demand is highly predictable — Friday evenings in the Bronx, summer weekends in Brooklyn — but the system doesn't act on those patterns ahead of time.

---

## The Solution

**FirstWave** is a predictive staging dashboard for NYC EMS dispatchers. It forecasts where 911 calls will cluster over the next hour using historical incident patterns, weather, and temporal demand signals — then recommends optimal pre-positioning locations for idle ambulances **before those calls arrive**.

---

## Key Results

Simulated on **25,200 Priority 1–2 calls from 2025**, a year the model never trained on (up to 150 calls sampled for each of the 168 hour-of-week slots, with results weighted back to each slot's real 2025 call volume), with **5 staged ambulances** (the dashboard default) placed from each call's own hour:

| Metric | Without FirstWave | With FirstWave |
|---|---|---|
| Calls reached within 8 minutes | 56.7% | **66.8%** |
| Calls whose zone gets a closer unit | — | **30.5%** |
| Response time saved, mean (median) | — | **81 s** (0 s) |
| Bronx within 8 minutes | 48.9% | **61.3%** |

**How to read these numbers.** "Without" is each call's real recorded response time (dispatch plus travel). "With" keeps the same dispatch time and shortens only the travel part, by how much closer the nearest staged ambulance is than the nearest station on the road network. Staged ambulances are extra to the stations, so no call gets slower. The median saving is 0 s because only about 30.5% of calls are in a zone that a staged unit reaches faster than the nearest station, so most calls are unchanged; the within-8-minute share and the mean are the meaningful measures.

**Where the ambulances go.** Sites are chosen to reach as many predicted calls as possible within 8 minutes. They mostly fill the biggest gaps in station coverage; the hour's forecast adjusts them at the margin. Across 8,260 simulated hours there were 11 distinct 5-site layouts, and the most common one (B2, K3, M3, Q6, S1) was used in 54% of hours.

**Equity.** Seconds saved by social-vulnerability quartile, mean (median): Q1 95 s (0), Q2 97 s (0), Q3 32 s (0), Q4 101 s (0). The gain is not monotonic in vulnerability: the most vulnerable quartile (Q4) gains the most on average, but Q3 gains far less than Q1–Q2, because placement follows station-coverage gaps, not vulnerability.

**More ambulances.** Same calls, sites re-placed each hour: 3 → 64.6%, 5 → 66.8%, 7 → 70.9%, 10 → 74.4% within 8 minutes.

> **Assumptions.** (1) Drive-time ratios come from free-flow road times (OSMnx). They scale each call's real travel time, so real traffic is kept, but the ratio itself ignores congestion. (2) "Without" assumes the nearest station's unit would have responded. (3) Staged units are always free (no queueing). (4) Travel inside a zone is estimated as half the drive from the nearest neighbouring zone centre.

Method: `pipeline/08_counterfactual_precompute.py`.

---

## Features

### Demand Heatmap + Historical Replay
A live map shades all 31 NYC dispatch zones by predicted calls per hour, relative to the busiest zone that hour: teal (low) through yellow/orange to red (the hour's peak). Pick any date from 2025-01-01 to 2026-06-30 and an hour. The model forecasts that hour from the real call history leading up to it, and the zone detail panel shows how many calls actually came in.

Weather defaults to **Actual**, the replayed hour's recorded weather. Clear, Light Rain, and Heavy Storm override it for a what-if. The forecast updates as you change date, hour, weather, or ambulance count.

### Watch the Wave ▶
Hit the play button next to the hour slider and watch the selected day's demand animate hour by hour at 1.5-second intervals. Hotspots shift through the day and total demand swings more than 2× (95 predicted calls citywide on Monday 4AM vs 220 on Friday 8PM). That's the core argument: demand is predictable, so staging should be proactive.

### Coverage-Optimal Staging
Places K ambulances at zone centres to reach as many predicted calls as possible within 8 minutes:
- Uses the road-network drive-time matrix and the 30 fixed EMS stations: a staged unit only helps a zone where it is closer than that zone's nearest station
- Solved exactly (a mixed-integer program), not approximated; ties go to the lower average response time
- With 5 or more ambulances, every borough gets at least one (equity constraint)
- Each pin's tooltip lists the zones it actually improves; the circle is a fixed 3,500 m display radius

### Counterfactual Impact Engine
The impact panel answers *how much faster would we have gotten there?* for the selected hour and ambulance count. For each zone:
- **Before** is the zone's historical average dispatch plus travel time.
- **After** keeps the same dispatch time and scales travel by how much closer the nearest staging site is than the nearest station.

Travel is slowed in bad weather by a factor of `1.0 + 0.012 × precip + 0.002 × max(0, wind − 15)`. The headline [Key Results](#key-results) come from a separate call-by-call simulation (see [Counterfactual Engine](#counterfactual-engine)).

### AI Dispatcher
A GPT-4o-mini-powered panel in the top-right corner of the dashboard. Two modes:
- **Auto-briefing:** Generates a 3-sentence operational summary every time the map updates (1.5s debounce). Tells dispatchers which zone has peak demand, what the coverage improvement is, and one concrete recommendation.
- **Interactive chat:** Describe any scenario in natural language. "Yankees game Friday night?" The AI responds and sets the hour and weekday for you; the replay date moves to that weekday in the same week. If the map changes, an **↩ Undo** button appears in the chat to revert.

### Equity / SVI Layer
A ZIP-level Social Vulnerability Index overlay in a purple gradient (transparent → dark purple for SVI 0→1). The impact panel breaks down estimated time savings by SVI quartile, so dispatchers can see who benefits; placement follows station-coverage gaps rather than vulnerability, so the gain is uneven across quartiles.

### FDNY Stations Overlay
Toggle on 30 FDNY EMS station locations as grey markers on the map. Hover for station name, borough, and address. The spatial gap between fixed station locations and where demand actually concentrates is immediately visible.

### Zone Detail Panel
Click any zone on the map to open a detail panel with its 24-hour demand curve, historical response time decomposition (dispatch vs. travel), SVI score, before/after response times, and acuity breakdown. In replay it also shows predicted vs actual calls for the selected hour.

---

## Architecture

```
[ NYC EMS Incident Dispatch Data — 7.2M incidents used, Dec 2021 → Jun 2026 ]
[ Open-Meteo hourly weather ] [ NYC permitted events ] [ NYC holiday + school calendar ]
         |
         v
[ DuckDB Pipeline ] — zone/borough/indicator filters, gap-free zone × hour grid, lag features
         |
         +-- demand_model.pkl           28-feature XGBoost (Poisson) regressor
         +-- model_metrics.json         splits, test metrics, deployment-gate record
         +-- zone_baselines.parquet     mean calls/hour per (zone, hour, weekday), 2022–2024
         +-- zone_stats.parquet         per-zone response times, SVI, acuity, held ratio
         +-- hourly_counts.parquet      real calls per zone-hour (lag features + replay "actual")
         +-- calendar_daily.parquet     holiday / school-day / major-event flags per day
         +-- weather_hourly.parquet     real weather for every replayable hour
         +-- drive_time_matrix.pkl      OSMnx shortest paths, 1,891 origin → zone pairs
         +-- counterfactual_*.parquet   call-level simulation, 168 (hour × weekday) bins
         |
         v
[ FastAPI Backend ]  — artifacts loaded at startup, hot-reloadable
    GET  /api/heatmap           31-zone forecast GeoJSON (+ actual calls when replaying a date)
    GET  /api/staging           K coverage-optimal staging locations GeoJSON
    GET  /api/counterfactual    coverage + time saved (median and mean) + by_borough + by_svi + by_zone
    GET  /api/historical/:zone  per-zone 24-hour demand + response stats
    GET  /api/breakdown         borough-level performance breakdown
    GET  /api/stations          FDNY EMS station locations GeoJSON
    POST /api/ai                GPT-4o-mini auto-briefing / scenario chat
    GET  /health                artifact load status
    POST /reload                hot-reload artifacts without restart
         |
         v
[ React 19 + Mapbox GL JS 3.18 Dashboard ]
    Choropleth demand heatmap (31 dispatch zones, teal → red)
    Staging pins with fixed 3,500 m display circles
    Watch the Wave animation (24-hour playback, 1.5s/step)
    FDNY stations overlay (grey markers, hover tooltips)
    Equity / SVI ZIP-level overlay (purple gradient)
    AI Dispatcher panel (auto-briefing + interactive chat + undo)
    Zone detail panel (click any zone; predicted vs actual in replay)
    Impact metrics panel (coverage bars + histogram + equity chart)
    Control panel (hour slider, replay date, weather, ambulance count)
```

`/api/heatmap`, `/api/staging`, and `/api/counterfactual` take an optional `date=YYYY-MM-DD` (2025-01-01 → 2026-06-30). Omit the weather parameters to replay that hour's real weather; pass any of them for a what-if.

---

## Machine Learning

### Model A — XGBoost Demand Forecaster

**Target:** `incident_count`, calls per dispatch zone per hour. One row per (zone, hour), zero-call hours included.
**Train:** 2022-01 → 2024-09 · **Early stopping:** Q4 2024 · **Test:** 2025 · **Recent check:** 2026 H1
**Objective:** `count:poisson` (chosen over squared error on the Q4 2024 split)

| 2025 test set | RMSE | MAE |
|---|---|---|
| **FirstWave model (with lag features)** | **2.525** | **1.910** |
| Same model without lag features | 2.538 | 1.917 |
| Zone average for that hour and weekday | 2.558 | 1.928 |
| Same hour last week | 3.569 | 2.658 |

Calls arrive randomly, so even a perfect model has an RMSE of about 2.4 at this level of detail (the Poisson noise floor).

**Training setup:** gradient-boosted trees, `max_depth=6`, `learning_rate=0.05`, `subsample=0.8`, `colsample_bytree=0.8`, `tree_method="hist"`. Up to 2,000 trees; early stopping (patience 50) kept **319**. Full details and the deployment-gate decision are in `backend/artifacts/model_metrics.json` and `CLAUDE.md`.

**28 features** (canonical list: `pipeline/fw_config.py`):

| Group | Features |
|---|---|
| Long-run baseline | `zone_baseline_avg`: mean calls per hour for this (zone, hour, weekday) over the 2022–2024 training years |
| Recent history | `lag_1h`, `lag_2h`, `lag_3h`, `lag_24h`, `lag_168h`, `roll_7d_same_hour` (same hour, last 7 days), `roll_4w_same_hour_dow` (same hour and weekday, last 4 weeks) |
| Time | `hour_sin/cos`, `dow_sin/cos`, `month_sin/cos` (cyclical encodings), `is_weekend` |
| Weather | `temperature_2m`, `precipitation`, `windspeed_10m`, `is_severe_weather`, `is_extreme_heat` (≥ 35 °C), `is_heat_emergency` (≥ 35 °C, or ≥ 32.2 °C in the prior 24 h), `subway_disruption_idx` (constant placeholder) |
| Calendar | `is_holiday`, `is_school_day`, `is_major_event` (per borough, NYC permitted events) |
| Zone character | `svi_score` (CDC SVI), `high_acuity_ratio`, `held_ratio` |

**What drives predictions: SHAP feature importance**

![Mean absolute SHAP value per feature on the 2025 test set](docs/images/shap_importance.png)

These are exact TreeSHAP values over all 271,560 zone-hours in 2025. The model predicts in log space, so a SHAP value *v* multiplies the prediction by *e^v*.

- **The long-run baseline dominates (72%).** "What's normal for this zone at this hour on this weekday" sets the prediction, typically scaling the city-wide average of 5.8 calls up or down by about 1.56×.
- **Recent history adjusts it (17%).** `roll_7d_same_hour` catches zones running hotter or colder than their long-run norm.
- **Weather, time, and calendar add small corrections (~10% together).**
- **Three features are never used:** `is_extreme_heat`, `is_major_event`, and `subway_disruption_idx`.

`zone_baseline_avg` and `roll_7d_same_hour` are highly correlated (r = 0.94), so how credit is split between them is somewhat arbitrary; read them together as "how busy this zone normally is." Regenerate the chart with `python pipeline/shap_importance.py`.

### Model B — Coverage-Optimal Staging Optimizer

`backend/models/staging_optimizer.py`, shared by `/api/staging`, `/api/counterfactual`, and pipeline scripts 07–08. The travel model is `backend/models/coverage_model.py`.

For zone z and candidate site j (the 31 zone centres), the travel multiplier is `r(z, j) = min(station_drive(z), site_drive(z, j)) / station_drive(z)`. Both drives come from the OSMnx matrix plus a within-zone term: half the drive from the nearest neighbouring zone centre. A zone's expected response is `dispatch + travel × weather × r`, and its chance of an 8-minute response comes from a lognormal (CV 0.95) around that mean.

The optimizer picks K sites that maximise predicted calls reached within 8 minutes (tie-break: lower mean response), with at least one site per borough when K ≥ 5. It is solved exactly as a mixed-integer program with SciPy's HiGHS solver in a few milliseconds, and tests check it against brute force for K = 1–4.

Because the stations are part of the model, the best sites are set mostly by gaps in station coverage; the hour's forecast moves them only at the margin.

**Display radius:** 3,500 m (map circle only; placement uses drive times)

### Counterfactual Engine

Two versions answer "how much faster?":

**Call-level simulation** (`pipeline/08_counterfactual_precompute.py`). This produces the [Key Results](#key-results).
1. Take 2025 Priority 1–2 calls with valid response times, up to 150 per (hour, weekday) slot.
2. For each call's actual hour, forecast all 31 zones using that hour's real weather and place 5 staging sites with the same optimizer and inputs as the dashboard (`backend/tests/test_staging_parity.py` keeps them identical).
3. **Before** is the call's recorded response time. **After** keeps its dispatch time and scales its recorded travel time by `r(zone, nearest open site)`. Calls with a missing or invalid travel time (under 0.1%) are left out.
4. Results are saved per call (`counterfactual_raw`) and per slot (`counterfactual_summary`, 168 rows).
5. The script also logs results for 3, 7, and 10 ambulances.

**Live estimate** (`/api/counterfactual`, what the dashboard shows). This uses the same forecast, optimizer, and travel model as the map, for the selected date, hour, weather, and ambulance count. Per zone:
- **Before** = average dispatch + weather-adjusted average travel.
- **After** = the same dispatch + that travel × `r(zone, nearest open site)`.
- **% within 8 minutes** comes from a lognormal CDF (CV = 0.95) around each zone's mean. Results are demand-weighted by borough, SVI quartile, and zone.

The live estimate works from zone averages and the lognormal; the call-level simulation uses real per-call times. They share placement and travel model, so they are close but not identical.

The response carries both `median_seconds_saved` and `mean_seconds_saved` (top level), and `median_saved_sec` and `mean_saved_sec` in each `by_borough` and `by_svi_quartile` entry. Most calls are in zones no staged unit improves, so the medians are 0 for most slots; the means are the informative figure.

If the model or its history artifacts are missing, the endpoint falls back to the precomputed simulation.

---

## Data Sources

| Source | What We Used |
|---|---|
| [NYC Open Data — EMS Incident Dispatch Data](https://data.cityofnewyork.us/Public-Safety/EMS-Incident-Dispatch-Data/76xm-jjuj) | 7.2M incidents after filtering, Dec 2021 → Jun 2026 |
| [Open-Meteo Historical Weather API](https://archive-api.open-meteo.com) | Hourly temperature, precipitation, windspeed, and weather code for NYC. Free, no key. |
| [NYC Open Data — Permitted Event Information](https://data.cityofnewyork.us/City-Government/NYC-Permitted-Event-Information-Historical/bkfu-528j) | Large permitted events per borough per day (`is_major_event`) |
| NYC holiday + public-school calendars | Hand-coded in `pipeline/fw_calendar.py` (`is_holiday`, `is_school_day`) |
| [CDC Social Vulnerability Index](https://www.atsdr.cdc.gov/placeandhealth/svi/) | RPL_THEMES composite score, one value per dispatch zone |
| [OpenStreetMap via OSMnx](https://osmnx.readthedocs.io) | Full NYC drivable road network: drive times from 31 zone centroids and 30 EMS stations to every zone (1,891 pairs) |

All data sources are free and publicly available. No proprietary data.

---

## Why the 8-Minute Threshold?

The 8-minute mark (480 seconds) is the clinical standard for EMS response. For cardiac arrest:
- Response within 4 minutes: ~50% survival rate
- Response within 8 minutes: ~25% survival rate
- Response at 10+ minutes (Bronx average): ~10% survival rate

Every borough except Staten Island is currently averaging over this threshold. FirstWave is designed specifically to close that gap.
## Data Quality

Every incident must pass these filters (`pipeline/01_ingest_clean.py`):

```sql
incident_dt BETWEEN '2021-12-01' AND '2026-06-30 23:59'   -- Dec 2021 is lag warm-up only
AND REOPEN_INDICATOR   = 'N'                              -- exclude reopened incidents
AND TRANSFER_INDICATOR = 'N'                              -- exclude transfers
AND STANDBY_INDICATOR  = 'N'                              -- exclude standbys
AND BOROUGH IS NOT NULL AND BOROUGH != 'UNKNOWN'          -- known borough
AND INCIDENT_DISPATCH_AREA IN (31 clean zones)            -- B1–B5, K1–K7, M1–M9, Q1–Q7, S1–S3
AND zone prefix matches borough                           -- B→BRONX, K→BROOKLYN, etc.
```

Response-time validity is **not** a filter for demand, because dropping those calls would undercount it. Validity means both `VALID_*_RSPNS_TIME_INDC` flags are `Y` and the response takes 1–7200 s. It only decides which calls feed response-time averages and the counterfactual (92–96% of calls, depending on the year).

| Split | Dates | Incidents | Zone-hour rows |
|---|---|---|---|
| history (lag warm-up) | Dec 2021 | 131,075 | 2,232 |
| train | 2022-01 → 2024-09 | 4,339,847 | 746,976 |
| valid (early stopping) | 2024-10 → 2024-12 | 398,430 | 68,448 |
| test | 2025 | 1,584,147 | 271,560 |
| test_recent | 2026-01 → 2026-06 | 773,962 | 134,664 |

Grid rows start once a full 4-week look-back exists (2021-12-29), and history rows are never trained on. Every split has one row per zone per hour, zero-call hours included.

---

## Running the App

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker (optional, for PostGIS zone boundary geometries — graceful fallback without it)
- An OpenAI API key (optional, for AI Dispatcher — panel shows an informative error without it)

### 1. Backend

```bash
cd backend
pip install -r requirements.txt
```

Create `backend/.env`:
```
DATABASE_URL=postgresql://pp_user:pp_pass@localhost:5432/firstwave
ARTIFACTS_DIR=./artifacts
OPENAI_API_KEY=sk-...
```

**Optional — PostGIS (for precise zone boundaries):**
```bash
docker run --name firstwave-db \
  -e POSTGRES_DB=firstwave \
  -e POSTGRES_USER=pp_user \
  -e POSTGRES_PASSWORD=pp_pass \
  -p 5432:5432 \
  -d postgis/postgis:15-3.4

python3 backend/scripts/seed_zone_boundaries.py
```
*Without Docker, zone geometries fall back to bounding-box approximations from mock data — the app still runs.*

Start the server:
```bash
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

Health check: `curl http://127.0.0.1:8000/health`

### 2. Frontend

```bash
cd frontend
npm install
```

Create `frontend/.env`:
```
VITE_MAPBOX_TOKEN=pk.eyJ1IjoiLi4u...
VITE_API_BASE_URL=http://127.0.0.1:8000
```

Start dev server:
```bash
npm run dev   # http://localhost:3000
```

### 3. Hot-reload ML artifacts

If new model artifacts are dropped into `backend/artifacts/`:
```bash
curl -X POST http://localhost:8000/reload
```

### 4. Rebuild the model (optional)

The committed artifacts are enough to run the app. To rebuild them from raw data:

```bash
python -m venv pipeline/.venv && pipeline/.venv/bin/pip install -r pipeline/requirements-dev.txt
# Raw EMS CSV (~2GB): https://data.cityofnewyork.us/api/views/76xm-jjuj/rows.csv?accessType=DOWNLOAD
pipeline/.venv/bin/python pipeline/01_ingest_clean.py --csv ~/Downloads/ems_raw.csv
pipeline/.venv/bin/python pipeline/02_weather_merge.py
pipeline/.venv/bin/python pipeline/03_spatial_join.py
pipeline/.venv/bin/python pipeline/04_aggregate.py
pipeline/.venv/bin/python pipeline/05_train_demand_model.py
pipeline/.venv/bin/python pipeline/07_staging_optimizer.py        # validation only
pipeline/.venv/bin/python pipeline/08_counterfactual_precompute.py # ~10–30 min
pipeline/.venv/bin/python pipeline/test_artifacts.py
pipeline/.venv/bin/python pipeline/shap_importance.py             # README chart
```

`06_osmnx_matrix.py` (road network, 30–60 min) only needs rerunning if zones or stations change. `05` exits 1 and writes a candidate model instead of replacing the shipped one if it fails the deployment gate.

---

## Dispatch Zones

31 clean operational dispatch zones across 5 boroughs:

```
Bronx:        B1  B2  B3  B4  B5
Brooklyn:     K1  K2  K3  K4  K5  K6  K7
Manhattan:    M1  M2  M3  M4  M5  M6  M7  M8  M9
Queens:       Q1  Q2  Q3  Q4  Q5  Q6  Q7
Staten Island: S1  S2  S3
```

---

## Demo Scenarios

Each preset replays a real 2025 hour with its recorded weather.

| Preset | Replayed hour | Ambulances | What it shows |
|---|---|---|---|
| **Fri 8PM Peak** | Fri 2025-10-10, 20:00 | 5 | Bronx and Brooklyn go red. The staging pins fill the largest gaps in station coverage for that demand. This is the pitch. |
| **Mon 4AM Quiet** | Mon 2025-10-20, 04:00 | 5 | Citywide demand falls to 95 predicted calls/hour, vs 220 on Friday 8PM. The shading is relative to the hour's busiest zone, so compare the totals, not the colors. |
| **Storm** | Wed 2025-07-30, 18:00 | 7 | The rainiest Wednesday 6 PM of 2025 (8.2 mm/h, heavy rain). Weather feeds both the forecast and the counterfactual's travel times. |

---

## Tech Stack

| Layer | Technology | Version |
|---|---|---|
| ML — Demand Forecasting | XGBoost (count:poisson) | 3.2.0 |
| ML — Explainability | TreeSHAP (built into XGBoost) + matplotlib | 3.2.0 / 3.11 |
| ML — Staging Optimizer | SciPy MILP (HiGHS) | 1.17 |
| ML — AI Dispatcher | OpenAI GPT-4o-mini | latest |
| Spatial Routing | OSMnx + NetworkX | 1.9.1 / 3.3 |
| Data Processing | DuckDB, pandas, pyarrow | 1.5 / 3.0.1 / 23.0.1 |
| Backend API | FastAPI + Uvicorn | 0.110.0 / 0.29.0 |
| Database | PostgreSQL + PostGIS | 15 + 3.4 |
| Frontend | React | 19.2.0 |
| Map | Mapbox GL JS + react-map-gl | 3.18.1 / 7.1.9 |
| Charts | Plotly.js | 3.4.0 |
| Data Fetching | TanStack React Query | 5.90 |
| HTTP Client | Axios | 1.13.5 |
| Styling | Tailwind CSS | 4.2.0 |
| Build Tool | Vite | 7.3.1 |

---

## Repo Structure

```
firstwave/
├── backend/
│   ├── main.py                 App startup, CORS, artifact loading, health/reload
│   ├── routers/
│   │   ├── heatmap.py          GET /api/heatmap
│   │   ├── staging.py          GET /api/staging
│   │   ├── counterfactual.py   GET /api/counterfactual
│   │   ├── historical.py       GET /api/historical/:zone
│   │   ├── breakdown.py        GET /api/breakdown
│   │   ├── stations.py         GET /api/stations
│   │   └── ai_panel.py         POST /api/ai
│   ├── models/
│   │   ├── demand_forecaster.py    XGBoost inference wrapper (all 31 zones)
│   │   ├── lag_features.py         Serving-side lag features (parity-tested vs pipeline)
│   │   ├── replay.py               Replay-date, calendar, and real-weather lookup rules
│   │   ├── coverage_model.py       Travel model shared by staging, counterfactual, pipeline 07–08
│   │   └── staging_optimizer.py    Coverage-optimal staging (exact MILP)
│   ├── artifacts/              Pre-computed ML artifacts (pkl + parquet + model_metrics.json)
│   ├── scripts/
│   │   └── seed_zone_boundaries.py PostGIS seeding
│   └── requirements.txt
│
├── frontend/
│   └── src/
│       ├── App.jsx             Root state manager
│       ├── constants.js        Tokens, zone data, presets
│       ├── components/
│       │   ├── Map/
│       │   │   ├── MapContainer.jsx    Mapbox wrapper + event routing
│       │   │   ├── ZoneChoropleth.jsx  Demand intensity polygon outlines
│       │   │   ├── StagingPins.jsx     Ambulance pins + coverage circles
│       │   │   ├── StationLayer.jsx    FDNY station markers
│       │   │   ├── EquityLayer.jsx     SVI ZIP-level overlay
│       │   │   ├── ZoneTooltip.jsx     Hover tooltip
│       │   │   └── ZoneDetailPanel.jsx Click-to-expand zone stats
│       │   ├── Controls/
│       │   │   ├── ControlPanel.jsx    Left sidebar wrapper
│       │   │   ├── TimeSlider.jsx      Hour slider + Watch the Wave ▶ button
│       │   │   ├── DatePicker.jsx      Replay date (2025-01-01 → 2026-06-30)
│       │   │   ├── WeatherSelector.jsx Actual / Clear / Light Rain / Heavy Storm
│       │   │   ├── AmbulanceCount.jsx  K selector (1–10)
│       │   │   └── LayerToggle.jsx     Heatmap / Staging / Coverage / Stations
│       │   ├── Impact/
│       │   │   ├── ImpactPanel.jsx     Bottom impact bar
│       │   │   ├── CoverageBars.jsx    Before/after 8-min coverage bars
│       │   │   ├── ResponseHistogram.jsx Baseline vs. staged histogram
│       │   │   ├── EquityChart.jsx     SVI quartile savings chart
│       │   │   └── OverlayPanel.jsx    Equity layer toggle + legend
│       │   └── Chat/
│       │       └── AiPanel.jsx         AI Dispatcher (pill button → expanded panel)
│       ├── hooks/
│       │   ├── useHeatmap.js
│       │   ├── useStaging.js
│       │   ├── useCounterfactual.js
│       │   ├── useZoneHistory.js
│       │   ├── useStations.js
│       │   ├── useBreakdown.js
│       │   ├── useMapOverlays.js
│       │   └── useNycZipGeoJSON.js
│       └── utils/
│           ├── queryParams.js      Controls → API query params
│           └── replayDate.js       Replay-date helpers (weekday/month from date, AI day moves)
│
├── pipeline/                   DuckDB pipeline (scripts 01–08, run in order)
│   ├── fw_config.py            Splits, data window, canonical FEATURE_COLS
│   ├── fw_grid.py              Gap-free zone × hour grid + lag features
│   ├── fw_calendar.py          Holiday / school-day / event calendar
│   ├── fw_eval.py              Metrics + deployment gate
│   ├── fw_ingest.py            Raw CSV column checks
│   ├── shap_importance.py      SHAP feature-importance chart (docs/images/)
│   ├── test_artifacts.py       52-check artifact validation suite
│   └── tests/                  pytest suite incl. train/serve lag parity
│
├── data/
│   ├── mock_api_responses.json All endpoints mocked (frozen at Hour 0)
│   ├── ems_stations.json       30 FDNY EMS station locations
│   └── zone_centroids.json     31 dispatch zone centroids
│
├── CLAUDE.md                   Full technical spec and data dictionary
├── docs/                       Specs, plans, guides, README images
├── PRD_v3.md                   Product Requirements Document v3
└── devpost_strategy.md         Devpost submission content
```

---

**Hackathon:** GT Hacklytics 2026
**Tracks:** Healthcare (primary) · SafetyKit: Best AI for Human Safety (secondary)
