import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)
router = APIRouter()

VALID_ZONES = [
    'B1', 'B2', 'B3', 'B4', 'B5',
    'K1', 'K2', 'K3', 'K4', 'K5', 'K6', 'K7',
    'M1', 'M2', 'M3', 'M4', 'M5', 'M6', 'M7', 'M8', 'M9',
    'Q1', 'Q2', 'Q3', 'Q4', 'Q5', 'Q6', 'Q7',
    'S1', 'S2', 'S3',
]

ZONE_NAMES = {
    'B1': 'South Bronx', 'B2': 'West/Central Bronx', 'B3': 'East Bronx',
    'B4': 'North Bronx', 'B5': 'Riverdale',
    'K1': 'Southern Brooklyn', 'K2': 'Park Slope', 'K3': 'Bushwick',
    'K4': 'East New York', 'K5': 'Bed-Stuy', 'K6': 'Borough Park', 'K7': 'Williamsburg',
    'M1': 'Lower Manhattan', 'M2': 'Midtown South', 'M3': 'Midtown',
    'M4': 'Murray Hill', 'M5': 'Upper East Side S', 'M6': 'Upper East Side N',
    'M7': 'Harlem', 'M8': 'Washington Heights S', 'M9': 'Washington Heights N',
    'Q1': 'Far Rockaway', 'Q2': 'Flushing', 'Q3': 'Forest Hills',
    'Q4': 'Ridgewood', 'Q5': 'Jamaica', 'Q6': 'Astoria', 'Q7': 'Whitestone',
    'S1': 'North Shore SI', 'S2': 'Mid-Island SI', 'S3': 'South Shore SI',
}

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


@router.get("/historical/{zone_code}")
async def get_historical(zone_code: str):
    from main import ARTIFACTS, MOCK_DATA

    zone_code = zone_code.upper()
    if zone_code not in VALID_ZONES:
        raise HTTPException(status_code=404, detail={"error": "Zone not found", "zone": zone_code})

    zone_stats_df = ARTIFACTS.get("zone_stats")
    baselines_df = ARTIFACTS.get("baselines")

    if zone_stats_df is None:
        mock = dict(MOCK_DATA["historical_zone"])
        mock["zone"] = zone_code
        mock["borough"] = ZONE_BOROUGH[zone_code]
        mock["zone_name"] = ZONE_NAMES[zone_code]
        return JSONResponse(content=mock, headers={"X-Data-Source": "mock"})

    try:
        row = zone_stats_df[zone_stats_df["INCIDENT_DISPATCH_AREA"] == zone_code]
        if row.empty:
            mock = dict(MOCK_DATA["historical_zone"])
            mock["zone"] = zone_code
            mock["borough"] = ZONE_BOROUGH[zone_code]
            mock["zone_name"] = ZONE_NAMES[zone_code]
            return JSONResponse(content=mock, headers={"X-Data-Source": "mock", "X-Warning": "zone-not-in-stats"})

        r = row.iloc[0]

        # Build hourly_avg: average over all dow per hour for this zone
        hourly_avg = [0.0] * 24
        if baselines_df is not None:
            zone_baselines = baselines_df[baselines_df["INCIDENT_DISPATCH_AREA"] == zone_code]
            if not zone_baselines.empty:
                for h in range(24):
                    hour_rows = zone_baselines[zone_baselines["hour"] == h]
                    if not hour_rows.empty:
                        hourly_avg[h] = round(float(hour_rows["zone_baseline_avg"].mean()), 2)

        result = {
            "zone": zone_code,
            "borough": ZONE_BOROUGH[zone_code],
            "zone_name": ZONE_NAMES[zone_code],
            "svi_score": float(r["svi_score"]) if "svi_score" in r.index else 0.5,
            "avg_response_seconds": float(r["avg_response_seconds"]) if "avg_response_seconds" in r.index else 0.0,
            "avg_travel_seconds": float(r["avg_travel_seconds"]) if "avg_travel_seconds" in r.index else 0.0,
            "avg_dispatch_seconds": float(r["avg_dispatch_seconds"]) if "avg_dispatch_seconds" in r.index else 0.0,
            "high_acuity_ratio": float(r["high_acuity_ratio"]) if "high_acuity_ratio" in r.index else 0.0,
            "held_ratio": float(r["held_ratio"]) if "held_ratio" in r.index else 0.0,
            "hourly_avg": hourly_avg,
        }
        return JSONResponse(content=result, headers={"X-Data-Source": "parquet"})

    except Exception as exc:
        logger.exception("Historical lookup error: %s", exc)
        mock = dict(MOCK_DATA["historical_zone"])
        mock["zone"] = zone_code
        mock["borough"] = ZONE_BOROUGH[zone_code]
        mock["zone_name"] = ZONE_NAMES[zone_code]
        return JSONResponse(
            content=mock,
            headers={"X-Data-Source": "mock", "X-Warning": "lookup-error"},
        )
