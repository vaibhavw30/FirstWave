# Coverage-Optimal Staging (Staging v2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace weighted K-means staging with an exact coverage optimizer over the drive-time matrix, used identically by `/api/staging`, `/api/counterfactual`, and pipeline scripts 07/08, and regenerate the headline numbers with it.

**Architecture:** A pure travel model (`backend/models/coverage_model.py`) turns the drive-time matrix, the 30 fixed stations and `zone_stats` into a per-zone travel ratio for any set of open sites. A rewritten `backend/models/staging_optimizer.py` picks K zone centroids by solving a MILP (SciPy/HiGHS) that maximises expected calls within 8 minutes. The API routers and a new `pipeline/fw_staging.py` (used by 07 and 08) both call these two modules with identical inputs; a parity test pins them together.

**Tech Stack:** Python 3.14, NumPy 2.4, pandas 3.0, SciPy 1.17 (`scipy.optimize.milp`, `scipy.special.ndtr`), FastAPI + TestClient, pytest.

**Spec:** `docs/superpowers/specs/2026-09-28-coverage-staging-design.md`

## Global Constraints

- API contract unchanged: no field renamed or removed in `/api/staging`, `/api/counterfactual`, `/health` (adding `artifacts.coverage_model` to `/health` is additive).
- GeoJSON Point coordinates are `[longitude, latitude]`.
- Borough keys are exact strings, including `"RICHMOND / STATEN ISLAND"`.
- Mock fallback preserved: when inputs are missing, endpoints return mock data with header `X-Data-Source: mock`; never crash.
- Never modify `data/mock_api_responses.json`.
- `CLAUDE.md`: add only, never delete.
- Headline K = 5 (the UI default). Sensitivity K = 3, 7, 10 is logged only.
- Borough rule: at least one site per borough when K ≥ 5; no borough constraint when K < 5.
- Weather factor: `wf = 1 + 0.012 × precip_mm + 0.002 × max(0, wind_kmh − 15)`.
- Within-8-minute probability: lognormal, cv = 0.95, threshold 480 s.
- MILP: `scipy.optimize.milp`, `mip_rel_gap = 0`, tie-break weight ε = 1e-6 on `Σ d·T / (Σd × 7200)`.
- Backend tests run from `backend/` with `backend/.venv/bin/python`; pipeline scripts run from the repo root with `pipeline/.venv/bin/python`.
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Baselines before starting: `(cd backend && .venv/bin/python -m pytest tests -q)` → 55 passed; `pipeline/.venv/bin/python -m pytest pipeline/tests -q` → 57 passed.

## Review Focus

1. **A borough-forced site that improves no zone** (a station is closer everywhere it could help) → the pin is still well formed: `cluster_zones == []`, `zone_count == 0`, `predicted_demand_coverage == 0.0`, and it keeps a valid `staging_index`. Test: `test_pin_that_improves_nothing_is_well_formed` (Task 2).
2. **What-if weather** (request passes `precipitation`/`windspeed`) → the same `wf` reaches placement and the counterfactual's zone times. Test: `test_counterfactual_uses_the_staging_sites_and_coverage_model[what-if]` (Task 3).
3. **Incomplete inputs** (matrix pair missing, a zone missing from `zone_stats`, stations file missing) → `coverage_model` is `None`, both endpoints serve mock/fallback, no 500. Tests: `test_incomplete_matrix_is_rejected`, `test_build_returns_none_*` (Task 1), `test_missing_coverage_model_serves_mock` (Task 3).
4. **A replayed hour with no weather row** → API and script 08 both fall back to the request defaults through the same `resolve_weather` call. No test (the artifact covers every 2025 hour); reviewer checks `pipeline/fw_staging.py` calls `resolve_weather` exactly as `routers/staging.py` does.
5. **Concurrent `/api/staging` requests** run the MILP in executor threads → `StagingOptimizer` and `CoverageModel` must not mutate shared state after `__init__`. No test; reviewer checks both classes only read their arrays after construction.

---

## File Map

| File | Change | Responsibility |
|---|---|---|
| `backend/models/coverage_model.py` | Create | Travel model: intra-zone term, station/site drives, ratios, zone- and call-level times, `pct_within`, `weather_travel_factor`, `build_coverage_model` |
| `backend/models/staging_optimizer.py` | Rewrite | Exact MILP placement over 31 zone centroids; output in the existing list-of-dicts shape |
| `backend/main.py` | Modify | Build `ARTIFACTS["coverage_model"]` on load/reload; report it in `/health` |
| `backend/routers/staging.py` | Modify | Use the new optimizer with `wf`; mock when `coverage_model` is missing |
| `backend/routers/counterfactual.py` | Modify | Dynamic path uses the same optimizer + `CoverageModel.zone_times`; remove snap/fallback/floor code |
| `backend/requirements.txt` | Modify | Add `scipy` |
| `pipeline/fw_staging.py` | Create | `HourlyStager`: per-hour demand + placement with the API's exact inputs, for 07 and 08 |
| `pipeline/07_staging_optimizer.py` | Rewrite | Validation run on the shared optimizer |
| `pipeline/08_counterfactual_precompute.py` | Rewrite | Call-level before/after with K = 5 + sensitivity log |
| `pipeline/test_artifacts.py` | Modify | New hard checks; equity becomes informational |
| `pipeline/requirements.txt`, `pipeline/requirements-dev.txt` | Modify | Add `scipy` |
| `backend/tests/test_coverage_model.py` | Create | Hand-worked 3-zone network tests |
| `backend/tests/test_staging_optimizer.py` | Create | Real-matrix optimizer tests incl. brute force |
| `backend/tests/test_api.py` | Modify | Fixture copies the real matrix; new wiring tests |
| `backend/tests/test_staging_parity.py` | Create | 08's placement == `/api/staging` on real artifacts |
| `backend/artifacts/counterfactual_{summary,raw}.parquet` | Regenerate | Output of new 08 |
| `README.md`, `CLAUDE.md` | Modify | Method, assumptions, new numbers |

---

### Task 1: Travel model (`coverage_model.py`)

**Files:**
- Create: `backend/models/coverage_model.py`
- Create: `backend/tests/test_coverage_model.py`
- Modify: `backend/requirements.txt`

**Interfaces:**
- Consumes: `models.demand_forecaster.VALID_ZONES` (list of 31 zone codes).
- Produces:
  - `weather_travel_factor(precipitation: float, windspeed: float) -> float`
  - `pct_within(mean_seconds, threshold: float = 480) -> np.ndarray | np.float64` (vectorised)
  - `class CoverageModel(drive_time: dict, station_ids: list, zone_stats: pd.DataFrame, zones=VALID_ZONES)` with attributes `zones: list[str]`, `index: dict[str, int]`, `intra`, `station_drive`, `dispatch`, `travel` (1-D arrays, `zones` order), `site_drive`, `ratio` (2-D `[zone, site]`), and methods `ratios(sites: list[str]) -> np.ndarray` and `zone_times(sites: list[str], weather_factor: float = 1.0) -> dict[str, tuple[float, float]]` (`{zone: (before, after)}`)
  - `call_level_after(response_sec, travel_sec, ratio) -> np.ndarray` (NaN for unusable calls)
  - `build_coverage_model(drive_time, zone_stats, stations_path=STATIONS_PATH) -> CoverageModel | None`
  - `STATIONS_PATH` = repo `data/ems_stations.json`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_coverage_model.py`:

```python
"""CoverageModel on a hand-built 3-zone / 1-station network (numbers worked by hand)."""
import pathlib
import pickle

import numpy as np
import pandas as pd
import pytest
from scipy.stats import lognorm

from models.coverage_model import (
    CoverageModel, build_coverage_model, call_level_after, pct_within, weather_travel_factor)

ART = pathlib.Path(__file__).resolve().parents[1] / "artifacts"
ZONES = ["B1", "B2", "K1"]
# Symmetric zone-to-zone drive seconds; the one station "ST" sits next to K1.
_ZZ = {("B1", "B2"): 100, ("B1", "K1"): 300, ("B2", "K1"): 240}
_ST = {"B1": 400, "B2": 500, "K1": 60}


def matrix():
    m = {}
    for a in ZONES:
        for b in ZONES:
            m[(a, b)] = 0 if a == b else _ZZ.get((a, b), _ZZ.get((b, a)))
    for z, t in _ST.items():
        m[("ST", z)] = t
    return m


def stats():
    return pd.DataFrame({"INCIDENT_DISPATCH_AREA": ZONES,
                         "avg_dispatch_seconds": 200.0, "avg_travel_seconds": 300.0})


@pytest.fixture
def cm():
    return CoverageModel(matrix(), ["ST"], stats(), zones=ZONES)


def test_intra_zone_travel_is_half_the_nearest_neighbour_drive(cm):
    # B1: min(100, 300)/2   B2: min(100, 240)/2   K1: min(300, 240)/2
    np.testing.assert_allclose(cm.intra, [50, 50, 120])


def test_station_drive_includes_intra_zone_travel(cm):
    np.testing.assert_allclose(cm.station_drive, [450, 550, 180])


def test_site_in_its_own_zone_is_not_instant(cm):
    # The matrix diagonal is 0 s; the within-zone term replaces it.
    assert cm.site_drive[0, 0] == 50
    assert cm.ratios(["B1"])[0] == pytest.approx(50 / 450)


def test_no_sites_changes_nothing(cm):
    np.testing.assert_allclose(cm.ratios([]), 1.0)
    for before, after in cm.zone_times([]).values():
        assert before == after == 500


def test_site_ratios_against_the_nearest_station(cm):
    # B1 from B1: 50/450; B2 from B1: (100+50)/550; K1: station (180) beats B1 (300+120)
    np.testing.assert_allclose(cm.ratios(["B1"]), [50 / 450, 150 / 550, 1.0])


def test_best_open_site_wins(cm):
    # B2 from B2 (50/550) beats B2 from B1; K1 from K1: 120/180
    np.testing.assert_allclose(cm.ratios(["B1", "B2", "K1"]), [50 / 450, 50 / 550, 120 / 180])


def test_weather_scales_travel_not_dispatch(cm):
    before, after = cm.zone_times(["B1"], weather_factor=1.5)["B1"]
    assert before == pytest.approx(200 + 450)
    assert after == pytest.approx(200 + 450 * 50 / 450)


def test_weather_travel_factor():
    assert weather_travel_factor(0, 10) == 1.0
    assert weather_travel_factor(10, 25) == pytest.approx(1.14)


@pytest.mark.parametrize("mean", [300, 480, 641, 1200])
def test_pct_within_is_the_cv095_lognormal(mean):
    sigma = np.sqrt(np.log(1 + 0.95 ** 2))
    expected = lognorm.cdf(480, s=sigma, scale=np.exp(np.log(mean) - sigma ** 2 / 2))
    assert float(pct_within(mean)) == pytest.approx(expected, rel=1e-9)


def test_pct_within_falls_as_mean_rises():
    p = pct_within(np.array([300.0, 480.0, 700.0]))
    assert p[0] > p[1] > p[2]


def test_call_level_after_shrinks_only_travel():
    after = call_level_after([600, 600, 600, 600, 600],
                             [300, 0, 700, np.nan, 300],
                             [0.5, 0.5, 0.5, 0.5, 1.0])
    assert after[0] == 450            # 600 − 300 × (1 − 0.5)
    assert np.isnan(after[1:4]).all()  # travel 0, travel > response, travel missing
    assert after[4] == 600            # ratio 1: unchanged


def test_incomplete_matrix_is_rejected():
    m = matrix()
    del m[("ST", "K1")]
    with pytest.raises(ValueError, match="missing 1 pairs"):
        CoverageModel(m, ["ST"], stats(), zones=ZONES)


def test_build_returns_none_when_inputs_missing(tmp_path):
    assert build_coverage_model(None, stats()) is None
    assert build_coverage_model(matrix(), None) is None
    assert build_coverage_model(matrix(), stats(), stations_path=tmp_path / "nope.json") is None


