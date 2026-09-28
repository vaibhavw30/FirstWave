"""
Datamorph Python action (or run locally once) — SIMPLIFIED pipeline weather prep.
FirstWave | GT Hacklytics 2026

Fetches one year (2023) of hourly NYC weather from Open-Meteo and writes a clean
Parquet that the `weather` Source reads in the simple_ems_weather DuckDB Pipeline.

Output: pipeline/data/weather_2023.parquet
Columns: date_hour (TIMESTAMP), temperature_2m (C), precipitation (mm/hr), weathercode

No API key needed. If you'd rather stay fully no-code, see the CSV-URL note in
SIMPLE_PIPELINE_GUIDE.md and skip this script.
"""

import pathlib

import pandas as pd
import requests

OUT = pathlib.Path("pipeline/data")
OUT.mkdir(parents=True, exist_ok=True)
OUT_FILE = OUT / "weather_2023.parquet"

URL = "https://archive-api.open-meteo.com/v1/archive"
PARAMS = {
    "latitude": 40.7128,
    "longitude": -74.0060,
    "start_date": "2023-01-01",
    "end_date": "2023-12-31",
    "hourly": "temperature_2m,precipitation,weathercode",
    "timezone": "America/New_York",
}

if __name__ == "__main__":
    print("Fetching 2023 hourly NYC weather from Open-Meteo...")
    data = requests.get(URL, params=PARAMS, timeout=180).json()["hourly"]
    df = pd.DataFrame(data)
    df["date_hour"] = pd.to_datetime(df.pop("time"))
    df = df[["date_hour", "temperature_2m", "precipitation", "weathercode"]]
    df.to_parquet(OUT_FILE, index=False)
    print(f"Wrote {len(df):,} rows -> {OUT_FILE}")
    print(df.head().to_string(index=False))
