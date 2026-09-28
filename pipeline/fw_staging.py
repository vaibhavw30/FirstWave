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
