import logging
from fastapi import APIRouter
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)
router = APIRouter()

BOROUGH_ZONES = {
    "BRONX": ["B1", "B2", "B3", "B4", "B5"],
    "BROOKLYN": ["K1", "K2", "K3", "K4", "K5", "K6", "K7"],
    "MANHATTAN": ["M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8", "M9"],
    "QUEENS": ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7"],
    "RICHMOND / STATEN ISLAND": ["S1", "S2", "S3"],
}

BOROUGH_ORDER = ["BRONX", "BROOKLYN", "MANHATTAN", "QUEENS", "RICHMOND / STATEN ISLAND"]


@router.get("/breakdown")
async def get_breakdown():
    from main import ARTIFACTS, MOCK_DATA, BREAKDOWN_CACHE

    if BREAKDOWN_CACHE:
        return JSONResponse(content=BREAKDOWN_CACHE, headers={"X-Data-Source": "parquet"})

    if ARTIFACTS.get("zone_stats") is None:
        return JSONResponse(
            content=MOCK_DATA["breakdown"],
            headers={"X-Data-Source": "mock"},
        )

    # Fallback: compute on the fly if cache wasn't built at startup
    try:
        return JSONResponse(
            content=_compute_breakdown(ARTIFACTS["zone_stats"]),
            headers={"X-Data-Source": "parquet"},
        )
    except Exception as exc:
        logger.exception("Breakdown error: %s", exc)
        return JSONResponse(
            content=MOCK_DATA["breakdown"],
            headers={"X-Data-Source": "mock", "X-Warning": "compute-error"},
        )


def _compute_breakdown(zone_stats_df) -> list:
    results = []
    for borough in BOROUGH_ORDER:
        zones = BOROUGH_ZONES[borough]
        subset = zone_stats_df[zone_stats_df["BOROUGH"] == borough]

        if subset.empty:
            # fallback values
            results.append({
                "name": borough,
                "avg_dispatch_seconds": 0.0,
                "avg_travel_seconds": 0.0,
                "avg_total_seconds": 0.0,
                "pct_held": 0.0,
                "high_acuity_ratio": 0.0,
                "zones": zones,
            })
            continue

        results.append({
            "name": borough,
            "avg_dispatch_seconds": round(float(subset["avg_dispatch_seconds"].mean()), 1) if "avg_dispatch_seconds" in subset.columns else 0.0,
            "avg_travel_seconds": round(float(subset["avg_travel_seconds"].mean()), 1) if "avg_travel_seconds" in subset.columns else 0.0,
            "avg_total_seconds": round(float(subset["avg_response_seconds"].mean()), 1) if "avg_response_seconds" in subset.columns else 0.0,
            "pct_held": round(float(subset["held_ratio"].mean()) * 100, 1) if "held_ratio" in subset.columns else 0.0,
            "high_acuity_ratio": round(float(subset["high_acuity_ratio"].mean()), 3) if "high_acuity_ratio" in subset.columns else 0.0,
            "zones": zones,
        })

    return results
