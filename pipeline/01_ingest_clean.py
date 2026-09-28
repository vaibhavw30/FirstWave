"""
Script 01 — Ingest & Clean
FirstWave | GT Hacklytics 2026

Input:  raw EMS CSV (--csv)
        Download: https://data.cityofnewyork.us/api/views/76xm-jjuj/rows.csv?accessType=DOWNLOAD
Output: $FW_PIPELINE_DATA/incidents_cleaned.parquet (default pipeline/data)
        one row per incident, 2021-12-01 → 2026-06-30, with a split column.

The demand label counts every incident that passes the zone/borough/indicator
filters. Response-time validity is NOT a filter here — it is the
is_valid_response column, used only for response-time averages (zone_stats, 08).

Run: python pipeline/01_ingest_clean.py --csv /path/to/ems_raw.csv
"""

import argparse
import datetime as dt
import os
import pathlib
import sys

import duckdb

from fw_config import DATA_END, DATA_START, VALID_ZONES, split_case_sql
from fw_ingest import missing_columns, pick_id_column

# ── Paths ──────────────────────────────────────────────────────────────────────
PIPELINE_DATA = pathlib.Path(os.getenv("FW_PIPELINE_DATA", "pipeline/data"))
PIPELINE_DATA.mkdir(parents=True, exist_ok=True)
OUT_PARQUET = PIPELINE_DATA / "incidents_cleaned.parquet"

VALID_ZONES_SQL = ", ".join(f"'{z}'" for z in VALID_ZONES)
WINDOW_END = DATA_END + dt.timedelta(days=1)

# ── CLI ────────────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument("--csv", required=True, help="Path to raw EMS CSV")
args = parser.parse_args()

csv_path = pathlib.Path(args.csv).resolve()
if not csv_path.exists():
    print(f"ERROR: CSV not found at {csv_path}", file=sys.stderr)
    sys.exit(1)

conn = duckdb.connect()
# all_varchar: no type sniffing, so a mis-typed sample can't silently drop rows.
SRC = f"read_csv('{csv_path}', header=true, all_varchar=true, ignore_errors=true)"

columns = [d[0] for d in conn.execute(f"SELECT * FROM {SRC} LIMIT 0").description]
missing = missing_columns(columns)
if missing:
    print(f"ERROR: raw CSV is missing columns: {missing}", file=sys.stderr)
    print(f"       Found: {columns}", file=sys.stderr)
    sys.exit(1)
id_col = pick_id_column(columns)

raw_count = conn.execute(f"SELECT COUNT(*) FROM {SRC}").fetchone()[0]
print(f"Reading raw CSV: {csv_path}")
print(f"Raw row count: {raw_count:,}   (ID column: {id_col})")

INCIDENT_DT = (
    "COALESCE(TRY_CAST(INCIDENT_DATETIME AS TIMESTAMP), "
    "try_strptime(INCIDENT_DATETIME, '%m/%d/%Y %I:%M:%S %p'))"
)