def test_build_returns_none_when_zone_stats_incomplete():
    with open(ART / "drive_time_matrix.pkl", "rb") as f:
        drive_time = pickle.load(f)
    zs = pd.read_parquet(ART / "zone_stats.parquet")
    assert build_coverage_model(drive_time, zs) is not None
    assert build_coverage_model(drive_time, zs[zs["INCIDENT_DISPATCH_AREA"] != "Q1"]) is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `(cd backend && .venv/bin/python -m pytest tests/test_coverage_model.py -v)`
Expected: collection ERROR, `ModuleNotFoundError: No module named 'models.coverage_model'`.

- [ ] **Step 3: Write the implementation**

Create `backend/models/coverage_model.py`:

```python
"""Travel model shared by /api/staging, /api/counterfactual and pipeline scripts 07/08.

Staged units are extra to the fixed station network. A zone's travel time is scaled
by how much closer the nearest open staging site is than the nearest station, using
the free-flow drive-time matrix (script 06). Dispatch time is never changed.
"""
import json
import logging
import math
from pathlib import Path

import numpy as np
from scipy.special import ndtr

from models.demand_forecaster import VALID_ZONES

logger = logging.getLogger(__name__)

THRESHOLD_SEC = 480
_CV = 0.95
_SIGMA = math.sqrt(math.log(1 + _CV ** 2))
STATIONS_PATH = Path(__file__).resolve().parents[2] / "data" / "ems_stations.json"


def weather_travel_factor(precipitation: float, windspeed: float) -> float:
    """Travel-time multiplier: +1.2% per mm/hr of rain, +0.2% per km/h of wind above 15."""
    return 1.0 + 0.012 * precipitation + 0.002 * max(0.0, windspeed - 15)


def pct_within(mean_seconds, threshold: float = THRESHOLD_SEC):
    """P(response <= threshold) for a lognormal with this mean and CV 0.95.
    Calibrated so a zone mean above 8 min still has most calls under 8 min, as in the real data."""
    mean = np.maximum(np.asarray(mean_seconds, dtype=float), 1e-9)
    mu = np.log(mean) - _SIGMA ** 2 / 2
    return ndtr((math.log(threshold) - mu) / _SIGMA)


class CoverageModel:
    def __init__(self, drive_time: dict, station_ids: list, zone_stats, zones=VALID_ZONES):
        zones = list(zones)
        if not station_ids:
            raise ValueError("no stations")
        missing = [(o, z) for o in zones + list(station_ids) for z in zones if (o, z) not in drive_time]
        if missing:
            raise ValueError(f"drive-time matrix is missing {len(missing)} pairs, e.g. {missing[:3]}")
        m = np.array([[drive_time[(o, z)] for z in zones] for o in zones], dtype=float)  # [origin, dest]
        self.zones = zones
        self.index = {z: i for i, z in enumerate(zones)}
        # Within-zone travel: half the drive in from the nearest other zone centroid.
        self.intra = 0.5 * (m + np.diag(np.full(len(zones), np.inf))).min(axis=0)
        self.station_drive = np.array(
            [min(drive_time[(s, z)] for s in station_ids) for z in zones], dtype=float) + self.intra
        if (self.station_drive <= 0).any():
            raise ValueError("station drive time must be positive for every zone")
        self.site_drive = m.T + self.intra[:, None]                                     # [zone, site]
        # ratio[z, j]: travel multiplier for zone z with site j open (1 = the station is closer)
        self.ratio = np.minimum(self.site_drive, self.station_drive[:, None]) / self.station_drive[:, None]
        stats = zone_stats.set_index("INCIDENT_DISPATCH_AREA").reindex(zones)
        cols = ["avg_dispatch_seconds", "avg_travel_seconds"]
        if stats[cols].isna().any().any():
            raise ValueError("zone_stats is missing dispatch/travel for some zones")
        self.dispatch = stats["avg_dispatch_seconds"].to_numpy(dtype=float)
        self.travel = stats["avg_travel_seconds"].to_numpy(dtype=float)

    def ratios(self, sites) -> np.ndarray:
        """Per-zone travel ratio with these sites open, in self.zones order."""
        if not sites:
            return np.ones(len(self.zones))
        return self.ratio[:, [self.index[s] for s in sites]].min(axis=1)

    def zone_times(self, sites, weather_factor: float = 1.0) -> dict:
        """{zone: (before, after)} mean response seconds with these sites open."""
        travel = self.travel * weather_factor
        before = self.dispatch + travel
        after = self.dispatch + travel * self.ratios(sites)
        return {z: (float(before[i]), float(after[i])) for i, z in enumerate(self.zones)}


def call_level_after(response_sec, travel_sec, ratio) -> np.ndarray:
    """Staged response for real calls: only the travel part shrinks.
    NaN where travel is missing, non-positive, or longer than the whole response."""
    r = np.asarray(response_sec, dtype=float)
    t = np.asarray(travel_sec, dtype=float)
    q = np.asarray(ratio, dtype=float)
    ok = np.isfinite(r) & np.isfinite(t) & (t > 0) & (t <= r)
    return np.where(ok, r - np.where(ok, t, 0.0) * (1 - q), np.nan)


def build_coverage_model(drive_time, zone_stats, stations_path=STATIONS_PATH):
    """CoverageModel, or None (logged) when an input is missing or unusable."""
    if drive_time is None or zone_stats is None:
        return None
    try:
        with open(stations_path) as f:
            station_ids = [s["station_id"] for s in json.load(f)]
        return CoverageModel(drive_time, station_ids, zone_stats)
    except Exception as exc:
        logger.error("⚠  coverage model unavailable: %s", exc)
        return None
```

Add to `backend/requirements.txt`, after the `scikit-learn==1.4.1.post1` line:

```
scipy>=1.11
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `(cd backend && .venv/bin/python -m pytest tests/test_coverage_model.py -v)`
Expected: 17 passed.

- [ ] **Step 5: Run the backend suite**

Run: `(cd backend && .venv/bin/python -m pytest tests -q)`
Expected: 72 passed (55 existing + 17 new).

- [ ] **Step 6: Commit**

```bash
git add backend/models/coverage_model.py backend/tests/test_coverage_model.py backend/requirements.txt
git commit -m "feat: coverage travel model shared by staging and counterfactual

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Exact coverage optimizer (`staging_optimizer.py`)

**Files:**
- Rewrite: `backend/models/staging_optimizer.py`
- Create: `backend/tests/test_staging_optimizer.py`

**Interfaces:**
- Consumes (Task 1): `CoverageModel` (`zones`, `index`, `ratio`, `dispatch`, `travel`), `pct_within`, `build_coverage_model`.
- Produces:
  - `class StagingOptimizer(coverage: CoverageModel)`
  - `compute_staging(predicted_counts: dict, K: int, weather_factor: float = 1.0) -> list[dict]` — each dict has keys `zone` (site zone code, not sent by the API), `lat`, `lon`, `coverage_radius_m`, `predicted_demand_coverage`, `cluster_zones`, `zone_count`, `staging_index`; sorted by `predicted_demand_coverage` descending then `zone`; `staging_index` 0..K−1. Raises `ValueError` for K outside 1..len(zones); `RuntimeError` if the solver fails.
  - `expected_within(sites: list[str], predicted_counts: dict, weather_factor: float = 1.0) -> float` — the objective (expected calls within 8 min).
  - Module constants kept: `ZONE_CENTROIDS`, `ZONE_BOROUGH_PREFIX`, `COVERAGE_RADIUS_M`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_staging_optimizer.py`:

```python
"""Coverage optimizer on the real drive-time matrix with seeded demand draws."""
import itertools
import pathlib
import pickle
import time

import numpy as np
import pandas as pd
import pytest

from models.coverage_model import CoverageModel, build_coverage_model, pct_within
from models.demand_forecaster import VALID_ZONES
from models.staging_optimizer import ZONE_CENTROIDS, StagingOptimizer

ART = pathlib.Path(__file__).resolve().parents[1] / "artifacts"


@pytest.fixture(scope="module")
def coverage():
    with open(ART / "drive_time_matrix.pkl", "rb") as f:
        drive_time = pickle.load(f)
    return build_coverage_model(drive_time, pd.read_parquet(ART / "zone_stats.parquet"))


@pytest.fixture(scope="module")
def optimizer(coverage):
    return StagingOptimizer(coverage)


def demand(seed):
    rng = np.random.default_rng(seed)
    return {z: float(v) for z, v in zip(VALID_ZONES, rng.gamma(2.0, 3.0, len(VALID_ZONES)))}


def brute_force_best(coverage, predicted, K, wf):
    """Best expected calls within 8 min over every K-subset (no borough rule)."""
    n = len(coverage.zones)
    ratio = np.hstack([coverage.ratio, np.ones((n, 1))])
    P = pct_within(coverage.dispatch[:, None] + coverage.travel[:, None] * wf * ratio)
    d = np.array([max(predicted[z], 0.01) for z in coverage.zones])
    return max(float((d * P[:, list(S) + [n]].max(axis=1)).sum())
               for S in itertools.combinations(range(n), K))


def sites(points):
    return [p["zone"] for p in points]


@pytest.mark.parametrize("K", range(1, 11))
def test_returns_k_distinct_sites_on_zone_centroids(optimizer, K):
    points = optimizer.compute_staging(demand(0), K)
    assert len(set(sites(points))) == K
    assert set(sites(points)) <= set(VALID_ZONES)
    for p in points:
        assert (p["lon"], p["lat"]) == ZONE_CENTROIDS[p["zone"]]
        assert p["coverage_radius_m"] == 3500
    assert [p["staging_index"] for p in points] == list(range(K))


@pytest.mark.parametrize("K", range(5, 11))
@pytest.mark.parametrize("seed", range(3))
def test_every_borough_gets_a_site_from_k5(optimizer, K, seed):
    assert {z[0] for z in sites(optimizer.compute_staging(demand(seed), K))} == set("BKMQS")


def test_boroughs_are_not_forced_below_k5(optimizer):
    # With K < 5 the borough rule is off, so some draw puts two sites in one borough.
    repeats = [len({z[0] for z in sites(optimizer.compute_staging(demand(seed), K))}) < K
               for seed in range(3) for K in (2, 3, 4)]
    assert any(repeats)


@pytest.mark.parametrize("K", range(1, 5))
@pytest.mark.parametrize("seed", range(3))
def test_matches_brute_force(coverage, optimizer, K, seed):
    counts = demand(seed)
    chosen = sites(optimizer.compute_staging(counts, K, weather_factor=1.1))
    assert optimizer.expected_within(chosen, counts, 1.1) == pytest.approx(
        brute_force_best(coverage, counts, K, 1.1), abs=1e-6)


def test_is_deterministic(optimizer):
    assert optimizer.compute_staging(demand(1), 7) == optimizer.compute_staging(demand(1), 7)


def test_zero_demand_still_places_k_sites(optimizer):
    points = optimizer.compute_staging({z: 0.0 for z in VALID_ZONES}, 5)
    assert len(points) == 5
    assert all(p["predicted_demand_coverage"] == 0.0 for p in points)


def test_cluster_zones_are_the_zones_each_site_improves(coverage, optimizer):
    counts = demand(2)
    points = optimizer.compute_staging(counts, 6)
    open_cols = [coverage.index[s] for s in sites(points)]
    served = [z for p in points for z in p["cluster_zones"]]
    assert len(served) == len(set(served))
    for p in points:
        j = coverage.index[p["zone"]]
        for z in p["cluster_zones"]:
            i = coverage.index[z]
            assert coverage.ratio[i, j] < 1.0
            assert coverage.ratio[i, j] == coverage.ratio[i, open_cols].min()
        assert p["zone_count"] == len(p["cluster_zones"])
        assert p["predicted_demand_coverage"] == round(sum(counts[z] for z in p["cluster_zones"]), 2)
    unserved = set(VALID_ZONES) - set(served)
    for z in unserved:
        assert coverage.ratio[coverage.index[z], open_cols].min() == 1.0


