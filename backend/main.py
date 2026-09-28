import json
import logging
import os
import pickle
import traceback
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

ARTIFACTS_DIR = Path(os.getenv("ARTIFACTS_DIR", "./artifacts"))
MOCK_DATA_PATH = Path(__file__).parent.parent / "data" / "mock_api_responses.json"

# ── Shared state ──────────────────────────────────────────────────────────────

ARTIFACTS: dict = {
    "demand_model": None,
    "drive_time": None,
    "baselines": None,
    "zone_stats": None,
    "counterfactual_summary": None,
    "counterfactual_raw": None,
    "hourly_counts": None,     # wide: index date_hour, one column per zone
    "calendar_daily": None,    # {(date, zone_prefix): flags}
    "model_metrics": None,     # dict from model_metrics.json
    "weather_hourly": None,    # {hour Timestamp: real weather + flags} for replay
}

MOCK_DATA: dict = {}
ZONE_GEOM_CACHE: dict = {}   # zone_code → GeoJSON geometry dict
BREAKDOWN_CACHE: list = []   # pre-computed at startup from zone_stats


# ── Artifact loading ──────────────────────────────────────────────────────────

def load_all_artifacts():
    global ARTIFACTS, BREAKDOWN_CACHE

    artifact_configs = [
        ("demand_model", ARTIFACTS_DIR / "demand_model.pkl", "joblib"),
        ("drive_time", ARTIFACTS_DIR / "drive_time_matrix.pkl", "pickle"),
        ("baselines", ARTIFACTS_DIR / "zone_baselines.parquet", "parquet"),
        ("zone_stats", ARTIFACTS_DIR / "zone_stats.parquet", "parquet"),
        ("counterfactual_summary", ARTIFACTS_DIR / "counterfactual_summary.parquet", "parquet"),
        ("counterfactual_raw", ARTIFACTS_DIR / "counterfactual_raw.parquet", "parquet"),
        ("hourly_counts", ARTIFACTS_DIR / "hourly_counts.parquet", "parquet"),
        ("calendar_daily", ARTIFACTS_DIR / "calendar_daily.parquet", "parquet"),
        ("model_metrics", ARTIFACTS_DIR / "model_metrics.json", "json"),
        ("weather_hourly", ARTIFACTS_DIR / "weather_hourly.parquet", "parquet"),
    ]

    from models.lag_features import to_wide
    from models.replay import calendar_to_lookup, weather_to_lookup
    postprocess = {
        "hourly_counts": to_wide,
        "calendar_daily": calendar_to_lookup,
        "weather_hourly": weather_to_lookup,
    }

    for key, path, loader in artifact_configs:
        if not path.exists():
            logger.warning("⚠  %s not found at %s — using mock", key, path)
            ARTIFACTS[key] = None
            continue
        try:
            if loader == "joblib":
                obj = joblib.load(path)
            elif loader == "pickle":
                with open(path, "rb") as f:
                    obj = pickle.load(f)
            elif loader == "json":
                with open(path) as f:
                    obj = json.load(f)
            else:
                obj = pd.read_parquet(path)

            if loader == "joblib" and hasattr(obj, "predict"):
                names = getattr(obj, "feature_names_in_", None)
                if names is None:
                    raise ValueError("model has no feature_names_in_")
                _ = obj.predict(pd.DataFrame([[0.0] * len(names)], columns=list(names)))
            elif loader == "parquet" and isinstance(obj, pd.DataFrame):
                assert len(obj) > 0, f"{key} parquet is empty"

            if key in postprocess:
                obj = postprocess[key](obj)

            ARTIFACTS[key] = obj
            logger.info("✓  loaded %s", key)

        except Exception as exc:
            logger.error("⚠  failed to load %s: %s — using mock", key, exc)
            ARTIFACTS[key] = None

    # Pre-compute breakdown cache
    if ARTIFACTS["zone_stats"] is not None:
        try:
            from routers.breakdown import _compute_breakdown
            BREAKDOWN_CACHE = _compute_breakdown(ARTIFACTS["zone_stats"])
            logger.info("✓  breakdown cache built (%d boroughs)", len(BREAKDOWN_CACHE))
        except Exception as exc:
            logger.error("⚠  breakdown cache failed: %s", exc)


