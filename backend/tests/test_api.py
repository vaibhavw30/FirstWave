import datetime as dt
import os

import joblib
import numpy as np
import pandas as pd
import pytest
import xgboost as xgb

from fixtures_data import synthetic_count, synthetic_hourly_counts
from models.demand_forecaster import FEATURE_COLS, FEATURE_COLS_WITH_LAGS, VALID_ZONES


def tiny_model(features):
    rng = np.random.default_rng(0)
    X = pd.DataFrame(rng.random((200, len(features))), columns=features)
    m = xgb.XGBRegressor(n_estimators=5, max_depth=2)
    m.fit(X, rng.poisson(3, 200))
    return m


def _write_artifacts(art):
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
    assert body["query_params"] == {"hour": 20, "dow": 4, "month": 10, "date": "2025-10-10"}
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
