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


def tiny_model(features):
    rng = np.random.default_rng(0)
    X = pd.DataFrame(rng.random((200, len(features))), columns=features)
    m = xgb.XGBRegressor(n_estimators=5, max_depth=2)
    m.fit(X, rng.poisson(3, 200))
    return m


def _write_artifacts(art):
    shutil.copy(REAL_ARTIFACTS / "drive_time_matrix.pkl", art / "drive_time_matrix.pkl")
    joblib.dump(tiny_model(FEATURE_COLS_WITH_LAGS), art / "demand_model.pkl")
    pd.DataFrame([
        {"INCIDENT_DISPATCH_AREA": z, "hour": h, "dayofweek": d, "zone_baseline_avg": 2.0}
        for z in VALID_ZONES for h in range(24) for d in range(7)
    ]).to_parquet(art / "zone_baselines.parquet", index=False)
    pd.DataFrame([{
        "INCIDENT_DISPATCH_AREA": z, "BOROUGH": "BRONX", "svi_score": 0.5,
        "avg_response_seconds": 600.0, "avg_travel_seconds": 400.0, "avg_dispatch_seconds": 200.0,
        "high_acuity_ratio": 0.2, "held_ratio": 0.05, "total_incidents": 1000,
    } for z in VALID_ZONES]).to_parquet(art / "zone_stats.parquet", index=False)
    synthetic_hourly_counts().to_parquet(art / "hourly_counts.parquet", index=False)
    pd.DataFrame({
        "date": [dt.date(2025, 10, 10)] * 5, "zone_prefix": list("BKMQS"),
        "is_holiday": 0, "is_school_day": 1, "is_major_event": 0,
    }).to_parquet(art / "calendar_daily.parquet", index=False)
    (art / "model_metrics.json").write_text('{"objective": "count:poisson"}')
    hours = pd.date_range("2025-01-01", "2026-06-30 23:00", freq="h")
    pd.DataFrame({
        "date_hour": hours, "temperature_2m": 20.0, "precipitation": 0.0, "windspeed_10m": 7.0,
        "is_severe_weather": 0, "is_extreme_heat": 0, "is_heat_emergency": 0,
    }).to_parquet(art / "weather_hourly.parquet", index=False)


@pytest.fixture(scope="module")
def api(tmp_path_factory):
    art = tmp_path_factory.mktemp("artifacts")
    _write_artifacts(art)
    os.environ["ARTIFACTS_DIR"] = str(art)
    os.environ["DATABASE_URL"] = ""
    import main
    main.ARTIFACTS_DIR = art
    from fastapi.testclient import TestClient
    with TestClient(main.app) as client:
        yield client, main


def test_health_reports_new_artifacts(api):
    client, _ = api
    body = client.get("/health").json()
    assert body["artifacts"]["hourly_counts"] is True
    assert body["artifacts"]["calendar_daily"] is True
    assert body["model_metrics"] == {"objective": "count:poisson"}


def test_heatmap_with_date(api):
    client, _ = api
    r = client.get("/api/heatmap", params={"hour": 20, "dow": 4, "month": 10, "date": "2025-10-10"})
    assert r.status_code == 200 and r.headers["X-Data-Source"] == "model"
    body = r.json()
    qp = body["query_params"]
    assert {k: qp[k] for k in ("hour", "dow", "month", "date")} == {"hour": 20, "dow": 4, "month": 10, "date": "2025-10-10"}
    assert {"temperature", "precipitation", "windspeed", "weather_source"} <= set(qp)
    assert len(body["features"]) == 31
    k7 = next(f for f in body["features"] if f["properties"]["zone"] == "K7")["properties"]
    assert k7["actual_count"] == synthetic_count("K7", pd.Timestamp("2025-10-10 20:00"))


def test_heatmap_without_date_uses_standin(api):
    client, _ = api
    body = client.get("/api/heatmap", params={"hour": 20, "dow": 4, "month": 10}).json()
    assert body["query_params"]["date"] == "2025-10-17"


