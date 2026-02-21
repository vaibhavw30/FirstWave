import logging
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)
router = APIRouter()

BOROUGH_KEYS = ["BRONX", "BROOKLYN", "MANHATTAN", "QUEENS", "RICHMOND / STATEN ISLAND"]


@router.get("/counterfactual")
async def get_counterfactual(
    hour: int = Query(..., ge=0, le=23),
    dow: int = Query(..., ge=0, le=6),
):
    from main import ARTIFACTS, MOCK_DATA

    summary_df = ARTIFACTS.get("counterfactual_summary")
    raw_df = ARTIFACTS.get("counterfactual_raw")

    if summary_df is None:
        logger.info("Counterfactual: artifact not loaded, returning mock data")
        return JSONResponse(
            content=MOCK_DATA["counterfactual"],
            headers={"X-Data-Source": "mock"},
        )

    try:
        row = summary_df[
            (summary_df["hour"] == hour) & (summary_df["dayofweek"] == dow)
        ]
        if row.empty:
            return JSONResponse(
                content=MOCK_DATA["counterfactual"],
                headers={"X-Data-Source": "mock", "X-Warning": "no-row-found"},
            )

        r = row.iloc[0]
        result = {
            "hour": hour,
            "dayofweek": dow,
            "median_seconds_saved": float(r["median_seconds_saved"]),
            "pct_within_8min_static": float(r["pct_within_8min_static"]),
            "pct_within_8min_staged": float(r["pct_within_8min_staged"]),
            "by_borough": {},
            "by_svi_quartile": {},
            "histogram_baseline_seconds": [],
            "histogram_staged_seconds": [],
        }

        if raw_df is not None:
            subset = raw_df[(raw_df["hour"] == hour) & (raw_df["dayofweek"] == dow)]
            if not subset.empty and "BOROUGH" in subset.columns:
                for borough in BOROUGH_KEYS:
                    b = subset[subset["BOROUGH"] == borough]
                    if not b.empty:
                        result["by_borough"][borough] = {
                            "static": float(b["pct_within_8min_static"].mean()) if "pct_within_8min_static" in b.columns else 0.0,
                            "staged": float(b["pct_within_8min_staged"].mean()) if "pct_within_8min_staged" in b.columns else 0.0,
                            "median_saved_sec": float(b["median_seconds_saved"].median()) if "median_seconds_saved" in b.columns else 0.0,
                        }

            if "svi_quartile" in subset.columns:
                for q in ["Q1", "Q2", "Q3", "Q4"]:
                    qdata = subset[subset["svi_quartile"] == q]
                    if not qdata.empty:
                        result["by_svi_quartile"][q] = {
                            "median_saved_sec": float(qdata["median_seconds_saved"].median()) if "median_seconds_saved" in qdata.columns else 0.0,
                        }

        # Fall back to mock values if by_borough still empty
        if not result["by_borough"]:
            result["by_borough"] = MOCK_DATA["counterfactual"]["by_borough"]
        if not result["by_svi_quartile"]:
            result["by_svi_quartile"] = MOCK_DATA["counterfactual"]["by_svi_quartile"]
        if not result["histogram_baseline_seconds"]:
            result["histogram_baseline_seconds"] = MOCK_DATA["counterfactual"]["histogram_baseline_seconds"]
            result["histogram_staged_seconds"] = MOCK_DATA["counterfactual"]["histogram_staged_seconds"]

        return JSONResponse(content=result, headers={"X-Data-Source": "parquet"})

    except Exception as exc:
        logger.exception("Counterfactual error: %s", exc)
        return JSONResponse(
            content=MOCK_DATA["counterfactual"],
            headers={"X-Data-Source": "mock", "X-Warning": "lookup-error"},
        )
