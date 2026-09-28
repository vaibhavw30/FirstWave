"""
Datamorph Python action — Stage ② prep: fetch_lookups
FirstWave | GT Hacklytics 2026

Builds the 5 enrichment lookup Parquets that proc_sql_2 (weather_enrich) joins onto
the incident stream. Runs BEFORE the weather_enrich DuckDB Pipeline.

Outputs (Parquet, into pipeline/data/):
  _weather_tmp.parquet   -> datamorph Source "weather"
  _holidays_tmp.parquet  -> datamorph Source "holidays"
  _school_tmp.parquet    -> datamorph Source "school"
  _events_tmp.parquet    -> datamorph Source "events"
  _mta_tmp.parquet       -> datamorph Source "mta"

Mirrors: pipeline/02_weather_merge.py (sections 1-5). Self-contained for the
datamorph sandbox. Network failures degrade gracefully (defaults handled by
proc_sql_2 COALESCE).
"""

import datetime as dt
import pathlib

import pandas as pd
import requests

OUT = pathlib.Path("pipeline/data")
OUT.mkdir(parents=True, exist_ok=True)

SEVERE_WEATHER_CODES = {51, 53, 55, 61, 63, 65, 71, 73, 75, 77, 80, 81, 82, 85, 86, 95, 96, 99}
START_DATE, END_DATE = "2019-01-01", "2023-12-31"


# ── 1. Weather (Open-Meteo) ─────────────────────────────────────────────────────
def fetch_weather() -> pd.DataFrame:
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": 40.7128, "longitude": -74.0060,
        "start_date": START_DATE, "end_date": END_DATE,
        "hourly": "temperature_2m,precipitation,windspeed_10m,weathercode",
        "timezone": "America/New_York",
    }
    d = requests.get(url, params=params, timeout=180).json()["hourly"]
    df = pd.DataFrame(d)
    df["date_hour"] = pd.to_datetime(df.pop("time"))
    df["is_severe_weather"] = df["weathercode"].isin(SEVERE_WEATHER_CODES).astype(int)
    df["is_extreme_heat"] = (df["temperature_2m"] >= 35.0).astype(int)
    df = df.sort_values("date_hour").reset_index(drop=True)
    prior_24h_max = df["temperature_2m"].rolling(window=24, min_periods=1).max()
    df["is_heat_emergency"] = (
        (df["temperature_2m"] >= 35.0) | (prior_24h_max >= 32.2)
    ).astype(int)
    return df


# ── 2. Holidays (hardcoded federal + NYC) ──────────────────────────────────────
FEDERAL_HOLIDAYS = {
    "2019-01-01", "2019-01-21", "2019-02-18", "2019-05-27", "2019-07-04", "2019-09-02",
    "2019-10-14", "2019-11-11", "2019-11-28", "2019-12-25",
    "2020-01-01", "2020-01-20", "2020-02-17", "2020-05-25", "2020-07-03", "2020-09-07",
    "2020-10-12", "2020-11-11", "2020-11-26", "2020-12-25",
    "2021-01-01", "2021-01-18", "2021-02-15", "2021-05-31", "2021-06-19", "2021-07-05",
    "2021-09-06", "2021-10-11", "2021-11-11", "2021-11-25", "2021-12-24",
    "2022-01-17", "2022-02-21", "2022-05-30", "2022-06-20", "2022-07-04", "2022-09-05",
    "2022-10-10", "2022-11-11", "2022-11-24", "2022-12-26",
    "2023-01-02", "2023-01-16", "2023-02-20", "2023-05-29", "2023-06-19", "2023-07-04",
    "2023-09-04", "2023-10-09", "2023-11-10", "2023-11-23", "2023-12-25",
}
NYC_EXTRA_HOLIDAYS = {
    "2019-11-05", "2020-11-03", "2021-11-02", "2022-11-08", "2023-11-07",   # Election Day
    "2019-09-29", "2019-09-30", "2021-09-06", "2021-09-07",                 # Rosh Hashanah
    "2022-09-25", "2022-09-26", "2023-09-15", "2023-09-16",
    "2019-10-08", "2019-10-09", "2021-09-15", "2021-09-16",                 # Yom Kippur
    "2022-10-04", "2022-10-05", "2023-09-24", "2023-09-25",
}


def build_holidays() -> pd.DataFrame:
    rows = [{"holiday_date": d, "is_holiday": 1} for d in (FEDERAL_HOLIDAYS | NYC_EXTRA_HOLIDAYS)]
    df = pd.DataFrame(rows)
    df["holiday_date"] = pd.to_datetime(df["holiday_date"]).dt.date
    return df


