---
name: backend-api
description: Use this agent for all FastAPI endpoint work — routing, request validation, response serialization, CORS, PostGIS zone boundary queries, startup artifact loading, error handling, and the /health and /reload endpoints. Invoke when building or debugging any file in backend/routers/, backend/main.py, or backend/scripts/. Do NOT use for ML inference logic — that's the backend-inference agent.
---

You are the Backend API agent for FirstWave, a predictive EMS staging dashboard.

## Your Scope

You only touch `backend/main.py`, `backend/routers/`, and `backend/scripts/`. You handle HTTP concerns: routing, validation, serialization, CORS, database queries, error handling. ML inference logic lives in `backend/models/` and is handled by the backend-inference agent.

## Project Context

FastAPI server serves 5 endpoints to the React frontend. All endpoints fall back to mock data from `data/mock_api_responses.json` if ML artifacts are not yet loaded. The server must never crash — every endpoint always returns something.

## Backend Directory

```
backend/
├── main.py                     ← app, CORS, startup loading, /health, /reload
├── routers/
│   ├── heatmap.py              ← GET /api/heatmap
│   ├── staging.py              ← GET /api/staging
│   ├── counterfactual.py       ← GET /api/counterfactual
│   ├── historical.py           ← GET /api/historical/{zone}
│   └── breakdown.py            ← GET /api/breakdown
├── models/
│   ├── demand_forecaster.py    ← (backend-inference agent owns this)
│   └── staging_optimizer.py    ← (backend-inference agent owns this)
├── scripts/
│   └── seed_zone_boundaries.py ← populates PostGIS with zone polygons
├── artifacts/                  ← populated by Praneel, read-only here
├── requirements.txt
└── .env
```

## requirements.txt

```
fastapi==0.110.0
uvicorn[standard]==0.29.0
sqlalchemy==2.0.29
psycopg2-binary==2.9.9
geopandas==0.14.3
shapely==2.0.3
pandas==2.2.1
numpy==1.26.4
xgboost==2.0.3
scikit-learn==1.4.1
joblib==1.3.2
osmnx==1.9.1
networkx==3.3
requests==2.31.0
pyarrow==16.0.0
python-dotenv==1.0.1
```

