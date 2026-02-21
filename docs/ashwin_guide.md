# Ashwin's Personal Guide — PulsePoint

## Role: Backend Lead

## Tool: Claude Pro + GitHub Integration (`cd ~/pulsepoint-backend && claude`)

---

## Your Job in One Sentence

You build the entire FastAPI server — all 5 endpoints, model inference, database connections, and artifact loading. You are the bridge between Praneel's ML models and Vaibhav's frontend.

## What You Own

- `backend/` directory — entirely yours, nobody else touches it
- `data/mock_api_responses.json` — you write this in Hour 0 and it becomes the integration contract
- Performance of all API responses (every endpoint must be < 500ms)

## What You Do NOT Touch

- `frontend/` — that's Vaibhav's
- `databricks_notebooks/` — that's Praneel's
- `data/ems_stations.json` — that's Ansh's

## Your Two Most Important Moments

1. **Hour 0:** Write `mock_api_responses.json` with exact field names. This contract can never change — both Vaibhav's frontend and Praneel's test script depend on it.
2. **Hour ~10:** Praneel commits `demand_model.pkl` to `backend/artifacts/`. Wire it into `/api/heatmap` immediately. This is the moment the whole system becomes real.

---

## Pre-Hackathon Checklist

- [ ] Python 3.11+ installed: `python3 --version`
- [ ] Docker installed (for PostGIS): `docker --version`
- [ ] Claude Code installed: `npm install -g @anthropic-ai/claude-code`
- [ ] Connect Claude Pro to GitHub: in Claude Code, Settings → Integrations → GitHub → Authorize
- [ ] Clone the repo into your worktree (Vaibhav sets this up):

```bash
git clone https://github.com/yourteam/pulsepoint.git
cd pulsepoint
git checkout feat/backend
```

- [ ] Understand the 5 API endpoints cold — read them in CLAUDE.md before writing a line

---

## Hour 0 — Your First Task (30 minutes)

Before Vaibhav can write a single React component, he needs `mock_api_responses.json`. This is your very first task.

Create `data/mock_api_responses.json`:

```json
{
  "heatmap": {
    "type": "FeatureCollection",
    "query_params": { "hour": 20, "dow": 4, "month": 10 },
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
        "geometry": { "type": "MultiPolygon", "coordinates": [] }
      },
      {
        "type": "Feature",
        "properties": {
          "zone": "K4",
          "borough": "BROOKLYN",
          "zone_name": "East New York",
          "predicted_count": 14.1,
          "normalized_intensity": 0.71,
          "svi_score": 0.84,
          "historical_avg_response_sec": 581,
          "high_acuity_ratio": 0.24
        },
        "geometry": { "type": "MultiPolygon", "coordinates": [] }
      }
    ]
  },
  "staging": {
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
      },
      {
        "type": "Feature",
        "properties": {
          "staging_index": 1,
          "coverage_radius_m": 3500,
          "predicted_demand_coverage": 24.8,
          "cluster_zones": ["K3", "K4"],
          "zone_count": 2
        },
        "geometry": { "type": "Point", "coordinates": [-73.9075, 40.6929] }
      }
    ]
  },
  "counterfactual": {
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
    "histogram_baseline_seconds": [
      320, 480, 520, 610, 390, 720, 445, 510, 580, 630, 490, 560, 680, 420, 370
    ],
    "histogram_staged_seconds": [
      210, 310, 380, 440, 290, 510, 335, 390, 420, 480, 360, 410, 520, 310, 280
    ]
  },
  "historical_zone": {
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
  },
  "breakdown": [
    {
      "name": "BRONX",
      "avg_dispatch_seconds": 243,
      "avg_travel_seconds": 395,
      "avg_total_seconds": 638,
      "pct_held": 9.1,
      "high_acuity_ratio": 0.28,
      "zones": ["B1", "B2", "B3", "B4", "B5"]
    },
    {
      "name": "BROOKLYN",
      "avg_dispatch_seconds": 198,
      "avg_travel_seconds": 366,
      "avg_total_seconds": 564,
      "pct_held": 6.2,
      "high_acuity_ratio": 0.23,
      "zones": ["K1", "K2", "K3", "K4", "K5", "K6", "K7"]
    }
  ]
}
```

**Commit this immediately:**

