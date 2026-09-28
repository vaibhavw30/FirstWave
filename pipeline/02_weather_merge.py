"""
Script 02 — Weather + calendar lookup tables
FirstWave | GT Hacklytics 2026

External:
  - Open-Meteo historical archive API (free, no key)
  - NYC Permitted Events CSV (NYC Open Data bkfu-528j)
  - Holidays + DOE school calendars (pipeline/fw_calendar.py)

Outputs ($FW_PIPELINE_DATA, default pipeline/data):
  weather_hourly.parquet  — one row per local hour, 2021-12-01 → 2026-06-30
  calendar_daily.parquet  — one row per (date, zone prefix)

Script 04 joins both onto the full zone × hour grid, so zero-incident hours get
weather too. This script no longer rewrites incidents_cleaned.parquet.

MTA: both source datasets (data.ny.gov i8rn-y4np, j6d2-s8m2) are gone, so
subway_disruption_idx is the constant 0.5 set in script 04.

Run: python pipeline/02_weather_merge.py
"""

import datetime as dt
import os
import pathlib
import sys

import pandas as pd
import requests

from fw_calendar import build_calendar_daily
from fw_config import DATA_END, DATA_START

PIPELINE_DATA = pathlib.Path(os.getenv("FW_PIPELINE_DATA", "pipeline/data"))
PIPELINE_DATA.mkdir(parents=True, exist_ok=True)
WEATHER_OUT = PIPELINE_DATA / "weather_hourly.parquet"
CALENDAR_OUT = PIPELINE_DATA / "calendar_daily.parquet"
EVENTS_CACHE = PIPELINE_DATA / "_events_cache.parquet"

SEVERE_WEATHER_CODES = {51, 53, 55, 61, 63, 65, 71, 73, 75, 77, 80, 81, 82, 85, 86, 95, 96, 99}


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — WEATHER (Open-Meteo)
# ══════════════════════════════════════════════════════════════════════════════

def fetch_open_meteo(start_date: dt.date, end_date: dt.date) -> pd.DataFrame:
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": 40.7128,
        "longitude": -74.0060,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "hourly": "temperature_2m,precipitation,windspeed_10m,weathercode",
        "timezone": "America/New_York",
    }
    print(f"  Fetching weather {start_date} → {end_date} ...")
    resp = requests.get(url, params=params, timeout=180)
    resp.raise_for_status()
    df = pd.DataFrame(resp.json()["hourly"])
    df["date_hour"] = pd.to_datetime(df.pop("time"))
    return df


