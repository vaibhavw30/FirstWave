# Lag Features + Retrain on 2022–2026 — Design

**Date:** 2026-09-28
**Branch:** `feat/lag-features`
**Status:** Approved in conversation; awaiting written-spec review
**Scope owner:** Vaibhav (explicitly authorized edits to `pipeline/`, `backend/`, `frontend/`)

## 1. Goal

Replace the current demand model — which sees only calendar, weather, and static zone
features, and is trained on a month-summed label — with a **1-hour-ahead forecaster
that uses recent history (lag features)**, trained and evaluated on recent data
(2022–2026). Serve it through a **replay-by-date** API so the dashboard can show
predicted vs. actual demand for any hour from 2025-01-01 to 2026-06-30.

### Success criteria

1. Training table is at (zone, date, hour) grain, gap-free, with zero-count hours.
2. Every lag feature is strictly past-only (verified by tests, §7).
3. On the 2025 test year, the lag model is compared against three references
   (§5.3). Results are reported honestly whether or not lags help.
4. **Deployment gate:** the new model replaces `demand_model.pkl` only if its 2025
   RMSE beats the same-grain no-lag model by ≥ 2%. Otherwise, stop and report
   before touching the backend artifacts.
5. Backend serves `/api/heatmap` and `/api/staging` with an optional `date` param,
   stays backward compatible without it, and never crashes (mock fallback preserved).
6. Frontend replays a chosen date + hour and shows predicted vs. actual per zone.

### Non-goals

- A live CAD / real-time feed (the public dataset publishes ~3 months late).
- New model families (LightGBM, deep models) or hyperparameter search beyond §5.3.
- Changes to the drive-time matrix (script 06) or the staging algorithm itself.

## 2. Facts this design relies on (verified 2026-09-28 against live Socrata)

| Fact | Value |
|---|---|
| Dataset range | 2005-01-01 → 2026-06-30 |
| Incidents 2022 / 2023 / 2024 / 2025 / 2026-H1 | 1.58M / 1.62M / 1.63M / 1.61M / 0.79M |
| `VALID_INCIDENT_RSPNS_TIME_INDC='Y'` share | 2019 96.9% → 2023 95.6% → 2025 93.7% → Jun 2026 88.6% |
| All 31 zones present every year 2022–2026 | Yes, stable volumes (e.g. K7 ≈ 62k/yr) |
| Raw ID column name | `INCIDENT_ID` (01 currently selects `CAD_INCIDENT_ID` — bug) |
| MTA source datasets `i8rn-y4np`, `j6d2-s8m2` | 404 / login-walled — unavailable |
| Current model early-stops on the test set | Yes (`eval_set=[(X_test, y_test)]`) — leakage |

## 3. Data window and splits

| Split value | Rows | Purpose |
|---|---|---|
| `history` | 2021-12-01 → 2021-12-31 | Lag warm-up only; never trained or scored |
| `train` | 2022-01-01 → 2024-09-30 | Fit |
| `valid` | 2024-10-01 → 2024-12-31 | Early stopping + objective choice |
| `test` | 2025-01-01 → 2025-12-31 | Primary holdout; replay year |
| `test_recent` | 2026-01-01 → 2026-06-30 | Secondary holdout, reported separately (data still maturing) |
| `exclude` | everything else | Dropped at ingest |

2019–2021 are dropped (older CAD era; COVID and its tail). The final model is fit on
`train` only, with the `valid` window used for early stopping — not refit on
train+valid, so the reported best iteration is the one shipped.

## 4. Pipeline changes

### 4.1 `01_ingest_clean.py`

- Fix `CAD_INCIDENT_ID` → `INCIDENT_ID`.
- Keep filters: REOPEN/TRANSFER/STANDBY = 'N', BOROUGH not null/UNKNOWN, zone in the
  31 `VALID_ZONES`, zone-prefix ↔ borough match, non-null `INCIDENT_DATETIME`,
  datetime in 2021-12-01 → 2026-06-30.