def test_sorted_by_coverage(optimizer):
    cov = [p["predicted_demand_coverage"] for p in optimizer.compute_staging(demand(0), 8)]
    assert cov == sorted(cov, reverse=True)


def test_staging_beats_stations_only(optimizer):
    counts = demand(0)
    chosen = sites(optimizer.compute_staging(counts, 5))
    assert optimizer.expected_within(chosen, counts) > optimizer.expected_within([], counts)


def test_each_k_solves_in_under_100ms(optimizer):
    counts = demand(0)
    optimizer.compute_staging(counts, 5)  # warm-up
    for K in range(1, 11):
        t = time.perf_counter()
        optimizer.compute_staging(counts, K)
        assert time.perf_counter() - t < 0.1, K


@pytest.mark.parametrize("K", [0, 32])
def test_rejects_k_out_of_range(optimizer, K):
    with pytest.raises(ValueError):
        optimizer.compute_staging(demand(0), K)


def test_pin_that_improves_nothing_is_well_formed():
    # Station ST sits on K1 (0 s), so a K1 site can't beat it; B1 and B2 sites serve the Bronx.
    zones = ["B1", "B2", "K1"]
    zz = {("B1", "B2"): 100, ("B1", "K1"): 300, ("B2", "K1"): 240}
    m = {(a, b): 0 if a == b else zz.get((a, b), zz.get((b, a))) for a in zones for b in zones}
    m.update({("ST", "B1"): 400, ("ST", "B2"): 500, ("ST", "K1"): 0})
    stats = pd.DataFrame({"INCIDENT_DISPATCH_AREA": zones,
                          "avg_dispatch_seconds": 200.0, "avg_travel_seconds": 300.0})
    opt = StagingOptimizer(CoverageModel(m, ["ST"], stats, zones=zones))
    points = opt.compute_staging({"B1": 5.0, "B2": 3.0, "K1": 1.0}, 3)
    k1 = next(p for p in points if p["zone"] == "K1")
    assert k1["cluster_zones"] == [] and k1["zone_count"] == 0
    assert k1["predicted_demand_coverage"] == 0.0
    assert sorted(p["staging_index"] for p in points) == [0, 1, 2]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `(cd backend && .venv/bin/python -m pytest tests/test_staging_optimizer.py -v)`
Expected: FAIL/ERROR — `TypeError: StagingOptimizer() takes no arguments` (the old class has no `__init__`).

- [ ] **Step 3: Rewrite the optimizer**

Replace the whole of `backend/models/staging_optimizer.py` with:

```python
"""Coverage-optimal staging (staging v2).

Chooses K zone centroids that maximise expected calls reached within 8 minutes,
tie-broken by lower demand-weighted mean response, solved exactly as a MILP
(scipy.optimize.milp / HiGHS). With K >= 5 every borough gets at least one site.
"""
import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix

from models.coverage_model import pct_within

ZONE_BOROUGH_PREFIX = {
    'B': 'BRONX',
    'K': 'BROOKLYN',
    'M': 'MANHATTAN',
    'Q': 'QUEENS',
    'S': 'RICHMOND / STATEN ISLAND',
}

ZONE_CENTROIDS = {
    # Bronx — (longitude, latitude)
    'B1': (-73.9101, 40.8116),
    'B2': (-73.9196, 40.8448),
    'B3': (-73.8784, 40.8189),
    'B4': (-73.8600, 40.8784),
    'B5': (-73.9056, 40.8651),
    # Brooklyn
    'K1': (-73.9857, 40.5995),
    'K2': (-73.9442, 40.6501),
    'K3': (-73.9075, 40.6929),
    'K4': (-73.9015, 40.6501),
    'K5': (-73.9283, 40.6801),
    'K6': (-73.9645, 40.6401),
    'K7': (-73.9573, 40.7201),
    # Manhattan
    'M1': (-74.0060, 40.7128),
    'M2': (-74.0000, 40.7484),
    'M3': (-73.9857, 40.7580),
    'M4': (-73.9784, 40.7484),
    'M5': (-73.9584, 40.7701),
    'M6': (-73.9484, 40.7884),
    'M7': (-73.9428, 40.8048),
    'M8': (-73.9373, 40.8284),
    'M9': (-73.9312, 40.8484),
    # Queens
    'Q1': (-73.7840, 40.6001),
    'Q2': (-73.8284, 40.7501),
    'Q3': (-73.8784, 40.7201),
    'Q4': (-73.9073, 40.7101),
    'Q5': (-73.8073, 40.6901),
    'Q6': (-73.9173, 40.7701),
    'Q7': (-73.8373, 40.7701),
    # Staten Island
    'S1': (-74.1115, 40.6401),
    'S2': (-74.1515, 40.5901),
    'S3': (-74.1915, 40.5301),
}

COVERAGE_RADIUS_M = 3500   # display only; placement uses the drive-time matrix
MIN_BOROUGH_K = 5          # at or above this K, every borough gets a site
_TIE_EPS = 1e-6            # weight of the mean-response tie-break (< 1e-6 calls)


class StagingOptimizer:
    def __init__(self, coverage):
        self.coverage = coverage
        n = len(coverage.zones)
        ns = n + 1                                   # column n = "stations only"
        self._n = n
        nv = n + n * ns                              # y (n) then x (n x ns), row-major
        self._nv = nv

        def xi(z, j):
            return n + z * ns + j

        rows, cols, vals, lb, ub = [], [], [], [], []
        r = 0
        for z in range(n):                           # each zone served exactly once
            for j in range(ns):
                rows.append(r); cols.append(xi(z, j)); vals.append(1.0)
            lb.append(1); ub.append(1); r += 1
        for z in range(n):                           # only open sites can serve
            for j in range(n):
                rows += [r, r]; cols += [xi(z, j), j]; vals += [1.0, -1.0]
                lb.append(-np.inf); ub.append(0); r += 1
        self._base = LinearConstraint(coo_matrix((vals, (rows, cols)), shape=(r, nv)).tocsr(), lb, ub)
        self._count_row = np.concatenate([np.ones(n), np.zeros(n * ns)])
        self._borough_rows = []
        for prefix in ZONE_BOROUGH_PREFIX:
            row = np.zeros(nv)
            row[[i for i, z in enumerate(coverage.zones) if z[0] == prefix]] = 1
            if row.any():
                self._borough_rows.append(row)

    def _probabilities(self, weather_factor: float):
        """(T, P): mean response and P(within 8 min) for every zone x (site | stations only)."""
        cm = self.coverage
        ratio = np.hstack([cm.ratio, np.ones((self._n, 1))])
        T = cm.dispatch[:, None] + cm.travel[:, None] * weather_factor * ratio
        return T, pct_within(T)

    def _demand(self, predicted_counts: dict) -> np.ndarray:
        return np.array([max(float(predicted_counts.get(z, 0.0)), 0.01) for z in self.coverage.zones])

    def expected_within(self, sites, predicted_counts: dict, weather_factor: float = 1.0) -> float:
        """Expected calls reached within 8 min with these sites open (the objective)."""
        _, P = self._probabilities(weather_factor)
        cols = [self.coverage.index[s] for s in sites] + [self._n]
        return float((self._demand(predicted_counts) * P[:, cols].max(axis=1)).sum())

    def _solve(self, d: np.ndarray, K: int, weather_factor: float) -> list:
        T, P = self._probabilities(weather_factor)
        c_x = -(d[:, None] * P) + _TIE_EPS * d[:, None] * T / (d.sum() * 7200)
        c = np.concatenate([np.zeros(self._n), c_x.ravel()])
        constraints = [self._base, LinearConstraint(self._count_row[None, :], K, K)]
        if K >= MIN_BOROUGH_K and self._borough_rows:
            constraints.append(LinearConstraint(np.array(self._borough_rows), 1, np.inf))
        res = milp(c, constraints=constraints, integrality=np.ones(self._nv),
                   bounds=Bounds(0, 1), options={"mip_rel_gap": 0})
        if not res.success:
            raise RuntimeError(f"staging MILP failed: {res.message}")
        return [self.coverage.zones[j] for j in np.flatnonzero(res.x[:self._n] > 0.5)]

    def compute_staging(self, predicted_counts: dict, K: int, weather_factor: float = 1.0) -> list:
        if not 1 <= K <= self._n:
            raise ValueError(f"K must be between 1 and {self._n}, got {K}")
        sites = self._solve(self._demand(predicted_counts), K, weather_factor)
        return self._describe(sites, predicted_counts)

    def _describe(self, sites: list, predicted_counts: dict) -> list:
        """Pins in the API's shape; each zone is listed under the open site that improves it most."""
        cm = self.coverage
        r = cm.ratio[:, [cm.index[s] for s in sites]]          # [zone, open site]
        best = r.argmin(axis=1)
        results = []
        for k, site in enumerate(sites):
            served = [z for i, z in enumerate(cm.zones) if best[i] == k and r[i, k] < 1.0]
            lon, lat = ZONE_CENTROIDS[site]
            results.append({
                "zone": site,
                "lat": lat,
                "lon": lon,
                "coverage_radius_m": COVERAGE_RADIUS_M,
                "predicted_demand_coverage": round(float(sum(predicted_counts.get(z, 0) for z in served)), 2),
                "cluster_zones": sorted(served),
                "zone_count": len(served),
            })
        results.sort(key=lambda p: (-p["predicted_demand_coverage"], p["zone"]))
        for i, p in enumerate(results):
            p["staging_index"] = i
        return results
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `(cd backend && .venv/bin/python -m pytest tests/test_staging_optimizer.py -v)`
Expected: 50 passed.

- [ ] **Step 5: Run the backend suite**

Run: `(cd backend && .venv/bin/python -m pytest tests -q)`
Expected: FAIL in `tests/test_api.py` (staging/counterfactual tests) — the routers still call `StagingOptimizer()` with no argument. This is expected and fixed in Task 3; every other file passes. Record the failing test names.

- [ ] **Step 6: Commit**

```bash
git add backend/models/staging_optimizer.py backend/tests/test_staging_optimizer.py
git commit -m "feat: exact MILP coverage optimizer replaces weighted K-means

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Wire the API (`main.py`, staging and counterfactual routers)

**Files:**
- Modify: `backend/main.py` (ARTIFACTS dict ~line 27; end of `load_all_artifacts` ~line 111; `_artifact_status` ~line 197)
- Modify: `backend/routers/staging.py` (`_cached_heatmap_and_staging` body; guard in `get_staging`)
- Modify: `backend/routers/counterfactual.py` (imports/constants/helpers lines 1–119; zone loop in `_compute_dynamic_counterfactual`; `model_ready` in `get_counterfactual`)
- Modify: `backend/tests/test_api.py`

**Interfaces:**
- Consumes (Tasks 1–2): `build_coverage_model(drive_time, zone_stats)`, `weather_travel_factor`, `pct_within`, `StagingOptimizer(coverage).compute_staging(counts, K=, weather_factor=)`, `CoverageModel.zone_times(sites, weather_factor=)`, `ZONE_CENTROIDS`.
- Produces: `main.ARTIFACTS["coverage_model"]: CoverageModel | None`; `/health` and `/reload` report `artifacts.coverage_model: bool`; `/api/staging` returns mock with `X-Warning: coverage-model-missing` when it is `None`.

- [ ] **Step 1: Write the failing tests**

In `backend/tests/test_api.py`:

Replace the import block at the top (lines 1–11) with:

```python
import datetime as dt
import os
import pathlib
import shutil

import joblib
import numpy as np
import pandas as pd
import pytest
import xgboost as xgb

from fixtures_data import synthetic_count, synthetic_hourly_counts
from models.coverage_model import weather_travel_factor
from models.demand_forecaster import FEATURE_COLS, FEATURE_COLS_WITH_LAGS, VALID_ZONES
from models.staging_optimizer import ZONE_CENTROIDS

REAL_ARTIFACTS = pathlib.Path(__file__).resolve().parents[1] / "artifacts"
```

