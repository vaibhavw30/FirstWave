"""
End-to-end smoke test for scripts 04 and 05 on synthetic data spanning the real
data window. Incidents follow a zone-level day-to-day random walk so lags carry
signal.
"""
import datetime as dt
import json
import os
import pathlib
import subprocess
import sys

import joblib
import numpy as np
import pandas as pd
import pytest

from fw_calendar import build_calendar_daily
from fw_config import DATA_END, DATA_START, VALID_ZONES, ZONE_PREFIX_BOROUGH

REPO = pathlib.Path(__file__).resolve().parents[2]
SVI = {z: 0.2 + 0.02 * i for i, z in enumerate(VALID_ZONES)}


def _write_inputs(data_dir: pathlib.Path) -> None:
    rng = np.random.default_rng(0)
    hours = pd.date_range(pd.Timestamp(DATA_START), pd.Timestamp(DATA_END) + pd.Timedelta(hours=23), freq="h")
    n_days = len(hours) // 24
    hour_profile = 0.5 + 0.5 * np.sin(2 * np.pi * (hours.hour.to_numpy() - 8) / 24) + 0.5

    frames = []
    for zi, zone in enumerate(VALID_ZONES):
        walk = np.exp(np.cumsum(rng.normal(0, 0.08, n_days)))
        rate = (0.3 + 0.05 * zi) * hour_profile * np.repeat(walk / walk.mean(), 24)
        n = rng.poisson(rate)
        ts = np.repeat(hours.values, n)
        k = len(ts)
        frames.append(pd.DataFrame({
            "INCIDENT_DISPATCH_AREA": zone,
            "BOROUGH": ZONE_PREFIX_BOROUGH[zone[0]],
            "date_hour": ts,
            "INCIDENT_RESPONSE_SECONDS_QY": rng.uniform(200, 900, k),
            "INCIDENT_TRAVEL_TM_SECONDS_QY": rng.uniform(100, 600, k),
            "DISPATCH_RESPONSE_SECONDS_QY": rng.uniform(20, 300, k),
            "is_high_acuity": rng.integers(0, 2, k),
            "is_held": rng.integers(0, 2, k),
            "is_valid_response": (rng.random(k) < 0.95).astype(int),
            "svi_score": SVI[zone],
        }))
    inc = pd.concat(frames, ignore_index=True)
    ts = pd.to_datetime(inc["date_hour"])
    split = np.select(
        [ts < "2022-01-01", ts < "2024-10-01", ts < "2025-01-01", ts < "2026-01-01"],
        ["history", "train", "valid", "test"], default="test_recent")
    inc["split"] = split
    inc.to_parquet(data_dir / "incidents_cleaned.parquet", index=False)

    pd.DataFrame({
        "date_hour": hours,
        "temperature_2m": 15.0, "precipitation": 0.0, "windspeed_10m": 10.0, "weathercode": 0,
        "is_severe_weather": 0, "is_extreme_heat": 0, "is_heat_emergency": 0,
    }).to_parquet(data_dir / "weather_hourly.parquet", index=False)

    build_calendar_daily(DATA_START, DATA_END, pd.DataFrame(columns=["event_date", "zone_prefix"])) \
        .to_parquet(data_dir / "calendar_daily.parquet", index=False)


@pytest.fixture(scope="module")
def run_dirs(tmp_path_factory):
    root = tmp_path_factory.mktemp("smoke")
    data_dir, art_dir = root / "data", root / "artifacts"
    data_dir.mkdir()
    art_dir.mkdir()
    _write_inputs(data_dir)
    env = {**os.environ, "FW_PIPELINE_DATA": str(data_dir), "FW_ARTIFACTS_DIR": str(art_dir)}
    r = subprocess.run([sys.executable, "pipeline/04_aggregate.py"],
                       cwd=REPO, env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-4000:] + r.stderr[-4000:]
    return data_dir, art_dir, env


def test_04_outputs(run_dirs):
    data_dir, art_dir, _ = run_dirs
    grid = pd.read_parquet(data_dir / "training_grid.parquet")
    assert len(grid) == 1_223_880
    assert grid["split"].value_counts().to_dict() == {
        "train": 746_976, "test": 271_560, "test_recent": 134_664,
        "valid": 68_448, "history": 2_232}
    assert grid.drop(columns=["split"]).isna().sum().sum() == 0
    non_numeric = [c for c in grid.columns
                   if c not in ("INCIDENT_DISPATCH_AREA", "split", "date_hour", "date")
                   and not pd.api.types.is_numeric_dtype(grid[c])]
    assert non_numeric == []
    assert len(pd.read_parquet(art_dir / "zone_baselines.parquet")) == 5_208
    assert len(pd.read_parquet(art_dir / "zone_stats.parquet")) == 31
    hc = pd.read_parquet(art_dir / "hourly_counts.parquet")
    assert len(hc) == 429_288
    assert hc["date_hour"].min() == pd.Timestamp("2024-12-01 00:00")
    assert hc["date_hour"].max() == pd.Timestamp("2026-06-30 23:00")
    assert len(pd.read_parquet(art_dir / "calendar_daily.parquet")) == 2_730


def test_05_trains_and_reports(run_dirs):
    data_dir, art_dir, env = run_dirs
    r = subprocess.run([sys.executable, "pipeline/05_train_demand_model.py", "--max-trees", "40"],
                       cwd=REPO, env=env, capture_output=True, text=True)
    assert r.returncode in (0, 1), r.stdout[-4000:] + r.stderr[-4000:]
    if r.returncode == 0:
        metrics = json.loads((art_dir / "model_metrics.json").read_text())
        model = joblib.load(art_dir / "demand_model.pkl")
        assert list(model.feature_names_in_) == metrics["feature_cols"]
        assert len(metrics["feature_cols"]) == 28
        assert metrics["gate"]["passed"] is True
    else:
        metrics = json.loads((data_dir / "model_metrics_candidate.json").read_text())
        assert (data_dir / "demand_model_candidate.pkl").exists()
        assert not (art_dir / "demand_model.pkl").exists()
        assert metrics["gate"]["passed"] is False
    assert set(metrics["test"]) == {"lag", "no_lag", "naive_168h", "baseline_avg"}
    assert set(metrics["test"]["lag"]) == {"rmse", "mae", "poisson_deviance"}
    assert len(metrics["test_rmse_by_hour"]["lag"]) == 24
    assert metrics["objective"] in ("reg:squarederror", "count:poisson")
