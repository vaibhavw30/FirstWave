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
