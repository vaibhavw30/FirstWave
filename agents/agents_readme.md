# FirstWave — Subagents Directory

## How to Use These Files

Each `.md` file in this folder is a **Claude Code subagent**. To use one, tell Claude Code:

```
Use the [agent-name] agent. [your task]
```

Or reference it directly:

```
Read agents/machine-learning.md and then train the XGBoost model on the aggregated table.
```

Every agent already knows the project context, data schemas, exact field names, and expected outputs. You do not need to re-explain the project — just describe what you need done.

---

## Agent Map

| Agent File             | What It Covers                                                         | Who Uses It      |
| ---------------------- | ---------------------------------------------------------------------- | ---------------- |
| `frontend-ui.md`       | React components, Mapbox layers, Plotly charts, Tailwind styling       | **Vaibhav only** |
| `frontend-data.md`     | Hooks, API calls, mock data, USE_MOCK_DATA flag, App.jsx state         | **Vaibhav only** |
| `backend-api.md`       | FastAPI routing, request validation, CORS, PostGIS, /health, /reload   | **Ashwin only**  |
| `backend-inference.md` | XGBoost inference wrapper, K-Means staging logic inside backend        | **Ashwin only**  |
| `data-pipeline.md`     | Databricks Notebooks 01–04: clean, weather, SVI, aggregate             | **Praneel only** |
| `machine-learning.md`  | Databricks Notebook 05: XGBoost training, MLflow, validation           | **Praneel only** |
| `osmnx-routing.md`     | Databricks Notebook 06: NYC road network, drive-time matrix            | **Praneel only** |
| `counterfactual.md`    | Databricks Notebooks 07–08: staging validation, impact pre-computation | **Praneel only** |

---

## Vaibhav's Agents (Frontend)

You use **two agents** that divide cleanly between visuals and data.

### When to use `frontend-ui`

For anything you can see — building a component, styling it, adding a Mapbox layer, wiring a Plotly chart, fixing a layout issue.

**Examples:**

- "Build ZoneChoropleth.jsx"
- "The coverage circles are the wrong color"
- "Add a ZoneDetailPanel that opens when I click a zone"
- "The ImpactPanel layout is broken on 1280×800"
- "Style the TimeSlider to show hour labels at 6AM, 12PM, 6PM"

### When to use `frontend-data`

For anything that touches data flow — hooks, API calls, mock data, debouncing, state management, or the integration sprint.

**Examples:**

- "Build useHeatmap.js with React Query"
- "Wire the TimeSlider debounce so the API doesn't get called on every pixel"
- "I flipped USE_MOCK_DATA to false and now normalized_intensity is undefined"
- "Set up the App.jsx state shape for all 4 controls"
- "The counterfactual hook is refetching every time the slider moves — fix it"

### Quick Reference — Which Agent?

| Task                              | Agent         |
| --------------------------------- | ------------- |
| Building a .jsx component         | frontend-ui   |
| Styling with Tailwind             | frontend-ui   |
| Mapbox layer (fill, line, circle) | frontend-ui   |
| Plotly chart (histogram, bar)     | frontend-ui   |
| React hook (useHeatmap, etc.)     | frontend-data |
| constants.js / API_BASE_URL       | frontend-data |
| Debouncing slider inputs          | frontend-data |
| Wiring controls to API params     | frontend-data |
| Integration sprint debugging      | frontend-data |

---

## Ashwin's Agents (Backend)

You use **two agents** that divide between HTTP concerns and ML inference concerns.

### When to use `backend-api`

For anything FastAPI — defining routes, validating query params, formatting responses, PostGIS queries, CORS setup, error handling, the /health and /reload endpoints.

**Examples:**

- "Scaffold all 5 endpoints returning mock data"
- "Add CORS for localhost:3000"
- "Write the startup artifact loading function with graceful fallback"
- "The /api/historical endpoint is returning 404 for valid zones"
- "Seed zone boundaries into PostGIS using circular approximations"
- "Add lru_cache to /api/staging"

### When to use `backend-inference`

For the ML inference logic inside `backend/models/` — how feature vectors are built at inference time, how XGBoost predict is called, how K-Means is run, how predictions are normalized.

**Examples:**

- "Build demand_forecaster.py — predict_all_zones function"
- "The inference is taking 800ms — diagnose and fix"
- "Write staging_optimizer.py with weighted K-Means"
- "The normalized_intensity values are all coming back as 1.0 — fix normalization"
- "Write a standalone validation script that confirms top zones on Friday 8PM are in the Bronx"

### Quick Reference — Which Agent?

| Task                                  | Agent             |
| ------------------------------------- | ----------------- |
| FastAPI route definition              | backend-api       |
| Query param validation                | backend-api       |
| Response JSON shape                   | backend-api       |
| CORS / middleware                     | backend-api       |
| PostGIS setup / seeding               | backend-api       |
| /health and /reload                   | backend-api       |
| Error handling (try/except)           | backend-api       |
| `demand_forecaster.py`                | backend-inference |
| `staging_optimizer.py`                | backend-inference |
| Building the 31-row feature DataFrame | backend-inference |
| XGBoost batch predict                 | backend-inference |
| K-Means staging logic                 | backend-inference |
| Inference performance tuning          | backend-inference |

---

## Praneel's Agents (Pipeline)

You use **four agents** — one per phase of the pipeline. Run them in order.

### Notebook Order + Agent Map

```
Notebook 01 → 02 → 03 → 04     data-pipeline agent
Notebook 05                     machine-learning agent
Notebook 06                     osmnx-routing agent   ← RUN THIS PRE-HACKATHON
Notebook 07 → 08                counterfactual agent
```