# ── 3. School calendar (hardcoded NYC DOE) ─────────────────────────────────────
SCHOOL_SESSIONS = [
    ("2019-09-05", "2020-03-17"), ("2020-09-16", "2021-06-25"),
    ("2021-09-13", "2022-06-27"), ("2022-09-08", "2023-06-27"),
    ("2023-09-07", "2024-06-26"),
]
SCHOOL_CLOSURES = {
    "2019-10-14", "2019-11-05", "2019-11-11", "2019-11-27", "2019-11-28", "2019-11-29",
    "2019-12-24", "2019-12-25", "2019-12-26", "2019-12-27", "2019-12-28", "2019-12-31",
    "2020-01-01", "2020-01-20", "2020-02-17", "2020-02-18", "2020-02-19", "2020-02-20", "2020-02-21",
    "2020-11-03", "2020-11-26", "2020-11-27", "2020-12-24", "2020-12-25", "2020-12-28",
    "2020-12-29", "2020-12-30", "2020-12-31", "2021-01-01", "2021-01-18",
    "2021-02-15", "2021-02-16", "2021-02-17", "2021-02-18", "2021-02-19",
    "2021-04-01", "2021-04-02", "2021-04-05", "2021-04-06", "2021-04-07", "2021-04-08", "2021-04-09",
    "2021-05-31", "2021-10-11", "2021-11-02", "2021-11-25", "2021-11-26",
    "2021-12-23", "2021-12-24", "2021-12-27", "2021-12-28", "2021-12-29", "2021-12-30", "2021-12-31",
    "2022-01-17", "2022-02-21", "2022-02-22", "2022-02-23", "2022-02-24", "2022-02-25",
    "2022-04-14", "2022-04-15", "2022-04-18", "2022-04-19", "2022-04-20", "2022-04-21", "2022-04-22",
    "2022-05-30", "2022-09-26", "2022-10-05", "2022-10-10", "2022-11-08", "2022-11-24", "2022-11-25",
    "2022-12-23", "2022-12-26", "2022-12-27", "2022-12-28", "2022-12-29", "2022-12-30",
    "2023-01-02", "2023-01-16", "2023-02-20", "2023-02-21", "2023-02-22", "2023-02-23", "2023-02-24",
    "2023-04-05", "2023-04-06", "2023-04-07", "2023-04-10", "2023-04-11", "2023-04-12", "2023-04-13", "2023-04-14",
    "2023-05-29", "2023-09-15", "2023-09-16", "2023-10-09", "2023-11-07", "2023-11-23", "2023-11-24",
    "2023-12-25", "2023-12-26", "2023-12-27", "2023-12-28", "2023-12-29",
    "2024-01-01", "2024-01-15", "2024-02-19", "2024-02-20", "2024-02-21", "2024-02-22", "2024-02-23",
    "2024-03-29", "2024-04-01", "2024-04-02", "2024-04-03", "2024-04-04", "2024-04-05", "2024-05-27",
}


def _is_school_day(d: dt.date) -> int:
    if d.weekday() >= 5 or d.isoformat() in SCHOOL_CLOSURES:
        return 0
    for s, e in SCHOOL_SESSIONS:
        if dt.date.fromisoformat(s) <= d <= dt.date.fromisoformat(e):
            return 1
    return 0


def build_school() -> pd.DataFrame:
    rows, cur, end = [], dt.date(2019, 1, 1), dt.date(2023, 12, 31)
    while cur <= end:
        rows.append({"school_date": cur, "is_school_day": _is_school_day(cur)})
        cur += dt.timedelta(days=1)
    return pd.DataFrame(rows)


# ── 4. NYC Special Events (NYC Open Data bkfu-528j) ────────────────────────────
EVENTS_URL = "https://data.cityofnewyork.us/api/views/bkfu-528j/rows.csv?accessType=DOWNLOAD"
MAJOR_EVENT_TYPES = {
    "Special Event", "Farmers Market", "Fair/Festival", "Festival", "Athletic Event",
    "Concert", "Parade", "Street Fair", "Block Party", "Run/Walk/Race", "Demonstration/Rally",
}
BOROUGH_TO_PREFIX = {"Manhattan": "M", "Bronx": "B", "Brooklyn": "K", "Queens": "Q", "Staten Island": "S"}