def test_date_overrides_dow_and_month(api):
    client, _ = api
    body = client.get("/api/heatmap", params={"hour": 20, "dow": 0, "month": 1, "date": "2025-10-10"}).json()
    assert (body["query_params"]["dow"], body["query_params"]["month"]) == (4, 10)


@pytest.mark.parametrize("bad", ["2024-06-01", "2026-07-01", "2025-13-01", "tomorrow"])
def test_bad_dates_are_422(api, bad):
    client, _ = api
    r = client.get("/api/heatmap", params={"hour": 20, "dow": 4, "month": 10, "date": bad})
    assert r.status_code == 422


def test_last_replay_hour_serves(api):
    client, _ = api
    r = client.get("/api/heatmap", params={"hour": 23, "dow": 1, "month": 6, "date": "2026-06-30"})
    assert r.status_code == 200 and r.headers["X-Data-Source"] == "model"


def test_staging_with_date(api):
    client, _ = api
    r = client.get("/api/staging", params={"hour": 20, "dow": 4, "month": 10, "date": "2025-10-10", "ambulances": 5})
    assert r.status_code == 200 and r.headers["X-Data-Source"] == "model"
    assert len(r.json()["features"]) == 5


def test_lag_model_without_hourly_counts_falls_back_to_mock(api):
    client, main = api
    saved = main.ARTIFACTS["hourly_counts"]
    main.ARTIFACTS["hourly_counts"] = None
    try:
        r = client.get("/api/heatmap", params={"hour": 20, "dow": 4, "month": 10, "date": "2025-10-10"})
        assert r.headers["X-Data-Source"] == "mock"
        assert r.headers["X-Warning"] == "lag-artifact-missing"
        r = client.get("/api/staging", params={"hour": 20, "dow": 4, "month": 10, "date": "2025-10-10"})
        assert r.headers["X-Warning"] == "lag-artifact-missing"
    finally:
        main.ARTIFACTS["hourly_counts"] = saved


def test_old_21_feature_model_still_serves(api):
    client, main = api
    saved = main.ARTIFACTS["demand_model"]
    main.ARTIFACTS["demand_model"] = tiny_model(FEATURE_COLS)
    try:
        r = client.get("/api/heatmap", params={"hour": 20, "dow": 4, "month": 10, "date": "2025-10-10"})
        assert r.headers["X-Data-Source"] == "model"
        assert "actual_count" in r.json()["features"][0]["properties"]
    finally:
        main.ARTIFACTS["demand_model"] = saved


def test_reload_clears_staging_cache(api):
    client, _ = api
    from routers.staging import _cached_heatmap_and_staging
    client.get("/api/staging", params={"hour": 8, "dow": 1, "month": 3, "date": "2025-03-04"})
    assert _cached_heatmap_and_staging.cache_info().currsize > 0
    assert client.post("/reload").status_code == 200
    assert _cached_heatmap_and_staging.cache_info().currsize == 0


def test_health_reports_weather_artifact(api):
    client, _ = api
    assert client.get("/health").json()["artifacts"]["weather_hourly"] is True


def test_replay_uses_actual_weather_by_default(api):
    client, _ = api
    body = client.get("/api/heatmap", params={"hour": 20, "dow": 4, "month": 10, "date": "2025-10-10"}).json()
    assert body["query_params"]["weather_source"] == "actual"
    assert body["query_params"]["temperature"] == 20.0


def test_explicit_weather_is_what_if(api):
    client, _ = api
    body = client.get("/api/heatmap", params={
        "hour": 20, "dow": 4, "month": 10, "date": "2025-10-10",
        "temperature": 8, "precipitation": 8, "windspeed": 30}).json()
    assert body["query_params"]["weather_source"] == "request"
    assert body["query_params"]["precipitation"] == 8.0


