import json
import logging
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)
router = APIRouter()

_STATIONS_FILE = Path(__file__).parent.parent.parent / "data" / "ems_stations.json"

# Load once at module import — pure static file, no artifact dependency
try:
    with open(_STATIONS_FILE, "r") as _f:
        _STATIONS_DATA: list = json.load(_f)
    logger.info("✓  ems_stations.json loaded (%d stations)", len(_STATIONS_DATA))
except FileNotFoundError:
    logger.error("⚠  ems_stations.json not found at %s", _STATIONS_FILE)
    _STATIONS_DATA = []
except Exception as exc:
    logger.error("⚠  failed to load ems_stations.json: %s", exc)
    _STATIONS_DATA = []


@router.get("/stations")
async def get_stations():
    if not _STATIONS_DATA:
        return JSONResponse(
            status_code=503,
            content={"error": "EMS station data unavailable", "path": str(_STATIONS_FILE)},
        )

    features = [
        {
            "type": "Feature",
            "properties": {
                "station_id": s["station_id"],
                "name": s["name"],
                "borough": s["borough"],
                "address": s["address"],
                "dispatch_zone": s["dispatch_zone"],
            },
            "geometry": {
                "type": "Point",
                "coordinates": [s["lon"], s["lat"]],  # GeoJSON: [lon, lat]
            },
        }
        for s in _STATIONS_DATA
    ]

    return {
        "type": "FeatureCollection",
        "count": len(features),
        "features": features,
    }