```bash
git add data/mock_api_responses.json
git commit -m "feat: mock_api_responses.json — integration contract for all 5 endpoints"
git push origin feat/backend
```

Tell the team in group chat: `mock_api_responses.json committed. Field names are FROZEN. Check before building against them.`

---

## Your Claude Code Setup

```bash
cd ~/pulsepoint-backend
claude
```

First session:

```
/init
Read CLAUDE.md for full project context. I'm building the FastAPI backend.
My module is backend/ only. Set up the directory structure:
backend/
├── main.py
├── routers/
│   ├── heatmap.py
│   ├── staging.py
│   ├── counterfactual.py
│   ├── historical.py
│   └── breakdown.py
├── models/
│   ├── demand_forecaster.py
│   └── staging_optimizer.py
├── artifacts/           (empty dir, artifacts go here)
├── requirements.txt
└── .env

Create requirements.txt with:
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

Create .env:
DATABASE_URL=postgresql://pp_user:pp_pass@localhost:5432/pulsepoint
ARTIFACTS_DIR=./artifacts
```

---

## Phase 1: Foundation (Hours 0–6)

### Step 1 — PostGIS Running (Hour 0–1)

```bash
docker run --name pulsepoint-db \
  -e POSTGRES_DB=pulsepoint \
  -e POSTGRES_USER=pp_user \
  -e POSTGRES_PASSWORD=pp_pass \
  -p 5432:5432 \
  -d postgis/postgis:15-3.4
```

Verify it's running: `docker ps` — should show `pulsepoint-db` as Up.

Connect to it:

```bash
docker exec -it pulsepoint-db psql -U pp_user -d pulsepoint
```

```sql
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS dispatch_zone_boundaries (
    zone_code       VARCHAR(3) PRIMARY KEY,
    zone_name       VARCHAR(100),
    borough         VARCHAR(30),
    svi_score       FLOAT,
    centroid_lat    FLOAT,
    centroid_lon    FLOAT,
    geom            GEOMETRY(MultiPolygon, 4326)
);

CREATE INDEX IF NOT EXISTS idx_dzb_geom ON dispatch_zone_boundaries USING GIST (geom);
```

**Note on zone geometries:** Getting the actual NYC EMS dispatch zone boundary polygons is hard — they're not a standard public dataset. Use this fallback approach: generate circular polygons around each zone centroid using PostGIS `ST_Buffer`. These won't be exact zone boundaries but they'll look correct on the map and the demo will work fine.

Ask Claude Code:

```
Write a script backend/scripts/seed_zone_boundaries.py that:
1. Takes the ZONE_CENTROIDS from CLAUDE.md (all 31 zones)
2. For each zone, creates a circular polygon using Shapely's Point.buffer()
   with a radius appropriate to the zone's geographic scale:
   - Bronx/Brooklyn/Queens/SI zones: 0.02 degrees (~2km radius)
   - Manhattan zones: 0.015 degrees (smaller, denser)
3. Inserts each zone as a MultiPolygon into dispatch_zone_boundaries
   with zone_code, zone_name (from ZONE_NAMES), borough, svi_score,
   centroid_lat, centroid_lon
4. Uses psycopg2 and shapely.wkb for geometry serialization
Run once at setup time.
```

Run it: `python scripts/seed_zone_boundaries.py`

### Step 2 — Mock FastAPI Server (Hour 1–4)

Ask Claude Code:

```
Build the complete FastAPI application with all 5 endpoints returning mock data.
The mock data is in data/mock_api_responses.json — load it at startup.

main.py structure:
- FastAPI app with title "PulsePoint API v2.0"
- CORS middleware: allow_origins=["http://localhost:3000"], allow_methods=["*"], allow_headers=["*"]
- Include all 5 routers with prefix /api
- Startup event: load mock_api_responses.json into a global MOCK_DATA dict
- Health check endpoint: GET /health → {"status": "ok", "model_loaded": false}

For each endpoint, for now return the corresponding mock data from MOCK_DATA.
Do not implement real inference yet — that comes when artifacts are available.

Query params for heatmap and staging:
  hour: int (0-23), dow: int (0-6), month: int (1-12)
  temperature: float (default 15.0), precipitation: float (default 0.0)
  windspeed: float (default 10.0), ambulances: int (default 5, min 1 max 10)

Add 422 validation for out-of-range params (hour > 23, etc.)
```

