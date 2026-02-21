"""
Script 01 — Ingest & Clean
FirstWave | GT Hacklytics 2026

Input:  EMS CSV file (path passed via --csv argument)
        Download: https://data.cityofnewyork.us/api/views/76xm-jjuj/rows.csv?accessType=DOWNLOAD
Output: pipeline/data/incidents_cleaned.parquet (~7.1M rows)

Run: python pipeline/01_ingest_clean.py --csv /path/to/ems_raw.csv
"""

import argparse
import pathlib
import sys
import duckdb

# ── Paths ──────────────────────────────────────────────────────────────────────
PIPELINE_DATA = pathlib.Path("pipeline/data")
PIPELINE_DATA.mkdir(parents=True, exist_ok=True)
OUT_PARQUET = PIPELINE_DATA / "incidents_cleaned.parquet"

# ── Constants ──────────────────────────────────────────────────────────────────
VALID_ZONES = [
    'B1','B2','B3','B4','B5',
    'K1','K2','K3','K4','K5','K6','K7',
    'M1','M2','M3','M4','M5','M6','M7','M8','M9',
    'Q1','Q2','Q3','Q4','Q5','Q6','Q7',
    'S1','S2','S3',
]
VALID_ZONES_SQL = ", ".join(f"'{z}'" for z in VALID_ZONES)

# ── CLI ────────────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument("--csv", required=True, help="Path to raw EMS CSV (~28.7M rows)")
args = parser.parse_args()

csv_path = pathlib.Path(args.csv).resolve()
if not csv_path.exists():
    print(f"ERROR: CSV not found at {csv_path}", file=sys.stderr)
    sys.exit(1)

print(f"Reading raw CSV: {csv_path}")
print("This will take 5-10 minutes for 28.7M rows via DuckDB...")

# ── DuckDB ingest + filter ─────────────────────────────────────────────────────
conn = duckdb.connect()

# Count raw rows first
raw_count = conn.execute(
    f"SELECT COUNT(*) FROM read_csv_auto('{csv_path}', ignore_errors=true)"
).fetchone()[0]
print(f"Raw row count: {raw_count:,}")

# DuckDB dayofweek(): 0=Sun...6=Sat
# Use (dayofweek + 6) % 7 to get 0=Mon, 6=Sun (same convention as CLAUDE.md)
conn.execute(f"""
COPY (
    SELECT
        -- parse datetime
        INCIDENT_DATETIME AS incident_dt,

        -- source columns kept for downstream use
        CAD_INCIDENT_ID,
        INCIDENT_DISPATCH_AREA,
        BOROUGH,
        INCIDENT_RESPONSE_SECONDS_QY::DOUBLE  AS INCIDENT_RESPONSE_SECONDS_QY,
        INCIDENT_TRAVEL_TM_SECONDS_QY::DOUBLE AS INCIDENT_TRAVEL_TM_SECONDS_QY,
        DISPATCH_RESPONSE_SECONDS_QY::DOUBLE  AS DISPATCH_RESPONSE_SECONDS_QY,
        FINAL_SEVERITY_LEVEL_CODE::INTEGER    AS FINAL_SEVERITY_LEVEL_CODE,
        HELD_INDICATOR,

        -- time features
        EXTRACT(year  FROM INCIDENT_DATETIME)::INTEGER AS year,
        EXTRACT(month FROM INCIDENT_DATETIME)::INTEGER AS month,
        (EXTRACT(dow  FROM INCIDENT_DATETIME)::INTEGER + 6) % 7 AS dayofweek,
        EXTRACT(hour  FROM INCIDENT_DATETIME)::INTEGER AS hour,
        date_trunc('hour', INCIDENT_DATETIME)          AS date_hour,
        CAST(INCIDENT_DATETIME AS DATE)                AS incident_date,

        -- derived flags
        CASE WHEN (EXTRACT(dow FROM INCIDENT_DATETIME)::INTEGER + 6) % 7 IN (5,6)
             THEN 1 ELSE 0 END AS is_weekend,
        CASE WHEN FINAL_SEVERITY_LEVEL_CODE::INTEGER IN (1,2) THEN 1 ELSE 0 END AS is_high_acuity,
        CASE WHEN HELD_INDICATOR = 'Y' THEN 1 ELSE 0 END AS is_held,
        CASE WHEN EXTRACT(year FROM INCIDENT_DATETIME) = 2020
             THEN 1 ELSE 0 END AS is_covid_year,

        -- train/test/exclude split
        CASE
            WHEN EXTRACT(year FROM INCIDENT_DATETIME) = 2023 THEN 'test'
            WHEN EXTRACT(year FROM INCIDENT_DATETIME) = 2020 THEN 'exclude'
            WHEN EXTRACT(year FROM INCIDENT_DATETIME)
                 BETWEEN 2019 AND 2022                                                          THEN 'train'
            ELSE 'exclude'
        END AS split

    FROM read_csv_auto('{csv_path}', ignore_errors=true)

    WHERE
        -- quality flags
        VALID_INCIDENT_RSPNS_TIME_INDC = 'Y'
        AND VALID_DISPATCH_RSPNS_TIME_INDC = 'Y'
        AND REOPEN_INDICATOR   = 'N'
        AND TRANSFER_INDICATOR = 'N'
        AND STANDBY_INDICATOR  = 'N'
        -- response time range
        AND TRY_CAST(INCIDENT_RESPONSE_SECONDS_QY AS DOUBLE) BETWEEN 1 AND 7200
        -- valid borough
        AND BOROUGH IS NOT NULL
        AND BOROUGH != 'UNKNOWN'
        -- valid dispatch zone
        AND INCIDENT_DISPATCH_AREA IN ({VALID_ZONES_SQL})
        -- zone-borough prefix must match
        AND (
               (BOROUGH = 'BRONX'              AND INCIDENT_DISPATCH_AREA LIKE 'B%')
            OR (BOROUGH = 'BROOKLYN'           AND INCIDENT_DISPATCH_AREA LIKE 'K%')
            OR (BOROUGH = 'MANHATTAN'          AND INCIDENT_DISPATCH_AREA LIKE 'M%')
            OR (BOROUGH = 'QUEENS'             AND INCIDENT_DISPATCH_AREA LIKE 'Q%')
            OR (BOROUGH LIKE '%STATEN%'        AND INCIDENT_DISPATCH_AREA LIKE 'S%')
        )
        -- datetime must parse successfully
        AND INCIDENT_DATETIME IS NOT NULL

) TO '{OUT_PARQUET}' (FORMAT PARQUET, COMPRESSION SNAPPY)
""")