In `_write_artifacts`, add as its first line:

```python
    shutil.copy(REAL_ARTIFACTS / "drive_time_matrix.pkl", art / "drive_time_matrix.pkl")
```

Append to the end of the file:

```python
def _staging_sites(body):
    by_coords = {v: k for k, v in ZONE_CENTROIDS.items()}
    return [by_coords[tuple(f["geometry"]["coordinates"])] for f in body["features"]]


def test_health_reports_coverage_model(api):
    client, _ = api
    assert client.get("/health").json()["artifacts"]["coverage_model"] is True


def test_staging_pins_are_optimizer_sites(api):
    client, _ = api
    body = client.get("/api/staging", params={
        "hour": 20, "dow": 4, "month": 10, "date": "2025-10-10", "ambulances": 5}).json()
    sites = _staging_sites(body)            # KeyError if a pin is not on a zone centroid
    assert {s[0] for s in sites} == set("BKMQS")
    served = [z for f in body["features"] for z in f["properties"]["cluster_zones"]]
    assert len(served) == len(set(served))


@pytest.mark.parametrize("weather", [
    pytest.param({}, id="actual"),          # fixture weather: 0 mm, 7 km/h -> wf 1.0
    pytest.param({"temperature": 5, "precipitation": 12, "windspeed": 40}, id="what-if"),
])
def test_counterfactual_uses_the_staging_sites_and_coverage_model(api, weather):
    client, main = api
    from routers.counterfactual import _compute_dynamic_counterfactual
    _compute_dynamic_counterfactual.cache_clear()
    params = {"hour": 20, "dow": 4, "month": 10, "date": "2025-10-10", "ambulances": 5, **weather}
    sites = _staging_sites(client.get("/api/staging", params=params).json())
    r = client.get("/api/counterfactual", params=params)
    assert r.headers["X-Data-Source"] == "dynamic"
    wf = weather_travel_factor(weather.get("precipitation", 0.0), weather.get("windspeed", 7.0))
    expected = main.ARTIFACTS["coverage_model"].zone_times(sites, weather_factor=wf)
    by_zone = r.json()["by_zone"]
    for zone, (before, after) in expected.items():
        assert by_zone[zone]["static_time"] == pytest.approx(round(before, 1))
        assert by_zone[zone]["staged_time"] == pytest.approx(round(after, 1))
        assert by_zone[zone]["staged_time"] <= by_zone[zone]["static_time"]


def test_missing_coverage_model_serves_mock(api):
    client, main = api
    from routers.counterfactual import _compute_dynamic_counterfactual
    from routers.staging import _cached_heatmap_and_staging
    saved = main.ARTIFACTS["coverage_model"]
    main.ARTIFACTS["coverage_model"] = None
    _cached_heatmap_and_staging.cache_clear()
    _compute_dynamic_counterfactual.cache_clear()
    try:
        params = {"hour": 21, "dow": 4, "month": 10, "date": "2025-10-10"}
        r = client.get("/api/staging", params=params)
        assert r.headers["X-Data-Source"] == "mock"
        assert r.headers["X-Warning"] == "coverage-model-missing"
        r = client.get("/api/counterfactual", params=params)
        assert r.headers["X-Data-Source"] == "mock"
    finally:
        main.ARTIFACTS["coverage_model"] = saved


def test_reload_rebuilds_coverage_model(api):
    client, main = api
    main.ARTIFACTS["coverage_model"] = None
    body = client.post("/reload").json()
    assert body["artifacts"]["coverage_model"] is True
    assert main.ARTIFACTS["coverage_model"] is not None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `(cd backend && .venv/bin/python -m pytest tests/test_api.py -v)`
Expected: FAIL — the new tests fail (`KeyError: 'coverage_model'` in `/health`; staging/counterfactual return `X-Data-Source: mock` with `X-Warning: inference-error` because the routers call `StagingOptimizer()`), and the existing staging/counterfactual tests that failed at the end of Task 2 still fail.

- [ ] **Step 3: Build the coverage model in `main.py`**

In the `ARTIFACTS` dict, after `"weather_hourly": None,    # {hour Timestamp: real weather + flags} for replay`, add:

```python
    "coverage_model": None,    # CoverageModel built from drive_time + stations + zone_stats
```

At the end of `load_all_artifacts()` (after the breakdown-cache `try/except`), add:

```python
    from models.coverage_model import build_coverage_model
    ARTIFACTS["coverage_model"] = build_coverage_model(ARTIFACTS["drive_time"], ARTIFACTS["zone_stats"])
    if ARTIFACTS["coverage_model"] is not None:
        logger.info("✓  coverage model built (%d zones)", len(ARTIFACTS["coverage_model"].zones))
    else:
        logger.warning("⚠  coverage model unavailable — staging serves mock")
```

In `_artifact_status()`, after `"weather_hourly": ARTIFACTS["weather_hourly"] is not None,` add:

```python
        "coverage_model": ARTIFACTS["coverage_model"] is not None,
```

- [ ] **Step 4: Update `routers/staging.py`**

Replace the body of `_cached_heatmap_and_staging` from `from main import ARTIFACTS` through `return staging_points` with:

```python
    from main import ARTIFACTS
    from models.coverage_model import weather_travel_factor
    from models.demand_forecaster import DemandForecaster
    from models.staging_optimizer import StagingOptimizer

    forecaster = DemandForecaster(ARTIFACTS["demand_model"])
    predicted_counts = forecaster.predict_all_zones(
        hour, dow, month,
        temperature, precipitation, windspeed,
        ARTIFACTS["zone_stats"],
        ARTIFACTS["baselines"],
        replay_date=dt.date.fromisoformat(replay_date_iso),
        counts_wide=ARTIFACTS["hourly_counts"],
        calendar=ARTIFACTS["calendar_daily"],
        weather_flags=dict(weather_flags) if weather_flags else None,
    )

    optimizer = StagingOptimizer(ARTIFACTS["coverage_model"])
    return optimizer.compute_staging(
        predicted_counts, K=ambulances,
        weather_factor=weather_travel_factor(precipitation, windspeed),
    )
```

In `get_staging`, directly after the `lag-artifact-missing` `if` block (before `try:`), add:

```python
    if ARTIFACTS.get("coverage_model") is None:
        logger.warning("Staging: coverage model unavailable (drive-time matrix, stations or zone_stats missing)")
        return JSONResponse(
            content=MOCK_DATA["staging"],
            headers={"X-Data-Source": "mock", "X-Warning": "coverage-model-missing"},
        )
```

- [ ] **Step 5: Update `routers/counterfactual.py`**

5a. Replace everything from line 1 through the end of `_estimate_pct_under_threshold` (the line `    return float(0.5 * (1.0 + math.erf(z / math.sqrt(2))))`) with:

```python
import asyncio
import datetime as dt
import logging
import random
from functools import lru_cache
from typing import Optional

import numpy as np
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from models.coverage_model import pct_within, weather_travel_factor

logger = logging.getLogger(__name__)
router = APIRouter()

BOROUGH_KEYS = ["BRONX", "BROOKLYN", "MANHATTAN", "QUEENS", "RICHMOND / STATEN ISLAND"]

ZONE_BOROUGH = {
    'B1': 'BRONX', 'B2': 'BRONX', 'B3': 'BRONX', 'B4': 'BRONX', 'B5': 'BRONX',
    'K1': 'BROOKLYN', 'K2': 'BROOKLYN', 'K3': 'BROOKLYN', 'K4': 'BROOKLYN',
    'K5': 'BROOKLYN', 'K6': 'BROOKLYN', 'K7': 'BROOKLYN',
    'M1': 'MANHATTAN', 'M2': 'MANHATTAN', 'M3': 'MANHATTAN', 'M4': 'MANHATTAN',
    'M5': 'MANHATTAN', 'M6': 'MANHATTAN', 'M7': 'MANHATTAN', 'M8': 'MANHATTAN', 'M9': 'MANHATTAN',
    'Q1': 'QUEENS', 'Q2': 'QUEENS', 'Q3': 'QUEENS', 'Q4': 'QUEENS',
    'Q5': 'QUEENS', 'Q6': 'QUEENS', 'Q7': 'QUEENS',
    'S1': 'RICHMOND / STATEN ISLAND', 'S2': 'RICHMOND / STATEN ISLAND', 'S3': 'RICHMOND / STATEN ISLAND',
}

SVI_DEFAULTS = {
    'B1': 0.94, 'B2': 0.89, 'B3': 0.87, 'B4': 0.72, 'B5': 0.68,
    'K1': 0.52, 'K2': 0.58, 'K3': 0.82, 'K4': 0.84, 'K5': 0.79, 'K6': 0.60, 'K7': 0.45,
    'M1': 0.31, 'M2': 0.18, 'M3': 0.15, 'M4': 0.20, 'M5': 0.12,
    'M6': 0.14, 'M7': 0.73, 'M8': 0.65, 'M9': 0.61,
    'Q1': 0.71, 'Q2': 0.44, 'Q3': 0.38, 'Q4': 0.55, 'Q5': 0.67, 'Q6': 0.48, 'Q7': 0.41,
    'S1': 0.38, 'S2': 0.32, 'S3': 0.28,
}


def _svi_quartile(svi):
    if svi <= 0.25:
        return "Q1"
    elif svi <= 0.50:
        return "Q2"
    elif svi <= 0.75:
        return "Q3"
    return "Q4"
```

(This deletes `AVG_RESPONSE_DEFAULTS`, `AVG_DISPATCH_DEFAULTS`, `AVG_TRAVEL_DEFAULTS`, `ZONE_CENTROIDS`, `_weather_travel_factor`, `_haversine_km`, `_estimate_pct_under_threshold`, and the `scipy.stats.lognorm` try-import. Nothing else imports them — `grep -rn "AVG_RESPONSE_DEFAULTS\|_haversine_km\|_estimate_pct" backend --include='*.py'` must print nothing after this step.)

5b. In `_compute_dynamic_counterfactual`, replace from the line `    optimizer = StagingOptimizer()` through the end of the `for zone in predicted_counts:` loop (the closing `})` of `zone_data.append({...})`) with:

```python
    coverage = ARTIFACTS["coverage_model"]
    weather_factor = weather_travel_factor(precipitation, windspeed)
    staging_points = StagingOptimizer(coverage).compute_staging(
        predicted_counts, K=ambulances, weather_factor=weather_factor)
    zone_times = coverage.zone_times([sp["zone"] for sp in staging_points], weather_factor=weather_factor)
    zone_stats_df = ARTIFACTS.get("zone_stats")

    # Per zone: mean response before/after staging, from the same travel model as /api/staging
    zone_data = []
    for zone in predicted_counts:
        svi = SVI_DEFAULTS.get(zone, 0.5)
        if zone_stats_df is not None and "svi_score" in zone_stats_df.columns:
            row = zone_stats_df[zone_stats_df["INCIDENT_DISPATCH_AREA"] == zone]
            if not row.empty:
                svi = float(row["svi_score"].iloc[0])
        static_time, staged_time = zone_times[zone]
        zone_data.append({
            "zone": zone,
            "borough": ZONE_BOROUGH.get(zone, "UNKNOWN"),
            "svi": svi,
            "demand": predicted_counts[zone],
            "static_time": static_time,
            "staged_time": staged_time,
            "seconds_saved": static_time - staged_time,
        })
```

5c. In the rest of `_compute_dynamic_counterfactual`, replace every `_estimate_pct_under_threshold(zd["static_time"])` with `float(pct_within(zd["static_time"]))` and every `_estimate_pct_under_threshold(zd["staged_time"])` with `float(pct_within(zd["staged_time"]))` (4 occurrences in total).

5d. In `get_counterfactual`, replace

```python
    model_ready = ARTIFACTS.get("demand_model") is not None and ARTIFACTS.get("baselines") is not None
```

