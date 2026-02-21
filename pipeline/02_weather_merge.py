"""
Script 02 — Weather Merge
FirstWave | GT Hacklytics 2026

Input:  pipeline/data/incidents_cleaned.parquet (from Script 01)
External: Open-Meteo historical API (free, no key required)
Output: pipeline/data/incidents_cleaned.parquet (overwritten with weather columns)

Run: python pipeline/02_weather_merge.py
"""

import pathlib
import sys
import requests
import pandas as pd
import duckdb

# ── Paths ──────────────────────────────────────────────────────────────────────
PIPELINE_DATA = pathlib.Path("pipeline/data")
PARQUET = PIPELINE_DATA / "incidents_cleaned.parquet"

if not PARQUET.exists():
    print(f"ERROR: {PARQUET} not found. Run 01_ingest_clean.py first.", file=sys.stderr)
    sys.exit(1)

# ── Constants ──────────────────────────────────────────────────────────────────
SEVERE_WEATHER_CODES = {51,53,55,61,63,65,71,73,75,77,80,81,82,85,86,95,96,99}


def fetch_open_meteo(start_date: str, end_date: str) -> pd.DataFrame:
    """Fetch hourly weather for NYC from Open-Meteo historical archive."""
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": 40.7128,
        "longitude": -74.0060,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": "temperature_2m,precipitation,windspeed_10m,weathercode",
        "timezone": "America/New_York",
    }
    print(f"Fetching weather: {start_date} to {end_date}...")
    resp = requests.get(url, params=params, timeout=180)
    resp.raise_for_status()

    d = resp.json()["hourly"]
    df = pd.DataFrame(d)
    df["time"] = pd.to_datetime(df["time"])
    df.rename(columns={"time": "date_hour"}, inplace=True)
    df["is_severe_weather"] = df["weathercode"].isin(SEVERE_WEATHER_CODES).astype(int)

    print(f"  Fetched {len(df):,} hourly weather records")
    print(f"  Date range: {df['date_hour'].min()} to {df['date_hour'].max()}")
    print(f"  Severe weather hours: {df['is_severe_weather'].sum():,}")
    return df


# ── Fetch weather (2019-2023 in one call) ─────────────────────────────────────
try:
    weather_pd = fetch_open_meteo("2019-01-01", "2023-12-31")
except requests.exceptions.Timeout:
    print("WARNING: Open-Meteo timeout -- trying year-by-year fallback...")
    dfs = []
    for year in [2019, 2021, 2022, 2023]:
        try:
            dfs.append(fetch_open_meteo(f"{year}-01-01", f"{year}-12-31"))
        except Exception as e:
            print(f"  Year {year} failed: {e}")
    weather_pd = pd.concat(dfs, ignore_index=True)

print(f"\nTotal weather rows: {len(weather_pd):,}")

# Save weather to temp parquet so DuckDB can join it
WEATHER_TMP = PIPELINE_DATA / "_weather_tmp.parquet"
weather_pd.to_parquet(WEATHER_TMP, index=False)

# ── DuckDB join + overwrite ────────────────────────────────────────────────────
conn = duckdb.connect()
TMP_OUT = PIPELINE_DATA / "incidents_cleaned_tmp.parquet"

conn.execute(f"""
COPY (
    SELECT
        inc.*,
        COALESCE(w.temperature_2m,    15.0) AS temperature_2m,
        COALESCE(w.precipitation,      0.0) AS precipitation,
        COALESCE(w.windspeed_10m,     10.0) AS windspeed_10m,
        COALESCE(w.weathercode,          0) AS weathercode,
        COALESCE(w.is_severe_weather,    0) AS is_severe_weather
    FROM read_parquet('{PARQUET}') AS inc
    LEFT JOIN read_parquet('{WEATHER_TMP}') AS w
        ON inc.date_hour = w.date_hour
) TO '{TMP_OUT}' (FORMAT PARQUET, COMPRESSION SNAPPY)
""")

# Atomically replace original
TMP_OUT.replace(PARQUET)
WEATHER_TMP.unlink(missing_ok=True)

print("incidents_cleaned.parquet updated with weather columns.")

# ── Validation ─────────────────────────────────────────────────────────────────
stats = conn.execute(f"""
    SELECT
        COUNT(*) AS total,
        SUM(CASE WHEN temperature_2m IS NULL THEN 1 ELSE 0 END) AS null_weather,
        AVG(temperature_2m)    AS avg_temp_c,
        AVG(precipitation)     AS avg_precip_mm,
        AVG(windspeed_10m)     AS avg_wind_kmh,
        AVG(is_severe_weather) AS pct_severe
    FROM read_parquet('{PARQUET}')
""").fetchone()

total, null_w, avg_t, avg_p, avg_w, pct_sev = stats
null_pct = (null_w / total * 100) if total else 0

print()
print("=" * 55)
print("  SCRIPT 02 — VALIDATION")
print("=" * 55)
print(f"  Total rows:           {total:,}")
print(f"  Null weather rows:    {null_w:,} ({null_pct:.3f}%)")
print(f"  Avg temperature:      {avg_t:.1f} C")
print(f"  Avg precipitation:    {avg_p:.3f} mm")
print(f"  Avg wind speed:       {avg_w:.1f} km/h")
print(f"  Pct severe weather:   {pct_sev*100:.2f}%")
print()

if null_pct > 0.1:
    print("  WARNING: Null weather > 0.1% -- check date_hour type alignment")
else:
    print("  OK: Null weather < 0.1%")

print()
print("=" * 55)
print("  Next: python pipeline/03_spatial_join.py")
print("=" * 55)
