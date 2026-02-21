"""
Script 04 — Aggregation
FirstWave | GT Hacklytics 2026

Input:  pipeline/data/incidents_cleaned.parquet (from Scripts 01-03)
Outputs:
  - pipeline/data/incidents_aggregated.parquet
  - backend/artifacts/zone_baselines.parquet   <- written directly (artifact)
  - backend/artifacts/zone_stats.parquet       <- written directly (artifact)

Run: python pipeline/04_aggregate.py
"""

import math
import pathlib
import sys
import duckdb

# ── Paths ──────────────────────────────────────────────────────────────────────
PIPELINE_DATA   = pathlib.Path("pipeline/data")
ARTIFACTS_DIR   = pathlib.Path("backend/artifacts")
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

CLEANED  = PIPELINE_DATA / "incidents_cleaned.parquet"
AGGD     = PIPELINE_DATA / "incidents_aggregated.parquet"
BASELINE = ARTIFACTS_DIR / "zone_baselines.parquet"
STATS    = ARTIFACTS_DIR / "zone_stats.parquet"

if not CLEANED.exists():
    print(f"ERROR: {CLEANED} not found. Run 01-03 first.", file=sys.stderr)
    sys.exit(1)

conn = duckdb.connect()

# Count loaded rows
total = conn.execute(f"SELECT COUNT(*) FROM read_parquet('{CLEANED}')").fetchone()[0]
print(f"Incidents loaded (all splits): {total:,}")

PI = math.pi

# ── Step 1: Hourly zone-level aggregation ─────────────────────────────────────
print("\nStep 1: Aggregating to hourly zone level...")
conn.execute(f"""
COPY (
    SELECT
        INCIDENT_DISPATCH_AREA,
        BOROUGH,
        year,
        month,
        dayofweek,
        hour,
        is_weekend,
        ROUND(AVG(temperature_2m), 2)    AS temperature_2m,
        ROUND(AVG(precipitation), 3)     AS precipitation,
        ROUND(AVG(windspeed_10m), 2)     AS windspeed_10m,
        MAX(is_severe_weather)           AS is_severe_weather,
        ROUND(AVG(svi_score), 4)         AS svi_score,
        split,

        -- aggregated metrics
        COUNT(CAD_INCIDENT_ID)                           AS incident_count,
        AVG(INCIDENT_RESPONSE_SECONDS_QY)                AS avg_response_seconds,
        AVG(INCIDENT_TRAVEL_TM_SECONDS_QY)               AS avg_travel_seconds,
        AVG(DISPATCH_RESPONSE_SECONDS_QY)                AS avg_dispatch_seconds,
        SUM(is_high_acuity)                              AS high_acuity_count,
        SUM(is_held)                                     AS held_count,
        MEDIAN(INCIDENT_RESPONSE_SECONDS_QY)             AS median_response_seconds,

        -- cyclical time features for XGBoost
        SIN(2 * {PI} * hour / 24)     AS hour_sin,
        COS(2 * {PI} * hour / 24)     AS hour_cos,
        SIN(2 * {PI} * dayofweek / 7) AS dow_sin,
        COS(2 * {PI} * dayofweek / 7) AS dow_cos,
        SIN(2 * {PI} * month / 12)    AS month_sin,
        COS(2 * {PI} * month / 12)    AS month_cos

    FROM read_parquet('{CLEANED}')
    WHERE split IN ('train', 'test')
    GROUP BY
        INCIDENT_DISPATCH_AREA, BOROUGH, year, month, dayofweek,
        hour, is_weekend, split

) TO '{AGGD}' (FORMAT PARQUET, COMPRESSION SNAPPY)
""")

agg_count = conn.execute(f"SELECT COUNT(*) FROM read_parquet('{AGGD}')").fetchone()[0]
print(f"incidents_aggregated.parquet: {agg_count:,} rows")

# ── Step 2: Zone baselines (most important XGBoost feature) ───────────────────
# Rolling avg incidents per (zone, hour, dayofweek) over training years only
# "On a typical Monday at 8PM, how many incidents does B2 see?"
print("\nStep 2: Computing zone_baselines (train split only)...")

conn.execute(f"""
COPY (
    SELECT
        INCIDENT_DISPATCH_AREA,
        hour,
        dayofweek,
        AVG(daily_count) AS zone_baseline_avg
    FROM (
        SELECT
            INCIDENT_DISPATCH_AREA,
            hour,
            dayofweek,
            incident_date,
            COUNT(CAD_INCIDENT_ID) AS daily_count
        FROM read_parquet('{CLEANED}')
        WHERE split = 'train'
        GROUP BY INCIDENT_DISPATCH_AREA, hour, dayofweek, incident_date
    )
    GROUP BY INCIDENT_DISPATCH_AREA, hour, dayofweek
) TO '{BASELINE}' (FORMAT PARQUET, COMPRESSION SNAPPY)
""")