with

```python
    model_ready = (
        ARTIFACTS.get("demand_model") is not None
        and ARTIFACTS.get("baselines") is not None
        and ARTIFACTS.get("coverage_model") is not None
    )
```

- [ ] **Step 6: Run the API tests to verify they pass**

Run: `(cd backend && .venv/bin/python -m pytest tests/test_api.py -v)`
Expected: 29 passed (23 existing + 6 new).

- [ ] **Step 7: Run the backend suite**

Run: `(cd backend && .venv/bin/python -m pytest tests -q)`
Expected: all pass, 0 failed.

- [ ] **Step 8: Commit**

```bash
git add backend/main.py backend/routers/staging.py backend/routers/counterfactual.py backend/tests/test_api.py
git commit -m "feat: staging and counterfactual share the coverage optimizer and travel model

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Shared per-hour stager for the pipeline + parity test

**Files:**
- Create: `pipeline/fw_staging.py`
- Create: `backend/tests/test_staging_parity.py`
- Modify: `pipeline/requirements.txt`, `pipeline/requirements-dev.txt`

**Interfaces:**
- Consumes (Tasks 1–3): `build_coverage_model`, `weather_travel_factor`, `StagingOptimizer`; `models.replay.resolve_weather`, `weather_to_lookup`, `calendar_to_lookup`; `models.lag_features.to_wide`; `models.demand_forecaster.DemandForecaster`.
- Produces: `class HourlyStager(artifacts_dir=REPO/"backend"/"artifacts", stations_path=REPO/"data"/"ems_stations.json")` with attributes `coverage`, `optimizer`, `forecaster`, and methods `demand(date_hour) -> tuple[dict, float]` (predicted counts, weather factor) and `staging(date_hour, K: int) -> list[dict]` (cached; same dicts as `compute_staging`). Raises `RuntimeError` if the coverage model can't be built.

- [ ] **Step 1: Write the failing parity test**

Create `backend/tests/test_staging_parity.py`:

```python
"""Script 08 (via pipeline/fw_staging.py) must place the same sites as /api/staging (spec §5)."""
import datetime as dt
import pathlib
import sys

import pandas as pd
import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
REAL = REPO / "backend" / "artifacts"
NEEDED = ["demand_model.pkl", "drive_time_matrix.pkl", "zone_stats.parquet", "zone_baselines.parquet",
          "hourly_counts.parquet", "calendar_daily.parquet", "weather_hourly.parquet"]
pytestmark = pytest.mark.skipif(not all((REAL / f).exists() for f in NEEDED),
                                reason="real artifacts not present")


@pytest.fixture(scope="module")
def real_api():
    import main
    from fastapi.testclient import TestClient
    from routers.counterfactual import _compute_dynamic_counterfactual
    from routers.staging import _cached_heatmap_and_staging
    saved = main.ARTIFACTS_DIR
    main.ARTIFACTS_DIR = REAL
    _cached_heatmap_and_staging.cache_clear()
    try:
        with TestClient(main.app) as client:
            yield client
    finally:
        main.ARTIFACTS_DIR = saved
        _cached_heatmap_and_staging.cache_clear()
        _compute_dynamic_counterfactual.cache_clear()


@pytest.fixture(scope="module")
def stager():
    sys.path.insert(0, str(REPO / "pipeline"))
    from fw_staging import HourlyStager
    return HourlyStager(REAL)


@pytest.mark.parametrize("date,hour,K", [
    ("2025-10-10", 20, 5),   # Fri 8 PM demo preset
    ("2025-10-20", 4, 5),    # Mon 4 AM demo preset
    ("2025-07-30", 18, 7),   # storm preset: 8.2 mm/h, wf > 1
])
def test_script_08_places_the_same_sites_as_the_api(real_api, stager, date, hour, K):
    d = dt.date.fromisoformat(date)
    r = real_api.get("/api/staging", params={
        "hour": hour, "dow": d.weekday(), "month": d.month, "date": date, "ambulances": K})
    assert r.headers["X-Data-Source"] == "model"
    api = [(tuple(f["geometry"]["coordinates"]), f["properties"]["cluster_zones"],
            f["properties"]["predicted_demand_coverage"]) for f in r.json()["features"]]
    offline = [((p["lon"], p["lat"]), p["cluster_zones"], p["predicted_demand_coverage"])
               for p in stager.staging(pd.Timestamp(date) + pd.Timedelta(hours=hour), K)]
    assert api == offline
```

- [ ] **Step 2: Run it to verify it fails**

Run: `(cd backend && .venv/bin/python -m pytest tests/test_staging_parity.py -v)`
Expected: 3 ERROR — `ModuleNotFoundError: No module named 'fw_staging'`.

- [ ] **Step 3: Write `pipeline/fw_staging.py`**

```python
"""Per-hour staging placement for pipeline scripts 07 and 08.

Mirrors /api/staging step for step — replay weather lookup, 1-dp rounding, forecast,
coverage optimizer — so offline results use the same sites the dashboard shows.
backend/tests/test_staging_parity.py holds the two in lockstep.
"""
import pathlib
import pickle
import sys

import joblib
import pandas as pd

REPO = pathlib.Path(__file__).resolve().parent.parent
if str(REPO / "backend") not in sys.path:
    sys.path.insert(0, str(REPO / "backend"))

from models.coverage_model import build_coverage_model, weather_travel_factor  # noqa: E402
from models.demand_forecaster import DemandForecaster  # noqa: E402
from models.lag_features import to_wide  # noqa: E402
from models.replay import calendar_to_lookup, resolve_weather, weather_to_lookup  # noqa: E402
from models.staging_optimizer import StagingOptimizer  # noqa: E402


class HourlyStager:
    def __init__(self, artifacts_dir=REPO / "backend" / "artifacts",
                 stations_path=REPO / "data" / "ems_stations.json"):
        a = pathlib.Path(artifacts_dir)
        self.zone_stats = pd.read_parquet(a / "zone_stats.parquet")
        self.baselines = pd.read_parquet(a / "zone_baselines.parquet")
        self.counts_wide = to_wide(pd.read_parquet(a / "hourly_counts.parquet"))
        self.calendar = calendar_to_lookup(pd.read_parquet(a / "calendar_daily.parquet"))
        self.weather = weather_to_lookup(pd.read_parquet(a / "weather_hourly.parquet"))
        self.forecaster = DemandForecaster(joblib.load(a / "demand_model.pkl"))
        with open(a / "drive_time_matrix.pkl", "rb") as f:
            drive_time = pickle.load(f)
        self.coverage = build_coverage_model(drive_time, self.zone_stats, stations_path)
        if self.coverage is None:
            raise RuntimeError("coverage model could not be built; see the log above")
        self.optimizer = StagingOptimizer(self.coverage)
        self._demand: dict = {}
        self._staging: dict = {}

    def demand(self, date_hour) -> tuple[dict, float]:
        """(predicted counts per zone, weather travel factor) for one replayed hour,
        with the hour's real weather resolved and rounded exactly as /api/staging does."""
        ts = pd.Timestamp(date_hour)
        if ts not in self._demand:
            day = ts.date()
            wx, flags, _ = resolve_weather(self.weather, day, ts.hour, None, None, None)
            temp, precip, wind = (round(wx[k], 1) for k in ("temperature", "precipitation", "windspeed"))
            counts = self.forecaster.predict_all_zones(
                ts.hour, day.weekday(), day.month, temp, precip, wind,
                self.zone_stats, self.baselines,
                replay_date=day, counts_wide=self.counts_wide, calendar=self.calendar,
                weather_flags=flags,
            )
            self._demand[ts] = (counts, weather_travel_factor(precip, wind))
        return self._demand[ts]

    def staging(self, date_hour, K: int) -> list:
        """Staging pins for one replayed hour and K ambulances (cached)."""
        key = (pd.Timestamp(date_hour), K)
        if key not in self._staging:
            counts, wf = self.demand(date_hour)
            self._staging[key] = self.optimizer.compute_staging(counts, K, weather_factor=wf)
        return self._staging[key]
```

Add `scipy>=1.11` to `pipeline/requirements.txt` (after `scikit-learn>=1.4.1`) and to `pipeline/requirements-dev.txt` (after `scikit-learn==1.8.0`).

- [ ] **Step 4: Run the parity test to verify it passes**

Run: `(cd backend && .venv/bin/python -m pytest tests/test_staging_parity.py -v)`
Expected: 3 passed.

- [ ] **Step 5: Run both suites**

Run: `(cd backend && .venv/bin/python -m pytest tests -q) && pipeline/.venv/bin/python -m pytest pipeline/tests -q`
Expected: backend all pass; pipeline 57 passed.

- [ ] **Step 6: Commit**

```bash
git add pipeline/fw_staging.py backend/tests/test_staging_parity.py pipeline/requirements.txt pipeline/requirements-dev.txt
git commit -m "feat: shared per-hour stager for pipeline, parity-tested against /api/staging

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Script 07 validation on the shared optimizer

**Files:**
- Rewrite: `pipeline/07_staging_optimizer.py`

**Interfaces:**
- Consumes (Task 4): `HourlyStager` (`demand`, `staging`, `coverage`, `optimizer`); Task 2 `expected_within`; Task 1 `pct_within`.
- Produces: a validation run that exits 1 if any staging check fails.

- [ ] **Step 1: Run the current script to record its behaviour (the failing baseline)**

Run: `pipeline/.venv/bin/python pipeline/07_staging_optimizer.py 2>&1 | tail -25`
Expected: completes with the old K-means output (`-> nearest zone:` lines, "Check 4: Friday staging = [...]"); it has no borough/brute-force/coverage checks. Note the Check 1–3 PASS/WARN results; they must be unchanged after the rewrite.

- [ ] **Step 2: Rewrite `pipeline/07_staging_optimizer.py`**