# dow: DuckDB 0=Sun..6=Sat -> (dow + 6) % 7 gives 0=Mon..6=Sun
conn.execute(f"""
COPY (
    WITH src AS (
        SELECT *, {INCIDENT_DT} AS incident_dt FROM {SRC}
    )
    SELECT
        incident_dt,
        {id_col}                                                 AS INCIDENT_ID,
        INCIDENT_DISPATCH_AREA,
        BOROUGH,
        TRY_CAST(INCIDENT_RESPONSE_SECONDS_QY  AS DOUBLE)        AS INCIDENT_RESPONSE_SECONDS_QY,
        TRY_CAST(INCIDENT_TRAVEL_TM_SECONDS_QY AS DOUBLE)        AS INCIDENT_TRAVEL_TM_SECONDS_QY,
        TRY_CAST(DISPATCH_RESPONSE_SECONDS_QY  AS DOUBLE)        AS DISPATCH_RESPONSE_SECONDS_QY,
        TRY_CAST(FINAL_SEVERITY_LEVEL_CODE     AS INTEGER)       AS FINAL_SEVERITY_LEVEL_CODE,
        HELD_INDICATOR,

        EXTRACT(year  FROM incident_dt)::INTEGER                 AS year,
        EXTRACT(month FROM incident_dt)::INTEGER                 AS month,
        (EXTRACT(dow  FROM incident_dt)::INTEGER + 6) % 7        AS dayofweek,
        EXTRACT(hour  FROM incident_dt)::INTEGER                 AS hour,
        date_trunc('hour', incident_dt)                          AS date_hour,
        CAST(incident_dt AS DATE)                                AS incident_date,

        CASE WHEN (EXTRACT(dow FROM incident_dt)::INTEGER + 6) % 7 IN (5, 6)
             THEN 1 ELSE 0 END                                   AS is_weekend,
        CASE WHEN TRY_CAST(FINAL_SEVERITY_LEVEL_CODE AS INTEGER) IN (1, 2)
             THEN 1 ELSE 0 END                                   AS is_high_acuity,
        CASE WHEN HELD_INDICATOR = 'Y' THEN 1 ELSE 0 END         AS is_held,
        CASE WHEN VALID_INCIDENT_RSPNS_TIME_INDC = 'Y'
              AND VALID_DISPATCH_RSPNS_TIME_INDC = 'Y'
              AND TRY_CAST(INCIDENT_RESPONSE_SECONDS_QY AS DOUBLE) BETWEEN 1 AND 7200
             THEN 1 ELSE 0 END                                   AS is_valid_response,

        {split_case_sql('incident_dt')}                          AS split

    FROM src
    WHERE incident_dt >= TIMESTAMP '{DATA_START} 00:00:00'
      AND incident_dt <  TIMESTAMP '{WINDOW_END} 00:00:00'
      AND REOPEN_INDICATOR   = 'N'
      AND TRANSFER_INDICATOR = 'N'
      AND STANDBY_INDICATOR  = 'N'
      AND BOROUGH IS NOT NULL
      AND BOROUGH != 'UNKNOWN'
      AND INCIDENT_DISPATCH_AREA IN ({VALID_ZONES_SQL})
      AND (
             (BOROUGH = 'BRONX'       AND INCIDENT_DISPATCH_AREA LIKE 'B%')
          OR (BOROUGH = 'BROOKLYN'    AND INCIDENT_DISPATCH_AREA LIKE 'K%')
          OR (BOROUGH = 'MANHATTAN'   AND INCIDENT_DISPATCH_AREA LIKE 'M%')
          OR (BOROUGH = 'QUEENS'      AND INCIDENT_DISPATCH_AREA LIKE 'Q%')
          OR (BOROUGH LIKE '%STATEN%' AND INCIDENT_DISPATCH_AREA LIKE 'S%')
      )
) TO '{OUT_PARQUET}' (FORMAT PARQUET, COMPRESSION SNAPPY)
""")

print(f"\nParquet written: {OUT_PARQUET}")

# ── Validation ─────────────────────────────────────────────────────────────────
summary = conn.execute(f"""
    SELECT split, year, COUNT(*) AS incidents,
           ROUND(AVG(is_valid_response) * 100, 1) AS pct_valid_response
    FROM read_parquet('{OUT_PARQUET}')
    GROUP BY split, year ORDER BY year, split
""").fetchdf()
zones = conn.execute(
    f"SELECT COUNT(DISTINCT INCIDENT_DISPATCH_AREA) FROM read_parquet('{OUT_PARQUET}')"
).fetchone()[0]

print()
print("=" * 60)
print("  SCRIPT 01 — VALIDATION")
print("=" * 60)
print(summary.to_string(index=False))
print(f"\n  Distinct zones: {zones}   <- expect 31")
print("  Expect ~1.5M+ incidents per full year and pct_valid_response")
print("  falling over time (~97% in 2022 to ~89% in mid-2026).")
if zones != 31:
    print(f"  WARNING: expected 31 zones, found {zones}")
print("=" * 60)
print("  Next: python pipeline/02_weather_merge.py")
