"""
Script 04 — Zone × hour grid, lag features, artifacts
FirstWave | GT Hacklytics 2026

Inputs ($FW_PIPELINE_DATA, default pipeline/data):
  incidents_cleaned.parquet (01 + 03), weather_hourly.parquet, calendar_daily.parquet (02)
Outputs:
  $FW_PIPELINE_DATA/training_grid.parquet          one row per (zone, local hour), lags + features
  $FW_ARTIFACTS_DIR/zone_baselines.parquet         mean hourly count (incl. zeros), train split
  $FW_ARTIFACTS_DIR/zone_stats.parquet             per-zone response stats, train + valid responses
  $FW_ARTIFACTS_DIR/hourly_counts.parquet          replay lag source, 2024-12-01 → 2026-06-30
  $FW_ARTIFACTS_DIR/calendar_daily.parquet         replay calendar flags, 2025-01-01 → 2026-06-30
  $FW_ARTIFACTS_DIR/weather_hourly.parquet         replay weather + training flags, 2025-01-01 → 2026-06-30

Run: python pipeline/04_aggregate.py
"""

import math
import os
import pathlib
import sys

import duckdb
import pandas as pd

from fw_config import (
    DATA_END, DATA_START, HOURLY_COUNTS_START, LAG_FEATURE_COLS, REPLAY_START,
    VALID_ZONES, split_case_sql,
)
from fw_grid import add_lags, create_counts, create_grid

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "backend"))
from models.lag_features import build_lag_features, to_wide  # noqa: E402  (parity check)

PIPELINE_DATA = pathlib.Path(os.getenv("FW_PIPELINE_DATA", "pipeline/data"))
ARTIFACTS_DIR = pathlib.Path(os.getenv("FW_ARTIFACTS_DIR", "backend/artifacts"))
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

CLEANED = PIPELINE_DATA / "incidents_cleaned.parquet"
WEATHER = PIPELINE_DATA / "weather_hourly.parquet"
CALENDAR = PIPELINE_DATA / "calendar_daily.parquet"
GRID_OUT = PIPELINE_DATA / "training_grid.parquet"
BASELINE = ARTIFACTS_DIR / "zone_baselines.parquet"
STATS = ARTIFACTS_DIR / "zone_stats.parquet"
HOURLY_OUT = ARTIFACTS_DIR / "hourly_counts.parquet"
CAL_OUT = ARTIFACTS_DIR / "calendar_daily.parquet"
WX_OUT = ARTIFACTS_DIR / "weather_hourly.parquet"

for p in (CLEANED, WEATHER, CALENDAR):
    if not p.exists():
        print(f"ERROR: {p} not found. Run scripts 01–03 first.", file=sys.stderr)
        sys.exit(1)

conn = duckdb.connect()
cols = [d[0] for d in conn.execute(f"SELECT * FROM read_parquet('{CLEANED}') LIMIT 0").description]
for needed in ("is_valid_response", "svi_score", "split", "date_hour"):
    if needed not in cols:
        print(f"ERROR: incidents_cleaned is missing '{needed}' — re-run 01 and 03.", file=sys.stderr)
        sys.exit(1)

PI = math.pi

# ── Step 1: counts → gap-free grid → lags ─────────────────────────────────────
print("Step 1: zone × hour grid with lags...")
create_counts(conn, str(CLEANED))
n_grid = create_grid(conn, VALID_ZONES, DATA_START, DATA_END)
add_lags(conn)
print(f"  grid: {n_grid:,} rows (31 zones × every local hour, zeros included)")

