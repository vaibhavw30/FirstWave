"""
Script 03 — SVI Spatial Join
FirstWave | GT Hacklytics 2026

Input:  pipeline/data/incidents_cleaned.parquet (from Script 02)
Data:   Hardcoded CDC SVI lookup per zone (no external file needed)
Output: pipeline/data/incidents_cleaned.parquet (overwritten with svi_score column)

Run: python pipeline/03_spatial_join.py
"""

import pathlib
import sys
import pandas as pd
import duckdb

# ── Paths ──────────────────────────────────────────────────────────────────────
PIPELINE_DATA = pathlib.Path("pipeline/data")
PARQUET = PIPELINE_DATA / "incidents_cleaned.parquet"

if not PARQUET.exists():
    print(f"ERROR: {PARQUET} not found. Run 02_weather_merge.py first.", file=sys.stderr)
    sys.exit(1)

# ── CDC SVI RPL_THEMES scores (0-1, higher = more vulnerable) ─────────────────
ZONE_SVI = {
    'B1':0.94, 'B2':0.89, 'B3':0.87, 'B4':0.72, 'B5':0.68,
    'K1':0.52, 'K2':0.58, 'K3':0.82, 'K4':0.84, 'K5':0.79, 'K6':0.60, 'K7':0.45,
    'M1':0.31, 'M2':0.18, 'M3':0.15, 'M4':0.20, 'M5':0.12,
    'M6':0.14, 'M7':0.73, 'M8':0.65, 'M9':0.61,
    'Q1':0.71, 'Q2':0.44, 'Q3':0.38, 'Q4':0.55, 'Q5':0.67, 'Q6':0.48, 'Q7':0.41,
    'S1':0.38, 'S2':0.32, 'S3':0.28,
}

print(f"ZONE_SVI loaded: {len(ZONE_SVI)} zones")
print(f"  Highest SVI: {max(ZONE_SVI, key=ZONE_SVI.get)} = {max(ZONE_SVI.values())}")
print(f"  Lowest SVI:  {min(ZONE_SVI, key=ZONE_SVI.get)} = {min(ZONE_SVI.values())}")

# ── Build SVI lookup parquet for DuckDB join ───────────────────────────────────
svi_df = pd.DataFrame([
    {"INCIDENT_DISPATCH_AREA": zone, "svi_score": score}
    for zone, score in ZONE_SVI.items()
])
SVI_TMP = PIPELINE_DATA / "_svi_tmp.parquet"
svi_df.to_parquet(SVI_TMP, index=False)

# ── DuckDB join + overwrite ────────────────────────────────────────────────────
conn = duckdb.connect()
TMP_OUT = PIPELINE_DATA / "incidents_cleaned_tmp.parquet"

conn.execute(f"""
COPY (
    SELECT
        inc.*,
        COALESCE(s.svi_score, 0.5) AS svi_score
    FROM read_parquet('{PARQUET}') AS inc
    LEFT JOIN read_parquet('{SVI_TMP}') AS s
        USING (INCIDENT_DISPATCH_AREA)
) TO '{TMP_OUT}' (FORMAT PARQUET, COMPRESSION SNAPPY)
""")

TMP_OUT.replace(PARQUET)
SVI_TMP.unlink(missing_ok=True)

print("incidents_cleaned.parquet updated with svi_score column.")

# ── Validation ─────────────────────────────────────────────────────────────────
stats = conn.execute(f"""
    SELECT
        COUNT(*) AS total,
        SUM(CASE WHEN svi_score IS NULL THEN 1 ELSE 0 END) AS null_svi,
        COUNT(DISTINCT INCIDENT_DISPATCH_AREA)             AS distinct_zones
    FROM read_parquet('{PARQUET}')
""").fetchone()

total, null_svi, distinct_zones = stats

print()
print("=" * 55)
print("  SCRIPT 03 — VALIDATION")
print("=" * 55)
print(f"  Total rows:       {total:,}")
print(f"  Null SVI rows:    {null_svi}   <- expect 0")
print(f"  Distinct zones:   {distinct_zones}   <- expect 31")
print()

if null_svi > 0:
    print(f"  WARNING: {null_svi} null SVI rows -- unexpected zone codes present")
    bad = conn.execute(f"""
        SELECT INCIDENT_DISPATCH_AREA, COUNT(*) AS cnt
        FROM read_parquet('{PARQUET}')
        WHERE svi_score IS NULL
        GROUP BY 1 ORDER BY 2 DESC LIMIT 10
    """).fetchdf()
    print(bad.to_string(index=False))
else:
    print("  OK: No null SVI rows -- all zones matched")

if distinct_zones != 31:
    print(f"  WARNING: Expected 31 zones, found {distinct_zones}")
else:
    print("  OK: Exactly 31 dispatch zones")

print()
print("  SVI distribution by zone (sorted by SVI score):")
svi_dist = conn.execute(f"""
    SELECT INCIDENT_DISPATCH_AREA, BOROUGH,
           ROUND(AVG(svi_score), 2) AS svi_score,
           COUNT(*) AS incident_count
    FROM read_parquet('{PARQUET}')
    GROUP BY 1, 2
    ORDER BY 3 DESC
""").fetchdf()
print(svi_dist.to_string(index=False))

print()
print("=" * 55)
print("  Next: python pipeline/04_aggregate.py")
print("=" * 55)
