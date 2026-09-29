import asyncio
import datetime as dt
import logging
import random
from functools import lru_cache
from typing import Optional

import numpy as np
import pandas as pd
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


@lru_cache(maxsize=256)
def _compute_dynamic_counterfactual(
    hour: int, dow: int, month: int,
    temperature: float, precipitation: float, windspeed: float,
    ambulances: int,
    replay_date_iso: str,
    weather_flags: tuple | None = None,
):
    from main import ARTIFACTS
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

    # Demand-weighted aggregation
    total_demand = sum(zd["demand"] for zd in zone_data)
    if total_demand < 0.01:
        total_demand = 1.0

    # Overall metrics
    weighted_saved = sum(zd["seconds_saved"] * zd["demand"] for zd in zone_data) / total_demand
    demand_static_within_8 = sum(
        zd["demand"] * float(pct_within(zd["static_time"]))
        for zd in zone_data
    )
    demand_staged_within_8 = sum(
        zd["demand"] * float(pct_within(zd["staged_time"]))
        for zd in zone_data
    )
    pct_static = demand_static_within_8 / total_demand * 100
    pct_staged = demand_staged_within_8 / total_demand * 100

    # Median seconds saved (demand-weighted by repeating values)
    expanded_saved = []
    for zd in zone_data:
        count = max(1, round(zd["demand"]))
        expanded_saved.extend([zd["seconds_saved"]] * count)
    median_saved = float(np.median(expanded_saved)) if expanded_saved else 0.0

    # By borough
    by_borough = {}
    for borough in BOROUGH_KEYS:
        b_zones = [zd for zd in zone_data if zd["borough"] == borough]
        if not b_zones:
            continue
        b_demand = sum(zd["demand"] for zd in b_zones)
        if b_demand < 0.01:
            b_demand = 1.0
        b_static_8 = sum(
            zd["demand"] * float(pct_within(zd["static_time"]))
            for zd in b_zones
        ) / b_demand * 100
        b_staged_8 = sum(
            zd["demand"] * float(pct_within(zd["staged_time"]))
            for zd in b_zones
        ) / b_demand * 100
        b_saved_exp = []
        for zd in b_zones:
            b_saved_exp.extend([zd["seconds_saved"]] * max(1, round(zd["demand"])))
        by_borough[borough] = {
            "static": round(b_static_8, 1),
            "staged": round(b_staged_8, 1),
            "median_saved_sec": round(float(np.median(b_saved_exp)), 1),
            "mean_saved_sec": round(_weighted_mean_saved(b_zones), 1),
        }

    # By SVI quartile
    by_svi_quartile = {}
    for q in ["Q1", "Q2", "Q3", "Q4"]:
        q_zones = [zd for zd in zone_data if _svi_quartile(zd["svi"]) == q]
        if not q_zones:
            by_svi_quartile[q] = {"median_saved_sec": 0.0, "mean_saved_sec": 0.0}
            continue
        q_saved_exp = []
        for zd in q_zones:
            q_saved_exp.extend([zd["seconds_saved"]] * max(1, round(zd["demand"])))
        by_svi_quartile[q] = {
            "median_saved_sec": round(float(np.median(q_saved_exp)), 1),
            "mean_saved_sec": round(_weighted_mean_saved(q_zones), 1),
        }

    # Histogram: demand-weighted per-zone response times
    histogram_baseline = []
    histogram_staged = []
    for zd in zone_data:
        count = max(1, round(zd["demand"]))
        # Add slight jitter for visual distribution spread
        for _ in range(count):
            jitter = random.gauss(0, 15)
            histogram_baseline.append(round(zd["static_time"] + jitter))
            histogram_staged.append(round(zd["staged_time"] + jitter))

    # Sample down to ~50 values for the histogram arrays
    if len(histogram_baseline) > 50:
        rng = random.Random(42)
        indices = rng.sample(range(len(histogram_baseline)), 50)
        histogram_baseline = [histogram_baseline[i] for i in sorted(indices)]
        histogram_staged = [histogram_staged[i] for i in sorted(indices)]

    by_zone = {
        zd["zone"]: {
            "static_time": round(zd["static_time"], 1),
            "staged_time": round(zd["staged_time"], 1),
            "seconds_saved": round(zd["seconds_saved"], 1),
        }
        for zd in zone_data
    }

    return {
        "hour": hour,
        "dayofweek": dow,
        "median_seconds_saved": round(median_saved, 1),
        "mean_seconds_saved": round(weighted_saved, 1),
        "pct_within_8min_static": round(pct_static, 1),
        "pct_within_8min_staged": round(pct_staged, 1),
        "by_borough": by_borough,
        "by_svi_quartile": by_svi_quartile,
        "histogram_baseline_seconds": histogram_baseline,
        "histogram_staged_seconds": histogram_staged,
        "by_zone": by_zone,
    }


def _weighted_mean_saved(zones):
    """Mean seconds saved over zone dicts, weighted like the median expansion (max(1, round(demand)))."""
    weights = [max(1, round(zd["demand"])) for zd in zones]
    return sum(zd["seconds_saved"] * w for zd, w in zip(zones, weights)) / sum(weights)


def _slot_rows(raw_df, hour, dow):
    if raw_df is None or not {"hour", "dayofweek"} <= set(raw_df.columns):
        return pd.DataFrame()
    return raw_df[(raw_df["hour"] == hour) & (raw_df["dayofweek"] == dow)]


def _mean_saved(rows):
    if rows is None or rows.empty or "seconds_saved" not in rows.columns:
        return 0.0
    return float(rows["seconds_saved"].mean())