- **Remove** from the WHERE clause: both response-time validity flags and the
  1–7200 s response range. Instead emit
  `is_valid_response = 1` iff both flags are 'Y' and response ∈ [1, 7200].
  Rationale: a call with a missing response time still happened; filtering it out
  undercounts demand, increasingly so in recent years (§2).
- Emit `split` per §3.
- Fix docstring row-count claims to match actual output.

### 4.2 `02_weather_merge.py`

- Open-Meteo window: 2021-12-01 → 2026-06-30 (timezone `America/New_York`).
- Extend hardcoded calendars through 2026-06-30:
  - US federal holidays 2024, 2025, 2026 (OPM federal holiday list).
  - NYC DOE school-year session ranges for 2024-25 and 2025-26 and their closure
    days (Jewish holidays, Lunar New Year, Eid, etc.), each block commented with its
    source (official NYC DOE school-year calendar).
  - Election Day 2024, 2025.
- MTA: both sources are gone; `subway_disruption_idx` becomes the constant 0.5
  (the value the backend already sends at inference). Kept as a column so the
  feature list stays stable; documented as inert.
- **New:** persist the lookup tables it already builds so 04 can join them to the
  full grid (zero-incident hours need weather too):
  - `pipeline/data/weather_hourly.parquet` — (date_hour, temperature_2m,
    precipitation, windspeed_10m, weathercode, is_severe_weather,
    is_extreme_heat, is_heat_emergency)
  - `pipeline/data/calendar_daily.parquet` — (date, zone_prefix, is_holiday,
    is_school_day, is_major_event)

### 4.3 `03_spatial_join.py`

No logic change (SVI dict join). Verify it runs on the new columns.

### 4.4 `04_aggregate.py` — new grain

1. **Counts:** `incident_count` = COUNT(*) per (zone, `date_hour`) from
   `incidents_cleaned`, **no validity filter**.
2. **Grid:** CROSS JOIN 31 zones × every local calendar hour 2021-12-01 00:00 →
   2026-06-30 23:00 (24 labels/day, matching Open-Meteo's local labels). LEFT JOIN
   counts, COALESCE to 0. Expected 31 × 40,152 = 1,244,712 rows.
   DST: the spring-forward 02:00 label will read 0 and the fall-back 01:00 label
   holds two clock hours — accepted, documented.
3. **Lags** (DuckDB window functions, `PARTITION BY zone ORDER BY date_hour`; the
   grid is gap-free so row offsets equal hour offsets):

   | Feature | Definition |
   |---|---|
   | `lag_1h` | count at t−1h |
   | `lag_2h` | count at t−2h |
   | `lag_3h` | count at t−3h |
   | `lag_24h` | count at t−24h |
   | `lag_168h` | count at t−168h |
   | `roll_7d_same_hour` | mean of counts at t−24h, t−48h, …, t−168h (7 values) |
   | `roll_4w_same_hour_dow` | mean of counts at t−168h, t−336h, t−504h, t−672h |

   Rows whose lags reach before 2021-12-01 get NULL and are dropped (all fall in
   `history`).
4. **Enrichment:** join `weather_hourly` on `date_hour`, `calendar_daily` on
   (date, zone prefix), SVI via the existing zone map. Derive cyclical encodings and
   `is_weekend` from the grid's own timestamp (not from incidents).
5. **Outputs:**
   - `pipeline/data/training_grid.parquet` — full table (all splits).
   - `backend/artifacts/zone_baselines.parquet` — same schema as today; now the mean
     hourly count **including zeros** per (zone, hour, dayofweek) over `train` rows.
   - `backend/artifacts/zone_stats.parquet` — same schema; computed over `train`
     rows of `incidents_cleaned` with `is_valid_response = 1`.
   - **New** `backend/artifacts/hourly_counts.parquet` — (INCIDENT_DISPATCH_AREA,
     date_hour, incident_count) for 2024-12-01 → 2026-06-30 (31 × 13,848 = 429,288 rows).
   - **New** `backend/artifacts/calendar_daily.parquet` — (date, zone_prefix,
     is_holiday, is_school_day, is_major_event) for 2025-01-01 → 2026-06-30.

Remove the old `incidents_aggregated.parquet` output.

### 4.5 `05_train_demand_model.py`

- `FEATURE_COLS` = existing 21 + the 7 lags (28 total, fixed order; the lags appended
  at the end).
- Hyperparameters unchanged except `n_estimators=2000`, `early_stopping_rounds=50`,
  `eval_set=[(X_valid, y_valid)]`.
- **Objective:** fit both `reg:squarederror` and `count:poisson`; keep the one with
  lower `valid` RMSE. Hourly counts are small non-negative integers, so Poisson is
  the principled default; the comparison makes the choice empirical.
- Save `demand_model.pkl` via joblib only if the §1 deployment gate passes;
  otherwise save as `pipeline/data/demand_model_candidate.pkl` and exit non-zero with
  the comparison table printed.
- Write `backend/artifacts/model_metrics.json` (all numbers from §5.4, feature list,
  objective, best_iteration, data window).
- Replace the scenario sanity checks with replay checks on fixed 2025 dates.

### 4.6 `07_staging_optimizer.py` and `08_counterfactual_precompute.py`

Both currently hand-build 21-feature rows and will break. Change both to import
`DemandForecaster` from `backend/models/demand_forecaster.py` (via `sys.path`) so
there is exactly one inference-row builder.

- 07: validate on the preset replay dates (§7).
- 08: incidents come from `split = 'test'` (now 2025) with `is_high_acuity = 1` and
  `is_valid_response = 1`. For each sampled incident, staging uses the model's
  prediction for **that incident's own date_hour** (cache K-Means per unique
  date_hour) instead of a fixed October representative. Output schemas of
  `counterfactual_summary.parquet` / `counterfactual_raw.parquet` unchanged.