Test it:

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

```bash
curl http://localhost:8000/health
curl "http://localhost:8000/api/heatmap?hour=20&dow=4&month=10&temperature=15&precipitation=0&windspeed=10&ambulances=5"
curl "http://localhost:8000/api/counterfactual?hour=20&dow=4"
curl "http://localhost:8000/api/historical/B2"
curl "http://localhost:8000/api/breakdown"
```

All should return 200 with JSON. Post in group chat: `backend READY: all 5 endpoints live on localhost:8000 returning mock data`

### Step 3 — Startup Artifact Loading (Hour 4–6)

Ask Claude Code:

```
Add artifact loading to main.py startup event.
The artifacts are in backend/artifacts/ (they arrive from Praneel during the hackathon).
Load them into module-level globals with graceful fallback.

ARTIFACTS_STATE should track what's loaded:
  demand_model: None  ← loaded from demand_model.pkl
  drive_time:   None  ← loaded from drive_time_matrix.pkl
  baselines:    None  ← loaded from zone_baselines.parquet
  zone_stats:   None  ← loaded from zone_stats.parquet
  counterfactual: None ← loaded from counterfactual_summary.parquet

For each artifact: try to load it, log success or "artifact not yet available — using mock"
If an artifact is missing, endpoints fall back to mock data (don't crash).

Update GET /health to show which artifacts are loaded:
{
  "status": "ok",
  "artifacts": {
    "demand_model": true/false,
    "drive_time": true/false,
    ...
  }
}

Add a POST /reload endpoint (no auth needed for hackathon) that re-runs the artifact loading.
This lets Praneel drop a new pkl file and we reload without restarting the server.
```

---

## Phase 2: Real Model Inference (Hours 6–20)

### Step 4 — /api/heatmap Real Inference (Do this the moment demand_model.pkl lands)

Watch for Praneel's message: `demand_model.pkl AVAILABLE: backend/artifacts/demand_model.pkl`

When you see it, hit `POST /reload` or restart uvicorn, verify `/health` shows `demand_model: true`, then:

Ask Claude Code:

```
Wire real XGBoost inference into backend/routers/heatmap.py.

The model is loaded at startup as ARTIFACTS_STATE["demand_model"].
FEATURE_COLS from CLAUDE.md:
["hour_sin","hour_cos","dow_sin","dow_cos","month_sin","month_cos",
 "is_weekend","temperature_2m","precipitation","windspeed_10m",
 "is_severe_weather","svi_score","zone_baseline_avg","high_acuity_ratio","held_ratio"]

ZONE_CENTROIDS from CLAUDE.md (all 31 zones, lon/lat pairs).

For the heatmap endpoint:
1. Build a pandas DataFrame with one row per zone (31 rows)
2. Compute cyclical features: hour_sin=sin(2π×hour/24), hour_cos, dow_sin, dow_cos, month_sin, month_cos
3. is_weekend: 1 if dow in [5,6] else 0
4. is_severe_weather: 1 if precipitation > 5 else 0
5. Look up svi_score, high_acuity_ratio, held_ratio from ARTIFACTS_STATE["zone_stats"]
   (keyed by zone_code) — fallback to SVI_DEFAULTS dict if zone_stats not loaded
6. Look up zone_baseline_avg from ARTIFACTS_STATE["baselines"]
   (keyed by (zone_code, hour, dow)) — fallback to 5.0 if not found
7. Run model.predict(features_df) in a single batch — must be < 200ms
8. Clip negatives to 0
9. Normalize: normalized = (val - min) / (max - min), avoid div by zero
10. Query PostGIS for zone boundary geometries
11. Build GeoJSON FeatureCollection with predicted_count, normalized_intensity,
    svi_score, historical_avg_response_sec, high_acuity_ratio per zone

If ARTIFACTS_STATE["demand_model"] is None: return MOCK_DATA["heatmap"] with a
response header X-Data-Source: mock
```

SVI defaults to use if zone_stats artifact isn't loaded:

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

Test the timing:

```bash
time curl "http://localhost:8000/api/heatmap?hour=20&dow=4&month=10&temperature=15&precipitation=0&windspeed=10&ambulances=5"
```

Must be under 500ms total. XGBoost inference on 31 rows should be ~20–50ms. If it's slow, the bottleneck is PostGIS — add a cache for zone geometries.