def add_weather_flags(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values("date_hour").reset_index(drop=True)
    df["is_severe_weather"] = df["weathercode"].isin(SEVERE_WEATHER_CODES).astype(int)
    # is_extreme_heat: any hour >= 35 °C (95 °F)
    df["is_extreme_heat"] = (df["temperature_2m"] >= 35.0).astype(int)
    # is_heat_emergency approximation: temp >= 35 °C or prior-24h max >= 32.2 °C
    prior_24h_max = df["temperature_2m"].rolling(window=24, min_periods=1).max()
    df["is_heat_emergency"] = ((df["temperature_2m"] >= 35.0) | (prior_24h_max >= 32.2)).astype(int)
    return df


print("\n── SECTION 1: Weather ──────────────────────────────────────────────────")
chunks = []
for year in range(DATA_START.year, DATA_END.year + 1):
    start = max(DATA_START, dt.date(year, 1, 1))
    end = min(DATA_END, dt.date(year, 12, 31))
    chunks.append(fetch_open_meteo(start, end))
# Flags are computed after concatenation so the 24h rolling max spans year ends.
weather = add_weather_flags(pd.concat(chunks, ignore_index=True))

expected_hours = ((DATA_END - DATA_START).days + 1) * 24
if len(weather) != expected_hours or weather["date_hour"].duplicated().any():
    print(f"ERROR: weather has {len(weather):,} rows "
          f"({weather['date_hour'].duplicated().sum()} duplicate hours), "
          f"expected {expected_hours:,} unique local hours", file=sys.stderr)
    sys.exit(1)
if weather[["temperature_2m", "precipitation", "windspeed_10m"]].isna().any().any():
    print("ERROR: weather has null values", file=sys.stderr)
    sys.exit(1)

weather[[
    "date_hour", "temperature_2m", "precipitation", "windspeed_10m", "weathercode",
    "is_severe_weather", "is_extreme_heat", "is_heat_emergency",
]].to_parquet(WEATHER_OUT, index=False)
print(f"  weather_hourly.parquet: {len(weather):,} rows "
      f"| severe {weather['is_severe_weather'].mean():.1%} "
      f"| heat emergency {weather['is_heat_emergency'].mean():.1%}")


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — NYC SPECIAL EVENTS (NYC Open Data)
# ══════════════════════════════════════════════════════════════════════════════
print("\n── SECTION 2: NYC Special Events ───────────────────────────────────────")

EVENTS_URL = "https://data.cityofnewyork.us/api/views/bkfu-528j/rows.csv?accessType=DOWNLOAD"

if EVENTS_CACHE.exists():
    print("  Loading events from cache...")
    events_raw = pd.read_parquet(EVENTS_CACHE)
else:
    print("  Downloading NYC Permitted Events...")
    try:
        events_raw = pd.read_csv(EVENTS_URL, low_memory=False)
        events_raw.columns = (
            events_raw.columns.str.lower()
            .str.replace(r"[^a-z0-9]+", "_", regex=True)
            .str.strip("_")
        )
        events_raw.to_parquet(EVENTS_CACHE, index=False)
        print(f"  Downloaded {len(events_raw):,} rows, cached to {EVENTS_CACHE.name}")
    except Exception as e:
        print(f"  WARNING: events download failed ({e}); is_major_event will be 0 everywhere.")
        events_raw = None

# Event types that meaningfully raise EMS demand (no construction/maintenance/film).
MAJOR_EVENT_TYPES = {
    "Special Event", "Farmers Market", "Fair/Festival", "Festival",
    "Athletic Event", "Concert", "Parade", "Street Fair", "Block Party",
    "Run/Walk/Race", "Demonstration/Rally",
}
BOROUGH_TO_PREFIX = {
    "Manhattan": "M", "Bronx": "B", "Brooklyn": "K", "Queens": "Q", "Staten Island": "S",
}

event_days = pd.DataFrame(columns=["event_date", "zone_prefix"])
if events_raw is not None:
    start_col = next((c for c in events_raw.columns if "start" in c and "date" in c), None)
    end_col = next((c for c in events_raw.columns if "end" in c and "date" in c), None)
    type_col = next((c for c in events_raw.columns if "type" in c), None)
    boro_col = next((c for c in events_raw.columns if "borough" in c), None)

    if start_col and end_col and boro_col:
        ev = events_raw.copy()
        ev[start_col] = pd.to_datetime(ev[start_col], errors="coerce")
        ev[end_col] = pd.to_datetime(ev[end_col], errors="coerce")
        if type_col:
            ev = ev[ev[type_col].isin(MAJOR_EVENT_TYPES)]
        ev = ev.dropna(subset=[start_col, end_col, boro_col])
        ev = ev[(ev[end_col] >= pd.Timestamp(DATA_START)) & (ev[start_col] <= pd.Timestamp(DATA_END))]

        rows = set()
        for s, e, boro in zip(ev[start_col], ev[end_col], ev[boro_col]):
            prefix = BOROUGH_TO_PREFIX.get(str(boro).strip())
            if prefix is None:
                continue
            day = max(s.date(), DATA_START)
            while day <= min(e.date(), DATA_END):
                rows.add((day, prefix))
                day += dt.timedelta(days=1)
        event_days = pd.DataFrame(sorted(rows), columns=["event_date", "zone_prefix"])
        print(f"  Major event (date × borough) combinations: {len(event_days):,}")
    else:
        print(f"  WARNING: could not identify event columns. Found: {list(events_raw.columns[:10])}")


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — CALENDAR TABLE
# ══════════════════════════════════════════════════════════════════════════════
print("\n── SECTION 3: calendar_daily ───────────────────────────────────────────")
calendar = build_calendar_daily(DATA_START, DATA_END, event_days)
calendar.to_parquet(CALENDAR_OUT, index=False)

per_day = calendar[calendar["zone_prefix"] == "B"]
weekdays = per_day[pd.to_datetime(per_day["date"]).dt.dayofweek < 5]
print(f"  calendar_daily.parquet: {len(calendar):,} rows")
print(f"  Holidays: {per_day['is_holiday'].sum()} days")
print(f"  School days: {per_day['is_school_day'].sum()} "
      f"({weekdays['is_school_day'].mean():.0%} of weekdays; expect ~65–75%)")
print(f"  Major-event rows: {calendar['is_major_event'].mean():.1%}")

print()
print("=" * 60)
print("  Next: python pipeline/03_spatial_join.py")
print("=" * 60)