### 4.7 `test_artifacts.py`

Update to 28 features, new artifacts, new zone_baselines scale (hourly, not
month-summed).

## 5. Model evaluation

### 5.1 Label

`incident_count` per zone per local hour. Mean ≈ 5; K7 Friday 20:00 ≈ 8 (was ≈ 37
under the old month-summed grain).

### 5.2 Leakage controls

- Lags are window-function offsets on a gap-free grid, past-only by construction.
- `zone_baselines` uses `train` rows only. It is still in-sample for training rows
  (target encoding over ~143 weeks per cell); accepted and noted as a limitation.
- Early stopping and objective selection use `valid` only; `test` and
  `test_recent` are scored once.

### 5.3 Models compared

| Name | Description |
|---|---|
| `lag` | 28 features (the candidate) |
| `no_lag` | same grain, same objective, the 21 original features |
| `naive_168h` | prediction = `lag_168h` |
| `baseline_avg` | prediction = `zone_baseline_avg` |

### 5.4 Metrics

RMSE, MAE, and mean Poisson deviance on `test` and `test_recent`; RMSE broken down
by borough and by hour of day for `test`. Printed as a table and saved in
`model_metrics.json`.

## 6. Backend changes

### 6.1 API (additive; no field renamed or removed)

`GET /api/heatmap` and `GET /api/staging` gain `date: str | None` (`YYYY-MM-DD`,
valid range 2025-01-01 → 2026-06-30).

- **date given:** `dow` and `month` are derived from it (the passed `dow`/`month`
  are ignored). Lag features come from `hourly_counts` for (zone, date, hour).
  Holiday/school/event flags come from `calendar_daily`. Weather still comes from
  the `temperature`/`precipitation`/`windspeed` params (what-if preserved).
- **date omitted:** the backend picks a stand-in date — the lower-median 2025 date
  with the requested `month` and `dow` (e.g. 5 matches → 3rd; 4 matches → 2nd) —
  and proceeds as above. Existing callers keep working.
- **date out of range:** 422 via FastAPI validation.
- Response: `query_params` gains `date`; each heatmap feature's `properties` gains
  `actual_count` (integer, from `hourly_counts`).