```python
"""
Script 07 — Staging Optimizer Validation (staging v2)
FirstWave | GT Hacklytics 2026

Validates the coverage optimizer (backend/models/staging_optimizer.py) on 3 replayed
hours, with the same inputs as /api/staging (pipeline/fw_staging.py).
This is a confidence check -- NOT an artifact producer. Exits 1 if a staging check fails.

Prerequisites: backend/artifacts/{demand_model.pkl, drive_time_matrix.pkl,
  zone_baselines.parquet, zone_stats.parquet, hourly_counts.parquet,
  calendar_daily.parquet, weather_hourly.parquet}, data/ems_stations.json

Run: pipeline/.venv/bin/python pipeline/07_staging_optimizer.py
"""

import itertools
import pathlib
import sys

import numpy as np
import pandas as pd

ARTIFACTS_DIR = pathlib.Path("backend/artifacts")
for name in ("demand_model.pkl", "drive_time_matrix.pkl", "zone_baselines.parquet", "zone_stats.parquet",
             "hourly_counts.parquet", "calendar_daily.parquet", "weather_hourly.parquet"):
    if not (ARTIFACTS_DIR / name).exists():
        print(f"ERROR: {ARTIFACTS_DIR / name} not found. Run Scripts 04–06 first.", file=sys.stderr)
        sys.exit(1)

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from fw_staging import HourlyStager  # noqa: E402
from models.coverage_model import pct_within  # noqa: E402
from models.demand_forecaster import VALID_ZONES  # noqa: E402
from models.staging_optimizer import ZONE_BOROUGH_PREFIX  # noqa: E402

K = 5

print("Loading artifacts...")
stager = HourlyStager(ARTIFACTS_DIR)
coverage, optimizer = stager.coverage, stager.optimizer
failures = []


def check(name: str, ok: bool, detail: str = ""):
    print(f"  {'PASS' if ok else 'FAIL'}: {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        failures.append(name)


def brute_force_best(counts: dict, k: int, wf: float) -> float:
    """Best expected calls within 8 min over every k-subset of sites (no borough rule)."""
    n = len(coverage.zones)
    ratio = np.hstack([coverage.ratio, np.ones((n, 1))])
    P = pct_within(coverage.dispatch[:, None] + coverage.travel[:, None] * wf * ratio)
    d = np.array([max(counts[z], 0.01) for z in coverage.zones])
    return max(float((d * P[:, list(S) + [n]].max(axis=1)).sum())
               for S in itertools.combinations(range(n), k))


# ── Step 2: Validate 3 scenarios ──────────────────────────────────────────────
scenarios = [
    ("Monday 4AM (quiet)", pd.Timestamp("2025-10-20 04:00")),
    ("Wednesday Noon",     pd.Timestamp("2025-10-22 12:00")),
    ("Friday 8PM (peak)",  pd.Timestamp("2025-10-10 20:00")),
]

results = {}
for label, ts in scenarios:
    counts, wf = stager.demand(ts)
    staging = stager.staging(ts, K)
    top5 = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:5]
    results[label] = {"ts": ts, "counts": counts, "wf": wf, "staging": staging, "top5": top5}

    print(f"\n{'─'*50}")
    print(f"Scenario: {label}  (weather factor {wf:.3f})")
    print(f"  Top 5 zones by predicted demand:")
    for zone, count in top5:
        bar = "#" * min(int(count), 30)
        print(f"    {zone}: {count:.1f} {bar}")
    print(f"  Total city demand: {sum(counts.values()):.1f} incidents/hr")
    print(f"  Staging sites (K={K}):")
    for p in staging:
        print(f"    [{p['staging_index']}] {p['zone']} ({p['lon']:.4f}, {p['lat']:.4f}) "
              f"improves {p['cluster_zones']} ({p['predicted_demand_coverage']:.1f} demand)")

# ── Step 3: Demand checks (unchanged from v1; informational) ─────────────────
print("\n" + "=" * 55)
print("  SCRIPT 07 -- VALIDATION CHECKS")
print("=" * 55)

fri_top5_zones = [z for z, _ in results["Friday 8PM (peak)"]["top5"]]
bk_in_top5 = sum(1 for z in fri_top5_zones if z.startswith(("B", "K")))
print(f"\n  Check 1: Friday 8PM top-5 = {fri_top5_zones}")
if bk_in_top5 >= 3:
    print(f"  PASS: {bk_in_top5}/5 are B/K zones (Bronx/Brooklyn)")
else:
    print(f"  FAIL: Only {bk_in_top5}/5 are B/K zones -- check zone_baseline_avg merge")

mon_counts = results["Monday 4AM (quiet)"]["counts"]
mon_max = max(mon_counts.values())
mon_mean = sum(mon_counts.values()) / len(mon_counts)
print(f"\n  Check 2: Monday 4AM -- max={mon_max:.2f}, mean={mon_mean:.2f}")
if mon_max < 8.0:
    print(f"  PASS: Monday 4AM max demand < 8 (quiet period)")
else:
    print(f"  WARNING: Monday 4AM max = {mon_max:.1f} -- seems high for quiet period")

fri_total = sum(results["Friday 8PM (peak)"]["counts"].values())
mon_total = sum(results["Monday 4AM (quiet)"]["counts"].values())
ratio = fri_total / mon_total if mon_total > 0 else 0
print(f"\n  Check 3: Demand ratio Friday 8PM / Monday 4AM = {ratio:.1f}x")
if ratio > 2.0:
    print(f"  PASS: Friday peak is {ratio:.1f}x Monday quiet")
else:
    print(f"  FAIL: Ratio < 2x -- model not capturing temporal patterns")

# ── Step 4: Staging checks (hard; exit 1 on failure) ─────────────────────────
print(f"\n  Check 4: coverage optimizer")
for label, r in results.items():
    counts, wf = r["counts"], r["wf"]
    sites = [p["zone"] for p in r["staging"]]
    check(f"{label}: {K} distinct valid sites", len(set(sites)) == K and set(sites) <= set(VALID_ZONES),
          str(sites))
    check(f"{label}: every borough has a site",
          {ZONE_BOROUGH_PREFIX[s[0]] for s in sites} == set(ZONE_BOROUGH_PREFIX.values()))
    staged = optimizer.expected_within(sites, counts, wf)
    stations_only = optimizer.expected_within([], counts, wf)
    check(f"{label}: staged coverage > stations only", staged > stations_only,
          f"{stations_only:.1f} -> {staged:.1f} expected calls within 8 min")
    k3 = [p["zone"] for p in stager.staging(r["ts"], 3)]
    best = brute_force_best(counts, 3, wf)
    check(f"{label}: K=3 matches brute force",
          abs(optimizer.expected_within(k3, counts, wf) - best) <= 1e-6, f"{best:.4f}")

fri = sorted(p["zone"] for p in results["Friday 8PM (peak)"]["staging"])
mon = sorted(p["zone"] for p in results["Monday 4AM (quiet)"]["staging"])
print(f"\n  Placement: Friday 8PM {fri} vs Monday 4AM {mon} "
      f"({'same sites' if fri == mon else 'sites differ'})")

print("\n" + "=" * 55)
if failures:
    print(f"  {len(failures)} staging check(s) FAILED: {failures}")
    print("=" * 55)
    sys.exit(1)
print("  -> All staging checks pass: run pipeline/.venv/bin/python pipeline/08_counterfactual_precompute.py")
print("=" * 55)
```

- [ ] **Step 3: Run it**

Run: `pipeline/.venv/bin/python pipeline/07_staging_optimizer.py 2>&1 | tail -30; echo "exit=${PIPESTATUS[0]}"`
Expected: 12 `PASS:` lines under Check 4 (4 per scenario), Checks 1–3 the same results as Step 1, `exit=0`.

- [ ] **Step 4: Run the pipeline suite**

Run: `pipeline/.venv/bin/python -m pytest pipeline/tests -q`
Expected: 57 passed.

- [ ] **Step 5: Commit**

```bash
git add pipeline/07_staging_optimizer.py
git commit -m "feat: script 07 validates the coverage optimizer (borough rule, brute force, gain)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Script 08 call-level counterfactual, artifact checks, regenerated artifacts

**Files:**
- Modify: `pipeline/test_artifacts.py` (Check 6 block; Check 7 equity block)
- Rewrite: `pipeline/08_counterfactual_precompute.py`
- Regenerate: `backend/artifacts/counterfactual_summary.parquet`, `backend/artifacts/counterfactual_raw.parquet`

**Interfaces:**
- Consumes (Tasks 1, 4): `HourlyStager.staging(ts, K)`, `HourlyStager.coverage` (`index`, `ratios`), `call_level_after`.
- Produces: parquet schemas unchanged — summary `hour, dayofweek, median_seconds_saved, pct_within_8min_static, pct_within_8min_staged, n_incidents` (168 rows); raw `hour, dayofweek, incident_zone, borough, svi_quartile, baseline_drive_sec, staged_drive_sec, seconds_saved, baseline_within_8min, staged_within_8min`. A `README VALUES` block on stdout that Task 7 reads.

- [ ] **Step 1: Tighten the artifact checks**

In `pipeline/test_artifacts.py`, replace:

```python
        # staged > static (when not null) — allow some bins to be worse
        # (e.g., geographically isolated areas like Staten Island)
        valid = cs.dropna(subset=["pct_within_8min_static","pct_within_8min_staged"])
        if len(valid):
            staged_better_count = (valid["pct_within_8min_staged"] >= valid["pct_within_8min_static"]).sum()
            pct_better = staged_better_count / len(valid) * 100
            check("staged >= static in majority of bins (>60%)", pct_better > 60,
                  f"{pct_better:.0f}% of {len(valid)} bins")
```

with:

```python
        # Staged units are extra to the stations, so no bin may get worse.
        valid = cs.dropna(subset=["pct_within_8min_static","pct_within_8min_staged"])
        if len(valid):
            worse = int((valid["pct_within_8min_staged"] < valid["pct_within_8min_static"]).sum())
            check("staged >= static in every bin", worse == 0, f"{worse} of {len(valid)} bins worse")
```

and replace:

```python
        # Equity check: Q4 should have more seconds saved than Q1
        q1_med = cr[cr["svi_quartile"]=="Q1"]["seconds_saved"].median()
        q4_med = cr[cr["svi_quartile"]=="Q4"]["seconds_saved"].median()
        check("equity: Q4 seconds_saved >= Q1", q4_med >= q1_med,
              f"Q1={q1_med:.0f}s, Q4={q4_med:.0f}s")
```

with:

```python
        # Staged units are extra to the stations, so no call may get slower.
        negative = int((cr["seconds_saved"] < 0).sum())
        check("seconds_saved >= 0 on every row", negative == 0, f"{negative:,} negative rows")

        # Equity is reported, not gated (staging v2): Q4 vs Q1 median seconds saved.
        q1_med = cr[cr["svi_quartile"]=="Q1"]["seconds_saved"].median()
        q4_med = cr[cr["svi_quartile"]=="Q4"]["seconds_saved"].median()
        print(f"  INFO  equity: median seconds saved Q1={q1_med:.0f}s, Q4={q4_med:.0f}s "
              f"({'Q4 >= Q1' if q4_med >= q1_med else 'Q4 < Q1'})")
```

- [ ] **Step 2: Run the checks against the current (v1) artifacts to verify they fail**

Run: `pipeline/.venv/bin/python pipeline/test_artifacts.py 2>&1 | tail -15; echo "exit=${PIPESTATUS[0]}"`
Expected: `FAIL  seconds_saved >= 0 on every row — 5,338 negative rows`, `exit=1`.

- [ ] **Step 3: Rewrite `pipeline/08_counterfactual_precompute.py`**

```python
"""
Script 08 — Counterfactual Pre-Computation (staging v2)
FirstWave | GT Hacklytics 2026

Produces the before/after impact numbers behind the README's Key Results and the
dashboard's fallback impact panel.

For real 2025 Priority 1+2 calls (up to 150 per hour x weekday slot):
  - BEFORE: the call's recorded response time (dispatch + travel)
  - AFTER:  the same dispatch; travel scaled by (drive from the nearest staging site or
            station) / (drive from the nearest station). Sites are placed for the call's
            own hour by the same optimizer and inputs as /api/staging, with K = 5.

Outputs:
  backend/artifacts/counterfactual_summary.parquet  (168 rows)
  backend/artifacts/counterfactual_raw.parquet      (one row per scored call, K = 5)

Prerequisites: backend/artifacts/{demand_model.pkl, drive_time_matrix.pkl,
  zone_baselines.parquet, zone_stats.parquet, hourly_counts.parquet,
  calendar_daily.parquet, weather_hourly.parquet}, pipeline/data/incidents_cleaned.parquet,
  data/ems_stations.json

Run: pipeline/.venv/bin/python pipeline/08_counterfactual_precompute.py
"""

import pathlib
import sys
from itertools import product

import numpy as np
import pandas as pd

# ── Paths ──────────────────────────────────────────────────────────────────────
PIPELINE_DATA = pathlib.Path("pipeline/data")
ARTIFACTS_DIR = pathlib.Path("backend/artifacts")
CLEANED_PQ    = PIPELINE_DATA / "incidents_cleaned.parquet"
SUMMARY_OUT   = ARTIFACTS_DIR / "counterfactual_summary.parquet"
RAW_OUT       = ARTIFACTS_DIR / "counterfactual_raw.parquet"

REQUIRED = [ARTIFACTS_DIR / name for name in (
    "demand_model.pkl", "drive_time_matrix.pkl", "zone_baselines.parquet", "zone_stats.parquet",
    "hourly_counts.parquet", "calendar_daily.parquet", "weather_hourly.parquet")] + [CLEANED_PQ]
for p in REQUIRED:
    if not p.exists():
        print(f"ERROR: {p} not found.", file=sys.stderr)
        sys.exit(1)