def test_staging_with_actual_weather(api):
    client, _ = api
    r = client.get("/api/staging", params={"hour": 18, "dow": 2, "month": 7, "date": "2025-07-30"})
    assert r.status_code == 200 and r.headers["X-Data-Source"] == "model"


def _spy_predict(monkeypatch):
    from models.demand_forecaster import DemandForecaster
    calls = []
    real = DemandForecaster.predict_all_zones

    def spy(self, *args, **kwargs):
        calls.append((args, kwargs))
        return real(self, *args, **kwargs)

    monkeypatch.setattr(DemandForecaster, "predict_all_zones", spy)
    from routers.counterfactual import _compute_dynamic_counterfactual
    _compute_dynamic_counterfactual.cache_clear()
    return calls


def test_counterfactual_replays_date_with_lags_and_actual_weather(api, monkeypatch):
    client, main = api
    calls = _spy_predict(monkeypatch)
    r = client.get("/api/counterfactual", params={"hour": 20, "dow": 0, "date": "2025-10-10"})
    assert r.status_code == 200 and r.headers["X-Data-Source"] == "dynamic"
    assert len(r.json()["by_zone"]) == len(VALID_ZONES)
    (args, kwargs), = calls
    assert args[:3] == (20, 4, 10)                      # dow/month come from the date
    assert args[3:6] == (20.0, 0.0, 7.0)                # the hour's real weather
    assert kwargs["replay_date"] == dt.date(2025, 10, 10)
    assert kwargs["counts_wide"] is main.ARTIFACTS["hourly_counts"]
    assert kwargs["calendar"] is main.ARTIFACTS["calendar_daily"]


def test_counterfactual_explicit_weather_is_what_if(api, monkeypatch):
    client, _ = api
    calls = _spy_predict(monkeypatch)
    client.get("/api/counterfactual", params={
        "hour": 20, "dow": 4, "date": "2025-10-10", "temperature": 4, "precipitation": 12, "windspeed": 40})
    (args, kwargs), = calls
    assert args[3:6] == (4.0, 12.0, 40.0)
    assert kwargs["weather_flags"] is None


@pytest.mark.parametrize("bad", ["2024-06-01", "2026-07-01"])
def test_counterfactual_bad_dates_are_422(api, bad):
    client, _ = api
    r = client.get("/api/counterfactual", params={"hour": 20, "dow": 4, "date": bad})
    assert r.status_code == 422


def test_counterfactual_lag_model_without_hourly_counts_skips_dynamic(api):
    client, main = api
    from routers.counterfactual import _compute_dynamic_counterfactual
    _compute_dynamic_counterfactual.cache_clear()
    saved = main.ARTIFACTS["hourly_counts"]
    main.ARTIFACTS["hourly_counts"] = None
    try:
        r = client.get("/api/counterfactual", params={"hour": 20, "dow": 4, "date": "2025-10-10"})
        assert r.status_code == 200 and r.headers["X-Data-Source"] != "dynamic"
    finally:
        main.ARTIFACTS["hourly_counts"] = saved


def test_reload_clears_counterfactual_cache(api):
    client, _ = api
    from routers.counterfactual import _compute_dynamic_counterfactual
    client.get("/api/counterfactual", params={"hour": 9, "dow": 2, "date": "2025-03-05"})
    assert _compute_dynamic_counterfactual.cache_info().currsize > 0
    assert client.post("/reload").status_code == 200
    assert _compute_dynamic_counterfactual.cache_info().currsize == 0


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


# --- mean seconds saved (additive next to the frozen medians) -------------------------------

BOROUGHS = ["BRONX", "BROOKLYN", "MANHATTAN", "QUEENS", "RICHMOND / STATEN ISLAND"]