def _load_mock_data():
    global MOCK_DATA
    try:
        with open(MOCK_DATA_PATH, "r") as f:
            MOCK_DATA = json.load(f)
        logger.info("✓  mock data loaded from %s", MOCK_DATA_PATH)
    except Exception as exc:
        logger.error("FATAL: could not load mock data: %s", exc)
        MOCK_DATA = {}


def _populate_zone_geom_cache():
    """
    Load zone geometries from PostGIS into memory at startup.
    If DB is unavailable, fall back to bounding-box approximations.
    """
    global ZONE_GEOM_CACHE
    database_url = os.getenv("DATABASE_URL", "")

    if database_url:
        try:
            import psycopg2
            conn = psycopg2.connect(database_url)
            cur = conn.cursor()
            cur.execute("""
                SELECT zone_code, ST_AsGeoJSON(geom)::json
                FROM dispatch_zone_boundaries
            """)
            for zone_code, geom in cur.fetchall():
                ZONE_GEOM_CACHE[zone_code] = geom
            cur.close()
            conn.close()
            logger.info("✓  zone geometry cache loaded (%d zones)", len(ZONE_GEOM_CACHE))
            return
        except Exception as exc:
            logger.warning("⚠  PostGIS unavailable (%s) — using centroid fallback geometries", exc)

    # Fallback: use mock heatmap geometries
    if MOCK_DATA and "heatmap" in MOCK_DATA:
        for feature in MOCK_DATA["heatmap"].get("features", []):
            zone = feature["properties"]["zone"]
            ZONE_GEOM_CACHE[zone] = feature["geometry"]
        logger.info("✓  zone geometry cache populated from mock data (%d zones)", len(ZONE_GEOM_CACHE))


# ── App setup ─────────────────────────────────────────────────────────────────

app = FastAPI(
    title="FirstWave API",
    version="2.0.0",
    description="Predictive ambulance staging dashboard — NYC EMS",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3004", "http://localhost:5173", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    _load_mock_data()
    load_all_artifacts()
    _populate_zone_geom_cache()
    logger.info("FirstWave API startup complete")


# ── Routers ───────────────────────────────────────────────────────────────────

from routers import heatmap, staging, counterfactual, historical, breakdown, stations, ai_panel  # noqa: E402

app.include_router(heatmap.router, prefix="/api")
app.include_router(staging.router, prefix="/api")
app.include_router(counterfactual.router, prefix="/api")
app.include_router(historical.router, prefix="/api")
app.include_router(breakdown.router, prefix="/api")
app.include_router(stations.router, prefix="/api")
app.include_router(ai_panel.router, prefix="/api")


# ── Health + Reload ───────────────────────────────────────────────────────────

def _artifact_status() -> dict:
    return {
        "demand_model": ARTIFACTS["demand_model"] is not None,
        "drive_time": ARTIFACTS["drive_time"] is not None,
        "baselines": ARTIFACTS["baselines"] is not None,
        "zone_stats": ARTIFACTS["zone_stats"] is not None,
        "counterfactual": ARTIFACTS["counterfactual_summary"] is not None,
        "hourly_counts": ARTIFACTS["hourly_counts"] is not None,
        "calendar_daily": ARTIFACTS["calendar_daily"] is not None,
        "weather_hourly": ARTIFACTS["weather_hourly"] is not None,
    }


@app.get("/health")
async def health():
    return {"status": "ok", "artifacts": _artifact_status(), "model_metrics": ARTIFACTS["model_metrics"]}


@app.post("/reload")
async def reload_artifacts():
    from routers.staging import _cached_heatmap_and_staging
    from routers.counterfactual import _compute_dynamic_counterfactual
    load_all_artifacts()
    _cached_heatmap_and_staging.cache_clear()
    _compute_dynamic_counterfactual.cache_clear()
    _populate_zone_geom_cache()
    return {"status": "reloaded", "artifacts": _artifact_status(), "model_metrics": ARTIFACTS["model_metrics"]}


# ── Exception handlers ────────────────────────────────────────────────────────

@app.exception_handler(422)
async def validation_error_handler(request: Request, exc):
    return JSONResponse(
        status_code=422,
        content={"error": "Invalid query parameters", "detail": str(exc)},
    )


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return JSONResponse(
        status_code=404,
        content={"error": "Resource not found", "path": str(request.url.path)},
    )


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception on %s: %s\n%s", request.url.path, exc, traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"},
        headers={"X-Warning": "unhandled-exception"},
    )