### 6.2 `backend/models/demand_forecaster.py`

- Reads the expected feature list from the loaded model
  (`get_booster().feature_names`). Builds lag columns only if the model expects them,
  so the old 21-feature pickle still works (rollback path).
- New pure function `build_lag_features(hourly_counts, zone, target_date_hour) -> dict`
  implementing §4.4 step 3 exactly; used by the backend, 07, 08, and the parity test.
- Replaces hardcoded holiday/school/event defaults with `calendar_daily` lookups when
  available; falls back to today's defaults if that artifact is missing.

### 6.3 `backend/main.py`

Load `hourly_counts` and `calendar_daily` (and `model_metrics.json`, exposed in
`/health`). `/reload` picks them up. If the model expects lags but `hourly_counts`
is missing, heatmap/staging return mock data with `X-Data-Source: mock` and
`X-Warning: lag-artifact-missing`.

### 6.4 Routers

`heatmap.py` and `staging.py` accept and pass `date`; heatmap adds `actual_count`.
Staging's LRU cache key includes the resolved date.

## 7. Frontend changes

- `DayPicker` + hidden month → a date input constrained to 2025-01-01 → 2026-06-30.
  `dow` and `month` are derived client-side and still sent (backward compatible).
  The hour slider is unchanged.
- `DEMO_SCENARIOS`:
  - `friday_peak` → 2025-10-10 (Fri) 20:00
  - `monday_quiet` → 2025-10-20 (Mon) 04:00
  - `storm` → the Wednesday in November 2025 with the highest 18:00 precipitation in
    Open-Meteo data, selected during implementation and hardcoded with a comment.
- Zone tooltip and detail panel show "predicted X · actual Y" when `actual_count` is
  present; unchanged when absent (mock mode).
- `data/mock_api_responses.json` is not modified.

## 8. Testing

**Pipeline**
- Grid completeness: row count = 31 × hours in range; no duplicate (zone, date_hour).
- Lag correctness: for 200 random rows, recompute each lag from `incident_count` by
  timestamp arithmetic (not row offset) and assert equality.
- Past-only: for each lag, assert that the source timestamp < the row's timestamp.
- **Train/serve parity:** for 200 random 2025 rows, `build_lag_features` over
  `hourly_counts` equals the training grid's lag columns.

**Backend (pytest)**
- `build_lag_features`: midnight row (t−1h is the previous date), 2025-01-01 00:00
  (lags reach into Dec 2024), and exactly 7/4 values in the rolling means.
- Forecaster with a 21-feature model (no lag columns built).
- Stand-in date resolution for month/dow with 4 and 5 matches.
- Heatmap: `date` given, omitted, out of range (422); `actual_count` present.
- Missing `hourly_counts` with a lag model → mock + `X-Warning`.

**Frontend**
- Update `components/Controls/__tests__` for the date input and preset → date mapping.

**End-to-end**
- Run the backend on the new artifacts; load the dashboard in the browser pane;
  select `friday_peak`; confirm the choropleth renders and tooltips show predicted and
  actual.

## 9. Documentation

Add (never delete) a section to `CLAUDE.md`: new splits, label definition, 28
`FEATURE_COLS`, the `date` param and `actual_count` field, new artifacts, and the
final metrics from `model_metrics.json`.

## 10. Execution notes and risks

- **Raw data:** requires downloading the full EMS CSV (~2 GB) from NYC Open Data.
  The user confirms the download before it starts.
- **DOE calendars:** the 2024-25 and 2025-26 closure lists are transcribed by hand;
  a wrong date mislabels a day's `is_school_day`. Mitigated by citing sources inline.
- **2026 data maturity:** the validity-flag share is still falling month by month,
  suggesting records are still being backfilled; `test_recent` is reported separately
  for this reason.
- **Lag model at serve time depends on history existing:** outside the replay range
  there are no lags. This is intrinsic to the replay design (no live feed).
