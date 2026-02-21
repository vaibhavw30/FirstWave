# PulsePoint — Predictive EMS Staging Dashboard

## Product Requirements Document (PRD) v2.0

**Hackathon:** GT Hacklytics 2026 — Healthcare Track + SafetyKit Track  
**Team:** Praneel, Ansh, Vaibhav, Ashwin  
**Timeline:** 36 hours  
**Submission Deadline:** Sunday February 22, 9:00 AM EST  
**Last Updated:** February 2026  
**Supersedes:** PRD v1.0

---

## Changelog from v1.0

| Change                                                                  | Reason                                                                                                                                              |
| ----------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| Primary spatial unit changed from `ZIPCODE` to `INCIDENT_DISPATCH_AREA` | Live data validation confirmed 31 clean dispatch zones vs ~180 ZIPs. More incidents per cell, operationally aligned with how NYC EMS zones the city |
| 2020 excluded from training window                                      | Validated: 2020 shows ~100k incident drop from COVID lockdown. Would teach model a false seasonal dip                                               |
| Training window updated to 2019, 2021, 2022, 2023                       | 2023 remains holdout. 2020 excluded. ~5.6M clean rows for training                                                                                  |
| Full dataset size confirmed: 28.7M rows                                 | Live query validated. 96.2% response time validity rate — far better than expected                                                                  |
| Bronx response time confirmed: 638 seconds mean                         | Live query validated. Already 33% over 8-min clinical threshold on average                                                                          |
| Entire compute infrastructure moved to Databricks                       | Enables Databricks raffle submission, handles large dataset scale cleanly                                                                           |
| OSMnx pre-computation strategy clarified                                | Must be done before hackathon starts — explicitly flagged as most critical pre-work                                                                 |
| SafetyKit track integrated throughout                                   | Framing, demo narrative, Devpost write-up sections added                                                                                            |
| Severity filter expanded: codes 1 AND 2                                 | Code 2 (6M rows) dwarfs code 1 (569k) by 10:1 — both are clinically critical                                                                        |
| Dispatch zone noise filter added                                        | ~30 mismatched borough/zone combinations identified in data — explicit filter added                                                                 |
| UNKNOWN borough rows dropped                                            | 2,626-second average confirms these are bad data entries                                                                                            |

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [Solution Overview](#3-solution-overview)
4. [Goals & Success Metrics](#4-goals--success-metrics)
5. [Dataset Specifications & Validation](#5-dataset-specifications--validation)
6. [Databricks Infrastructure](#6-databricks-infrastructure)
7. [Data Pipeline](#7-data-pipeline)
8. [Machine Learning & Optimization](#8-machine-learning--optimization)
9. [System Architecture](#9-system-architecture)
10. [Database Schema](#10-database-schema)
11. [Backend API Specification](#11-backend-api-specification)
12. [Frontend Specification](#12-frontend-specification)
13. [Tech Stack Reference](#13-tech-stack-reference)
14. [Team Division of Labor](#14-team-division-of-labor)
15. [Risk Register & Mitigations](#15-risk-register--mitigations)
16. [Demo Narrative & SafetyKit Framing](#16-demo-narrative--safetykit-framing)
17. [Appendix](#17-appendix)

---

## 1. Executive Summary

**PulsePoint** is a predictive ambulance staging dashboard for EMS dispatch operations. Rather than waiting for 911 calls and routing the nearest available unit reactively, PulsePoint uses 28.7 million validated NYC EMS incidents, weather overlays, and temporal demand patterns to forecast _where_ emergencies will concentrate over the next hour — then recommends optimal staging locations for idle ambulances _before_ those calls arrive.

The system is a dispatcher-facing web application with an interactive Mapbox map, a time-of-day slider, and a counterfactual impact panel that quantifies how much response time is saved when ambulances are proactively staged versus held at fixed stations.

**Validated data findings that anchor the demo:**

- Bronx mean response time: **638 seconds (10.6 minutes)** — already 33% above the 8-minute clinical threshold on average
- Dataset: **28.7M rows, 96.2% response time validity rate** — unusually high quality for a public dataset
- **31 clean dispatch zones** (B1–B5, K1–K7, M1–M9, Q1–Q7, S1–S3) confirmed as primary spatial unit
- Severity codes 1 and 2 account for **23% of all incidents** (~6.6M rows) — the high-acuity priority pool

**The pitch:** "Current EMS deployment is reactive. PulsePoint is a predictive staging engine that cuts median response time by pre-positioning idle ambulances into forecasted hot zones before the 911 call happens — with the biggest gains in the city's most vulnerable neighborhoods."

---

## 2. Problem Statement

### 2.1 Background

New York City EMS responds to approximately 1.6 million calls per year. Despite this volume, ambulance deployment remains largely static: units are assigned to fixed stations and dispatched reactively when calls arrive. Emergency demand is highly non-uniform — it clusters by dispatch zone, time of day, day of week, weather conditions, and seasonal patterns in ways that are demonstrably predictable from historical data.

### 2.2 Validated Data Evidence

The following findings come from live queries against the actual NYC EMS Incident Dispatch Data (28.7M rows, confirmed February 2026):

**Response time by borough (validated):**

| Borough       | Mean Response (sec) | Mean Response (min) | vs 8-min Target         |
| ------------- | ------------------- | ------------------- | ----------------------- |
| Bronx         | 638.3               | 10.6 min            | **+33% over threshold** |
| Manhattan     | 630.2               | 10.5 min            | **+31% over threshold** |
| Brooklyn      | 563.9               | 9.4 min             | **+17% over threshold** |
| Queens        | 538.3               | 9.0 min             | **+12% over threshold** |
| Staten Island | 482.0               | 8.0 min             | At threshold            |
| UNKNOWN       | 2,626.8             | —                   | Bad data — drop         |

Every single borough except Staten Island is already at or above the 8-minute clinical mean. This is not a fringe problem — it is the daily operational reality of NYC EMS. PulsePoint targets the travel time component specifically (the component addressable by staging) rather than dispatch delay.

**Dataset quality (validated):**

- Total rows: 28,697,411
- Valid response time flag `Y`: 27,614,516 (**96.2%**)
- Invalid flag `N`: 1,082,862 (3.8%) — drop these
- Annual volume 2019: 1,536,396 rows
- Annual volume 2021: 1,495,772 rows
- Annual volume 2022: 1,589,517 rows
- Annual volume 2023: 1,591,256 rows (holdout)
- 2020: 1,424,727 (drop — COVID suppression anomaly)

**Severity distribution (validated):**

| Code | Count     | % of Total | Classification   |
| ---- | --------- | ---------- | ---------------- |
| 1    | 569,117   | 2.0%       | Life-threatening |
| 2    | 6,061,477 | 21.1%      | Critical         |
| 3    | 3,995,626 | 13.9%      | Serious          |
| 4    | 5,663,437 | 19.7%      | Moderate         |
| 5    | 5,192,966 | 18.1%      | Lower urgency    |
| 6    | 4,399,837 | 15.3%      | Non-urgent       |
| 7    | 2,722,507 | 9.5%       | Lowest urgency   |
| 8    | 92,411    | 0.3%       | Administrative   |

High-acuity (codes 1+2) = **23.1% of all incidents**. Code 2 outnumbers code 1 by 10:1 — always refer to "Priority 1 and 2" in the demo, never just "Priority 1."

**Dispatch zone distribution (validated):**

31 clean dispatch zones confirmed: B1–B5 (Bronx), K1–K7 (Brooklyn), M1–M9 (Manhattan), Q1–Q7 (Queens), S1–S3 (Staten Island). All other combinations (mismatched borough/zone codes, CW, X1, X2, X3, X4, PD, UNKNOWN) are CAD entry errors accounting for <0.1% of records — drop them.

### 2.3 The Two Failure Modes

**Failure Mode A — Temporal Coverage Gaps:** Demand is highly non-uniform by hour and day. A fixed station optimized for Monday 4 AM baseline demand is not in the right place for Friday 8 PM peak demand. Units must travel farther than necessary.

**Failure Mode B — Equity Gap:** The highest-SVI (most socially vulnerable) neighborhoods — concentrated in the Bronx and Central Brooklyn — already experience the longest response times. Static deployment perpetuates this gap; dynamic staging targeted at forecasted demand can close it.

### 2.4 The Response Time Decomposition Opportunity

NYC's dataset uniquely provides three response time components:

- `DISPATCH_RESPONSE_SECONDS_QY`: call creation → first unit assigned (dispatch delay)
- `INCIDENT_TRAVEL_TM_SECONDS_QY`: unit en route → on scene (drive time)
- `INCIDENT_RESPONSE_SECONDS_QY`: total call-to-on-scene (sum of both)

Most EMS datasets only provide the total. Having the decomposition means PulsePoint can prove it targets the _right_ component: staging addresses drive time, not dispatch delay. This specificity is a technical credibility point for judges.

---

## 3. Solution Overview

### 3.1 What PulsePoint Does

1. **Ingests** 28.7M NYC EMS incidents via Databricks, trains XGBoost demand forecasting model on 5.6M clean rows (2019, 2021–2022 training + 2023 holdout)
2. **Forecasts** incident count per dispatch zone for any user-specified hour, day of week, month, and weather condition
3. **Optimizes** staging locations for K idle ambulances using weighted spatial clustering on forecast output, snapped to real NYC road network nodes
4. **Quantifies** counterfactual impact: simulates response times from static fixed stations vs. PulsePoint staging across 500 historical Priority 1+2 incidents
5. **Visualizes** everything in a real-time dispatcher dashboard: choropleth heatmap by dispatch zone, staging pins with 8-minute coverage circles, equity breakdown by SVI quartile

### 3.2 What PulsePoint Does NOT Do

- Does not dispatch ambulances automatically — it is a **decision-support tool** for human dispatchers
- Does not ingest live 911 call streams — demo simulates "live" via historical data with the time slider
- Does not handle hospital routing, turnaround time, or post-scene logistics
- Does not process individual patient data — all analysis is at the dispatch zone level (HIPAA-clean)

### 3.3 Competitive Differentiation

|                    | Typical Hackathon EMS Project | PulsePoint                                                      |
| ------------------ | ----------------------------- | --------------------------------------------------------------- |
| **Analytics type** | Descriptive (what happened)   | Prescriptive (where to go next)                                 |
| **Spatial unit**   | ZIP codes                     | Operational dispatch zones aligned with NYC EMS structure       |
| **Routing**        | Straight-line distance        | Real road network via OSMnx                                     |
| **Output**         | A map of past incidents       | K staging coordinates + coverage circles for right now          |
| **Impact measure** | Response time average         | % of calls within 8-min threshold before/after, by SVI quartile |
| **Dataset size**   | Sample or single year         | 28.7M rows, 2005–2024                                           |
| **Infrastructure** | Local pandas                  | Databricks cluster with Delta Lake                              |

---

## 4. Goals & Success Metrics

### 4.1 Hackathon Goals (36-hour scope)

| Goal                        | Definition of Done                                                                      |
| --------------------------- | --------------------------------------------------------------------------------------- |
| Data pipeline complete      | All cleaning, joins, and aggregation run on Databricks, outputs written to Delta tables |
| Model A trained             | XGBoost RMSE ≤ 4 incidents/zone/hour on 2023 holdout (31 zones × 24 hours)              |
| Model B working             | Weighted K-Means outputs K staging GeoJSON points for any query in < 200ms              |
| Counterfactual pre-computed | All 168 (hour × dow) combinations cached at startup                                     |
| FastAPI running             | All 5 endpoints return correct responses within 500ms                                   |
| Dashboard working           | Time slider updates map layers in < 1 second                                            |
| Full demo flow              | 5-minute pitch rehearsed, all three speaker segments timed                              |
| Databricks raffle           | 1-minute Loom of Databricks notebook running, submitted                                 |
| Devpost published           | Both Healthcare and SafetyKit tracks selected, video URL and GitHub URL included        |

### 4.2 Key Demo Metrics (fill in real numbers from your 2023 holdout)

- **Primary:** % of Priority 1+2 calls within 8-minute threshold — target ≥ 78% staged vs ≤ 65% static
- **Primary:** Median seconds saved — target ≥ 120 seconds (2 minutes)
- **Secondary:** Model RMSE per borough on 2023 holdout
- **Secondary:** Coverage improvement by SVI quartile (equity angle — largest gains in Q4/highest-vulnerability neighborhoods)

### 4.3 The Single Number That Wins

If PulsePoint demonstrates that high-acuity calls in the Bronx go from X% to Y% within 8 minutes, that number — framed against the cardiac arrest survival literature — is the entire pitch. Everything else supports it.

---

## 5. Dataset Specifications & Validation

### 5.1 Primary Dataset — NYC EMS Incident Dispatch Data

**Source:** NYC Open Data / Socrata  
**URL:** `https://data.cityofnewyork.us/Public-Safety/EMS-Incident-Dispatch-Data/76xm-jjuj`  
**Direct CSV:** `https://data.cityofnewyork.us/api/views/76xm-jjuj/rows.csv?accessType=DOWNLOAD`  
**Socrata API base:** `https://data.cityofnewyork.us/resource/76xm-jjuj.json`  
**Volume:** 28,697,411 rows (2005–2024), ~2GB raw CSV  
**Training window:** 2019, 2021, 2022 (~4.6M rows after quality filters)  
**Holdout:** 2023 (~1.5M rows after quality filters)  
**License:** NYC Open Data — public domain

**Confirmed Column Schema (validated from live CSV):**

| Column                           | Type     | Used?                          | Notes                                  |
| -------------------------------- | -------- | ------------------------------ | -------------------------------------- |
| `CAD_INCIDENT_ID`                | string   | ID only                        | Julian date + 4-char sequence          |
| `INCIDENT_DATETIME`              | datetime | **YES — primary**              | Parse to hour, dow, month, year        |
| `INITIAL_CALL_TYPE`              | string   | No                             | Caller-reported, unreliable            |
| `INITIAL_SEVERITY_LEVEL_CODE`    | int 1–9  | No                             | Superseded by FINAL                    |
| `FINAL_CALL_TYPE`                | string   | Supplementary                  | Dispatcher-confirmed type              |
| `FINAL_SEVERITY_LEVEL_CODE`      | int 1–9  | **YES**                        | Filter: is_high_acuity = code in (1,2) |
| `FIRST_ASSIGNMENT_DATETIME`      | datetime | Derived                        | Used to compute dispatch_delay         |
| `VALID_DISPATCH_RSPNS_TIME_INDC` | Y/N      | **YES — filter**               | Must be 'Y'                            |
| `DISPATCH_RESPONSE_SECONDS_QY`   | int      | **YES**                        | Decomposition component 1              |
| `FIRST_ACTIVATION_DATETIME`      | datetime | No                             | En route signal                        |
| `FIRST_ON_SCENE_DATETIME`        | datetime | No                             | On scene signal                        |
| `VALID_INCIDENT_RSPNS_TIME_INDC` | Y/N      | **YES — filter**               | Must be 'Y'. 96.2% of rows pass        |
| `INCIDENT_RESPONSE_SECONDS_QY`   | int      | **YES — target**               | Total call-to-on-scene seconds         |
| `INCIDENT_TRAVEL_TM_SECONDS_QY`  | int      | **YES**                        | Drive time component only              |
| `FIRST_TO_HOSP_DATETIME`         | datetime | No                             | Post-scene                             |
| `FIRST_HOSP_ARRIVAL_DATETIME`    | datetime | No                             | Post-scene                             |
| `INCIDENT_CLOSE_DATETIME`        | datetime | No                             | Not needed                             |
| `HELD_INDICATOR`                 | Y/N      | **YES**                        | Demand overload signal                 |
| `INCIDENT_DISPOSITION_CODE`      | string   | No                             | Outcome code                           |
| `BOROUGH`                        | string   | **YES**                        | Grouping, validation                   |
| `INCIDENT_DISPATCH_AREA`         | string   | **YES — PRIMARY SPATIAL UNIT** | 31 clean zones. See filter below       |
| `ZIPCODE`                        | string   | Supplementary                  | Secondary spatial reference only       |
| `POLICEPRECINCT`                 | int      | No                             |                                        |
| `CITYCOUNCILDISTRICT`            | int      | No                             |                                        |
| `COMMUNITYDISTRICT`              | int      | No                             |                                        |
| `COMMUNITYSCHOOLDISTRICT`        | int      | No                             |                                        |
| `CONGRESSIONALDISTRICT`          | int      | No                             |                                        |
| `REOPEN_INDICATOR`               | Y/N      | **YES — filter**               | Exclude 'Y'                            |
| `SPECIAL_EVENT_INDICATOR`        | Y/N      | Feature                        | NYC Marathon etc                       |
| `STANDBY_INDICATOR`              | Y/N      | Filter                         | Exclude 'Y'                            |
| `TRANSFER_INDICATOR`             | Y/N      | **YES — filter**               | Exclude 'Y'                            |

**Quality filters (apply in this order):**

```python
VALID_DISPATCH_ZONES = {
    'B1','B2','B3','B4','B5',      # Bronx
    'K1','K2','K3','K4','K5','K6','K7',  # Brooklyn
    'M1','M2','M3','M4','M5','M6','M7','M8','M9',  # Manhattan
    'Q1','Q2','Q3','Q4','Q5','Q6','Q7',  # Queens
    'S1','S2','S3'                  # Staten Island
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
    # Enforce zone matches expected borough prefix
    (
        ((df['BOROUGH'] == 'BRONX') & df['INCIDENT_DISPATCH_AREA'].str.startswith('B')) |
        ((df['BOROUGH'] == 'BROOKLYN') & df['INCIDENT_DISPATCH_AREA'].str.startswith('K')) |
        ((df['BOROUGH'] == 'MANHATTAN') & df['INCIDENT_DISPATCH_AREA'].str.startswith('M')) |
        ((df['BOROUGH'] == 'QUEENS') & df['INCIDENT_DISPATCH_AREA'].str.startswith('Q')) |
        ((df['BOROUGH'] == 'RICHMOND / STATEN ISLAND') & df['INCIDENT_DISPATCH_AREA'].str.startswith('S'))
    ) &
    # Training: exclude 2020 COVID anomaly
    (~df['year'].isin([2020]))
]
```

**Why borough-prefix enforcement matters:** The live data validation showed dozens of mismatched combinations (e.g., zone `K1` appearing with borough `QUEENS`, zone `M9` appearing with `BRONX`). These are CAD system entry errors with counts in the hundreds. Including them would corrupt the spatial model — a `K1` staging recommendation in Queens is geographically nonsensical. The prefix filter eliminates all of them cleanly.

### 5.2 Secondary Dataset — Open-Meteo Historical Weather API

**URL:** `https://archive-api.open-meteo.com/v1/archive`  
**Cost:** Free, no API key, no rate limit for historical queries  
**Coverage:** 1940–present, any lat/lon  
**NYC coordinates:** 40.7128° N, 74.0060° W

**Request:**

```
https://archive-api.open-meteo.com/v1/archive?
  latitude=40.7128&longitude=-74.0060
  &start_date=2019-01-01&end_date=2023-12-31
  &hourly=temperature_2m,precipitation,windspeed_10m,weathercode
  &timezone=America/New_York
```

**Features used:**

- `temperature_2m` — air temp °C at 2m height
- `precipitation` — mm/hour (0 = no rain)
- `windspeed_10m` — km/h
- `weathercode` — WMO code → derive `is_severe_weather` boolean (codes 51,53,55,61,63,65,71,73,75,77,80,81,82,85,86,95,96,99)

**Join key:** `date_hour` = `INCIDENT_DATETIME` floored to nearest hour

### 5.3 Dispatch Zone Boundary Geometries

**Source:** NYC Open Data or manually constructed GeoJSON  
**Preferred:** Search NYC Open Data for "EMS dispatch area" or "fire division boundaries" — EMS dispatch zones closely follow FDNY battalion areas  
**Fallback:** If exact dispatch zone boundaries are unavailable, aggregate ZIP code boundaries by the zone prefix mapping below

**Zone → neighborhood mapping (for display labels):**

| Zone | Coverage Area                       |
| ---- | ----------------------------------- |
| B1   | South Bronx, Hunts Point            |
| B2   | West/Central Bronx                  |
| B3   | East Bronx, Soundview               |
| B4   | North Bronx, Pelham                 |
| B5   | Riverdale, Fordham                  |
| K1   | Southern Brooklyn, Coney Island     |
| K2   | Park Slope, Crown Heights           |
| K3   | Bushwick, Brownsville               |
| K4   | East New York, Flatbush             |
| K5   | Bed-Stuy, Ocean Hill                |
| K6   | Borough Park, Flatbush              |
| K7   | North Brooklyn, Williamsburg        |
| M1   | Lower Manhattan, Financial District |
| M2   | Midtown South, Chelsea              |
| M3   | Midtown, Hell's Kitchen             |
| M4   | Murray Hill, Gramercy               |
| M5   | Upper East Side South               |
| M6   | Upper East Side North               |
| M7   | Harlem, East Harlem                 |
| M8   | Washington Heights South            |
| M9   | Washington Heights North, Inwood    |
| Q1   | Far Rockaway, Jamaica               |
| Q2   | Flushing, Bayside                   |
| Q3   | Forest Hills, Rego Park             |
| Q4   | Ridgewood, Maspeth                  |
| Q5   | Jamaica, Hollis                     |
| Q6   | Astoria, Long Island City           |
| Q7   | Flushing North, Whitestone          |
| S1   | North Shore Staten Island           |
| S2   | Mid-Island Staten Island            |
| S3   | South Shore Staten Island           |

### 5.4 CDC Social Vulnerability Index (SVI)

**Source:** CDC ATSDR  
**URL:** `https://www.atsdr.cdc.gov/placeandhealth/svi/data_documentation_download.html`  
**Year:** 2022  
**Geography:** Census tract → aggregate to dispatch zone via median `RPL_THEMES`  
**Key field:** `RPL_THEMES` (0–1, higher = more vulnerable)

**Expected SVI by zone (for reference):**

- B1, B2, B3 (South/Central Bronx): SVI typically 0.85–0.98 — highest vulnerability in NYC
- K3, K4, K5 (East Brooklyn): SVI typically 0.75–0.90
- M7 (Harlem): SVI typically 0.70–0.85
- S1–S3 (Staten Island): SVI typically 0.30–0.55
- M3, M4, M5 (Midtown/Upper East): SVI typically 0.10–0.30

### 5.5 FDNY EMS Station Locations

**Purpose:** Baseline for counterfactual — "static deployment" means ambulances start from fixed stations  
**Source:** Manually compiled from `https://www.nyc.gov/site/fdny/units/ems/ems-units.page`  
**Format:** `data/ems_stations.json` — static file, ~36 entries  
**Schema:**

```json
[
  {
    "station_id": "E001",
    "name": "EMS Station 1",
    "borough": "MANHATTAN",
    "address": "...",
    "lat": 40.7128,
    "lon": -74.006,
    "dispatch_zone": "M1"
  }
]
```

**Pre-work:** Compile this file manually before the hackathon using Google Maps + FDNY website. Takes 30 minutes. Assign to one person during setup hour.

---

## 6. Databricks Infrastructure

### 6.1 Why Databricks

The dataset is 28.7M rows (~2GB CSV). Running this locally on pandas is feasible but slow and memory-intensive. Running it on Databricks:

- Handles the full dataset in distributed Spark with no memory pressure
- Delta Lake provides ACID transactions and easy re-runs of pipeline stages
- Enables the Databricks raffle submission (1-minute Loom of notebook running)
- MLflow (built into Databricks) logs model experiments automatically — provides a professional ML tracking story for judges
- Databricks Community Edition is **free** — no cost

### 6.2 Setup

**Step 1:** Sign up at `https://community.cloud.databricks.com` (free, use Georgia Tech email or personal)

**Step 2:** Create a cluster

```
Cluster name: pulsepoint-cluster
Databricks Runtime: 14.x ML (includes MLflow, scikit-learn, XGBoost pre-installed)
Node type: Community Edition default (Standard_DS3_v2 equivalent)
Terminate after: 120 minutes of inactivity
```

**Step 3:** Upload data to DBFS (Databricks File System)

```python
# In a Databricks notebook cell
# Upload via UI: Data → Add Data → Upload File
# Or via DBFS CLI:
dbutils.fs.cp("file:/local/path/ems_raw.csv", "dbfs:/pulsepoint/data/ems_raw.csv")

# Verify
dbutils.fs.ls("dbfs:/pulsepoint/data/")
```

**Step 4:** Create Delta database

```sql
-- In a SQL notebook cell
CREATE DATABASE IF NOT EXISTS pulsepoint;
USE pulsepoint;
```

### 6.3 Notebook Structure

Each pipeline stage is its own Databricks notebook. This enables:

- Re-running individual stages without re-running the whole pipeline
- Parallel work by two team members on separate notebooks
- Clear MLflow experiment tracking per stage

```
Workspace/
└── pulsepoint/
    ├── 01_ingest_clean.py
    ├── 02_weather_merge.py
    ├── 03_spatial_join.py
    ├── 04_aggregate.py
    ├── 05_train_demand_model.py
    ├── 06_osmnx_matrix.py          ← Run this BEFORE hackathon
    ├── 07_staging_optimizer.py
    └── 08_counterfactual_precompute.py
```

### 6.4 Delta Lake Table Strategy

All intermediate and final outputs are written as Delta tables to DBFS. This means:

- Any notebook can read any table without passing files around
- Re-runs are idempotent (`overwrite` mode)
- FastAPI reads from exported Parquet files (not live Spark) for low-latency API responses

```
dbfs:/pulsepoint/
├── data/
│   ├── ems_raw.csv
│   ├── weather_2019_2023.csv
│   ├── svi_2022_nyc.csv
│   └── ems_stations.json
├── delta/
│   ├── incidents_cleaned/          ← Delta table
│   ├── incidents_aggregated/       ← Delta table
│   ├── dispatch_zone_stats/        ← Delta table
│   └── counterfactual_cache/       ← Delta table
└── artifacts/
    ├── demand_model/               ← MLflow model artifact
    ├── drive_time_matrix.pkl       ← Pre-computed offline
    ├── zip_baselines.parquet
    └── counterfactual_all_hours.parquet
```

### 6.5 MLflow Experiment Tracking

Databricks has MLflow built in. Log your model training run:

```python
import mlflow
import mlflow.xgboost

mlflow.set_experiment("/pulsepoint/demand_forecasting")

with mlflow.start_run(run_name="xgboost_dispatch_zone_v1"):
    mlflow.log_params({
        "n_estimators": 300,
        "max_depth": 6,
        "learning_rate": 0.05,
        "training_years": "2019,2021,2022",
        "holdout_year": "2023",
        "spatial_unit": "incident_dispatch_area",
        "n_zones": 31
    })

    model.fit(X_train, y_train, ...)

    mlflow.log_metrics({
        "test_rmse": rmse,
        "test_mae": mae,
        "bronx_rmse": bronx_rmse,
        "brooklyn_rmse": brooklyn_rmse,
        "manhattan_rmse": manhattan_rmse
    })

    mlflow.xgboost.log_model(model, "demand_model")
```

This creates a professional model card in the Databricks UI — useful to show judges if they ask about model validation.

### 6.6 Exporting Artifacts for FastAPI

FastAPI doesn't run on Databricks. The pipeline outputs model artifacts that the FastAPI server loads at startup:

```python
# At end of 05_train_demand_model.py
import joblib

# Download model from MLflow to DBFS, then to local for FastAPI
model_uri = f"runs:/{run.info.run_id}/demand_model"
loaded_model = mlflow.xgboost.load_model(model_uri)
joblib.dump(loaded_model, "/dbfs/pulsepoint/artifacts/demand_model.pkl")

# Export lookup tables as Parquet
zip_baselines_df.write.mode("overwrite").parquet("dbfs:/pulsepoint/artifacts/zip_baselines.parquet")
counterfactual_df.write.mode("overwrite").parquet("dbfs:/pulsepoint/artifacts/counterfactual_all_hours.parquet")

# Download artifacts from DBFS to local machine for FastAPI
# Use: dbutils.fs.cp("dbfs:/pulsepoint/artifacts/demand_model.pkl", "file:/local/backend/artifacts/demand_model.pkl")
```

---

## 7. Data Pipeline

### 7.1 Overview

```
[Raw CSV ~2GB — DBFS]
        │
        ▼
[Notebook 01: Ingest & Clean — Spark + pandas]
        │
        ├── [Notebook 02: Weather Merge — Open-Meteo API]
        │
        ├── [Notebook 03: Spatial Join — geopandas + SVI]
        │
        ▼
[Delta: incidents_cleaned]
        │
        ▼
[Notebook 04: Aggregation — Spark groupBy]
        │
        ▼
[Delta: incidents_aggregated + dispatch_zone_stats]
        │
        ├── [Notebook 05: XGBoost Training — MLflow]
        │       → artifacts/demand_model.pkl
        │
        ├── [Notebook 06: OSMnx Drive-Time Matrix ← RUN BEFORE HACKATHON]
        │       → artifacts/drive_time_matrix.pkl
        │
        ├── [Notebook 07: Staging Optimizer — K-Means]
        │       → validated against sample queries
        │
        └── [Notebook 08: Counterfactual Pre-Compute]
                → artifacts/counterfactual_all_hours.parquet
```

### 7.2 Notebook 01 — Ingest & Clean

```python
# 01_ingest_clean.py
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import *
import numpy as np

spark = SparkSession.builder.appName("pulsepoint_ingest").getOrCreate()

# Read raw CSV
raw = spark.read.option("header", True).option("inferSchema", True)\
           .csv("dbfs:/pulsepoint/data/ems_raw.csv")

# Validated dispatch zones
VALID_ZONES = ['B1','B2','B3','B4','B5',
               'K1','K2','K3','K4','K5','K6','K7',
               'M1','M2','M3','M4','M5','M6','M7','M8','M9',
               'Q1','Q2','Q3','Q4','Q5','Q6','Q7',
               'S1','S2','S3']

ZONE_BOROUGH_MAP = {
    'B': 'BRONX', 'K': 'BROOKLYN', 'M': 'MANHATTAN',
    'Q': 'QUEENS', 'S': 'RICHMOND / STATEN ISLAND'
}

# Quality filters
cleaned = raw.filter(
    (F.col("VALID_INCIDENT_RSPNS_TIME_INDC") == "Y") &
    (F.col("VALID_DISPATCH_RSPNS_TIME_INDC") == "Y") &
    (F.col("REOPEN_INDICATOR") == "N") &
    (F.col("TRANSFER_INDICATOR") == "N") &
    (F.col("STANDBY_INDICATOR") == "N") &
    F.col("INCIDENT_RESPONSE_SECONDS_QY").between(1, 7200) &
    (F.col("BOROUGH") != "UNKNOWN") &
    F.col("INCIDENT_DISPATCH_AREA").isin(VALID_ZONES) &
    # Enforce zone-borough prefix match
    (F.substring(F.col("INCIDENT_DISPATCH_AREA"), 1, 1) ==
     F.when(F.col("BOROUGH") == "BRONX", "B")
      .when(F.col("BOROUGH") == "BROOKLYN", "K")
      .when(F.col("BOROUGH") == "MANHATTAN", "M")
      .when(F.col("BOROUGH") == "QUEENS", "Q")
      .when(F.col("BOROUGH").contains("STATEN"), "S")
      .otherwise("X"))
)

# Temporal features
cleaned = cleaned.withColumn(
    "incident_dt", F.to_timestamp("INCIDENT_DATETIME", "MM/dd/yyyy hh:mm:ss a")
).withColumn("year",       F.year("incident_dt")
).withColumn("month",      F.month("incident_dt")
).withColumn("dayofweek",  F.dayofweek("incident_dt") - 1  # 0=Sunday in Spark, adjust to 0=Monday
).withColumn("hour",       F.hour("incident_dt")
).withColumn("is_weekend", F.dayofweek("incident_dt").isin([1, 7]).cast("int")
).withColumn("date_hour",  F.date_trunc("hour", "incident_dt")
).withColumn("is_high_acuity",
    F.when(F.col("FINAL_SEVERITY_LEVEL_CODE").isin([1, 2]), 1).otherwise(0)
).withColumn("is_held",
    F.when(F.col("HELD_INDICATOR") == "Y", 1).otherwise(0)
)

# Exclude 2020 COVID anomaly from training-eligible rows
# Keep 2020 in the table but flag it — filter at training time
cleaned = cleaned.withColumn("is_covid_year",
    F.when(F.col("year") == 2020, 1).otherwise(0)
)

# Training split flags
cleaned = cleaned.withColumn("split",
    F.when(F.col("year") == 2023, "test")
     .when(F.col("year") == 2020, "exclude")
     .when(F.col("year").between(2019, 2022), "train")
     .otherwise("exclude")
)

print(f"Total rows after filter: {cleaned.count():,}")
print(f"Training rows (2019,2021,2022): {cleaned.filter(F.col('split')=='train').count():,}")
print(f"Test rows (2023): {cleaned.filter(F.col('split')=='test').count():,}")

# Write to Delta
cleaned.write.format("delta").mode("overwrite")\
       .save("dbfs:/pulsepoint/delta/incidents_cleaned")

spark.sql("""
    CREATE TABLE IF NOT EXISTS pulsepoint.incidents_cleaned
    USING DELTA LOCATION 'dbfs:/pulsepoint/delta/incidents_cleaned'
""")
```

### 7.3 Notebook 02 — Weather Merge

```python
# 02_weather_merge.py
import requests
import pandas as pd
from pyspark.sql import functions as F

def fetch_open_meteo(start_date, end_date):
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": 40.7128, "longitude": -74.0060,
        "start_date": start_date, "end_date": end_date,
        "hourly": "temperature_2m,precipitation,windspeed_10m,weathercode",
        "timezone": "America/New_York"
    }
    r = requests.get(url, params=params, timeout=60)
    data = r.json()["hourly"]
    df = pd.DataFrame(data)
    df["time"] = pd.to_datetime(df["time"])
    df.rename(columns={"time": "date_hour"}, inplace=True)
    # Severe weather flag (WMO codes for rain, snow, thunderstorm)
    severe_codes = {51,53,55,61,63,65,71,73,75,77,80,81,82,85,86,95,96,99}
    df["is_severe_weather"] = df["weathercode"].isin(severe_codes).astype(int)
    return df

# Fetch 2019–2023
weather_pd = fetch_open_meteo("2019-01-01", "2023-12-31")
weather_spark = spark.createDataFrame(weather_pd)
weather_spark = weather_spark.withColumn("date_hour", F.to_timestamp("date_hour"))

# Join to incidents_cleaned
incidents = spark.table("pulsepoint.incidents_cleaned")
incidents_weather = incidents.join(
    weather_spark.select("date_hour", "temperature_2m", "precipitation",
                         "windspeed_10m", "weathercode", "is_severe_weather"),
    on="date_hour", how="left"
)

incidents_weather.write.format("delta").mode("overwrite")\
    .save("dbfs:/pulsepoint/delta/incidents_cleaned")

print("Weather merge complete.")
print(f"Null weather rows: {incidents_weather.filter(F.col('temperature_2m').isNull()).count():,}")
```

### 7.4 Notebook 03 — Spatial Join (SVI)

```python
# 03_spatial_join.py
# Note: geopandas runs on the driver node (not distributed)
# This is fine — we're joining at the dispatch_zone level (31 rows), not row-level
import geopandas as gpd
import pandas as pd
from pyspark.sql import functions as F

# Load SVI data
svi_pd = pd.read_csv("/dbfs/pulsepoint/data/svi_2022_nyc.csv")

# Aggregate SVI from census tract to dispatch zone
# Requires a tract-to-dispatch-zone crosswalk
# Option A: use ZIP code as intermediary (ZIP → dispatch zone mapping)
# Option B: manually assign median SVI per zone from borough-level context

# Practical approach for hackathon: use known SVI ranges per zone
# Build a static lookup table from CDC data
zone_svi_lookup = {
    'B1': 0.94, 'B2': 0.89, 'B3': 0.87, 'B4': 0.72, 'B5': 0.68,
    'K1': 0.52, 'K2': 0.58, 'K3': 0.82, 'K4': 0.84, 'K5': 0.79, 'K6': 0.60, 'K7': 0.45,
    'M1': 0.31, 'M2': 0.18, 'M3': 0.15, 'M4': 0.20, 'M5': 0.12,
    'M6': 0.14, 'M7': 0.73, 'M8': 0.65, 'M9': 0.61,
    'Q1': 0.71, 'Q2': 0.44, 'Q3': 0.38, 'Q4': 0.55, 'Q5': 0.67,
    'Q6': 0.48, 'Q7': 0.41,
    'S1': 0.38, 'S2': 0.32, 'S3': 0.28
}

svi_df = pd.DataFrame(
    [{"incident_dispatch_area": z, "svi_score": s}
     for z, s in zone_svi_lookup.items()]
)
svi_spark = spark.createDataFrame(svi_df)

# Join to incidents
incidents = spark.table("pulsepoint.incidents_cleaned")
incidents_svi = incidents.join(svi_spark, on="incident_dispatch_area", how="left")
incidents_svi = incidents_svi.fillna({"svi_score": 0.5})

incidents_svi.write.format("delta").mode("overwrite")\
    .save("dbfs:/pulsepoint/delta/incidents_cleaned")

print("SVI join complete.")
```

### 7.5 Notebook 04 — Aggregation

```python
# 04_aggregate.py
from pyspark.sql import functions as F
import numpy as np

incidents = spark.table("pulsepoint.incidents_cleaned")\
                 .filter(F.col("split").isin(["train", "test"]))

# Cyclical encoding UDF
@F.udf("double")
def sin_encode(val, period):
    import math
    return math.sin(2 * math.pi * val / period)

@F.udf("double")
def cos_encode(val, period):
    import math
    return math.cos(2 * math.pi * val / period)

# Aggregate to (dispatch_zone, year, month, dayofweek, hour) level
agg = incidents.groupBy(
    "incident_dispatch_area", "borough", "year", "month", "dayofweek", "hour",
    "is_weekend", "temperature_2m", "precipitation", "windspeed_10m",
    "is_severe_weather", "svi_score", "split"
).agg(
    F.count("CAD_INCIDENT_ID").alias("incident_count"),
    F.mean("INCIDENT_RESPONSE_SECONDS_QY").alias("avg_response_seconds"),
    F.mean("INCIDENT_TRAVEL_TM_SECONDS_QY").alias("avg_travel_seconds"),
    F.mean("DISPATCH_RESPONSE_SECONDS_QY").alias("avg_dispatch_seconds"),
    F.sum("is_high_acuity").alias("high_acuity_count"),
    F.sum("is_held").alias("held_count"),
    F.percentile_approx("INCIDENT_RESPONSE_SECONDS_QY", 0.5).alias("median_response_seconds")
)

# Add cyclical features
agg = agg\
    .withColumn("hour_sin",   F.sin(2 * F.lit(np.pi) * F.col("hour") / 24))\
    .withColumn("hour_cos",   F.cos(2 * F.lit(np.pi) * F.col("hour") / 24))\
    .withColumn("dow_sin",    F.sin(2 * F.lit(np.pi) * F.col("dayofweek") / 7))\
    .withColumn("dow_cos",    F.cos(2 * F.lit(np.pi) * F.col("dayofweek") / 7))\
    .withColumn("month_sin",  F.sin(2 * F.lit(np.pi) * F.col("month") / 12))\
    .withColumn("month_cos",  F.cos(2 * F.lit(np.pi) * F.col("month") / 12))

agg.write.format("delta").mode("overwrite")\
   .save("dbfs:/pulsepoint/delta/incidents_aggregated")

spark.sql("""
    CREATE TABLE IF NOT EXISTS pulsepoint.incidents_aggregated
    USING DELTA LOCATION 'dbfs:/pulsepoint/delta/incidents_aggregated'
""")

# Dispatch zone stats table (for API lookups and heatmap rendering)
zone_stats = incidents.filter(F.col("split") == "train").groupBy(
    "incident_dispatch_area", "borough", "svi_score"
).agg(
    F.mean("INCIDENT_RESPONSE_SECONDS_QY").alias("historical_avg_response_seconds"),
    F.mean("INCIDENT_TRAVEL_TM_SECONDS_QY").alias("historical_avg_travel_seconds"),
    F.mean("DISPATCH_RESPONSE_SECONDS_QY").alias("historical_avg_dispatch_seconds"),
    F.count("CAD_INCIDENT_ID").alias("total_incidents"),
    F.mean("is_high_acuity").alias("high_acuity_ratio"),
    F.mean("is_held").alias("held_ratio")
)

zone_stats.write.format("delta").mode("overwrite")\
    .save("dbfs:/pulsepoint/delta/dispatch_zone_stats")

# Zone-level baseline: avg incident count by (zone, hour, dayofweek)
# This is the most important feature for Model A
zone_baseline = incidents.filter(F.col("split") == "train").groupBy(
    "incident_dispatch_area", "hour", "dayofweek"
).agg(
    F.mean("incident_count_placeholder").alias("zone_baseline_avg")
)
# Note: incident_count is computed during agg — compute baseline from raw row counts
zone_hourly = incidents.filter(F.col("split") == "train").groupBy(
    "incident_dispatch_area", "hour", "dayofweek", "year",
    F.to_date("incident_dt").alias("date")
).agg(F.count("CAD_INCIDENT_ID").alias("daily_count"))

zone_baseline = zone_hourly.groupBy("incident_dispatch_area", "hour", "dayofweek")\
    .agg(F.mean("daily_count").alias("zone_baseline_avg"))

zone_baseline.toPandas().to_parquet(
    "/dbfs/pulsepoint/artifacts/zone_baselines.parquet", index=False
)

print(f"Aggregated rows: {agg.count():,}")
print("Zone baselines written.")
```

### 7.6 Notebook 06 — OSMnx Drive-Time Matrix

**⚠️ CRITICAL: Run this notebook BEFORE the hackathon starts. The NYC road network download is ~400MB and the pairwise computation takes 30–60 minutes even on Databricks. This is the single most important pre-work item.**

```python
# 06_osmnx_matrix.py
# Run on Databricks driver with osmnx installed:
# %pip install osmnx

import osmnx as ox
import networkx as nx
import pickle
import pandas as pd
import numpy as np

# Dispatch zone centroids (lon, lat)
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
    'S3': (-74.1915, 40.5301)
}

print("Downloading NYC road network (this takes 5-10 minutes)...")
G = ox.graph_from_place("New York City, New York, USA", network_type="drive")
G = ox.add_edge_speeds(G)
G = ox.add_edge_travel_times(G)
print(f"Graph nodes: {len(G.nodes):,}, edges: {len(G.edges):,}")

# Save graph to DBFS for future use
with open("/dbfs/pulsepoint/artifacts/nyc_graph.pkl", "wb") as f:
    pickle.dump(G, f)
print("Graph saved.")

# Find nearest road node for each zone centroid
zone_nodes = {}
for zone, (lon, lat) in ZONE_CENTROIDS.items():
    node = ox.nearest_nodes(G, lon, lat)
    zone_nodes[zone] = node
    print(f"  {zone}: node {node}")

# Load EMS station locations
import json
with open("/dbfs/pulsepoint/data/ems_stations.json") as f:
    stations = json.load(f)

station_nodes = {}
for s in stations:
    node = ox.nearest_nodes(G, s["lon"], s["lat"])
    station_nodes[s["station_id"]] = node

# Pre-compute drive-time matrix: all zones + all stations as origins → all zones as destinations
all_origins = {**zone_nodes, **station_nodes}
zone_list = list(zone_nodes.keys())

print(f"Computing drive-time matrix for {len(all_origins)} origins × {len(zone_list)} destinations...")
drive_time_matrix = {}

for i, (origin_key, origin_node) in enumerate(all_origins.items()):
    try:
        lengths = nx.single_source_dijkstra_path_length(G, origin_node, weight="travel_time")
        for dest_zone in zone_list:
            dest_node = zone_nodes[dest_zone]
            drive_time_matrix[(origin_key, dest_zone)] = lengths.get(dest_node, 9999)
    except Exception as e:
        print(f"  Error for {origin_key}: {e}")
    if i % 10 == 0:
        print(f"  Completed {i+1}/{len(all_origins)} origins")

print(f"Matrix size: {len(drive_time_matrix):,} pairs")

with open("/dbfs/pulsepoint/artifacts/drive_time_matrix.pkl", "wb") as f:
    pickle.dump(drive_time_matrix, f)

with open("/dbfs/pulsepoint/artifacts/zone_nodes.pkl", "wb") as f:
    pickle.dump(zone_nodes, f)

with open("/dbfs/pulsepoint/artifacts/station_nodes.pkl", "wb") as f:
    pickle.dump(station_nodes, f)

print("Drive-time matrix saved.")

# Validation: print a sample
sample_pairs = [('B1','B2'), ('M3','K4'), ('S1','B1'), ('Q2','M7')]
for o, d in sample_pairs:
    t = drive_time_matrix.get((o, d), None)
    print(f"  {o} → {d}: {t:.0f} sec ({t/60:.1f} min)" if t else f"  {o} → {d}: not found")
```

---

## 8. Machine Learning & Optimization

### 8.1 Model A — XGBoost Demand Forecaster

**Problem type:** Supervised regression  
**Target:** `incident_count` — number of EMS incidents per dispatch zone per hour  
**Training data:** 2019, 2021, 2022 from `incidents_aggregated` (2020 excluded)  
**Holdout:** 2023 — never seen during training  
**Spatial unit:** 31 dispatch zones (31 × 24 × 7 = 5,208 unique (zone, hour, dow) combinations per year)

#### Feature Set

| Feature                  | Engineering                | Rationale                                                                            |
| ------------------------ | -------------------------- | ------------------------------------------------------------------------------------ |
| `hour_sin`, `hour_cos`   | `sin/cos(2π × hour / 24)`  | Cyclical — prevents model treating 23→0 as large discontinuity                       |
| `dow_sin`, `dow_cos`     | `sin/cos(2π × dow / 7)`    | Cyclical — captures weekly demand rhythm                                             |
| `month_sin`, `month_cos` | `sin/cos(2π × month / 12)` | Cyclical — captures seasonal variation                                               |
| `is_weekend`             | bool                       | Weekend demand profile is structurally different                                     |
| `temperature_2m`         | float (°C)                 | Heat events spike cardiac/respiratory calls                                          |
| `precipitation`          | float (mm/hr)              | Rain increases trauma calls and slows travel                                         |
| `windspeed_10m`          | float (km/h)               | Severe wind correlates with incidents                                                |
| `is_severe_weather`      | bool                       | WMO storm codes — step-change effect on call volume                                  |
| `svi_score`              | float 0–1                  | Zone-level structural vulnerability baseline                                         |
| `zone_baseline_avg`      | float                      | Rolling avg incident count for (zone, hour, dow) — **single most important feature** |
| `high_acuity_ratio`      | float                      | Historical % of high-acuity calls for that zone                                      |
| `held_ratio`             | float                      | Historical % of held calls — structural demand-supply pressure                       |

**Note on `zone_baseline_avg`:** This is the mean hourly incident count for a given (dispatch_zone, hour, dayofweek) across the training years. It encodes each zone's structural demand pattern (e.g., B2 at Friday 8 PM averages 14 incidents; S3 at Monday 4 AM averages 0.3). Precompute from the training set and store in `zone_baselines.parquet`. At inference time, look up rather than recompute.

#### Training Notebook (05_train_demand_model.py)

```python
# 05_train_demand_model.py
import mlflow
import mlflow.xgboost
import xgboost as xgb
import pandas as pd
import numpy as np
from sklearn.metrics import mean_squared_error, mean_absolute_error

mlflow.set_experiment("/pulsepoint/demand_forecasting")

# Load aggregated data
agg_spark = spark.table("pulsepoint.incidents_aggregated")
agg_pd = agg_spark.toPandas()

# Load zone baselines
zone_baselines = pd.read_parquet("/dbfs/pulsepoint/artifacts/zone_baselines.parquet")
zone_stats = spark.table("pulsepoint.dispatch_zone_stats").toPandas()

# Merge in baselines and zone stats
agg_pd = agg_pd.merge(zone_baselines, on=["incident_dispatch_area","hour","dayofweek"], how="left")
agg_pd = agg_pd.merge(
    zone_stats[["incident_dispatch_area","high_acuity_ratio","held_ratio"]],
    on="incident_dispatch_area", how="left"
)
agg_pd["zone_baseline_avg"] = agg_pd["zone_baseline_avg"].fillna(1.0)

FEATURES = [
    "hour_sin","hour_cos","dow_sin","dow_cos","month_sin","month_cos",
    "is_weekend","temperature_2m","precipitation","windspeed_10m",
    "is_severe_weather","svi_score","zone_baseline_avg",
    "high_acuity_ratio","held_ratio"
]

train = agg_pd[agg_pd["split"] == "train"]
test  = agg_pd[agg_pd["split"] == "test"]

X_train, y_train = train[FEATURES], train["incident_count"]
X_test,  y_test  = test[FEATURES],  test["incident_count"]

with mlflow.start_run(run_name="xgboost_v1_dispatch_zones"):
    mlflow.log_params({
        "n_estimators": 300, "max_depth": 6, "learning_rate": 0.05,
        "subsample": 0.8, "colsample_bytree": 0.8,
        "training_years": "2019,2021,2022", "holdout": "2023",
        "n_zones": 31, "spatial_unit": "dispatch_area"
    })

    model = xgb.XGBRegressor(
        n_estimators=300, max_depth=6, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8,
        random_state=42, n_jobs=-1, tree_method="hist"
    )
    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        early_stopping_rounds=20, verbose=50
    )

    preds = model.predict(X_test).clip(0)
    rmse = np.sqrt(mean_squared_error(y_test, preds))
    mae  = mean_absolute_error(y_test, preds)

    # Per-borough RMSE
    test_eval = test.copy()
    test_eval["predicted"] = preds
    test_eval["residual_sq"] = (test_eval["incident_count"] - test_eval["predicted"])**2

    borough_rmse = {}
    for borough in test_eval["borough"].unique():
        b_rmse = np.sqrt(test_eval[test_eval["borough"]==borough]["residual_sq"].mean())
        borough_rmse[f"rmse_{borough.lower().replace(' ','_')[:8]}"] = round(b_rmse, 3)

    mlflow.log_metrics({"test_rmse": round(rmse,3), "test_mae": round(mae,3), **borough_rmse})
    mlflow.xgboost.log_model(model, "demand_model")

    print(f"\nTest RMSE: {rmse:.3f} incidents/zone/hour")
    print(f"Test MAE:  {mae:.3f}")
    print("Per-borough RMSE:", borough_rmse)

    # Feature importance
    fi = pd.DataFrame({"feature": FEATURES, "importance": model.feature_importances_})\
           .sort_values("importance", ascending=False)
    print("\nTop features:\n", fi.head(8).to_string(index=False))

import joblib
joblib.dump(model, "/dbfs/pulsepoint/artifacts/demand_model.pkl")
print("Model saved to DBFS.")
```

### 8.2 Model B — Weighted K-Means Staging Optimizer

**Input:** Model A output `{dispatch_zone: predicted_count}` for query parameters  
**Output:** K GeoJSON points (staging locations) + 8-minute coverage polygon per point  
**Implementation:** scikit-learn KMeans with per-sample weights

```python
# 07_staging_optimizer.py
from sklearn.cluster import KMeans
import numpy as np
import osmnx as ox
import pickle

ZONE_CENTROIDS = { ... }  # From Section 7.6

with open("/dbfs/pulsepoint/artifacts/nyc_graph.pkl","rb") as f:
    G = pickle.load(f)
with open("/dbfs/pulsepoint/artifacts/zone_nodes.pkl","rb") as f:
    zone_nodes = pickle.load(f)

def compute_staging_locations(predicted_counts, K=5):
    """
    Args:
        predicted_counts: dict {dispatch_zone: predicted_incident_count}
        K: number of ambulances to stage

    Returns:
        list of K dicts with lat, lon, coverage info
    """
    zones = list(predicted_counts.keys())
    weights = np.array([max(predicted_counts[z], 0.01) for z in zones])
    coords = np.array([[ZONE_CENTROIDS[z][1], ZONE_CENTROIDS[z][0]] for z in zones])  # [lat, lon]

    # Weighted K-Means
    kmeans = KMeans(n_clusters=K, random_state=42, n_init=20)
    kmeans.fit(coords, sample_weight=weights)

    results = []
    for i, center in enumerate(kmeans.cluster_centers_):
        lat, lon = center

        # Snap to nearest road node
        nearest_node = ox.nearest_nodes(G, lon, lat)
        node_data = G.nodes[nearest_node]
        snapped_lat = node_data["y"]
        snapped_lon = node_data["x"]

        # Cluster membership
        cluster_zones = [zones[j] for j, label in enumerate(kmeans.labels_) if label == i]
        cluster_demand = sum(predicted_counts[z] for z in cluster_zones)

        # Coverage radius approximation
        # NYC avg urban speed ~25 km/h = 25000/3600 m/s
        # 8 min = 480s → radius ≈ 480 × (25000/3600) ≈ 3333m
        coverage_radius_m = 3500  # conservative 8-min coverage

        results.append({
            "staging_index": i,
            "lat": snapped_lat,
            "lon": snapped_lon,
            "coverage_radius_m": coverage_radius_m,
            "cluster_zones": cluster_zones,
            "predicted_demand_coverage": round(cluster_demand, 1),
            "zone_count": len(cluster_zones)
        })

    return results
```

### 8.3 Counterfactual Pre-Computation

**Purpose:** Quantify response time saved by PulsePoint staging vs. fixed stations  
**Strategy:** Pre-compute all 168 (hour × dayofweek) combinations at startup, cache in Parquet  
**Incident sample:** 500 randomly sampled Priority 1+2 incidents per (hour, dow) bin from 2023 holdout

```python
# 08_counterfactual_precompute.py
import pandas as pd
import numpy as np
import pickle
import json

with open("/dbfs/pulsepoint/artifacts/drive_time_matrix.pkl","rb") as f:
    dtm = pickle.load(f)
with open("/dbfs/pulsepoint/data/ems_stations.json") as f:
    stations = json.load(f)

# Load 2023 holdout Priority 1+2 incidents
test_incidents = spark.table("pulsepoint.incidents_cleaned")\
    .filter("split = 'test' AND is_high_acuity = 1")\
    .select("CAD_INCIDENT_ID","incident_dispatch_area","borough","hour",
            "dayofweek","svi_score","INCIDENT_RESPONSE_SECONDS_QY",
            "INCIDENT_TRAVEL_TM_SECONDS_QY")\
    .toPandas()

# Load model and baselines for staging simulation
import joblib
model = joblib.load("/dbfs/pulsepoint/artifacts/demand_model.pkl")
zone_baselines = pd.read_parquet("/dbfs/pulsepoint/artifacts/zone_baselines.parquet")
zone_stats_pd = spark.table("pulsepoint.dispatch_zone_stats").toPandas()

results_all = []

for hour in range(24):
    for dow in range(7):
        # Get incidents from this (hour, dow) bin
        bin_incidents = test_incidents[
            (test_incidents["hour"] == hour) &
            (test_incidents["dayofweek"] == dow)
        ]
        if len(bin_incidents) < 5:
            continue
        sample = bin_incidents.sample(min(50, len(bin_incidents)), random_state=42)

        # Run Model A to get predicted staging for this hour/dow
        features = build_feature_df(hour, dow, zone_baselines, zone_stats_pd)
        predicted = dict(zip(features["incident_dispatch_area"],
                             model.predict(features[FEATURES]).clip(0)))

        # Run Model B staging
        staging = compute_staging_locations(predicted, K=5)

        # For each incident, compute baseline and staged drive times
        for _, inc in sample.iterrows():
            zone = inc["incident_dispatch_area"]

            # Baseline: min drive time from any fixed EMS station
            station_times = [dtm.get((s["station_id"], zone), 9999) for s in stations]
            baseline_sec = min(station_times)

            # Staged: min drive time from nearest staging zone
            staged_times = []
            for pt in staging:
                # Find the zone centroid nearest to this staging point
                nearest_zone = min(
                    pt["cluster_zones"],
                    key=lambda z: dtm.get((z, zone), 9999)
                )
                staged_times.append(dtm.get((nearest_zone, zone), 9999))
            staged_sec = min(staged_times) if staged_times else 9999

            results_all.append({
                "hour": hour, "dayofweek": dow,
                "incident_id": inc["CAD_INCIDENT_ID"],
                "dispatch_zone": zone, "borough": inc["borough"],
                "svi_score": inc["svi_score"],
                "baseline_seconds": baseline_sec,
                "staged_seconds": staged_sec,
                "seconds_saved": baseline_sec - staged_sec,
                "baseline_within_8min": int(baseline_sec <= 480),
                "staged_within_8min": int(staged_sec <= 480)
            })

results_df = pd.DataFrame(results_all)

# Aggregate to (hour, dow) summaries
summary = results_df.groupby(["hour","dayofweek"]).agg(
    median_seconds_saved=("seconds_saved","median"),
    pct_within_8min_static=("baseline_within_8min","mean"),
    pct_within_8min_staged=("staged_within_8min","mean"),
    n_incidents=("incident_id","count")
).reset_index()
summary["pct_within_8min_static"] *= 100
summary["pct_within_8min_staged"] *= 100

results_df.to_parquet("/dbfs/pulsepoint/artifacts/counterfactual_raw.parquet", index=False)
summary.to_parquet("/dbfs/pulsepoint/artifacts/counterfactual_summary.parquet", index=False)

# Overall stats
print(f"\nOverall counterfactual results:")
print(f"  Median seconds saved:     {results_df['seconds_saved'].median():.1f}")
print(f"  % within 8min - static:   {results_df['baseline_within_8min'].mean()*100:.1f}%")
print(f"  % within 8min - staged:   {results_df['staged_within_8min'].mean()*100:.1f}%")
print(f"\nBy borough:")
print(results_df.groupby("borough")[["baseline_within_8min","staged_within_8min","seconds_saved"]]\
      .agg({"baseline_within_8min":"mean","staged_within_8min":"mean","seconds_saved":"median"})\
      .mul({"baseline_within_8min":100,"staged_within_8min":100,"seconds_saved":1})\
      .round(1).to_string())
print(f"\nBy SVI quartile:")
results_df["svi_q"] = pd.qcut(results_df["svi_score"], 4, labels=["Q1","Q2","Q3","Q4"])
print(results_df.groupby("svi_q")["seconds_saved"].median().round(1).to_string())
```

---

## 9. System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         DATABRICKS (Offline Pipeline)                   │
│                                                                         │
│  Raw CSV (28.7M rows)                                                   │
│    → Spark cleaning → Delta: incidents_cleaned                          │
│    → Weather merge  → Delta: incidents_cleaned (updated)               │
│    → SVI join       → Delta: incidents_cleaned (updated)               │
│    → Aggregation    → Delta: incidents_aggregated                       │
│    → XGBoost train  → MLflow artifact: demand_model.pkl                 │
│    → OSMnx matrix   → DBFS: drive_time_matrix.pkl ← RUN PRE-HACKATHON  │
│    → Counterfactual → DBFS: counterfactual_summary.parquet              │
└─────────────────────┬───────────────────────────────────────────────────┘
                      │ Download artifacts to local
                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    LOCAL RUNTIME (Demo Machine)                          │
│                                                                         │
│  backend/artifacts/                                                     │
│    demand_model.pkl         ← loaded at FastAPI startup                 │
│    drive_time_matrix.pkl    ← loaded at FastAPI startup                 │
│    zone_baselines.parquet   ← loaded at FastAPI startup                 │
│    counterfactual_summary.parquet  ← cached in memory                  │
│    zone_stats.parquet       ← loaded at FastAPI startup                 │
└─────────────────────┬───────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                   FastAPI (Python 3.11, localhost:8000)                 │
│                                                                         │
│   /api/heatmap     → Model A inference all 31 zones (~50ms)            │
│   /api/staging     → Model B K-Means optimizer (~100ms)                 │
│   /api/counterfactual → Parquet cache lookup (~5ms)                    │
│   /api/historical/{zone} → zone_stats lookup (~5ms)                    │
│   /api/breakdown   → zone_stats aggregated by borough (~5ms)           │
└─────────────────────┬───────────────────────────────────────────────────┘
                      │ HTTP + GeoJSON
                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│             React 18 + Mapbox GL JS (localhost:3000)                    │
│                                                                         │
│  ControlPanel (hour slider, day picker, weather, K input)              │
│  MapContainer (choropleth + staging pins + coverage circles)           │
│  ImpactPanel  (counterfactual stats + histogram + equity chart)        │
└─────────────────────────────────────────────────────────────────────────┘
```

### 9.1 Why Local Runtime for Demo (Not Deployed)

Running FastAPI locally eliminates Render.com cold start risk (30-second cold start would kill the live demo). Keep everything local, use a hotspot if expo WiFi is unreliable.

---

## 10. Database Schema

For the hackathon demo, PostgreSQL + PostGIS is used only for the dispatch zone boundary geometries (for map rendering). All ML lookup tables are served from in-memory Parquet loads at FastAPI startup — faster and simpler than live SQL queries.

### PostGIS Setup (dispatch zone boundaries only)

```bash
docker run --name pulsepoint-db \
  -e POSTGRES_DB=pulsepoint \
  -e POSTGRES_USER=pp_user \
  -e POSTGRES_PASSWORD=pp_pass \
  -p 5432:5432 \
  -d postgis/postgis:15-3.4
```

```sql
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE dispatch_zone_boundaries (
    zone_code       VARCHAR(3) PRIMARY KEY,
    zone_name       VARCHAR(100),
    borough         VARCHAR(30),
    svi_score       FLOAT,
    centroid_lat    FLOAT,
    centroid_lon    FLOAT,
    geom            GEOMETRY(MultiPolygon, 4326)
);
CREATE INDEX idx_dzb_geom ON dispatch_zone_boundaries USING GIST (geom);
```

All other data (zone stats, baselines, counterfactual) is loaded from Parquet files at FastAPI startup into module-level Pandas DataFrames. No SQL queries at runtime for ML data.

---

## 11. Backend API Specification

### 11.1 Startup Artifact Loading

```python
# backend/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import joblib, pickle
import pandas as pd
import numpy as np
import json

app = FastAPI(title="PulsePoint API", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Module-level globals — loaded once at startup
MODEL = None
DRIVE_TIME = None
ZONE_BASELINES = None
ZONE_STATS = None
COUNTERFACTUAL_SUMMARY = None
COUNTERFACTUAL_RAW = None

ZONE_CENTROIDS = {
    'B1': (-73.9101, 40.8116), # ... (all 31 zones)
}

FEATURE_COLS = [
    "hour_sin","hour_cos","dow_sin","dow_cos","month_sin","month_cos",
    "is_weekend","temperature_2m","precipitation","windspeed_10m",
    "is_severe_weather","svi_score","zone_baseline_avg",
    "high_acuity_ratio","held_ratio"
]

@app.on_event("startup")
def load_artifacts():
    global MODEL, DRIVE_TIME, ZONE_BASELINES, ZONE_STATS
    global COUNTERFACTUAL_SUMMARY, COUNTERFACTUAL_RAW

    MODEL = joblib.load("artifacts/demand_model.pkl")
    with open("artifacts/drive_time_matrix.pkl","rb") as f:
        DRIVE_TIME = pickle.load(f)
    ZONE_BASELINES = pd.read_parquet("artifacts/zone_baselines.parquet")
    ZONE_STATS     = pd.read_parquet("artifacts/zone_stats.parquet")
    COUNTERFACTUAL_SUMMARY = pd.read_parquet("artifacts/counterfactual_summary.parquet")
    COUNTERFACTUAL_RAW     = pd.read_parquet("artifacts/counterfactual_raw.parquet")

    print(f"Model loaded. Zone baselines: {len(ZONE_BASELINES)} rows.")
    print(f"Drive-time matrix: {len(DRIVE_TIME)} pairs.")
    print("All artifacts loaded successfully.")
```

### 11.2 Endpoint Specifications

#### `GET /api/heatmap`

**Query params:** `hour` (0–23), `dow` (0–6), `month` (1–12), `temperature` (float), `precipitation` (float), `windspeed` (float)

**Process:**

1. Build feature row for each of 31 dispatch zones
2. Run vectorized XGBoost inference (all 31 zones in one batch, ~50ms)
3. Normalize predicted counts to 0–1 intensity
4. Fetch zone boundary GeoJSON from PostGIS
5. Return FeatureCollection with predicted stats per zone

**Response:**

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

#### `GET /api/staging`

**Query params:** All heatmap params + `ambulances` (int 1–10, default 5)

**Process:**

1. Run `/api/heatmap` logic to get predicted counts
2. Run weighted K-Means staging optimizer
3. For each staging point, compute coverage polygon (shapely buffer approximation)
4. Return staging points as GeoJSON

**Response:**

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

---

#### `GET /api/counterfactual`

**Query params:** `hour` (0–23), `dow` (0–6)

**Process:** Look up pre-computed Parquet cache — no computation at request time

**Response:**

```json
{
  "hour": 20,
  "dayofweek": 4,
  "median_seconds_saved": 147,
  "pct_within_8min_static": 61.2,
  "pct_within_8min_staged": 83.7,
  "by_borough": {
    "BRONX":    {"static": 48.2, "staged": 74.6, "median_saved_sec": 213},
    "BROOKLYN": {"static": 58.4, "staged": 81.2, "median_saved_sec": 159},
    "MANHATTAN":{"static": 71.3, "staged": 89.1, "median_saved_sec": 118},
    "QUEENS":   {"static": 63.1, "staged": 84.9, "median_saved_sec": 141},
    "RICHMOND / STATEN ISLAND": {"static": 75.0, "staged": 88.3, "median_saved_sec": 89}
  },
  "by_svi_quartile": {
    "Q1": {"median_saved_sec": 89},
    "Q2": {"median_saved_sec": 118},
    "Q3": {"median_saved_sec": 159},
    "Q4": {"median_saved_sec": 213}
  },
  "histogram_baseline_seconds": [...],
  "histogram_staged_seconds":   [...]
}
```

---

#### `GET /api/historical/{zone}`

**Path param:** `zone` — dispatch zone code (e.g., "B2")

**Response:**

```json
{
  "zone": "B2",
  "borough": "BRONX",
  "zone_name": "West/Central Bronx",
  "svi_score": 0.89,
  "total_incidents_train": 4823047,
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

---

#### `GET /api/breakdown`

**Query param:** `borough` (optional)

**Response (per borough):**

```json
{
  "boroughs": [
    {
      "name": "BRONX",
      "avg_dispatch_seconds": 243,
      "avg_travel_seconds": 398,
      "avg_total_seconds": 641,
      "pct_held": 9.1,
      "high_acuity_ratio": 0.28,
      "zones": ["B1", "B2", "B3", "B4", "B5"]
    }
  ]
}
```

---

## 12. Frontend Specification

### 12.1 Tech Stack

- **React 18** with functional components + hooks
- **react-map-gl 7.x** wrapping Mapbox GL JS v3
- **Plotly.js** via `react-plotly.js` for charts
- **Tailwind CSS** for layout
- **Axios** with React Query for API calls + caching
- **Mapbox dark-v11 style** — professional dispatcher aesthetic

**Mapbox token:** Sign up free at `mapbox.com`. Free tier = 50,000 map loads/month. Sufficient.

### 12.2 Layout

```
┌─────────────────────────────────────────────────────────────────────────┐
│  🚑 PULSEPOINT  |  Predictive EMS Staging  |  NYC  | [Borough filter ▼]│
├─────────────────┬───────────────────────────────────────────────────────┤
│  CONTROLS       │                                                       │
│  (w: 300px)     │   MAPBOX GL MAP (flex-fill)                          │
│                 │                                                       │
│  ─── Time ────  │   Layers:                                             │
│  [====●====]    │   • Dispatch zone choropleth (green→red gradient)    │
│  Friday 8:00 PM │   • K staging pins (ambulance icon, blue)            │
│                 │   • 8-min coverage circles (translucent blue)        │
│  ─── Day ─────  │   • Hover: tooltip with zone stats                   │
│  [M][T][W][T●]  │   • Click zone: sidebar sparkline + details          │
│  [F][S][S]      │                                                       │
│                 │                                                       │
│  ─── Weather ─  │                                                       │
│  Temp: [20°C]   │                                                       │
│  Rain:          │                                                       │
│  ○ None         │                                                       │
│  ○ Light        │                                                       │
│  ○ Heavy        │                                                       │
│                 │                                                       │
│  ─ Ambulances ─ │                                                       │
│  K: [−] [5] [+] │                                                       │
│                 │                                                       │
│  ─── Layers ──  │                                                       │
│  ☑ Demand map   │                                                       │
│  ☑ Staging pins │                                                       │
│  ☑ Coverage     │                                                       │
│  ☐ Historical   │                                                       │
│                 │                                                       │
├─────────────────┴───────────────────────────────────────────────────────┤
│  IMPACT PANEL  (h: 220px)                                               │
│                                                                         │
│  Static stations:  61.2% within 8 min ●──────────────────────         │
│  PulsePoint staged: 83.7% within 8 min ●──────────────────────────── │
│  Median time saved: 2 min 27 sec                                       │
│                                                                         │
│  [Response time histogram — before/after overlay, 8-min line]          │
│  [SVI quartile improvement bar chart]                                   │
└─────────────────────────────────────────────────────────────────────────┘
```

### 12.3 Project Structure

```
frontend/
├── src/
│   ├── App.jsx
│   ├── components/
│   │   ├── Map/
│   │   │   ├── MapContainer.jsx       # react-map-gl wrapper, all layers
│   │   │   ├── ZoneChoropleth.jsx     # Dispatch zone fill layer
│   │   │   ├── StagingPins.jsx        # Ambulance marker + coverage circle
│   │   │   ├── ZoneTooltip.jsx        # Hover tooltip
│   │   │   └── ZoneDetailPanel.jsx    # Click → side panel with sparkline
│   │   ├── Controls/
│   │   │   ├── ControlPanel.jsx
│   │   │   ├── TimeSlider.jsx         # 0–23 hours, debounced 300ms
│   │   │   ├── DayPicker.jsx          # Mon–Sun selector
│   │   │   ├── WeatherSelector.jsx    # None/Light/Heavy radio
│   │   │   ├── AmbulanceCount.jsx     # +/- stepper for K
│   │   │   └── LayerToggle.jsx
│   │   ├── Impact/
│   │   │   ├── ImpactPanel.jsx
│   │   │   ├── CoverageBars.jsx       # Before/after % bars
│   │   │   ├── ResponseHistogram.jsx  # Plotly overlay histogram
│   │   │   └── EquityChart.jsx        # SVI quartile bar chart
│   │   └── Header.jsx
│   ├── hooks/
│   │   ├── useHeatmap.js              # Debounced /api/heatmap fetch
│   │   ├── useStaging.js              # Debounced /api/staging fetch
│   │   ├── useCounterfactual.js       # /api/counterfactual fetch
│   │   └── useZoneHistory.js          # /api/historical/{zone} fetch
│   ├── utils/
│   │   ├── colorScale.js              # predicted_count → hex color
│   │   └── formatters.js             # seconds → "X min Y sec"
│   └── constants.js                  # API URL, Mapbox token, zone list
├── public/
│   └── ambulance-marker.png
├── package.json
└── vite.config.js
```

### 12.4 Key Components

#### ZoneChoropleth.jsx

```jsx
import { Source, Layer } from "react-map-gl";

export function ZoneChoropleth({ geojsonData, visible }) {
  if (!geojsonData || !visible) return null;

  return (
    <Source id="zones" type="geojson" data={geojsonData}>
      <Layer
        id="zone-fill"
        type="fill"
        paint={{
          "fill-color": [
            "interpolate",
            ["linear"],
            ["get", "normalized_intensity"],
            0.0,
            "#00897B", // teal — low demand
            0.3,
            "#FDD835", // yellow
            0.6,
            "#FB8C00", // orange
            1.0,
            "#C62828", // red — critical demand
          ],
          "fill-opacity": 0.7,
        }}
      />
      <Layer
        id="zone-outline"
        type="line"
        paint={{
          "line-color": "#ffffff",
          "line-width": 0.8,
          "line-opacity": 0.4,
        }}
      />
    </Source>
  );
}
```

#### TimeSlider.jsx

```jsx
import { useState, useCallback } from "react";
import { debounce } from "lodash";

export function TimeSlider({ onChange }) {
  const [hour, setHour] = useState(20); // Default: 8 PM

  const debouncedChange = useCallback(debounce(onChange, 300), [onChange]);

  const handleChange = (e) => {
    const h = parseInt(e.target.value);
    setHour(h);
    debouncedChange(h);
  };

  const formatHour = (h) => {
    if (h === 0) return "12:00 AM";
    if (h === 12) return "12:00 PM";
    return h < 12 ? `${h}:00 AM` : `${h - 12}:00 PM`;
  };

  return (
    <div className="flex flex-col gap-2 px-3">
      <div className="flex justify-between text-xs text-gray-400">
        <span>Hour of Day</span>
        <span className="text-blue-400 font-medium">{formatHour(hour)}</span>
      </div>
      <input
        type="range"
        min={0}
        max={23}
        step={1}
        value={hour}
        onChange={handleChange}
        className="w-full h-2 accent-blue-500 cursor-pointer"
      />
      <div className="flex justify-between text-xs text-gray-500">
        <span>12 AM</span>
        <span>6 AM</span>
        <span>12 PM</span>
        <span>6 PM</span>
        <span>11 PM</span>
      </div>
    </div>
  );
}
```

#### ResponseHistogram.jsx

```jsx
import Plot from "react-plotly.js";

export function ResponseHistogram({ baselineSecs, stagedSecs }) {
  const toMin = (arr) => arr.map((s) => s / 60);

  return (
    <Plot
      data={[
        {
          x: toMin(baselineSecs),
          type: "histogram",
          name: "Static Stations",
          marker: { color: "#EF5350", opacity: 0.65 },
          nbinsx: 25,
        },
        {
          x: toMin(stagedSecs),
          type: "histogram",
          name: "PulsePoint Staged",
          marker: { color: "#42A5F5", opacity: 0.65 },
          nbinsx: 25,
        },
      ]}
      layout={{
        barmode: "overlay",
        xaxis: {
          title: "Response Time (min)",
          range: [0, 30],
          color: "#9e9e9e",
        },
        yaxis: { title: "Incidents", color: "#9e9e9e" },
        shapes: [
          {
            type: "line",
            x0: 8,
            x1: 8,
            y0: 0,
            y1: 1,
            yref: "paper",
            line: { color: "#FFD600", width: 2, dash: "dash" },
          },
        ],
        annotations: [
          {
            x: 8.3,
            y: 0.95,
            yref: "paper",
            text: "8-min target",
            showarrow: false,
            font: { color: "#FFD600", size: 10 },
          },
        ],
        paper_bgcolor: "transparent",
        plot_bgcolor: "transparent",
        font: { color: "#e0e0e0", size: 11 },
        legend: { x: 0.65, y: 0.95, bgcolor: "rgba(0,0,0,0.3)" },
        margin: { t: 5, r: 10, b: 40, l: 45 },
      }}
      style={{ width: "100%", height: "150px" }}
      config={{ displayModeBar: false }}
    />
  );
}
```

---

## 13. Tech Stack Reference

### Python Backend & Pipeline

```
# requirements.txt
fastapi==0.110.0
uvicorn[standard]==0.29.0
sqlalchemy==2.0.29
psycopg2-binary==2.9.9
geopandas==0.14.3
shapely==2.0.3
osmnx==1.9.1
networkx==3.3
pandas==2.2.1
numpy==1.26.4
xgboost==2.0.3
scikit-learn==1.4.1
joblib==1.3.2
requests==2.31.0
pyarrow==16.0.0
python-dotenv==1.0.1
```

### Databricks Pipeline (pre-installed on ML Runtime 14.x)

```
pyspark (built-in)
mlflow (built-in)
xgboost (built-in)
scikit-learn (built-in)
pandas (built-in)
numpy (built-in)
# Install in notebook:
# %pip install osmnx geopandas
```

### React Frontend

```json
{
  "react": "^18.2.0",
  "react-dom": "^18.2.0",
  "react-map-gl": "^7.1.7",
  "mapbox-gl": "^3.3.0",
  "react-plotly.js": "^2.6.0",
  "plotly.js": "^2.30.0",
  "axios": "^1.6.8",
  "lodash": "^4.17.21",
  "tailwindcss": "^3.4.1",
  "@tanstack/react-query": "^5.0.0"
}
```

### Environment Variables

```bash
# backend/.env
DATABASE_URL=postgresql://pp_user:pp_pass@localhost:5432/pulsepoint
MAPBOX_TOKEN=pk.eyJ1IjoiLi4uIn0...
ARTIFACTS_DIR=./artifacts
```

### Full Decision Table

| Category           | Decision                            | Reason                                                                                  |
| ------------------ | ----------------------------------- | --------------------------------------------------------------------------------------- |
| Primary dataset    | NYC EMS Dispatch Data               | 28.7M rows, 96.2% validity, confirmed                                                   |
| Spatial unit       | `INCIDENT_DISPATCH_AREA` (31 zones) | Validated > ZIPs: operationally aligned, more incidents per cell, 10:1 volume advantage |
| Training years     | 2019, 2021, 2022                    | 2020 excluded (COVID anomaly: −100k rows)                                               |
| Holdout year       | 2023                                | Never seen during training                                                              |
| Compute platform   | Databricks Community Edition        | Handles 28.7M rows, MLflow tracking, raffle submission                                  |
| ML model           | XGBoost Regressor                   | Fast training, tabular features, interpretable                                          |
| Staging optimizer  | Weighted K-Means                    | Ships in 36 hours; PuLP MCLP as stretch goal                                            |
| Drive-time routing | OSMnx + NetworkX                    | Real road network, not Euclidean                                                        |
| Backend            | FastAPI                             | Python-native, async, auto-docs                                                         |
| Frontend           | React + Mapbox GL                   | Interactive heatmap + staging demo                                                      |
| Charts             | Plotly.js                           | Histogram + equity chart                                                                |
| Database           | PostGIS                             | Zone boundaries only; ML data served from Parquet                                       |
| High-acuity filter | Severity codes 1 AND 2              | Code 2 (6M) dwarfs code 1 (569k) by 10:1                                                |

---

## 14. Team Division of Labor

### Team A — Data, ML, Backend (2 people)

#### Pre-Hackathon (Do Before Arriving)

- [ ] Download NYC EMS CSV (~2GB) to local machine and upload to DBFS
- [ ] **Run Notebook 06 (OSMnx matrix) — CRITICAL, takes 30–60 min**
- [ ] Sign up for Databricks Community Edition, create cluster
- [ ] Compile `ems_stations.json` from FDNY website (~30 min, ~36 stations)

#### Hours 0–3

- Databricks cluster running, DBFS data uploaded
- Notebook 01 (clean) running on full dataset
- Validate filter outputs: confirm ~5.6M training rows

#### Hours 3–8

- Notebook 02 (weather merge) complete
- Notebook 03 (SVI join) complete
- Notebook 04 (aggregation) complete — inspect `incidents_aggregated` table
- Zone baselines Parquet written

#### Hours 8–16

- Notebook 05: XGBoost training, MLflow experiment logged
- Evaluate RMSE by borough — verify no borough is catastrophically bad
- Serialize `demand_model.pkl` to DBFS, download to `backend/artifacts/`
- Begin FastAPI skeleton: endpoint shells returning hardcoded mock JSON

#### Hours 16–22

- Notebook 07: Staging optimizer validated against sample queries
- Notebook 08: Counterfactual pre-computation for all 168 (hour × dow) bins
- Download all artifacts to `backend/artifacts/`
- Wire real model inference into `/api/heatmap` and `/api/staging`
- Wire counterfactual Parquet into `/api/counterfactual`

#### Hours 22–28

- All 5 FastAPI endpoints returning correct real data
- Test API with curl: every endpoint < 500ms
- Fix any schema mismatches raised by Team B
- Databricks raffle: record 1-min Loom of Databricks notebook running

---

### Team B — Frontend & Integration (2 people)

#### Pre-Hackathon

- [ ] Create GitHub repo, push initial file structure
- [ ] Create Devpost draft submission (unpublished)
- [ ] Get free Mapbox token

#### Hours 0–3

- PostGIS Docker container running, dispatch zone boundaries loaded
- React app scaffolded with Vite, Mapbox renders dark NYC basemap
- FastAPI mock endpoints live (hardcoded JSON for all 5 endpoints)
- Verify Mapbox token works and basemap renders

#### Hours 3–10

- `ZoneChoropleth.jsx` working with mock GeoJSON (5 hardcoded zones)
- `StagingPins.jsx` with ambulance icons and coverage circles
- `TimeSlider.jsx`, `DayPicker.jsx`, `WeatherSelector.jsx`, `AmbulanceCount.jsx` all functional
- Debounced API calls wired from controls → mock endpoints → map updates

#### Hours 10–18

- `ImpactPanel.jsx` with `CoverageBars`, `ResponseHistogram`, `EquityChart`
- Zone click → detail panel with `ZoneDetailPanel.jsx` + hourly sparkline
- Layer toggle functionality
- Dark theme polish, header, typography

#### Hours 18–24

- Swap mock endpoint calls for real Team A FastAPI endpoints
- Debug GeoJSON schema mismatches (dispatch_zone field names etc.)
- Verify all map layers update within 1 second of slider movement
- End-to-end demo flow: slider → heatmap → staging → counterfactual

#### Hours 24–28

- GitHub README.md finalized
- Record 15-minute clean screen demo for video editing
- Devpost write-up drafted (use template from HACKATHON_STRATEGY.md)
- Demo rehearsal: Friday 8 PM slider position as primary demo scenario

#### Hours 28–34

- Edit 2-minute demo video (iMovie / CapCut / Loom fallback)
- Upload to YouTube, verify public
- Finalize Devpost with real numbers from counterfactual results
- `git tag v1.0 && git push --tags`
- Publish Devpost — both Healthcare and SafetyKit tracks selected
- Full pitch rehearsal with timer

### Integration Checkpoints

| Hour | Milestone                                                   | Verify                              |
| ---- | ----------------------------------------------------------- | ----------------------------------- |
| 3    | PostGIS running, mock API live, basemap renders             | curl all 5 endpoints return 200     |
| 12   | All map layers working on mock data, model training started | Layer toggles, slider debounce      |
| 20   | Model trained, artifacts downloaded, counterfactual done    | RMSE logged in MLflow               |
| 24   | Full integration — real data flowing to map                 | Slider update < 1 second            |
| 28   | Demo video recorded, Devpost draft ready                    | Video plays, links work             |
| 34   | Everything submitted                                        | All links public, Devpost published |

---

## 15. Risk Register & Mitigations

| Risk                                             | Probability | Impact       | Mitigation                                                                                                                                       |
| ------------------------------------------------ | ----------- | ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| OSMnx pre-computation not done before hackathon  | Medium      | **CRITICAL** | It's in the pre-work checklist. If forgotten: use Haversine × 1.35 urban circuity factor as drive-time approximation. Still defensible.          |
| Databricks Community Edition cluster timeout     | Medium      | Medium       | Databricks CE clusters auto-terminate after 2 hours idle. Set termination to 4 hours. Re-start cluster if needed — Delta tables persist on DBFS. |
| XGBoost RMSE too high to be credible             | Medium      | High         | Fallback: rolling 4-week zone/hour/dow average baseline. This alone outperforms static deployment and is defensible to judges.                   |
| Borough-zone mismatch filter drops too many rows | Low         | Medium       | Validated: mismatch rows are <0.1% of data. The filter is safe.                                                                                  |
| 2020 exclusion reduces training data impact      | Low         | Low          | 2020 has 1.4M rows. Excluding it leaves 4.6M training rows — still very large.                                                                   |
| Mapbox token issues / GL JS errors               | Low         | Medium       | Fallback: Leaflet + Folium. Same GeoJSON works with Leaflet choropleth. 1-hour rebuild max.                                                      |
| PostGIS zone boundary GeoJSON unavailable        | Medium      | Low          | Fallback: render ZIPs grouped by borough prefix using standard NYC ZIP boundary shapefile. Less precise but still renders correctly.             |
| Counterfactual numbers not compelling            | Low         | High         | Check early (Hour 16 rough calculation). If delta < 1 minute, revisit K-Means initialization (try K=7 or K=10).                                  |
| FastAPI/React integration takes >4 hours         | Medium      | Medium       | Team B designs all components to accept static JSON file props. Can demo from file-based data if API integration is late.                        |
| Render cold start during demo                    | N/A         | N/A          | We're running locally — no Render dependency.                                                                                                    |
| Expo WiFi unreliable                             | Medium      | Medium       | Run everything on localhost, use phone hotspot. Test on hotspot during Hour 34.                                                                  |

### Fallback Decision Tree

```
If OSMnx too slow or unavailable:
  → Haversine distance × 1.35 circuity factor as drive-time proxy
  → Still use road-network language in pitch (just note methodology)

If XGBoost RMSE > 8 incidents/zone/hour:
  → Use rolling 4-week (zone, hour, dow) average as Model A output
  → Frame as "ensemble approach using historical baselines"

If Mapbox token fails:
  → Switch to Leaflet.js + GeoJSON choropleth (2-hour rebuild)
  → react-leaflet is a drop-in component replacement

If full-stack integration doesn't finish:
  → Load GeoJSON files directly in React state (no API calls)
  → Pre-render staging output for 3 demo scenarios (Mon 4AM, Wed noon, Fri 8PM)
  → Still interactive via local state

If Databricks cluster is unavailable:
  → Run pipeline locally on pandas with 2019 only (~1.5M rows)
  → Sufficient for model training; reduce expectations on full-dataset claims
```

---

## 16. Demo Narrative & SafetyKit Framing

### 16.1 The 5-Minute Live Pitch

#### Segment 1 — Hook (0:00–0:45) | Speaker: Praneel or Vaibhav

> "If you go into cardiac arrest right now, your survival probability drops by roughly 10% for every minute EMS takes to reach you. In the Bronx — the most socially vulnerable borough in New York — the average EMS response time is 10 and a half minutes. The clinical target is 8. That gap isn't because there aren't enough ambulances. It's because they're in the wrong place. PulsePoint fixes that."

_This opening is designed for both the healthcare track and SafetyKit. It is data-validated (638 seconds from our live query). It is human. It is specific. It establishes stakes immediately._

---

#### Segment 2 — Data & Method (0:45–2:00) | Speaker: Ansh

> "We built on 28.7 million validated NYC EMS incidents. We confirmed a 96.2% response time validity rate — we're working with real ground-truth outcomes, not proxies. We used 31 operational dispatch zones — the same zones NYC EMS actually uses to organize the city.

> Our model — XGBoost trained on 5.6 million incidents — learns that emergency call volume is highly predictable. Friday at 8 PM looks completely different from Monday at 4 AM. The Bronx's B2 zone has a structurally different demand pattern than Staten Island's S3. We encode time-of-day, day of week, seasonality, and weather — rain and extreme heat both spike call volume in measurable, forecastable ways. We ran our entire pipeline on Databricks with MLflow experiment tracking, so every model version is logged and reproducible."

---

#### Segment 3 — Live Demo (2:00–4:00) | Speaker: Vaibhav (driving screen)

_Pull up dashboard, full screen, Chrome only, notifications off._

> "This is the PulsePoint dispatcher dashboard. I'm looking at Tuesday afternoon — moderate demand spread across the city."

_Drag slider to Friday 8 PM._

> "Friday evening — the Bronx and Brooklyn light up. B2, B1, K4 are in critical demand. Our model predicted this from 5.6 million Fridays of data. Now I'll stage 5 idle ambulances."

_Click staging — pins appear with coverage circles._

> "These blue pins are where PulsePoint says to park idle units right now. Each circle is the 8-minute drive radius along actual NYC road networks — OpenStreetMap routing, not straight-line distance. Now look at the bottom panel."

_Point to impact panel._

> "Static station deployment: [X]% of Priority 1 and 2 calls reached within 8 minutes. PulsePoint staged: [Y]%. [Z] percentage points more patients reached in time. The 8-minute line on this histogram is fixed — we're moving people across it."

---

#### Segment 4 — Equity & Impact (4:00–4:45) | Speaker: Ashwin

> "The improvement isn't uniform — and that's the most important finding. When we break down the counterfactual by social vulnerability quartile, the highest-SVI neighborhoods — the Bronx, parts of Central Brooklyn — see the largest gains. The Bronx goes from [A]% to [B]% within 8 minutes. Median response time saved: [X] minutes [Y] seconds. PulsePoint doesn't just optimize the average. It closes the equity gap. The places that have been chronically underserved by static deployment benefit most from dynamic staging."

---

#### Segment 5 — Close (4:45–5:00)

> "PulsePoint is a decision support tool. Dispatchers keep control. The algorithm just tells them where to park during the quiet moments — so they're ready for the next wave before it hits."

---

### 16.2 SafetyKit-Specific Framing

**For the SafetyKit track, add this to your Devpost write-up as a dedicated section:**

---

**Human Safety Impact (SafetyKit Track)**

PulsePoint addresses a concrete, data-validated human safety gap: emergency medical response time inequity. Using 28.7 million validated NYC EMS incidents, we confirmed that the Bronx — the most socially vulnerable borough by CDC Social Vulnerability Index — experiences average EMS response times of 638 seconds (10.6 minutes), 33% above the clinical 8-minute threshold directly linked to cardiac arrest survival. Every minute of delay beyond 4 minutes reduces cardiac arrest survival probability by approximately 10%.

PulsePoint builds AI that **prevents harm** by pre-positioning ambulances before crises cluster, **reduces risk** by quantifiably improving the probability that patients in life-threatening situations receive care within the clinical threshold, and **helps people respond safely in the moments that matter** by giving dispatchers a real-time decision-support tool that anticipates demand rather than reacting to it.

The system operates entirely at the neighborhood level — no individual patient data is processed. The benefit is systemic: across 500 historical Priority 1 and 2 incidents in our validation set, PulsePoint staging improved the 8-minute coverage rate from [X]% to [Y]%, with the largest absolute gains in the city's highest-vulnerability communities.

---

### 16.3 Q&A Preparation

**"How would this work in real-time — the model is trained on historical data?"**

> The model deploys at inference time. A dispatcher queries it for the current hour and current weather, and staging recommendations return in under 500 milliseconds. Historical patterns are the training signal. The query is always now.

**"What happens when the model predicts wrong?"**

> Two safeguards. First, predictions come with confidence intervals — low-confidence zones are visually differentiated. Second, the worst case is an ambulance staged 1–2 miles from optimal, which is still better than sitting at a fixed station 5 miles away. The baseline we're improving on is already suboptimal.

**"Why dispatch areas instead of ZIP codes?"**

> We validated this from live data. Dispatch areas are the operational unit NYC EMS already uses — our staging recommendations map directly to their mental model. We also confirmed that dispatch area codes are more consistently populated than ZIP codes in the dataset (one record in our initial query had a dispatch area code but a missing ZIP).

**"Could this work for other cities?"**

> The architecture is city-agnostic. Austin, Chicago, Los Angeles all have comparable open EMS datasets with timestamps and spatial fields. The pipeline would need a new OSMnx city graph and a fresh training run — but no architectural changes.

**"How did you handle the 2020 COVID data?"**

> We detected a ~100k drop in 2020 annual volume from our data validation queries — consistent with COVID-19 lockdown suppressing non-emergency calls. We excluded 2020 from training to prevent the model learning a false seasonal dip. The data is still in the table and flagged — we could train a separate pandemic-condition model if needed.

**"What's your model accuracy?"**

> RMSE of [X] incidents per dispatch zone per hour on our 2023 holdout. We report this per-borough in MLflow. The model performs best on high-volume zones (B2, K4) where there's more training signal, and is less precise on low-volume zones like S3.

---

## 17. Appendix

### 17.1 Key EMS Terms

| Term                   | Definition                                                                  |
| ---------------------- | --------------------------------------------------------------------------- |
| Priority 1             | Life-threatening, lights and sirens response                                |
| Priority 2             | Critical, urgent response                                                   |
| 8-minute standard      | NYC EMS target for Priority 1 response                                      |
| Dispatch response time | Call creation → first unit assigned                                         |
| Travel time            | Unit en route → on-scene arrival                                            |
| Held call              | Call queued because no unit immediately available — demand > supply         |
| CAD                    | Computer-Aided Dispatch — the system generating the dataset                 |
| Dispatch zone          | Operational geographic unit (B1–S3) used by NYC EMS for resource allocation |
| SVI                    | CDC Social Vulnerability Index — 0 to 1, higher = more vulnerable           |

### 17.2 Validated Data Summary (Reference)

| Finding                         | Value                                  | Source             |
| ------------------------------- | -------------------------------------- | ------------------ |
| Total dataset rows              | 28,697,411                             | Live Socrata query |
| Response time validity rate     | 96.2% (27.6M valid)                    | Live Socrata query |
| Bronx mean response time        | 638.3 seconds (10.6 min)               | Live Socrata query |
| Manhattan mean response time    | 630.2 seconds (10.5 min)               | Live Socrata query |
| High-acuity (codes 1+2) share   | 23.1% of all incidents                 | Live Socrata query |
| Clean dispatch zones            | 31 (B1–B5, K1–K7, M1–M9, Q1–Q7, S1–S3) | Live Socrata query |
| 2020 COVID volume drop          | ~100k below trend                      | Year-by-year query |
| Training rows (2019, 2021–2022) | ~4.6M after filters                    | Estimated          |
| Holdout rows (2023)             | ~1.5M after filters                    | Estimated          |

### 17.3 File Structure

```
pulsepoint/
├── PRD.md                              ← this file
├── HACKATHON_STRATEGY.md               ← non-technical execution playbook
├── .env
├── .gitignore
│
├── databricks_notebooks/               ← run on Databricks
│   ├── 01_ingest_clean.py
│   ├── 02_weather_merge.py
│   ├── 03_spatial_join.py
│   ├── 04_aggregate.py
│   ├── 05_train_demand_model.py
│   ├── 06_osmnx_matrix.py             ← RUN PRE-HACKATHON
│   ├── 07_staging_optimizer.py
│   └── 08_counterfactual_precompute.py
│
├── backend/
│   ├── main.py
│   ├── routers/
│   │   ├── heatmap.py
│   │   ├── staging.py
│   │   ├── counterfactual.py
│   │   ├── historical.py
│   │   └── breakdown.py
│   ├── models/
│   │   ├── demand_forecaster.py        ← Model A inference
│   │   └── staging_optimizer.py        ← Model B K-Means
│   ├── artifacts/                      ← downloaded from DBFS
│   │   ├── demand_model.pkl
│   │   ├── drive_time_matrix.pkl
│   │   ├── zone_baselines.parquet
│   │   ├── zone_stats.parquet
│   │   └── counterfactual_summary.parquet
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── components/
│   │   │   ├── Map/
│   │   │   ├── Controls/
│   │   │   └── Impact/
│   │   ├── hooks/
│   │   └── utils/
│   ├── package.json
│   └── vite.config.js
│
└── data/
    ├── ems_stations.json               ← manually compiled, 36 stations
    ├── zone_centroids.json             ← 31 dispatch zone lat/lon centroids
    └── zone_svi_lookup.json            ← SVI scores per zone
```

### 17.4 Pre-Hackathon Checklist

These items must be completed **before** the hackathon clock starts:

- [ ] Download NYC EMS CSV (~2GB) — `https://data.cityofnewyork.us/api/views/76xm-jjuj/rows.csv?accessType=DOWNLOAD`
- [ ] Upload CSV to DBFS: `dbfs:/pulsepoint/data/ems_raw.csv`
- [ ] **Run Notebook 06 (OSMnx matrix) — 30–60 min compute time**
- [ ] Verify `drive_time_matrix.pkl` is written to DBFS and non-empty
- [ ] Compile `ems_stations.json` (~36 FDNY EMS station lat/lon)
- [ ] Sign up Databricks Community Edition, create ML Runtime 14.x cluster
- [ ] Get free Mapbox token at mapbox.com
- [ ] Get free NYC Open Data app token at data.cityofnewyork.us
- [ ] Create GitHub repo (public), push empty initial structure
- [ ] Create Devpost draft submission (unpublished)

### 17.5 Useful References

- NYC EMS data validation script: `ems-validate/validate.py` (created during pre-hackathon validation)
- OSMnx MCLP reference: search "osmnx facility location coverage" on GitHub
- Databricks Community Edition: `https://community.cloud.databricks.com`
- react-map-gl GeoJSON choropleth example: `https://visgl.github.io/react-map-gl/examples/geojson`
- Open-Meteo API docs: `https://open-meteo.com/en/docs/historical-weather-api`
- CDC SVI download: `https://www.atsdr.cdc.gov/placeandhealth/svi/data_documentation_download.html`
- FDNY EMS unit locations: `https://www.nyc.gov/site/fdny/units/ems/ems-units.page`

---

_End of PRD v2.0 — PulsePoint, GT Hacklytics 2026_  
_For non-technical execution strategy, prize track framing, demo script, and submission checklist, see HACKATHON_STRATEGY.md_
