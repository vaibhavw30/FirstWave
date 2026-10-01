# Coverage-Optimal Staging (Staging v2) — Design

**Date:** 2026-09-28
**Branch:** `feat/coverage-staging` (from `main` after PR #24)
**Status:** Approved in conversation; awaiting written-spec review
**Scope owner:** Vaibhav (explicitly authorized edits to `pipeline/`, `backend/`, docs)

## 1. Goal

Replace weighted K-means staging with an **exact optimizer over the drive-time
matrix**, and use **one travel model and one optimizer** for the API
(`/api/staging`, `/api/counterfactual`) and the offline headline simulation
(script 08), so the numbers on screen and the numbers in the pitch come from the
same method. Numbers must be defensible under Q&A; the headline may go down.

### Success criteria

1. `/api/staging` and script 08 return **identical sites** for the same
   (date, hour, weather, K) — enforced by a parity test.
2. The optimizer is **provably optimal** for its stated objective (exact MILP),
   and matches brute force for K = 1–4 in tests.
3. The two known flaws are gone: staged times include dispatch, and the matrix's
   0-s diagonal no longer produces instant responses.
4. Staged time ≤ static time for every zone and every call, by construction.
5. API contract unchanged: no field renamed or removed; mock fallback preserved.
6. README and CLAUDE.md state the method, its assumptions, and the new results
   honestly, whatever they are.

### Non-goals

- Changing the demand model, heatmap, or drive-time matrix (script 06).
- Modelling unit capacity / queueing (stated as an assumption instead).
- Replacing the synthetic counterfactual histograms (noted as a known issue).
- Frontend code changes (including the "%" label on `predicted_demand_coverage`).

## 2. Facts this design relies on (verified 2026-09-28)

| Fact | Value |
|---|---|
| Matrix entries | 1,891 = 61 origins (31 zone centroids + 30 stations) × 31 zone destinations; no 9999s |
| Matrix diagonal | 0 s (e.g. `(B1, B1) = 0`) |
| Matrix speeds | free-flow OSM; straight-line ÷ time ≈ 30–45 km/h |
| Worst station gap | Q1 centroid: nearest station 1,387 s (EMS_K70) |
| Stations per borough | B 6 · K 6 · M 8 · Q 7 · S 3 (`data/ems_stations.json`) |
| 08 "after" today | matrix drive only — dispatch omitted |
| 08 "before" today | real `INCIDENT_RESPONSE_SECONDS_QY` (= dispatch + travel) |
| scipy in backend venv | 1.17.0 (transitive via scikit-learn; not pinned) |
| Prototype MILP solve time | 6–40 ms for K = 3–10; equals brute force at K = 3 |
| Prototype result, Fri 2025-10-10 20:00, K=5 (zone-level) | 49.3% → 58.3% within 8 min (current API: 66.2%) |
| Prototype sites, K=5 | B2, K3, M3, Q6, S1 — identical for Fri 8 PM and Mon 4 AM |

The last row is a finding to report, not a bug: with the station network in the
model, the best posts are set mostly by **station-coverage gaps**; hourly demand
moves them only at the margin.

## 3. The travel model (`backend/models/coverage_model.py`)

Pure numpy/scipy; no FastAPI imports.

**Inputs:** drive-time matrix, station list (`data/ems_stations.json`),
`zone_stats` (per-zone `avg_dispatch_seconds`, `avg_travel_seconds`).

**Precomputed once:**

```
intra_z          = ½ × min over zones o ≠ z of matrix[o, z]      # within-zone travel
station_drive_z  = min over stations s of matrix[s, z] + intra_z
site_drive[z, j] = matrix[j, z] + intra_z                         # j ∈ 31 zone centroids
```

**Ratio for a set S of open sites:**

```
ratio_z(S) = min(station_drive_z, min_{j∈S} site_drive[z, j]) / station_drive_z   ∈ (0, 1]
```

Staged units are **additional** to the station network; a zone no site improves
has ratio 1.

**Zone-level times (API):**

```
wf       = 1 + 0.012 × precip_mm + 0.002 × max(0, wind_kmh − 15)
before_z = dispatch_z + travel_z × wf
after_z  = dispatch_z + travel_z × wf × ratio_z(S)
```

**Call-level times (08):** for a call in zone z with real response `r` and real
travel `t` (weather already included):

```
after = r − t × (1 − ratio_z(S))
```

Calls with missing, non-positive, or `t > r` travel are excluded and counted in the log.

**Within-8-minute probability (zone level):** unchanged lognormal, cv = 0.95:

```
σ = √ln(1 + 0.95²),  μ = ln(mean) − σ²/2,  P = Φ((ln 480 − μ) / σ)
```

`_weather_travel_factor` and `_estimate_pct_under_threshold` move here from
`routers/counterfactual.py`.

**Removed:** 2 km snap/borrowed rows, straight-line 25 km/h fallback, 120-s floor,
`min(staged, static)` cap (redundant because ratio ≤ 1).

## 4. The optimizer (`backend/models/staging_optimizer.py`, rewritten)

`StagingOptimizer(coverage_model).compute_staging(predicted_counts, K, weather_factor=1.0)`

**Objective (lexicographic):** maximise expected calls within 8 min; tie-break by
lower demand-weighted mean response.

**MILP** (`scipy.optimize.milp`, HiGHS, `mip_rel_gap = 0`):

- Variables: `y_j ∈ {0,1}` for 31 sites; `x_zj ∈ {0,1}` for each zone z and
  j ∈ sites ∪ {stations-only}.
- Coefficients per (z, j): `d_z = max(demand_z, 0.01)`,
  `T_zj = dispatch_z + travel_z × wf × r_zj`, `P_zj = P(within 480 | T_zj)`,
  where `r_zj = min(station_drive_z, site_drive[z, j]) / station_drive_z`
  and `r_z,stations-only = 1`.
- Maximise `Σ d_z P_zj x_zj − ε Σ d_z T_zj x_zj / (Σ d_z × 7200)` with
  `ε = 1e-6` (tie-break term bounded below 1e-6 calls).
- Constraints: `Σ_j x_zj = 1` ∀z; `x_zj ≤ y_j` for sites; `Σ y_j = K`;
  if K ≥ 5: `Σ_{j∈borough b} y_j ≥ 1` for each of the 5 boroughs. No borough
  constraint when K < 5.

**Output** (same list-of-dicts shape as today):

- `lat`, `lon` = the chosen zone's centroid.
- `cluster_zones` = zones whose assigned `j` is this site **and** `r_zj < 1`
  (zones left with stations appear in no pin).
- `predicted_demand_coverage` = Σ demand over `cluster_zones`; `zone_count`
  = len; `coverage_radius_m` = 3500 (display only).
- Sorted by coverage descending; `staging_index` reassigned 0..K−1.

K-means, D'Hondt allocation, and the weighted-centroid code are deleted.

## 5. Wiring

**`backend/main.py`:** after artifacts load (and on `POST /reload`), build
`ARTIFACTS["coverage_model"]` from `drive_time` + `ems_stations.json` +
`zone_stats`; `None` if any input is missing. `/health` reports it.

**`/api/staging`:** uses the new optimizer with the resolved weather's `wf`. If
`coverage_model` is `None`, return mock with `X-Data-Source: mock`. Cache and
`/reload` clearing unchanged.

**`/api/counterfactual`:** dynamic path calls the same optimizer and
`CoverageModel.zone_times`; aggregation (demand-weighted %, expanded medians,
borough / SVI breakdowns, `by_zone`) unchanged in shape. Fallback chain unchanged
(precomputed parquet → mock).

**Script 08:** imports `CoverageModel` and `StagingOptimizer` from `backend/`;
places sites per incident hour with that hour's actual weather `wf`, **K = 5**
(UI default). Writes K = 5 results to the existing parquet schemas
(`baseline_drive_sec` = real response, `staged_drive_sec` = after). Logs a
sensitivity table for K = 3, 7, 10 (not written to artifacts) and the per-SVI
quartile result.

**Script 07:** uses the shared optimizer; checks listed in §6.

**`backend/requirements.txt`:** add `scipy`. (A concurrent task is updating pins in
this file; resolve by merge.)

## 6. Testing (test-first)

**`backend/tests/test_coverage_model.py`** — hand-built 3-zone / 1-station matrix:

- `intra_z` = ½ nearest other zone; diagonal no longer yields 0.
- No sites → ratio 1 everywhere → after = before.
- Site at z → `ratio_z = intra / (station + intra)`; = 1 when the station is closer.
- `wf` scales travel in before and after; dispatch untouched.
- Call-level formula and exclusion of invalid travel.

**`backend/tests/test_staging_optimizer.py`** — real matrix, seeded demand draws:

- Exactly K distinct valid sites; ≥ 1 per borough when K ≥ 5; none forced when K < 5.
- Equals brute force for K = 1–4 over several draws.
- Deterministic; all-zero demand still returns K sites.
- `cluster_zones` only contains improved zones; coverage sums match.
- K = 1–10 each solves in < 100 ms.

**`backend/tests/test_api.py`** — existing staging/counterfactual tests pass; add:

- `by_zone` staged ≤ static for every zone.
- Missing matrix → both endpoints mock with `X-Data-Source: mock`.
- `/reload` rebuilds `coverage_model`.

**Parity test:** 08's placement function and `/api/staging` return identical sites
for the same date / hour / weather / K = 5.

**`pipeline/test_artifacts.py`:**

- New hard checks: `seconds_saved ≥ 0` on every raw row; staged ≥ static in
  **every** summary bin (was "> 60%").
- Equity check (Q4 ≥ Q1 seconds saved) becomes **informational**: printed every
  run and reported in the README either way; not a gate.

**Script 07** (validation run): valid sites, borough rule, K distinct, brute-force
match at K = 3, staged coverage > stations-only.

## 7. Docs

- **README:** rewrite Key Results with the new 08 numbers; replace the K-means
  description with the coverage optimizer; add an assumptions box (free-flow ratio,
  nearest-station baseline, no capacity, within-zone term); state that placement is
  driven mostly by station-coverage gaps with demand adjusting at the margin.
- **CLAUDE.md:** append a "Staging v2" section; mark the Model B section as
  superseded without deleting it (add-only rule).

## 8. Rollout

1. Implementation plan (writing-plans), then implement test-first on this branch.
2. Run 07 → 08 (10–30 min) → `pipeline/test_artifacts.py`; full backend and
   pipeline test suites.
3. Commit regenerated `counterfactual_summary.parquet` / `counterfactual_raw.parquet`.
4. Open a PR to `main`; merge is the owner's call.

## 9. Assumptions and known limits (to be stated publicly)

- Drive-time ratios come from free-flow road times; they scale real travel, so
  real traffic is kept but the ratio itself ignores congestion patterns.
- "Before" assumes the nearest station's unit would have responded.
- Staged units have unlimited capacity within their area.
- Within-zone travel is approximated as half the drive to the nearest neighbouring
  zone centroid.
- Zone-level API numbers use a lognormal assumption; 08 uses real per-call times —
  same placement and travel model, different aggregation, so they will be close
  but not identical.