# ── Step 2: training grid (features joined onto every hour) ───────────────────
print("Step 2: joining weather + calendar onto the grid...")
lag_select = ", ".join(f"g.{c}" for c in LAG_FEATURE_COLS)
conn.execute(f"""
COPY (
    WITH t AS (
        SELECT g.INCIDENT_DISPATCH_AREA, g.date_hour, g.incident_count, {lag_select},
               CAST(g.date_hour AS DATE)                          AS date,
               EXTRACT(year  FROM g.date_hour)::INTEGER           AS year,
               EXTRACT(month FROM g.date_hour)::INTEGER           AS month,
               (EXTRACT(dow  FROM g.date_hour)::INTEGER + 6) % 7  AS dayofweek,
               EXTRACT(hour  FROM g.date_hour)::INTEGER           AS hour
        FROM grid_lags g
        WHERE g.roll_4w_same_hour_dow IS NOT NULL
    )
    SELECT t.*,
           CASE WHEN t.dayofweek IN (5, 6) THEN 1 ELSE 0 END AS is_weekend,
           SIN(2 * {PI} * t.hour / 24)       AS hour_sin,
           COS(2 * {PI} * t.hour / 24)       AS hour_cos,
           SIN(2 * {PI} * t.dayofweek / 7)   AS dow_sin,
           COS(2 * {PI} * t.dayofweek / 7)   AS dow_cos,
           SIN(2 * {PI} * t.month / 12)      AS month_sin,
           COS(2 * {PI} * t.month / 12)      AS month_cos,
           w.temperature_2m, w.precipitation, w.windspeed_10m,
           w.is_severe_weather, w.is_extreme_heat, w.is_heat_emergency,
           c.is_holiday, c.is_school_day, c.is_major_event,
           0.5::DOUBLE AS subway_disruption_idx,
           {split_case_sql('t.date_hour')} AS split
    FROM t
    LEFT JOIN read_parquet('{WEATHER}') w ON w.date_hour = t.date_hour
    LEFT JOIN read_parquet('{CALENDAR}') c
           ON c.date = t.date AND c.zone_prefix = LEFT(t.INCIDENT_DISPATCH_AREA, 1)
) TO '{GRID_OUT}' (FORMAT PARQUET, COMPRESSION SNAPPY)
""")

nulls = conn.execute(f"""
    SELECT SUM(CASE WHEN temperature_2m IS NULL THEN 1 ELSE 0 END),
           SUM(CASE WHEN is_school_day  IS NULL THEN 1 ELSE 0 END),
           COUNT(*)
    FROM read_parquet('{GRID_OUT}')
""").fetchone()
if nulls[0] or nulls[1]:
    print(f"ERROR: {nulls[0]:,} rows missing weather, {nulls[1]:,} missing calendar — "
          "check date_hour alignment with 02 outputs.", file=sys.stderr)
    sys.exit(1)
print(f"  training_grid.parquet: {nulls[2]:,} rows, no missing weather/calendar")

# ── Step 3: zone_baselines (train only, zeros included) ───────────────────────
conn.execute(f"""
COPY (
    SELECT INCIDENT_DISPATCH_AREA, hour, dayofweek,
           AVG(incident_count) AS zone_baseline_avg
    FROM read_parquet('{GRID_OUT}')
    WHERE split = 'train'
    GROUP BY INCIDENT_DISPATCH_AREA, hour, dayofweek
) TO '{BASELINE}' (FORMAT PARQUET, COMPRESSION SNAPPY)
""")

# ── Step 4: zone_stats (train incidents with a valid response time) ───────────
conn.execute(f"""
COPY (
    SELECT INCIDENT_DISPATCH_AREA, BOROUGH,
           AVG(svi_score)                     AS svi_score,
           AVG(INCIDENT_RESPONSE_SECONDS_QY)  AS avg_response_seconds,
           AVG(INCIDENT_TRAVEL_TM_SECONDS_QY) AS avg_travel_seconds,
           AVG(DISPATCH_RESPONSE_SECONDS_QY)  AS avg_dispatch_seconds,
           AVG(is_high_acuity)                AS high_acuity_ratio,
           AVG(is_held)                       AS held_ratio,
           COUNT(*)                           AS total_incidents
    FROM read_parquet('{CLEANED}')
    WHERE split = 'train' AND is_valid_response = 1
    GROUP BY INCIDENT_DISPATCH_AREA, BOROUGH
) TO '{STATS}' (FORMAT PARQUET, COMPRESSION SNAPPY)
""")