# ── Constants ──────────────────────────────────────────────────────────────────
THRESHOLD             = 480   # 8-minute clinical target in seconds
MAX_INCIDENTS_PER_BIN = 150   # cap per (hour, dow) bin for compute speed
HEADLINE_K            = 5     # the dashboard's default ambulance count
SENSITIVITY_K         = (3, 7, 10)
BOROUGHS = ["BRONX", "BROOKLYN", "MANHATTAN", "QUEENS", "RICHMOND / STATEN ISLAND"]

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from fw_staging import HourlyStager  # noqa: E402
from models.coverage_model import call_level_after  # noqa: E402

# ── Step 1: Load artifacts ─────────────────────────────────────────────────────
print("Loading artifacts...")
stager = HourlyStager(ARTIFACTS_DIR)
coverage = stager.coverage

# ── Step 2: Load 2025 high-acuity incidents ────────────────────────────────────
print("\nLoading 2025 (test split) Priority 1+2 incidents from cleaned parquet...")
inc_all = pd.read_parquet(CLEANED_PQ, columns=[
    "INCIDENT_ID", "BOROUGH", "INCIDENT_DISPATCH_AREA",
    "hour", "dayofweek", "date_hour", "INCIDENT_RESPONSE_SECONDS_QY",
    "INCIDENT_TRAVEL_TM_SECONDS_QY", "svi_score",
    "split", "is_high_acuity", "is_valid_response",
])
incidents_test = inc_all[
    (inc_all["split"] == "test")
    & (inc_all["is_high_acuity"] == 1)
    & (inc_all["is_valid_response"] == 1)
].copy()
del inc_all

incidents_test["svi_quartile"] = pd.qcut(
    incidents_test["svi_score"], q=4, labels=["Q1", "Q2", "Q3", "Q4"]
).astype(str)

usable = np.isfinite(call_level_after(
    incidents_test["INCIDENT_RESPONSE_SECONDS_QY"], incidents_test["INCIDENT_TRAVEL_TM_SECONDS_QY"], 1.0))
print(f"2025 Priority 1+2 incidents: {len(incidents_test):,}")
print(f"  excluded (travel time missing, <= 0, or > response): {(~usable).sum():,} ({(~usable).mean():.2%})")
incidents_test = incidents_test[usable]
assert incidents_test["INCIDENT_DISPATCH_AREA"].isin(list(coverage.index)).all()

# ── Step 3: Sample up to 150 calls per (hour x dow) bin ───────────────────────
samples = []
for hour, dow in product(range(24), range(7)):
    b = incidents_test[(incidents_test["hour"] == hour) & (incidents_test["dayofweek"] == dow)]
    if len(b) > MAX_INCIDENTS_PER_BIN:
        b = b.sample(MAX_INCIDENTS_PER_BIN, random_state=42)
    samples.append(b)
calls = pd.concat(samples, ignore_index=True)
response = calls["INCIDENT_RESPONSE_SECONDS_QY"].to_numpy(dtype=float)
travel = calls["INCIDENT_TRAVEL_TM_SECONDS_QY"].to_numpy(dtype=float)
zone_idx = calls["INCIDENT_DISPATCH_AREA"].map(coverage.index).to_numpy(dtype=int)
hours = calls.groupby("date_hour").indices
print(f"\nScoring {len(calls):,} calls across {len(hours):,} distinct hours...")


def staged_response(K: int) -> np.ndarray:
    """Call-level staged response with K sites placed for each call's own hour."""
    ratio = np.empty(len(calls))
    for i, (ts, idx) in enumerate(hours.items()):
        sites = [p["zone"] for p in stager.staging(ts, K)]
        ratio[idx] = coverage.ratios(sites)[zone_idx[idx]]
        if (i + 1) % 1000 == 0:
            print(f"  K={K}: {i + 1:,}/{len(hours):,} hours placed")
    return call_level_after(response, travel, ratio)


staged = staged_response(HEADLINE_K)
assert not np.isnan(staged).any()

# ── Step 4: Save parquet files (schemas unchanged) ────────────────────────────
raw_df = pd.DataFrame({
    "hour":                 calls["hour"].astype(int).to_numpy(),
    "dayofweek":            calls["dayofweek"].astype(int).to_numpy(),
    "incident_zone":        calls["INCIDENT_DISPATCH_AREA"].to_numpy(),
    "borough":              calls["BOROUGH"].to_numpy(),
    "svi_quartile":         calls["svi_quartile"].to_numpy(),
    "baseline_drive_sec":   response,   # name kept for the API; it is the full real response
    "staged_drive_sec":     staged,
    "seconds_saved":        response - staged,
    "baseline_within_8min": (response <= THRESHOLD).astype(int),
    "staged_within_8min":   (staged <= THRESHOLD).astype(int),
})
g = raw_df.groupby(["hour", "dayofweek"])
summary_df = pd.DataFrame({
    "median_seconds_saved":   g["seconds_saved"].median(),
    "pct_within_8min_static": g["baseline_within_8min"].mean() * 100,
    "pct_within_8min_staged": g["staged_within_8min"].mean() * 100,
    "n_incidents":            g.size(),
}).reindex(pd.MultiIndex.from_product([range(24), range(7)], names=["hour", "dayofweek"])).reset_index()
summary_df["n_incidents"] = summary_df["n_incidents"].fillna(0).astype(int)

summary_df.to_parquet(SUMMARY_OUT, index=False)
raw_df.to_parquet(RAW_OUT, index=False)
print(f"counterfactual_summary.parquet: {len(summary_df)} rows -> {SUMMARY_OUT}")
print(f"counterfactual_raw.parquet:     {len(raw_df):,} rows -> {RAW_OUT}")

# ── Step 5: Print key results ──────────────────────────────────────────────────
saved = raw_df["seconds_saved"]
static_pct = raw_df["baseline_within_8min"].mean() * 100
staged_pct = raw_df["staged_within_8min"].mean() * 100

print()
print("=" * 60)
print(f"  FIRSTWAVE COUNTERFACTUAL RESULTS (K={HEADLINE_K}, call level)")
print("=" * 60)
print(f"  Calls scored:                {len(raw_df):,}")
print(f"  Within 8 min -- before:      {static_pct:.1f}%")
print(f"  Within 8 min -- after:       {staged_pct:.1f}%  (+{staged_pct - static_pct:.1f} pp)")
print(f"  Median seconds saved:        {saved.median():.0f} s")
print(f"  Mean seconds saved:          {saved.mean():.0f} s")
print(f"  Calls whose zone improves:   {(saved > 0).mean() * 100:.1f}%")

print("\n  By Borough (before -> after, median / mean seconds saved):")
borough_pct = {}
for borough in BOROUGHS:
    bdf = raw_df[raw_df["borough"] == borough]
    b_pct = bdf["baseline_within_8min"].mean() * 100
    s_pct = bdf["staged_within_8min"].mean() * 100
    borough_pct[borough] = (b_pct, s_pct)
    print(f"    {borough[:25]:25s}: {b_pct:.1f}% -> {s_pct:.1f}%, "
          f"{bdf['seconds_saved'].median():.0f}s / {bdf['seconds_saved'].mean():.0f}s")

print("\n  By SVI Quartile (equity, informational):")
svi_saved = {}
for q in ["Q1", "Q2", "Q3", "Q4"]:
    qdf = raw_df[raw_df["svi_quartile"] == q]
    svi_saved[q] = (qdf["seconds_saved"].median(), qdf["seconds_saved"].mean())
    print(f"    {q}: {qdf['baseline_within_8min'].mean()*100:.1f}% -> {qdf['staged_within_8min'].mean()*100:.1f}%, "
          f"median {svi_saved[q][0]:.0f}s, mean {svi_saved[q][1]:.0f}s saved")

layouts = pd.Series([tuple(sorted(p["zone"] for p in stager.staging(ts, HEADLINE_K))) for ts in hours])
top = layouts.value_counts()
print(f"\n  Placement stability: {layouts.nunique()} distinct {HEADLINE_K}-site layouts over "
      f"{len(layouts):,} hours; most common {list(top.index[0])} in {top.iloc[0] / len(layouts):.0%} of hours")

print("\n  Sensitivity (same calls, sites re-placed each hour):")
sens = {HEADLINE_K: staged_pct}
for K in SENSITIVITY_K:
    sens[K] = (staged_response(K) <= THRESHOLD).mean() * 100
for K in sorted(sens):
    print(f"    K={K:2d}: {static_pct:.1f}% -> {sens[K]:.1f}% within 8 min")

readme = {
    "N_CALLS": f"{len(raw_df):,}",
    "STATIC_PCT": f"{static_pct:.1f}",
    "STAGED_PCT": f"{staged_pct:.1f}",
    "MEDIAN_SAVED": f"{saved.median():.0f}",
    "MEAN_SAVED": f"{saved.mean():.0f}",
    "IMPROVED_PCT": f"{(saved > 0).mean() * 100:.1f}",
    "BRONX_STATIC": f"{borough_pct['BRONX'][0]:.1f}",
    "BRONX_STAGED": f"{borough_pct['BRONX'][1]:.1f}",
    "N_HOURS": f"{len(layouts):,}",
    "N_SITE_SETS": f"{layouts.nunique()}",
    "TOP_SET": ", ".join(top.index[0]),
    "TOP_SET_PCT": f"{top.iloc[0] / len(layouts) * 100:.0f}",
    **{f"{q}_MEDIAN_SAVED": f"{svi_saved[q][0]:.0f}" for q in svi_saved},
    **{f"{q}_MEAN_SAVED": f"{svi_saved[q][1]:.0f}" for q in svi_saved},
    **{f"K{K}_PCT": f"{sens[K]:.1f}" for K in SENSITIVITY_K},
}
print("\n  README VALUES")
for k, v in readme.items():
    print(f"    {k}={v}")
print("=" * 60)
```

- [ ] **Step 4: Run script 08 (10–40 min)**

Run in the background, logging to the plan workspace:
`pipeline/.venv/bin/python pipeline/08_counterfactual_precompute.py > "$WS/08_run.log" 2>&1` (where `$WS` is this plan's workspace directory; any scratch path works).
Wait for it to finish, then: `tail -60 "$WS/08_run.log"`
Expected: exits 0; `excluded ...: ~280 (0.08%)`; `counterfactual_summary.parquet: 168 rows`; `Within 8 min -- after` ≥ `before`; the `README VALUES` block with all 27 keys. Keep the log — Task 7 reads it.

- [ ] **Step 5: Run the artifact checks to verify they pass**

Run: `pipeline/.venv/bin/python pipeline/test_artifacts.py 2>&1 | tail -20; echo "exit=${PIPESTATUS[0]}"`
Expected: `PASS  staged >= static in every bin — 0 of 168 bins worse`, `PASS  seconds_saved >= 0 on every row — 0 negative rows`, an `INFO  equity:` line, `All checks passed!`, `exit=0`.

- [ ] **Step 6: Run both suites and script 07 again**

Run: `(cd backend && .venv/bin/python -m pytest tests -q) && pipeline/.venv/bin/python -m pytest pipeline/tests -q && pipeline/.venv/bin/python pipeline/07_staging_optimizer.py > /dev/null; echo "07 exit=$?"`
Expected: backend all pass; pipeline 57 passed; `07 exit=0`.

- [ ] **Step 7: Commit**

```bash
git add pipeline/test_artifacts.py pipeline/08_counterfactual_precompute.py backend/artifacts/counterfactual_summary.parquet backend/artifacts/counterfactual_raw.parquet
git commit -m "feat: script 08 scores real calls with the coverage optimizer at K=5; regenerate artifacts

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: README and CLAUDE.md

**Files:**
- Modify: `README.md` (Key Results; Features → optimizer and impact engine; Architecture line; Model B; Counterfactual Engine; Demo Scenarios Fri row; Tech Stack row; Repo Structure lines)
- Modify: `CLAUDE.md` (one added line under the Model B heading; new section appended at the end)

**Interfaces:**
- Consumes (Task 6): the `README VALUES` block in `$WS/08_run.log`. Every `{TOKEN}` below is replaced by the value printed for that key (e.g. `{STAGED_PCT}` ← the line `STAGED_PCT=58.3`). No `{` token may remain in either file.