baseline_count = conn.execute(f"SELECT COUNT(*) FROM read_parquet('{BASELINE}')").fetchone()[0]
max_expected = 31 * 24 * 7  # 5,208
print(f"zone_baselines.parquet: {baseline_count} rows (max possible: {max_expected})")

# ── Step 3: Zone stats (per-zone historical averages) ─────────────────────────
print("\nStep 3: Computing zone_stats (train split only)...")

conn.execute(f"""
COPY (
    SELECT
        INCIDENT_DISPATCH_AREA,
        BOROUGH,
        AVG(svi_score)                        AS svi_score,
        AVG(INCIDENT_RESPONSE_SECONDS_QY)     AS avg_response_seconds,
        AVG(INCIDENT_TRAVEL_TM_SECONDS_QY)    AS avg_travel_seconds,
        AVG(DISPATCH_RESPONSE_SECONDS_QY)     AS avg_dispatch_seconds,
        AVG(is_high_acuity)                   AS high_acuity_ratio,
        AVG(is_held)                          AS held_ratio,
        COUNT(CAD_INCIDENT_ID)                AS total_incidents
    FROM read_parquet('{CLEANED}')
    WHERE split = 'train'
    GROUP BY INCIDENT_DISPATCH_AREA, BOROUGH
) TO '{STATS}' (FORMAT PARQUET, COMPRESSION SNAPPY)
""")

stats_count = conn.execute(f"SELECT COUNT(*) FROM read_parquet('{STATS}')").fetchone()[0]
print(f"zone_stats.parquet: {stats_count} rows (expect 31)")

# ── Validation ─────────────────────────────────────────────────────────────────
print()
print("=" * 55)
print("  SCRIPT 04 — VALIDATION")
print("=" * 55)
print(f"  incidents_aggregated: {agg_count:,} rows")
print(f"  zone_baselines:       {baseline_count} rows (expect <= {max_expected})")
print(f"  zone_stats:           {stats_count} rows (expect 31)")
print()

if baseline_count < 31:
    print("  WARNING: zone_baselines < 31 rows -- join key may be wrong")
elif baseline_count > max_expected:
    print(f"  WARNING: zone_baselines > {max_expected} rows -- unexpected duplicates")
else:
    print("  OK: zone_baselines row count looks good")

if stats_count != 31:
    zones_found = conn.execute(
        f"SELECT INCIDENT_DISPATCH_AREA FROM read_parquet('{STATS}') ORDER BY 1"
    ).fetchdf()["INCIDENT_DISPATCH_AREA"].tolist()
    print(f"  WARNING: zone_stats has {stats_count} rows, expected 31")
    print(f"  Zones present: {sorted(zones_found)}")
else:
    print("  OK: zone_stats = 31 rows -- all zones present")

print()
print("  zone_baselines sample (top 5 highest baseline):")
top5 = conn.execute(f"""
    SELECT INCIDENT_DISPATCH_AREA, hour, dayofweek,
           ROUND(zone_baseline_avg, 2) AS zone_baseline_avg
    FROM read_parquet('{BASELINE}')
    ORDER BY zone_baseline_avg DESC LIMIT 5
""").fetchdf()
print(top5.to_string(index=False))

print()
print("  zone_stats (sorted by avg_response_seconds):")
stats_df = conn.execute(f"""
    SELECT INCIDENT_DISPATCH_AREA, BOROUGH,
           ROUND(avg_response_seconds, 1) AS avg_resp_sec,
           ROUND(high_acuity_ratio, 3) AS high_acuity_ratio,
           ROUND(held_ratio, 3) AS held_ratio
    FROM read_parquet('{STATS}')
    ORDER BY avg_response_seconds DESC
""").fetchdf()
print(stats_df.to_string(index=False))
print()
print("  <- Check: Bronx avg_resp_sec should be ~638, Manhattan ~630")
print("  <- Check: B1, B2, B3 should dominate highest zone_baseline_avg")
print()
print("  Artifacts written:")
print(f"    {BASELINE}")
print(f"    {STATS}")
print()
print("=" * 55)
print("  Next: python pipeline/05_train_demand_model.py")
print("         (run python pipeline/06_osmnx_matrix.py in parallel if not done)")
print("=" * 55)