### When to use `data-pipeline`

For everything that cleans and shapes the raw data — reading the 28.7M row CSV, applying quality filters, building datetime features, merging weather, joining SVI, aggregating to hourly zone-level, and writing Delta tables and parquets.

**Covers:** Notebooks 01, 02, 03, 04

**Examples:**

- "Write Notebook 01 — filter the raw CSV to 31 dispatch zones"
- "The weather merge is leaving 3% null rows — fix the join"
- "zone_baselines.parquet only has 800 rows instead of 5,208 — what's wrong"
- "Notebook 04 is failing on the dayofweek aggregation"

### When to use `machine-learning`

For training the XGBoost demand forecaster, MLflow logging, per-borough validation, and serializing the final model.

**Covers:** Notebook 05

**Examples:**

- "Write Notebook 05 — train XGBoost with MLflow tracking"
- "RMSE is 7.2 — how do I diagnose why zone_baseline_avg isn't helping"
- "Add per-borough RMSE metrics to the MLflow run"
- "The model is predicting negative values in some zones"
- "Write a script to download demand_model.pkl from DBFS to backend/artifacts/"

### When to use `osmnx-routing`

For the drive-time matrix computation using the NYC road network. **Run this before the hackathon starts** — it takes 30–60 minutes.

**Covers:** Notebook 06

**Examples:**

- "Write Notebook 06 — download NYC graph and compute drive-time matrix"
- "Some zone pairs are returning 9999 — how do I debug disconnected nodes"
- "The graph download is failing — how do I cache it to DBFS to avoid re-downloading"
- "Build the Haversine fallback matrix in case OSMnx fails"

### When to use `counterfactual`

For validating that staging makes geographic sense and pre-computing the before/after impact numbers for all 168 hour×dow combinations.

**Covers:** Notebooks 07, 08

**Examples:**

- "Write Notebook 08 — compute pct_within_8min_static vs staged for all 168 bins"
- "The counterfactual shows only 3% improvement — how do I debug the staging zones"
- "Write the validation checks in Notebook 07 for Monday 4AM and Friday 8PM"
- "Generate the by_borough and by_svi_quartile breakdown tables"

### Quick Reference — Which Agent?

| Task                                      | Agent            | Notebook |
| ----------------------------------------- | ---------------- | -------- |
| Reading + filtering raw CSV               | data-pipeline    | 01       |
| Weather merge (Open-Meteo)                | data-pipeline    | 02       |
| SVI join                                  | data-pipeline    | 03       |
| Aggregation + zone_baselines + zone_stats | data-pipeline    | 04       |
| XGBoost training + MLflow                 | machine-learning | 05       |
| NYC road network + drive-time matrix      | osmnx-routing    | 06       |
| Staging optimizer validation              | counterfactual   | 07       |
| Counterfactual simulation (168 bins)      | counterfactual   | 08       |

---

## Dependency Order (critical)

```
Ansh commits ems_stations.json
       ↓
Praneel copies ems_stations.json to DBFS
       ↓
data-pipeline (Notebooks 01–04 complete)
       ↓
machine-learning (Notebook 05) + osmnx-routing (Notebook 06)  ← parallel
       ↓
machine-learning delivers demand_model.pkl + zone_baselines + zone_stats
       ↓
Ashwin: merge PR → POST /reload → real /api/heatmap and /api/staging live
       ↓
counterfactual (Notebooks 07–08, needs demand_model.pkl + drive_time_matrix.pkl)
       ↓
counterfactual delivers counterfactual_summary.parquet + counterfactual_raw.parquet
       ↓
Ashwin: merge PR → POST /reload → real /api/counterfactual live
       ↓
Vaibhav: USE_MOCK_DATA = false → full integration
```

---

## Key Numbers to Know (context for all agents)

| Fact                          | Value                     |
| ----------------------------- | ------------------------- |
| Dataset size                  | 28.7M rows                |
| Training rows (after filters) | ~5.6M                     |
| Clean dispatch zones          | 31                        |
| Bronx avg response            | 638 sec (10.6 min)        |
| Clinical threshold            | 480 sec (8 min)           |
| High-acuity share             | 23.1% of incidents        |
| Expected RMSE                 | < 4.0 incidents/zone/hour |
| Expected improvement          | ~61% → ~83% within 8 min  |
| Expected median saved         | ~147 sec (2 min 27 sec)   |

---

## Starting a Claude Code Session

```bash
# Always run /init first — it reads CLAUDE.md automatically
cd ~/firstwave-[your-module]
claude
# Then: /init

# Tell Claude which agent to use:
"Read agents/frontend-ui.md and build ZoneChoropleth.jsx"
"Read agents/machine-learning.md and train the XGBoost model"
"Read agents/backend-api.md and scaffold all 5 mock endpoints"
```

---

## Agent Files At A Glance

```
agents/
├── README.md                ← this file — start here
├── frontend-ui.md           ← Vaibhav: React components + Mapbox + Plotly
├── frontend-data.md         ← Vaibhav: hooks + API integration + mock data
├── backend-api.md           ← Ashwin: FastAPI routes + PostGIS + CORS
├── backend-inference.md     ← Ashwin: XGBoost inference + K-Means (backend/models/)
├── data-pipeline.md         ← Praneel: Notebooks 01–04 (clean, weather, SVI, agg)
├── machine-learning.md      ← Praneel: Notebook 05 (XGBoost training + MLflow)
├── osmnx-routing.md         ← Praneel: Notebook 06 (drive-time matrix — PRE-HACKATHON)
└── counterfactual.md        ← Praneel: Notebooks 07–08 (impact simulation)
```
