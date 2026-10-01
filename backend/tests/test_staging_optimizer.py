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