### Step 5 — /api/staging (Hour 10–14)

Ask Claude Code:

```
Implement the staging endpoint in backend/routers/staging.py.

Input: same params as heatmap, plus ambulances=K.
Process:
1. Call heatmap logic to get predicted_counts dict {zone: count} for all 31 zones
2. Run weighted K-Means staging in backend/models/staging_optimizer.py:

class StagingOptimizer:
    ZONE_CENTROIDS = { ... all 31 zones ... }

    def compute_staging(self, predicted_counts: dict, K: int) -> list:
        zones = list(predicted_counts.keys())
        weights = np.array([max(predicted_counts[z], 0.01) for z in zones])
        coords = np.array([[self.ZONE_CENTROIDS[z][1], self.ZONE_CENTROIDS[z][0]]
                           for z in zones])  # [lat, lon]

        kmeans = KMeans(n_clusters=K, random_state=42, n_init=20)
        kmeans.fit(coords, sample_weight=weights)

        results = []
        for i, center in enumerate(kmeans.cluster_centers_):
            lat, lon = center
            cluster_zones = [zones[j] for j, l in enumerate(kmeans.labels_) if l==i]
            demand = sum(predicted_counts[z] for z in cluster_zones)
            results.append({
                "staging_index": i,
                "lat": lat, "lon": lon,
                "coverage_radius_m": 3500,
                "predicted_demand_coverage": round(demand, 1),
                "cluster_zones": cluster_zones,
                "zone_count": len(cluster_zones)
            })
        return results

3. Return as GeoJSON FeatureCollection (Point geometry for each staging location)

Cache the K-Means results: same params = same result. Use functools.lru_cache
on the tuple (hour, dow, month, temperature, precipitation, windspeed, ambulances).
```

### Step 6 — /api/counterfactual (Hour 14–16)

Watch for Praneel's message: `counterfactual_summary.parquet AVAILABLE`

Ask Claude Code:

```
Implement /api/counterfactual in backend/routers/counterfactual.py.

ARTIFACTS_STATE["counterfactual"] is a pandas DataFrame loaded from
counterfactual_summary.parquet. Columns:
hour, dayofweek, median_seconds_saved, pct_within_8min_static,
pct_within_8min_staged, n_incidents

Also load counterfactual_raw.parquet (if available) to compute
by_borough and by_svi_quartile breakdowns.

For GET /api/counterfactual?hour=H&dow=D:
1. Filter summary DataFrame to matching row
2. If counterfactual_raw is available, filter to (hour=H, dayofweek=D),
   compute by_borough aggregations, by_svi_quartile aggregations,
   and histogram arrays (convert seconds to int for histogram)
3. Return the full response shape from CLAUDE.md
4. If no raw data: return summary row + by_borough/quartile from MOCK_DATA as fallback

Response must be < 10ms (pure DataFrame lookup, no computation at request time).
```

### Step 7 — /api/historical + /api/breakdown (Hour 16–18)

Ask Claude Code:

```
Implement the remaining two endpoints.

/api/historical/{zone}:
- Look up zone_code in ARTIFACTS_STATE["zone_stats"]
- zone_stats has columns: zone_code, borough, svi_score, avg_response_seconds,
  avg_travel_seconds, avg_dispatch_seconds, high_acuity_ratio, held_ratio
- Also need hourly_avg: the avg incident count for each hour 0-23 for this zone
  This comes from zone_baselines grouped by zone+hour (average over all dow)
- Return the historical_zone shape from CLAUDE.md
- 404 if zone not in VALID_ZONES

/api/breakdown:
- Group zone_stats by borough
- For each borough: avg the response time components, sum zones list
- Return array of 5 borough dicts (the breakdown shape from CLAUDE.md)
- This is a startup-time computation — compute once, cache forever
```

---

## Phase 3: Hardening (Hours 18–22)

### Step 8 — Performance Validation (Hour 18–20)

Run this timing test against every endpoint and make sure all are under budget:

```bash
for endpoint in \
  "heatmap?hour=20&dow=4&month=10&temperature=15&precipitation=0&windspeed=10&ambulances=5" \
  "staging?hour=20&dow=4&month=10&temperature=15&precipitation=0&windspeed=10&ambulances=5" \
  "counterfactual?hour=20&dow=4" \
  "historical/B2" \
  "breakdown"
do
  echo -n "/api/$endpoint: "
  time curl -s "http://localhost:8000/api/$endpoint" > /dev/null
done
```