def build_events() -> pd.DataFrame:
    cols = ["event_date", "zone_prefix", "is_major_event"]
    try:
        raw = pd.read_csv(EVENTS_URL, low_memory=False)
    except Exception as e:
        print(f"  events download failed ({e}) — emitting empty lookup")
        return pd.DataFrame(columns=cols)
    raw.columns = raw.columns.str.lower().str.replace(r"[^a-z0-9]+", "_", regex=True).str.strip("_")
    start_col = next((c for c in raw.columns if "start" in c and "date" in c), None)
    end_col = next((c for c in raw.columns if "end" in c and "date" in c), None)
    type_col = next((c for c in raw.columns if "type" in c), None)
    boro_col = next((c for c in raw.columns if "borough" in c), None)
    if not (start_col and end_col and boro_col):
        return pd.DataFrame(columns=cols)
    raw[start_col] = pd.to_datetime(raw[start_col], errors="coerce")
    raw[end_col] = pd.to_datetime(raw[end_col], errors="coerce")
    if type_col:
        raw = raw[raw[type_col].isin(MAJOR_EVENT_TYPES)]
    raw = raw[(raw[start_col] >= pd.Timestamp("2019-01-01")) &
              (raw[start_col] <= pd.Timestamp("2023-12-31"))].dropna(subset=[start_col, end_col, boro_col])
    rows = []
    for _, r in raw.iterrows():
        prefix = BOROUGH_TO_PREFIX.get(str(r[boro_col]).strip())
        if prefix is None:
            continue
        cur, end_d = r[start_col].date(), r[end_col].date()
        while cur <= end_d and cur <= dt.date(2023, 12, 31):
            rows.append({"event_date": cur, "zone_prefix": prefix, "is_major_event": 1})
            cur += dt.timedelta(days=1)
    return pd.DataFrame(rows, columns=cols).drop_duplicates(subset=["event_date", "zone_prefix"])


# ── 5. MTA subway major incidents (data.ny.gov) ────────────────────────────────
MTA_URLS = [
    "https://data.ny.gov/api/views/i8rn-y4np/rows.csv?accessType=DOWNLOAD",   # pre-2020
    "https://data.ny.gov/api/views/j6d2-s8m2/rows.csv?accessType=DOWNLOAD",   # 2020+
]


def build_mta() -> pd.DataFrame:
    cols = ["year", "month_num", "subway_disruption_idx"]
    dfs = []
    for url in MTA_URLS:
        try:
            df = pd.read_csv(url, low_memory=False)
            df.columns = df.columns.str.lower().str.replace(r"[^a-z0-9]+", "_", regex=True).str.strip("_")
            dfs.append(df)
        except Exception as e:
            print(f"  MTA download failed ({e})")
    if not dfs:
        return pd.DataFrame(columns=cols)
    mta = pd.concat(dfs, ignore_index=True)
    month_col = next((c for c in mta.columns if "month" in c or "period" in c), None)
    count_col = next((c for c in mta.columns if "count" in c or "incident" in c or "total" in c), None)
    if not (month_col and count_col):
        return pd.DataFrame(columns=cols)
    mta["pm"] = pd.to_datetime(mta[month_col], errors="coerce")
    mta = mta.dropna(subset=["pm"])
    mta["year"], mta["month_num"] = mta["pm"].dt.year, mta["pm"].dt.month
    mta[count_col] = pd.to_numeric(mta[count_col], errors="coerce").fillna(0)
    monthly = mta.groupby(["year", "month_num"])[count_col].sum().reset_index()
    lo, hi = monthly[count_col].min(), monthly[count_col].max()
    monthly["subway_disruption_idx"] = (monthly[count_col] - lo) / (hi - lo + 1e-9)
    return monthly[cols]


# ── Run ─────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Building enrichment lookups...")
    build_holidays().to_parquet(OUT / "_holidays_tmp.parquet", index=False)
    build_school().to_parquet(OUT / "_school_tmp.parquet", index=False)
    build_events().to_parquet(OUT / "_events_tmp.parquet", index=False)
    build_mta().to_parquet(OUT / "_mta_tmp.parquet", index=False)
    try:
        fetch_weather().to_parquet(OUT / "_weather_tmp.parquet", index=False)
    except Exception as e:
        print(f"  weather fetch failed ({e}) — proc_sql_2 will COALESCE to defaults")
    print("Lookups written to pipeline/data/. Run the weather_enrich DuckDB Pipeline next.")
