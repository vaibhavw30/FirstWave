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