@router.get("/counterfactual")
async def get_counterfactual(
    hour: int = Query(..., ge=0, le=23),
    dow: int = Query(..., ge=0, le=6),
    month: int = Query(default=10, ge=1, le=12),
    # Omit all three to replay the hour's real weather; any value makes it a what-if.
    temperature: Optional[float] = Query(default=None),
    precipitation: Optional[float] = Query(default=None),
    windspeed: Optional[float] = Query(default=None),
    ambulances: int = Query(default=5, ge=1, le=10),
    date: Optional[dt.date] = Query(default=None),
):
    from main import ARTIFACTS, MOCK_DATA
    from models.demand_forecaster import DemandForecaster
    from models.replay import OutOfReplayRange, resolve_request, resolve_weather

    try:
        replay_date, dow, month = resolve_request(date, dow, month)
    except OutOfReplayRange as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    wx, wx_flags, _ = resolve_weather(
        ARTIFACTS["weather_hourly"], replay_date, hour, temperature, precipitation, windspeed)

    # Dynamic computation if demand model + baselines (+ history for a lag model) are available
    model_ready = (
        ARTIFACTS.get("demand_model") is not None
        and ARTIFACTS.get("baselines") is not None
        and ARTIFACTS.get("coverage_model") is not None
    )
    if model_ready and DemandForecaster(ARTIFACTS["demand_model"]).uses_lags and ARTIFACTS.get("hourly_counts") is None:
        logger.warning("Counterfactual: lag model loaded but hourly_counts missing; using precomputed")
        model_ready = False
    if model_ready:
        try:
            result = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: _compute_dynamic_counterfactual(
                        hour, dow, month,
                        round(wx["temperature"], 1), round(wx["precipitation"], 1), round(wx["windspeed"], 1),
                        ambulances,
                        replay_date.isoformat(),
                        tuple(sorted(wx_flags.items())) if wx_flags else None,
                    ),
                ),
                timeout=5.0,
            )
            return JSONResponse(content=result, headers={"X-Data-Source": "dynamic"})
        except asyncio.TimeoutError:
            logger.error("Dynamic counterfactual timed out, falling back")
        except Exception as exc:
            logger.exception("Dynamic counterfactual error: %s", exc)

    # Fallback: precomputed parquet data
    summary_df = ARTIFACTS.get("counterfactual_summary")
    raw_df = ARTIFACTS.get("counterfactual_raw")

    if summary_df is None:
        logger.info("Counterfactual: artifact not loaded, returning mock data")
        return JSONResponse(
            content=MOCK_DATA.get("counterfactual", {}),
            headers={"X-Data-Source": "mock"},
        )

    try:
        row = summary_df[
            (summary_df["hour"] == hour) & (summary_df["dayofweek"] == dow)
        ]
        if row.empty:
            return JSONResponse(
                content=MOCK_DATA.get("counterfactual", {}),
                headers={"X-Data-Source": "mock", "X-Warning": "no-row-found"},
            )

        r = row.iloc[0]
        # Means describe this (hour, dayofweek) slot only; 0.0 when rows or the column are missing.
        slot_raw = _slot_rows(raw_df, hour, dow)
        result = {
            "hour": hour,
            "dayofweek": dow,
            "median_seconds_saved": float(r["median_seconds_saved"]),
            "mean_seconds_saved": _mean_saved(slot_raw),
            "pct_within_8min_static": float(r["pct_within_8min_static"]),
            "pct_within_8min_staged": float(r["pct_within_8min_staged"]),
            "by_borough": {},
            "by_svi_quartile": {},
            "histogram_baseline_seconds": [],
            "histogram_staged_seconds": [],
            "by_zone": {},
        }

        if raw_df is not None:
            if "borough" in raw_df.columns:
                for borough in BOROUGH_KEYS:
                    b = raw_df[raw_df["borough"] == borough]
                    if not b.empty:
                        result["by_borough"][borough] = {
                            "static": float(b["baseline_within_8min"].mean() * 100) if "baseline_within_8min" in b.columns else 0.0,
                            "staged": float(b["staged_within_8min"].mean() * 100) if "staged_within_8min" in b.columns else 0.0,
                            "median_saved_sec": float(b["seconds_saved"].median()) if "seconds_saved" in b.columns else 0.0,
                            "mean_saved_sec": _mean_saved(slot_raw[slot_raw["borough"] == borough]),
                        }

            if "svi_quartile" in raw_df.columns:
                for q in ["Q1", "Q2", "Q3", "Q4"]:
                    qdata = raw_df[raw_df["svi_quartile"] == q]
                    if not qdata.empty:
                        result["by_svi_quartile"][q] = {
                            "median_saved_sec": float(qdata["seconds_saved"].median()) if "seconds_saved" in qdata.columns else 0.0,
                            "mean_saved_sec": _mean_saved(slot_raw[slot_raw["svi_quartile"] == q]),
                        }

        if not result["by_borough"]:
            result["by_borough"] = MOCK_DATA.get("counterfactual", {}).get("by_borough", {})
        if not result["by_svi_quartile"]:
            result["by_svi_quartile"] = MOCK_DATA.get("counterfactual", {}).get("by_svi_quartile", {})
        if not result["histogram_baseline_seconds"]:
            result["histogram_baseline_seconds"] = MOCK_DATA.get("counterfactual", {}).get("histogram_baseline_seconds", [])
            result["histogram_staged_seconds"] = MOCK_DATA.get("counterfactual", {}).get("histogram_staged_seconds", [])

        return JSONResponse(content=result, headers={"X-Data-Source": "parquet"})

    except Exception as exc:
        logger.exception("Counterfactual error: %s", exc)
        return JSONResponse(
            content=MOCK_DATA.get("counterfactual", {}),
            headers={"X-Data-Source": "mock", "X-Warning": "lookup-error"},
        )