def test_counterfactual_dynamic_reports_mean_seconds_saved_at_every_level(api):
    client, _ = api
    from routers.counterfactual import _compute_dynamic_counterfactual
    _compute_dynamic_counterfactual.cache_clear()
    r = client.get("/api/counterfactual", params={
        "hour": 20, "dow": 4, "month": 10, "date": "2025-10-10", "ambulances": 5})
    assert r.headers["X-Data-Source"] == "dynamic"
    body = r.json()
    assert "median_seconds_saved" in body                     # frozen field still there
    assert body["mean_seconds_saved"] > 0
    assert body["mean_seconds_saved"] >= body["median_seconds_saved"]
    assert set(body["by_borough"]) <= set(BOROUGHS) and body["by_borough"]
    for b in body["by_borough"].values():
        assert "median_saved_sec" in b and b["mean_saved_sec"] >= 0
    assert set(body["by_svi_quartile"]) == {"Q1", "Q2", "Q3", "Q4"}
    for q in body["by_svi_quartile"].values():
        assert "median_saved_sec" in q and q["mean_saved_sec"] >= 0


def test_counterfactual_dynamic_top_level_mean_is_demand_weighted_zone_mean(api):
    client, _ = api
    from routers.counterfactual import _compute_dynamic_counterfactual
    _compute_dynamic_counterfactual.cache_clear()
    body = client.get("/api/counterfactual", params={
        "hour": 20, "dow": 4, "month": 10, "date": "2025-10-10", "ambulances": 5}).json()
    saved = [z["seconds_saved"] for z in body["by_zone"].values()]
    # By-zone values are unweighted-rounded, so the weighted mean must sit inside their range.
    assert min(saved) <= body["mean_seconds_saved"] <= max(saved)


def _precomputed_frames():
    summary = pd.DataFrame([{
        "hour": 20, "dayofweek": 4, "median_seconds_saved": 0.0,
        "pct_within_8min_static": 60.0, "pct_within_8min_staged": 70.0, "n_incidents": 6}])
    raw = pd.DataFrame({
        "hour": [20] * 6 + [3], "dayofweek": [4] * 6 + [0],
        "borough": ["BRONX", "BRONX", "BRONX", "QUEENS", "QUEENS", "QUEENS", "BRONX"],
        "svi_quartile": ["Q4", "Q4", "Q4", "Q1", "Q1", "Q1", "Q4"],
        "seconds_saved": [0.0, 0.0, 300.0, 0.0, 60.0, 0.0, 999.0],
        "baseline_within_8min": [0, 1, 0, 1, 1, 1, 0], "staged_within_8min": [1, 1, 1, 1, 1, 1, 0]})
    return summary, raw


@pytest.fixture
def precomputed_only(api):
    """Force the parquet fallback: no coverage model, so the dynamic path is skipped."""
    client, main = api
    keys = ("coverage_model", "counterfactual_summary", "counterfactual_raw")
    saved = {k: main.ARTIFACTS.get(k) for k in keys}
    summary, raw = _precomputed_frames()
    main.ARTIFACTS.update(coverage_model=None, counterfactual_summary=summary, counterfactual_raw=raw)
    yield client
    main.ARTIFACTS.update(saved)


def test_counterfactual_precomputed_reports_mean_seconds_saved(precomputed_only):
    r = precomputed_only.get("/api/counterfactual", params={"hour": 20, "dow": 4, "date": "2025-10-10"})
    assert r.headers["X-Data-Source"] == "parquet"
    body = r.json()
    assert body["median_seconds_saved"] == 0.0                # unchanged
    assert body["mean_seconds_saved"] == pytest.approx(60.0)  # (0+0+300+0+60+0)/6, the other slot excluded
    assert body["by_borough"]["BRONX"]["mean_saved_sec"] == pytest.approx(100.0)
    assert body["by_borough"]["QUEENS"]["mean_saved_sec"] == pytest.approx(20.0)
    assert body["by_svi_quartile"]["Q4"]["mean_saved_sec"] == pytest.approx(100.0)   # the hour-3 row (999) is another slot
    assert body["by_svi_quartile"]["Q1"]["mean_saved_sec"] == pytest.approx(20.0)
