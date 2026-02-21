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

# Verify new enrichment columns exist before aggregating
print("Checking enrichment columns from Script 02...")
sample_cols = conn.execute(
    f"SELECT * FROM read_parquet('{CLEANED}') LIMIT 0"
).description
col_names = [d[0] for d in sample_cols]

ENRICHMENT_COLS = [
    "is_severe_weather", "is_extreme_heat", "is_heat_emergency",
    "is_holiday", "is_school_day", "is_major_event", "subway_disruption_idx",
]
missing = [c for c in ENRICHMENT_COLS if c not in col_names]
if missing:
    print(f"ERROR: Missing enrichment columns: {missing}", file=sys.stderr)
    print("       Re-run pipeline/02_weather_merge.py first.", file=sys.stderr)
    sys.exit(1)
print(f"  OK: all {len(ENRICHMENT_COLS)} enrichment columns present")

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
        split,

        -- ── Weather (average over all incidents in this zone-hour bin) ──────
        ROUND(AVG(temperature_2m),  2)   AS temperature_2m,
        ROUND(AVG(precipitation),   3)   AS precipitation,
        ROUND(AVG(windspeed_10m),   2)   AS windspeed_10m,

        -- ── Categorical weather / calendar flags ──────────────────────────
        -- MAX because: if ANY incident in this bin had a flag set, the bin
        -- should carry it. These are hour-level facts, not per-incident.
        MAX(is_severe_weather)           AS is_severe_weather,
        MAX(is_extreme_heat)             AS is_extreme_heat,
        MAX(is_heat_emergency)           AS is_heat_emergency,
        MAX(is_holiday)                  AS is_holiday,
        MAX(is_school_day)               AS is_school_day,
        MAX(is_major_event)              AS is_major_event,

        -- ── MTA (AVG is correct: all rows in a bin share the same monthly
        --    value, so AVG == MIN == MAX; AVG is just the safest aggregation) ─
        ROUND(AVG(subway_disruption_idx), 4) AS subway_disruption_idx,

        -- ── Zone equity ───────────────────────────────────────────────────
        ROUND(AVG(svi_score), 4)         AS svi_score,

        -- ── Demand metrics ─────────────────────────────────────────────────
        COUNT(CAD_INCIDENT_ID)                        AS incident_count,
        AVG(INCIDENT_RESPONSE_SECONDS_QY)             AS avg_response_seconds,
        AVG(INCIDENT_TRAVEL_TM_SECONDS_QY)            AS avg_travel_seconds,
        AVG(DISPATCH_RESPONSE_SECONDS_QY)             AS avg_dispatch_seconds,
        SUM(is_high_acuity)                           AS high_acuity_count,
        SUM(is_held)                                  AS held_count,
        MEDIAN(INCIDENT_RESPONSE_SECONDS_QY)          AS median_response_seconds,

        -- ── Cyclical time features for XGBoost ───────────────────────────
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
print("=" * 60)
print("  SCRIPT 04 — VALIDATION")
print("=" * 60)
print(f"  incidents_aggregated:  {agg_count:,} rows")
print(f"  zone_baselines:        {baseline_count} rows (expect <= {max_expected})")
print(f"  zone_stats:            {stats_count} rows (expect 31)")
print()

# ── Check 1: New enrichment columns in aggregated output ──────────────────────
print("  Checking new enrichment columns in incidents_aggregated...")
enrichment_check = conn.execute(f"""
    SELECT
        ROUND(AVG(is_extreme_heat),       4) AS pct_extreme_heat,
        ROUND(AVG(is_heat_emergency),     4) AS pct_heat_emergency,
        ROUND(AVG(is_holiday),            4) AS pct_holiday,
        ROUND(AVG(is_school_day),         4) AS pct_school_day,
        ROUND(AVG(is_major_event),        4) AS pct_major_event,
        ROUND(AVG(subway_disruption_idx), 4) AS avg_subway_idx,

        -- spot-check: default values would indicate join failure in Script 02
        SUM(CASE WHEN subway_disruption_idx = 0.5 THEN 1 ELSE 0 END) AS mta_defaults,
        SUM(CASE WHEN is_holiday       IS NULL   THEN 1 ELSE 0 END)  AS null_holiday,
        SUM(CASE WHEN is_school_day    IS NULL   THEN 1 ELSE 0 END)  AS null_school,
        SUM(CASE WHEN is_major_event   IS NULL   THEN 1 ELSE 0 END)  AS null_event,
        COUNT(*)                                                       AS total
    FROM read_parquet('{AGGD}')
""").fetchone()

(pct_xheat, pct_hemg, pct_hol, pct_school, pct_event,
 avg_mta, mta_def, null_hol, null_school, null_event, total_agg) = enrichment_check

mta_def_pct = (mta_def / total_agg * 100) if total_agg else 0

print(f"    is_extreme_heat:       {pct_xheat*100:.2f}%  (expect 3–8%, summer only)")
print(f"    is_heat_emergency:     {pct_hemg*100:.2f}%  (expect 5–12%)")
print(f"    is_holiday:            {pct_hol*100:.2f}%  (expect 2–4%)")
print(f"    is_school_day:         {pct_school*100:.2f}%  (expect 45–60%)")
print(f"    is_major_event:        {pct_event*100:.2f}%  (expect 5–15%)")
print(f"    subway_disruption_idx: {avg_mta:.3f} avg  (0=calm, 1=peak disruption)")
print(f"    MTA defaults (0.5):    {mta_def:,}  ({mta_def_pct:.1f}%)"
      "  <- 100% means MTA download failed in Script 02")

# ── Check 2: zone_baselines row count ─────────────────────────────────────────
print()
if baseline_count < 31:
    print("  ⚠  WARNING: zone_baselines < 31 rows -- join key may be wrong")
elif baseline_count > max_expected:
    print(f"  ⚠  WARNING: zone_baselines > {max_expected} rows -- unexpected duplicates")
else:
    print("  ✓  zone_baselines row count looks good")

# ── Check 3: zone_stats count ─────────────────────────────────────────────────
if stats_count != 31:
    zones_found = conn.execute(
        f"SELECT INCIDENT_DISPATCH_AREA FROM read_parquet('{STATS}') ORDER BY 1"
    ).fetchdf()["INCIDENT_DISPATCH_AREA"].tolist()
    print(f"  ⚠  WARNING: zone_stats has {stats_count} rows, expected 31")
    print(f"  Zones present: {sorted(zones_found)}")
else:
    print("  ✓  zone_stats = 31 rows -- all zones present")

# ── Check 4: null flags ────────────────────────────────────────────────────────
flag_checks = [
    ("is_holiday",    null_hol,    pct_hol,    1.0),
    ("is_school_day", null_school, pct_school, 20.0),
    ("is_major_event",null_event,  pct_event,  0.5),
]
for col, nulls, pct, min_pct in flag_checks:
    if nulls > 0:
        print(f"  ⚠  WARNING: {col} has {nulls:,} NULLs -- Script 02 join may have failed")
    elif pct * 100 < min_pct:
        print(f"  ⚠  WARNING: {col} = {pct*100:.2f}% -- lower than expected ({min_pct}% min)")
    else:
        print(f"  ✓  {col} looks good ({pct*100:.2f}%)")

# ── Sample outputs ─────────────────────────────────────────────────────────────
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
           ROUND(high_acuity_ratio, 3)    AS high_acuity_ratio,
           ROUND(held_ratio, 3)           AS held_ratio
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
print("=" * 60)
print("  Next: python pipeline/05_train_demand_model.py")
print("         (run python pipeline/06_osmnx_matrix.py in parallel if not done)")
print("=" * 60)