# ── Step 5: replay artifacts ───────────────────────────────────────────────────
conn.execute(f"""
COPY (
    SELECT INCIDENT_DISPATCH_AREA, date_hour, incident_count
    FROM grid
    WHERE date_hour >= TIMESTAMP '{HOURLY_COUNTS_START} 00:00:00'
    ORDER BY INCIDENT_DISPATCH_AREA, date_hour
) TO '{HOURLY_OUT}' (FORMAT PARQUET, COMPRESSION SNAPPY)
""")
conn.execute(f"""
COPY (
    SELECT * FROM read_parquet('{CALENDAR}') WHERE date >= DATE '{REPLAY_START}'
) TO '{CAL_OUT}' (FORMAT PARQUET, COMPRESSION SNAPPY)
""")
conn.execute(f"""
COPY (
    SELECT date_hour, temperature_2m, precipitation, windspeed_10m,
           is_severe_weather, is_extreme_heat, is_heat_emergency
    FROM read_parquet('{WEATHER}')
    WHERE date_hour >= TIMESTAMP '{REPLAY_START} 00:00:00'
    ORDER BY date_hour
) TO '{WX_OUT}' (FORMAT PARQUET, COMPRESSION SNAPPY)
""")

# ── Step 6: validation ─────────────────────────────────────────────────────────
counts = {
    "zone_baselines": conn.execute(f"SELECT COUNT(*) FROM read_parquet('{BASELINE}')").fetchone()[0],
    "zone_stats": conn.execute(f"SELECT COUNT(*) FROM read_parquet('{STATS}')").fetchone()[0],
    "hourly_counts": conn.execute(f"SELECT COUNT(*) FROM read_parquet('{HOURLY_OUT}')").fetchone()[0],
    "calendar_daily": conn.execute(f"SELECT COUNT(*) FROM read_parquet('{CAL_OUT}')").fetchone()[0],
    "weather_hourly": conn.execute(f"SELECT COUNT(*) FROM read_parquet('{WX_OUT}')").fetchone()[0],
}
expected = {"zone_baselines": 31 * 24 * 7, "zone_stats": 31,
            "hourly_counts": 31 * ((DATA_END - HOURLY_COUNTS_START).days + 1) * 24,
            "calendar_daily": 5 * ((DATA_END - REPLAY_START).days + 1),
            "weather_hourly": 24 * ((DATA_END - REPLAY_START).days + 1)}

print()
print("=" * 60)
print("  SCRIPT 04 — VALIDATION")
print("=" * 60)
ok = True
for name, n in counts.items():
    flag = "✓" if n == expected[name] else "⚠"
    ok &= n == expected[name]
    print(f"  {flag} {name:<16} {n:>10,}  (expect {expected[name]:,})")

by_split = conn.execute(f"""
    SELECT split, COUNT(*) AS rows, ROUND(AVG(incident_count), 3) AS mean_count
    FROM read_parquet('{GRID_OUT}') GROUP BY split ORDER BY MIN(date_hour)
""").fetchdf()
print("\n  Rows and mean hourly count by split (mean should NOT trend down):")
print(by_split.to_string(index=False))

# Train/serve parity on the real data: serving-side lags from the hourly_counts
# artifact must equal the training grid's lag columns.
wide = to_wide(pd.read_parquet(HOURLY_OUT))
# Filter in a subquery: DuckDB applies USING SAMPLE before WHERE.
sample = conn.execute(f"""
    SELECT * FROM (
        SELECT INCIDENT_DISPATCH_AREA, date_hour, {', '.join(LAG_FEATURE_COLS)}
        FROM read_parquet('{GRID_OUT}') WHERE split IN ('test', 'test_recent')
    ) USING SAMPLE reservoir(200 ROWS) REPEATABLE (42)
""").df()
mismatches = 0
for row in sample.itertuples(index=False):
    served = build_lag_features(wide, pd.Timestamp(row.date_hour)).loc[row.INCIDENT_DISPATCH_AREA]
    for c in LAG_FEATURE_COLS:
        if abs(served[c] - getattr(row, c)) > 1e-9:
            mismatches += 1
print(f"\n  {'✓' if mismatches == 0 else '⚠'} train/serve lag parity on 200 rows: {mismatches} mismatches")
ok &= mismatches == 0

if not ok:
    print("\nERROR: validation failed — see ⚠ lines above.", file=sys.stderr)
    sys.exit(1)
print("=" * 60)
print("  Next: python pipeline/05_train_demand_model.py")