print(f"\nParquet written: {OUT_PARQUET}")

# ── Validation ─────────────────────────────────────────────────────────────────
stats = conn.execute(f"""
    SELECT
        COUNT(*)                                              AS total,
        SUM(CASE WHEN split = 'train'   THEN 1 ELSE 0 END)  AS train_rows,
        SUM(CASE WHEN split = 'test'    THEN 1 ELSE 0 END)  AS test_rows,
        SUM(CASE WHEN split = 'exclude' THEN 1 ELSE 0 END)  AS excl_rows,
        COUNT(DISTINCT INCIDENT_DISPATCH_AREA)               AS distinct_zones
    FROM read_parquet('{OUT_PARQUET}')
""").fetchone()

total, train, test, excl, zones = stats

print()
print("=" * 55)
print("  SCRIPT 01 — VALIDATION")
print("=" * 55)
print(f"  Total after filters:    {total:>10,}")
print(f"  Training (2019,21,22):  {train:>10,}   <- expect ~5.6M")
print(f"  Holdout  (2023):        {test:>10,}   <- expect ~1.5M")
print(f"  Excluded (2020+other):  {excl:>10,}")
print(f"  Distinct zones:         {zones:>10}   <- expect 31")
print()

if train < 3_000_000:
    print("  WARNING: Training rows < 3M -- datetime parse may have failed!")
    print("  Check: inspect a few INCIDENT_DATETIME values for format variations")
else:
    print("  OK: Training row count looks good")

if test < 1_000_000:
    print("  WARNING: Test rows < 1M -- check year filter")
else:
    print("  OK: Test row count looks good")

if zones != 31:
    print(f"  WARNING: Expected 31 zones, found {zones}")
else:
    print("  OK: Exactly 31 dispatch zones")

# Zone distribution
print("\n  Zone distribution (top 10 by volume):")
zone_dist = conn.execute(f"""
    SELECT INCIDENT_DISPATCH_AREA, COUNT(*) AS cnt
    FROM read_parquet('{OUT_PARQUET}')
    GROUP BY 1 ORDER BY 2 DESC LIMIT 10
""").fetchdf()
print(zone_dist.to_string(index=False))

# Borough distribution
print("\n  Borough distribution:")
boro_dist = conn.execute(f"""
    SELECT BOROUGH, COUNT(*) AS cnt
    FROM read_parquet('{OUT_PARQUET}')
    GROUP BY 1 ORDER BY 2 DESC
""").fetchdf()
print(boro_dist.to_string(index=False))

print()
print("=" * 55)
print("  Next: python pipeline/02_weather_merge.py")
print("=" * 55)