- [ ] **Step 1: Write the check that fails first**

Run: `grep -n "K-Means\|K-means\|weighted centroid\|within 2 km\|floored at 2 minutes\|36% of calls" README.md | wc -l`
Expected: a non-zero count (the stale v1 descriptions). After Step 3 this must print `0`.

- [ ] **Step 2: Read the values**

Run: `sed -n '/README VALUES/,/====/p' "$WS/08_run.log"`
Expected: 27 `KEY=value` lines.

- [ ] **Step 3: Edit `README.md`**

3a. Replace the whole `## Key Results` section (from `## Key Results` up to, not including, the `---` before `## Features`) with:

```markdown
## Key Results

Simulated on **{N_CALLS} Priority 1–2 calls from 2025**, a year the model never trained on (up to 150 calls for each of the 168 hour-of-week slots), with **5 staged ambulances** (the dashboard default) placed from each call's own hour:

| Metric | Without FirstWave | With FirstWave |
|---|---|---|
| Calls reached within 8 minutes | {STATIC_PCT}% | **{STAGED_PCT}%** |
| Calls whose zone gets a closer unit | — | **{IMPROVED_PCT}%** |
| Response time saved, mean (median) | — | **{MEAN_SAVED} s** ({MEDIAN_SAVED} s) |
| Bronx within 8 minutes | {BRONX_STATIC}% | **{BRONX_STAGED}%** |

**How to read these numbers.** "Without" is each call's real recorded response time (dispatch plus travel). "With" keeps the same dispatch time and shortens only the travel part, by how much closer the nearest staged ambulance is than the nearest station on the road network. Staged ambulances are extra to the stations, so no call gets slower.

**Where the ambulances go.** Sites are chosen to reach as many predicted calls as possible within 8 minutes. They mostly fill the biggest gaps in station coverage; the hour's forecast adjusts them at the margin. Across {N_HOURS} simulated hours there were {N_SITE_SETS} distinct 5-site layouts, and the most common one ({TOP_SET}) was used in {TOP_SET_PCT}% of hours.

**Equity.** Seconds saved by social-vulnerability quartile, mean (median): Q1 {Q1_MEAN_SAVED} s ({Q1_MEDIAN_SAVED}), Q2 {Q2_MEAN_SAVED} s ({Q2_MEDIAN_SAVED}), Q3 {Q3_MEAN_SAVED} s ({Q3_MEDIAN_SAVED}), Q4 {Q4_MEAN_SAVED} s ({Q4_MEDIAN_SAVED}).

**More ambulances.** Same calls, sites re-placed each hour: 3 → {K3_PCT}%, 5 → {STAGED_PCT}%, 7 → {K7_PCT}%, 10 → {K10_PCT}% within 8 minutes.

> **Assumptions.** (1) Drive-time ratios come from free-flow road times (OSMnx). They scale each call's real travel time, so real traffic is kept, but the ratio itself ignores congestion. (2) "Without" assumes the nearest station's unit would have responded. (3) Staged units are always free (no queueing). (4) Travel inside a zone is estimated as half the drive from the nearest neighbouring zone centre.

Method: `pipeline/08_counterfactual_precompute.py`.
```

3b. Replace the `### Borough-Fair Staging Optimizer` feature block (heading plus its 4 lines) with:

```markdown
### Coverage-Optimal Staging
Places K ambulances at zone centres to reach as many predicted calls as possible within 8 minutes:
- Uses the road-network drive-time matrix and the 30 fixed EMS stations: a staged unit only helps a zone where it is closer than that zone's nearest station
- Solved exactly (a mixed-integer program), not approximated; ties go to the lower average response time
- With 5 or more ambulances, every borough gets at least one (equity constraint)
- Each pin's tooltip lists the zones it actually improves; the circle is a fixed 3,500 m display radius
```

3c. In `### Counterfactual Impact Engine`, replace the line
`- **After** is the same dispatch time plus the drive from the nearest staging point.`
with
`- **After** keeps the same dispatch time and scales travel by how much closer the nearest staging site is than the nearest station.`

3d. In the Architecture list, replace `K borough-fair staging locations GeoJSON` with `K coverage-optimal staging locations GeoJSON`.

3e. Replace the `### Model B — Borough-Fair Staging Optimizer` section (heading through the `**Coverage radius:**` line) with:

```markdown
### Model B — Coverage-Optimal Staging Optimizer

`backend/models/staging_optimizer.py`, shared by `/api/staging`, `/api/counterfactual`, and pipeline scripts 07–08. The travel model is `backend/models/coverage_model.py`.

For zone z and candidate site j (the 31 zone centres), the travel multiplier is `r(z, j) = min(station_drive(z), site_drive(z, j)) / station_drive(z)`. Both drives come from the OSMnx matrix plus a within-zone term: half the drive from the nearest neighbouring zone centre. A zone's expected response is `dispatch + travel × weather × r`, and its chance of an 8-minute response comes from a lognormal (CV 0.95) around that mean.

The optimizer picks K sites that maximise predicted calls reached within 8 minutes (tie-break: lower mean response), with at least one site per borough when K ≥ 5. It is solved exactly as a mixed-integer program with SciPy's HiGHS solver in a few milliseconds, and tests check it against brute force for K = 1–4.

Because the stations are part of the model, the best sites are set mostly by gaps in station coverage; the hour's forecast moves them only at the margin.

**Display radius:** 3,500 m (map circle only; placement uses drive times)
```

3f. In `### Counterfactual Engine`, replace steps 2 and 3 of the call-level list with:

```markdown
2. For each call's actual hour, forecast all 31 zones using that hour's real weather and place 5 staging sites with the same optimizer and inputs as the dashboard (`backend/tests/test_staging_parity.py` keeps them identical).
3. **Before** is the call's recorded response time. **After** keeps its dispatch time and scales its recorded travel time by `r(zone, nearest open site)`. Calls with a missing or invalid travel time (under 0.1%) are left out.
```

and add after step 4:

```markdown
5. The script also logs results for 3, 7, and 10 ambulances.
```

Then replace the live-estimate paragraph and its bullets (from `**Live estimate**` through the `% within 8 minutes` bullet) with:

```markdown
**Live estimate** (`/api/counterfactual`, what the dashboard shows). This uses the same forecast, optimizer, and travel model as the map, for the selected date, hour, weather, and ambulance count. Per zone:
- **Before** = average dispatch + weather-adjusted average travel.
- **After** = the same dispatch + that travel × `r(zone, nearest open site)`.
- **% within 8 minutes** comes from a lognormal CDF (CV = 0.95) around each zone's mean. Results are demand-weighted by borough, SVI quartile, and zone.

The live estimate works from zone averages and the lognormal; the call-level simulation uses real per-call times. They share placement and travel model, so they are close but not identical.
```

3g. In `## Demo Scenarios`, replace `Bronx and Brooklyn go red, and staging points cluster around the high-demand zones. This is the pitch.` with `Bronx and Brooklyn go red. The staging pins fill the largest gaps in station coverage for that demand. This is the pitch.`

3h. In `## Tech Stack`, replace `| ML — Staging Optimizer | scikit-learn (K-Means) | 1.8.0 |` with `| ML — Staging Optimizer | SciPy MILP (HiGHS) | 1.17 |`.

3i. In `## Repo Structure`, replace `│   │   └── staging_optimizer.py    Borough-fair weighted K-Means` with:

```
│   │   ├── coverage_model.py       Travel model shared by staging, counterfactual, pipeline 07–08
│   │   └── staging_optimizer.py    Coverage-optimal staging (exact MILP)
```

- [ ] **Step 4: Edit `CLAUDE.md` (add only)**

Directly under the heading `## Model B — Weighted K-Means Staging Optimizer`, insert one line (delete nothing):

```markdown
> **Superseded 2026-09-28 by Staging v2 (section at the end of this file). Kept for history.**
```

Append at the end of the file:

```markdown

---

## Staging v2 — Coverage-Optimal Staging (added 2026-09-28)

Spec: `docs/superpowers/specs/2026-09-28-coverage-staging-design.md` · Plan: `docs/superpowers/plans/2026-09-28-coverage-staging.md`

Replaces Model B. One travel model (`backend/models/coverage_model.py`) and one optimizer (`backend/models/staging_optimizer.py`) serve `/api/staging`, `/api/counterfactual`, and pipeline scripts 07 and 08 (via `pipeline/fw_staging.py`). `backend/tests/test_staging_parity.py` checks that 08 and `/api/staging` place identical sites.

- **Candidates:** the 31 zone centroids. The 30 stations in `data/ems_stations.json` are the fixed baseline; staged units are extra.
- **Travel ratio:** `r(z, j) = min(station_drive_z, site_drive[z, j]) / station_drive_z`, drives from `drive_time_matrix.pkl` plus `intra_z = ½ × nearest-other-zone drive` (the matrix diagonal is 0 s).
- **Zone level (API):** `after = dispatch + travel × wf × r`, `wf = 1 + 0.012 × precip + 0.002 × max(0, wind − 15)`; P(within 8 min) from a lognormal, CV 0.95.
- **Call level (08):** `after = response − travel × (1 − r)`; calls with missing, ≤ 0, or > response travel are excluded.
- **Objective:** maximise expected calls within 480 s, tie-break lower mean response; exact MILP (`scipy.optimize.milp`, HiGHS, `mip_rel_gap = 0`); ≥ 1 site per borough when K ≥ 5.
- **API:** field names unchanged. Pins sit on zone centroids; `cluster_zones` lists only zones the pin improves (a pin can have none); `coverage_radius_m` (3500) is display-only. `/health` adds `artifacts.coverage_model`. If the matrix, stations, or zone_stats are missing, `/api/staging` returns mock with `X-Warning: coverage-model-missing` and `/api/counterfactual` falls back to the precomputed parquet.
- **Headline (08, K = 5):** {STATIC_PCT}% → {STAGED_PCT}% of calls within 8 min; K = 3 / 7 / 10: {K3_PCT}% / {K7_PCT}% / {K10_PCT}%. `pipeline/test_artifacts.py` requires `seconds_saved ≥ 0` on every row and staged ≥ static in every bin; the SVI equity check is informational.
- **Finding:** placement is driven mostly by station-coverage gaps; demand moves it at the margin ({N_SITE_SETS} distinct K = 5 layouts over {N_HOURS} hours).
```

- [ ] **Step 5: Verify no stale text or tokens remain**

Run: `grep -n "K-Means\|K-means\|weighted centroid\|within 2 km\|floored at 2 minutes\|36% of calls" README.md | wc -l; grep -n "{[A-Z0-9_]*}" README.md CLAUDE.md | wc -l; git diff --stat CLAUDE.md`
Expected: `0`, `0`, and the CLAUDE.md diff shows only insertions (`+`), no deletions.

- [ ] **Step 6: Commit**

```bash
git add README.md CLAUDE.md
git commit -m "docs: coverage-optimal staging method, assumptions, and regenerated results

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Self-review

- **Spec coverage:** §3 travel model → Task 1; §4 optimizer → Task 2; §5 main/staging/counterfactual → Task 3, 08 → Task 6, 07 → Task 5, requirements → Tasks 1 and 4; §6 tests → Tasks 1–4 and 6; §7 docs → Task 7; §8 rollout 1–3 → Tasks 5–6 (PR is the finishing step, owner merges); §9 assumptions → README box in Task 7.
- **Spec §6 "08's placement function":** 08 is a script with top-level side effects, so its placement lives in `pipeline/fw_staging.py`, which 08 calls; the parity test exercises that module.
- **Types:** `compute_staging(predicted_counts, K, weather_factor)` returns dicts with `zone`, used by Tasks 3, 4, 6; `zone_times` returns `{zone: (before, after)}`, used by Task 3 and its test; `HourlyStager.staging(ts, K)` / `.demand(ts)` used by Tasks 5–6.