**Budget per endpoint:**

- `/api/heatmap`: < 300ms (XGBoost + PostGIS query)
- `/api/staging`: < 400ms (includes heatmap computation + K-Means)
- `/api/counterfactual`: < 20ms (Parquet lookup)
- `/api/historical`: < 20ms (DataFrame lookup)
- `/api/breakdown`: < 10ms (cached at startup)

If `/api/heatmap` is slow, add geometry caching:

```python
# In startup: load all 31 zone geometries into memory once
ZONE_GEOM_CACHE = {}  # {zone_code: geojson_dict}
```

If `/api/staging` is slow, it's the K-Means. Add `lru_cache`:

```python
from functools import lru_cache

@lru_cache(maxsize=168)  # 24 hours × 7 days
def get_staging_cached(hour, dow, month, temp, precip, wind, ambulances):
    ...
```

### Step 9 — Error Handling (Hour 20–22)

Ask Claude Code:

```
Add proper error handling throughout the backend:

1. FastAPI exception handlers:
   - 422 Unprocessable Entity: invalid param values (hour > 23, etc.)
   - 404 Not Found: invalid zone code in /api/historical/{zone}
   - 500 Internal Server Error: catch-all with logged traceback, return
     {"error": "Internal error", "detail": str(e)} — never expose raw tracebacks

2. All endpoints: if artifact is None (not yet loaded), return mock data
   with response header X-Data-Source: mock so Vaibhav can detect it

3. Timeout protection: wrap model inference in a 5-second timeout
   (in case something hangs — shouldn't happen but safe for demo)

4. Startup validation: after loading each artifact, run a quick sanity check
   (model.predict on 1 dummy row, parquet row count > 0, etc.)
   Log results at startup so we know immediately if something is corrupt
```

---

## Phase 4: Integration Testing (Hours 22–24)

### Step 10 — Full Integration Test

When Vaibhav flips `USE_MOCK_DATA = false`, be available in group chat to fix anything immediately.

**Run the integration test:**

```bash
python3 -c "
import requests, json

BASE = 'http://localhost:8000'
PARAMS = 'hour=20&dow=4&month=10&temperature=15&precipitation=0&windspeed=10&ambulances=5'
tests = [
    ('GET', f'/api/heatmap?{PARAMS}', lambda r: r['features'] and len(r['features']) > 0),
    ('GET', f'/api/staging?{PARAMS}', lambda r: r['features'] and len(r['features']) == 5),
    ('GET', '/api/counterfactual?hour=20&dow=4', lambda r: 'pct_within_8min_static' in r),
    ('GET', '/api/historical/B2', lambda r: len(r['hourly_avg']) == 24),
    ('GET', '/api/breakdown', lambda r: len(r) == 5),
]
for method, path, validator in tests:
    r = requests.get(BASE + path, timeout=5)
    data = r.json()
    ok = r.status_code == 200 and validator(data)
    icon = '✓' if ok else '✗'
    ms = r.elapsed.total_seconds() * 1000
    print(f'{icon} {path[:40]}: {r.status_code} ({ms:.0f}ms)')
    if not ok:
        print(f'  FAIL: {json.dumps(data)[:200]}')
"
```

All 5 must pass. Any failure, fix immediately.

**Common integration issues:**

- Vaibhav sees `normalized_intensity is undefined`: check your heatmap serializer is including this field for every feature
- Vaibhav sees CORS error: make sure `allow_origins=["http://localhost:3000"]` is in your CORS middleware — not `*` (some browsers block wildcard for credentialed requests)
- Vaibhav's staging circles have wrong positions: check your GeoJSON Point coordinates are `[lon, lat]` not `[lat, lon]`
- Vaibhav's impact panel shows NaN: counterfactual `by_borough` keys must exactly match `"BRONX"`, `"BROOKLYN"`, `"MANHATTAN"`, `"QUEENS"`, `"RICHMOND / STATEN ISLAND"` (with the slash)

---

## How to Use Claude Pro + GitHub Integration

### Setup

```bash
# In Claude Code session:
/github connect
# Follow OAuth flow
```

### Automated PR after each feature

Instead of doing git commands manually, say to Claude Code:

```
Feature complete: /api/heatmap is wired with real XGBoost inference,
tested and returning correct GeoJSON with 31 zones, response time < 250ms.
Commit all changes in backend/ with message 'feat: real XGBoost inference
in /api/heatmap — closes #14'. Push to feat/backend. Open a PR to main
titled 'Backend: real heatmap inference (#14)' with the backend label.
```

Claude Code runs `git add backend/`, `git commit`, `git push`, and opens the PR. Ansh gets a notification and approves within 10 minutes.

### Commit Schedule

Commit every 45–60 minutes even if a feature isn't done:

```
"Commit current state of backend/ with message 'wip: [what's in progress]
— working on #[issue]'. Push to feat/backend."
```

### PR Schedule

| Hour | PR Contents                                  | Closes   |
| ---- | -------------------------------------------- | -------- |
| 4    | Mock endpoints + PostGIS running             | #11, #12 |
| 8    | Startup artifact loading + graceful fallback | #13      |
| 12   | /api/heatmap real inference                  | #14      |
| 16   | /api/staging K-Means                         | #15      |
| 18   | /api/counterfactual Parquet                  | #16      |
| 20   | /api/historical + /api/breakdown             | #17      |
| 22   | Error handling + perf validation             | #18      |

---

## Group Chat Communication Rules

| When                              | Message                                                                                   |
| --------------------------------- | ----------------------------------------------------------------------------------------- |
| mock_api_responses.json committed | `mock_api_responses.json COMMITTED. Field names frozen. Check before building.`           |
| All mock endpoints live           | `backend READY: all 5 endpoints on localhost:8000, returns mock data. Vaibhav can start.` |
| Need artifact from Praneel        | `BLOCKED: Praneel — need demand_model.pkl in backend/artifacts/`                          |
| Artifact received + wired         | `backend: /api/heatmap real inference live, tested. POST /reload to pick it up.`          |
| Counterfactual wired              | `backend: /api/counterfactual showing real numbers. Impact panel can use real data.`      |
| Ready for integration             | `backend: all 5 endpoints real data, all < 500ms. Vaibhav: flip USE_MOCK_DATA=false`      |

---

## If Things Go Wrong

**Model inference is slow (> 1 second):**

1. Check if you're rebuilding the feature DataFrame on every request — cache the zone_stats and baselines DataFrames at startup
2. Check if PostGIS geometry query is running on every request — add geometry cache at startup
3. If still slow: switch heatmap to return mock data for the demo, fix after

**Parquet files corrupt or wrong schema:**
Tell Praneel in chat: "counterfactual_summary.parquet is missing column [X]. Can you re-export?"
Meanwhile use mock counterfactual data.

**PostGIS not running:**

```bash
docker start pulsepoint-db
```

If the container is gone:

```bash
docker run --name pulsepoint-db \
  -e POSTGRES_DB=pulsepoint -e POSTGRES_USER=pp_user \
  -e POSTGRES_PASSWORD=pp_pass -p 5432:5432 \
  -d postgis/postgis:15-3.4
# Then re-run seed script
python scripts/seed_zone_boundaries.py
```

**All else fails — demo fallback:**
Every endpoint has a fallback to mock data. If nothing works, restart uvicorn and hit `POST /reload`. The mock data will serve a perfectly functional demo.

---

## Your Hour-by-Hour Summary

| Hour  | Task                                                                  | Closes   |
| ----- | --------------------------------------------------------------------- | -------- |
| 0     | mock_api_responses.json, PostGIS running                              | —        |
| 0–4   | FastAPI skeleton + all 5 mock endpoints                               | #11, #12 |
| 4–6   | Startup artifact loading + graceful fallback                          | #13      |
| 6–10  | WAITING: Praneel's demand_model.pkl → wire /api/heatmap when it lands | —        |
| 10–14 | /api/heatmap real inference + /api/staging K-Means                    | #14, #15 |
| 14–16 | /api/counterfactual Parquet cache                                     | #16      |
| 16–18 | /api/historical/{zone} + /api/breakdown                               | #17      |
| 18–22 | Error handling, performance validation, all endpoints < 500ms         | #18      |
| 22–24 | Integration support: fix Vaibhav's CORS/field name issues             | —        |
| 24–30 | API stable, support team on any issues, pitch prep                    | —        |
