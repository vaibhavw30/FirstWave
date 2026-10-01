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