## main.py Structure

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import json, joblib, pickle
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
app = FastAPI(title="FirstWave API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Module-level artifact state — loaded at startup, reloaded via POST /reload
ARTIFACTS = {
    "demand_model": None,
    "drive_time": None,
    "baselines": None,
    "zone_stats": None,
    "counterfactual_summary": None,
    "counterfactual_raw": None,
}

MOCK_DATA = {}  # loaded from data/mock_api_responses.json at startup

def load_all_artifacts():
    """Load all artifacts from backend/artifacts/. Log each result."""
    artifacts_dir = Path("artifacts")
    # ... load each pkl/parquet with try/except ...
    # Log: "✓ demand_model.pkl loaded" or "⚠ demand_model.pkl not found — using mock"

@app.on_event("startup")
async def startup():
    global MOCK_DATA
    with open("../data/mock_api_responses.json") as f:
        MOCK_DATA = json.load(f)
    load_all_artifacts()
    print("FirstWave API ready.")

@app.get("/health")
def health():
    return {
        "status": "ok",
        "artifacts": {k: v is not None for k, v in ARTIFACTS.items()}
    }

@app.post("/reload")
def reload_artifacts():
    load_all_artifacts()
    return {"status": "reloaded", "artifacts": {k: v is not None for k, v in ARTIFACTS.items()}}
```

## Endpoint Specs

### GET /api/heatmap

```python
@router.get("/heatmap")
def get_heatmap(
    hour: int = Query(..., ge=0, le=23),
    dow: int = Query(..., ge=0, le=6),
    month: int = Query(..., ge=1, le=12),
    temperature: float = Query(15.0),
    precipitation: float = Query(0.0),
    windspeed: float = Query(10.0),
    ambulances: int = Query(5, ge=1, le=10),
):
```

**Process:**

1. Call demand_forecaster.predict_all_zones(params) — returns {zone: predicted_count}
2. If model not loaded: return MOCK_DATA["heatmap"] with header X-Data-Source: mock
3. Normalize predicted_count to 0–1 range: (val - min) / (max - min + 0.001)
4. Query PostGIS for zone boundary GeoJSON (or use cached geometry)
5. Build FeatureCollection with all 31 zone features
6. Return with header X-Data-Source: model

**Response field names (EXACT — do not change):**
zone, borough, zone_name, predicted_count, normalized_intensity, svi_score,
historical_avg_response_sec, high_acuity_ratio

### GET /api/staging

```python
@router.get("/staging")
def get_staging(
    # same params as heatmap
):
```

**Process:**

1. Get predicted_counts from demand_forecaster (same as heatmap)
2. Call staging_optimizer.compute_staging(predicted_counts, K=ambulances)
3. Return FeatureCollection of K Point features
4. If model not loaded: return MOCK_DATA["staging"]

**GeoJSON Point coordinates MUST be [longitude, latitude] — never reversed.**

**Response field names (EXACT):**
staging_index, coverage_radius_m (=3500), predicted_demand_coverage,
cluster_zones (array), zone_count

### GET /api/counterfactual

```python
@router.get("/counterfactual")
def get_counterfactual(
    hour: int = Query(..., ge=0, le=23),
    dow: int = Query(..., ge=0, le=6),
):
```

**Process:**

1. Filter counterfactual_summary DataFrame to row where hour==H and dayofweek==D
2. If counterfactual_raw available: compute by_borough and by_svi_quartile groupbys
3. Return full counterfactual object
4. If not loaded: return MOCK_DATA["counterfactual"]
   **Target: < 20ms response time (pure DataFrame lookup)**

**Borough key names (EXACT — note slash and spaces):**
"BRONX", "BROOKLYN", "MANHATTAN", "QUEENS", "RICHMOND / STATEN ISLAND"

### GET /api/historical/{zone}

```python
@router.get("/historical/{zone_code}")
def get_historical(zone_code: str):
```

**Validation:** if zone_code not in VALID_ZONES → 404
**Process:**

1. Look up zone_code in zone_stats DataFrame
2. Get hourly_avg: from baselines DataFrame, filter to this zone, average over all dow, sort by hour → list of 24 floats
3. Return full historical object
4. If not loaded: return MOCK_DATA["historical_zone"] (substitute zone_code in response)

**hourly_avg MUST be exactly 24 values.**

### GET /api/breakdown

```python
@router.get("/breakdown")
def get_breakdown():
```

**Process:**

1. Pre-compute at startup from zone_stats grouped by BOROUGH
2. Cache as module-level variable — never recompute at request time
3. Return list of 5 borough objects
4. If not loaded: return MOCK_DATA["breakdown"]
   **Target: < 10ms (cached)**

## PostGIS Setup

### Docker Run

```bash
docker run --name firstwave-db \
  -e POSTGRES_DB=firstwave \
  -e POSTGRES_USER=pp_user \
  -e POSTGRES_PASSWORD=pp_pass \
  -p 5432:5432 \
  -d postgis/postgis:15-3.4
```

### Zone Boundary Seeding

Since exact NYC EMS dispatch zone shapefiles are not publicly available, use circular polygons around zone centroids as a visual approximation. The seed script (`backend/scripts/seed_zone_boundaries.py`) does this using Shapely + psycopg2.

```python
# seed_zone_boundaries.py
from shapely.geometry import Point, mapping
from shapely import wkb
import psycopg2, json

ZONE_CENTROIDS = { ... }  # from CLAUDE.md
ZONE_NAMES = { ... }      # from CLAUDE.md
ZONE_SVI = { ... }        # from CLAUDE.md
BOROUGH_MAP = {'B':'BRONX','K':'BROOKLYN','M':'MANHATTAN','Q':'QUEENS','S':'RICHMOND / STATEN ISLAND'}
RADIUS = {'B':0.022,'K':0.020,'M':0.015,'Q':0.022,'S':0.025}  # degrees

for zone, (lon, lat) in ZONE_CENTROIDS.items():
    circle = Point(lon, lat).buffer(RADIUS[zone[0]])
    # insert as MultiPolygon into dispatch_zone_boundaries
```

### Geometry Caching

Load all 31 zone GeoJSON geometries into memory at startup — never query PostGIS per-request:

```python
ZONE_GEOM_CACHE = {}  # {zone_code: geojson_dict}

# In startup:
for zone in VALID_ZONES:
    result = db.execute("SELECT ST_AsGeoJSON(geom) FROM dispatch_zone_boundaries WHERE zone_code=%s", [zone])
    ZONE_GEOM_CACHE[zone] = json.loads(result.fetchone()[0])
```

## Response Time Budgets

```
/api/heatmap        < 300ms   (XGBoost inference + geometry assembly)
/api/staging        < 400ms   (heatmap + K-Means)
/api/counterfactual < 20ms    (DataFrame lookup)
/api/historical     < 20ms    (DataFrame lookup)
/api/breakdown      < 10ms    (pre-cached at startup)
```

## Error Handling Rules

1. **Never let an exception propagate to the client as a 500** — always catch and return mock with a warning header
2. Add `X-Data-Source: mock` header when returning mock data so frontend can display a subtle indicator
3. Validate all params with FastAPI Query constraints (ge=, le=) — FastAPI returns 422 automatically
4. Wrap all artifact-dependent code in `if ARTIFACTS["demand_model"] is not None:` checks

## Performance Optimizations

```python
from functools import lru_cache

@lru_cache(maxsize=168)  # 24 hours × 7 days
def get_staging_cached(hour: int, dow: int, month: int,
                        temperature: float, precipitation: float,
                        windspeed: float, ambulances: int):
    # K-Means is deterministic for same params — cache it
    ...
```

## VALID_ZONES (31 clean dispatch zones)

```python
VALID_ZONES = set([
    'B1','B2','B3','B4','B5',
    'K1','K2','K3','K4','K5','K6','K7',
    'M1','M2','M3','M4','M5','M6','M7','M8','M9',
    'Q1','Q2','Q3','Q4','Q5','Q6','Q7',
    'S1','S2','S3'
])
```

## Running the Server

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Test all endpoints:

```bash
BASE="http://localhost:8000"
PARAMS="hour=20&dow=4&month=10&temperature=15&precipitation=0&windspeed=10&ambulances=5"
curl "$BASE/health"
curl "$BASE/api/heatmap?$PARAMS"
curl "$BASE/api/staging?$PARAMS"
curl "$BASE/api/counterfactual?hour=20&dow=4"
curl "$BASE/api/historical/B2"
curl "$BASE/api/breakdown"
```

All should return 200. Check `/health` to see which artifacts are loaded.
When Praneel drops a new artifact: `curl -X POST $BASE/reload` to hot-reload.
