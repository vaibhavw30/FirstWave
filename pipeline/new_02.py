"""
Script 02 — Weather Merge + Feature Enrichment
FirstWave | GT Hacklytics 2026

Input:  pipeline/data/incidents_cleaned.parquet (from Script 01)
External:
  - Open-Meteo historical API   (free, no key)
  - NYC Permitted Events CSV    (free, NYC Open Data)
  - MTA Major Incidents CSVs   (free, data.ny.gov — two datasets)
  - Federal holidays            (hardcoded)
  - NYC school calendar         (hardcoded)
  - Heat emergency              (derived from weather data)

Output: pipeline/data/incidents_cleaned.parquet (overwritten)
New columns added:
  temperature_2m, precipitation, windspeed_10m, weathercode,
  is_severe_weather, is_extreme_heat, is_heat_emergency,
  is_holiday, is_school_day, is_major_event, subway_disruption_idx

Run: python pipeline/02_weather_merge.py
"""

import datetime as dt
import pathlib
import sys
import requests
import pandas as pd
import duckdb

# ── Paths ──────────────────────────────────────────────────────────────────────
PIPELINE_DATA = pathlib.Path("pipeline/data")
PARQUET       = PIPELINE_DATA / "incidents_cleaned.parquet"

if not PARQUET.exists():
    print(f"ERROR: {PARQUET} not found. Run 01_ingest_clean.py first.", file=sys.stderr)
    sys.exit(1)

# ── Severe weather WMO codes ───────────────────────────────────────────────────
SEVERE_WEATHER_CODES = {51,53,55,61,63,65,71,73,75,77,80,81,82,85,86,95,96,99}


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — WEATHER  (Open-Meteo)
# ══════════════════════════════════════════════════════════════════════════════

def fetch_open_meteo(start_date: str, end_date: str) -> pd.DataFrame:
    """Fetch hourly weather for NYC from Open-Meteo historical archive."""
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude":  40.7128,
        "longitude": -74.0060,
        "start_date": start_date,
        "end_date":   end_date,
        "hourly": "temperature_2m,precipitation,windspeed_10m,weathercode",
        "timezone": "America/New_York",
    }
    print(f"  Fetching weather {start_date} → {end_date} ...")
    resp = requests.get(url, params=params, timeout=180)
    resp.raise_for_status()

    d  = resp.json()["hourly"]
    df = pd.DataFrame(d)
    df["time"] = pd.to_datetime(df["time"])
    df.rename(columns={"time": "date_hour"}, inplace=True)
    df["is_severe_weather"] = df["weathercode"].isin(SEVERE_WEATHER_CODES).astype(int)

    # ── Heat flags (derived here while we have temp data) ──
    # is_extreme_heat: any hour >= 35 °C (95 °F)
    df["is_extreme_heat"] = (df["temperature_2m"] >= 35.0).astype(int)

    # is_heat_emergency: NYC threshold — heat index >= 95 °F for 2+ consecutive
    # days, or any single day >= 100 °F.
    # Approximation: flag hours where temp >= 35 °C OR the prior-24h max >= 32.2 °C
    df_sorted = df.sort_values("date_hour").reset_index(drop=True)
    prior_24h_max = df_sorted["temperature_2m"].rolling(window=24, min_periods=1).max()
    df_sorted["is_heat_emergency"] = (
        (df_sorted["temperature_2m"] >= 35.0) | (prior_24h_max >= 32.2)
    ).astype(int)
    df = df_sorted

    print(f"    Rows: {len(df):,}  |  Severe: {df['is_severe_weather'].sum():,}  "
          f"|  Extreme heat: {df['is_extreme_heat'].sum():,}  "
          f"|  Heat emergency: {df['is_heat_emergency'].sum():,}")
    return df


print("\n── SECTION 1: Weather ──────────────────────────────────────────────────")
try:
    weather_pd = fetch_open_meteo("2019-01-01", "2023-12-31")
except requests.exceptions.Timeout:
    print("  WARNING: timeout — falling back to year-by-year fetch")
    dfs = []
    for year in [2019, 2021, 2022, 2023]:
        try:
            dfs.append(fetch_open_meteo(f"{year}-01-01", f"{year}-12-31"))
        except Exception as e:
            print(f"  Year {year} failed: {e}")
    weather_pd = pd.concat(dfs, ignore_index=True)

WEATHER_TMP = PIPELINE_DATA / "_weather_tmp.parquet"
weather_pd.to_parquet(WEATHER_TMP, index=False)
print(f"  Total weather rows: {len(weather_pd):,}")


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — FEDERAL + NYC HOLIDAYS  (hardcoded, no download)
# ══════════════════════════════════════════════════════════════════════════════
print("\n── SECTION 2: Holidays (hardcoded) ─────────────────────────────────────")

FEDERAL_HOLIDAYS = {
    # 2019
    "2019-01-01","2019-01-21","2019-02-18","2019-05-27",
    "2019-07-04","2019-09-02","2019-10-14","2019-11-11",
    "2019-11-28","2019-12-25",
    # 2020 (excluded year — still included so inference works)
    "2020-01-01","2020-01-20","2020-02-17","2020-05-25",
    "2020-07-03","2020-09-07","2020-10-12","2020-11-11",
    "2020-11-26","2020-12-25",
    # 2021
    "2021-01-01","2021-01-18","2021-02-15","2021-05-31",
    "2021-06-19","2021-07-05","2021-09-06","2021-10-11",
    "2021-11-11","2021-11-25","2021-12-24",
    # 2022
    "2022-01-17","2022-02-21","2022-05-30",
    "2022-06-20","2022-07-04","2022-09-05","2022-10-10",
    "2022-11-11","2022-11-24","2022-12-26",
    # 2023
    "2023-01-02","2023-01-16","2023-02-20","2023-05-29",
    "2023-06-19","2023-07-04","2023-09-04","2023-10-09",
    "2023-11-10","2023-11-23","2023-12-25",
}

# NYC-observed holidays not in the federal list:
# Election Day (significant in NYC — schools close, patterns shift)
# Rosh Hashanah + Yom Kippur (public school closures — large Bronx/Brooklyn signal)
NYC_EXTRA_HOLIDAYS = {
    "2019-11-05","2020-11-03","2021-11-02","2022-11-08","2023-11-07",   # Election Day
    # Rosh Hashanah
    "2019-09-29","2019-09-30",
    "2021-09-06","2021-09-07",
    "2022-09-25","2022-09-26",
    "2023-09-15","2023-09-16",
    # Yom Kippur
    "2019-10-08","2019-10-09",
    "2021-09-15","2021-09-16",
    "2022-10-04","2022-10-05",
    "2023-09-24","2023-09-25",
}

ALL_HOLIDAYS = FEDERAL_HOLIDAYS | NYC_EXTRA_HOLIDAYS

holiday_rows = [{"holiday_date": d, "is_holiday": 1} for d in ALL_HOLIDAYS]
holidays_pd  = pd.DataFrame(holiday_rows)
holidays_pd["holiday_date"] = pd.to_datetime(holidays_pd["holiday_date"]).dt.date

HOLIDAYS_TMP = PIPELINE_DATA / "_holidays_tmp.parquet"
holidays_pd.to_parquet(HOLIDAYS_TMP, index=False)
print(f"  Total holiday dates: {len(holidays_pd)}")


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — NYC SCHOOL CALENDAR  (hardcoded, no download)
# ══════════════════════════════════════════════════════════════════════════════
print("\n── SECTION 3: School calendar (hardcoded) ──────────────────────────────")

# Instructional session windows: (first day, last day)
# Source: schools.nyc.gov/calendar PDF per year
SCHOOL_SESSIONS = [
    ("2019-09-05", "2020-03-17"),  # 2019-20: COVID closed schools 3/18/2020
    # 2020-21 is in the excluded year — still build rows for inference use
    ("2020-09-16", "2021-06-25"),  # 2020-21: remote learning year
    ("2021-09-13", "2022-06-27"),  # 2021-22
    ("2022-09-08", "2023-06-27"),  # 2022-23
    ("2023-09-07", "2024-06-26"),  # 2023-24 (holdout year)
]

# Closure dates WITHIN session windows (breaks, holidays, professional days)
# Source: NYC DOE calendar PDFs
SCHOOL_CLOSURES = {
    # ── 2019-20 ──
    "2019-10-14","2019-11-05","2019-11-11","2019-11-27","2019-11-28","2019-11-29",
    "2019-12-24","2019-12-25","2019-12-26","2019-12-27","2019-12-28","2019-12-31",
    "2020-01-01","2020-01-20",
    "2020-02-17","2020-02-18","2020-02-19","2020-02-20","2020-02-21",  # Mid-winter recess
    # ── 2020-21 (remote year) ──
    "2020-11-03","2020-11-26","2020-11-27",
    "2020-12-24","2020-12-25","2020-12-28","2020-12-29","2020-12-30","2020-12-31",
    "2021-01-01","2021-01-18",
    "2021-02-15","2021-02-16","2021-02-17","2021-02-18","2021-02-19",  # Mid-winter recess
    "2021-04-01","2021-04-02","2021-04-05","2021-04-06","2021-04-07",
    "2021-04-08","2021-04-09",  # Spring recess
    "2021-05-31",
    # ── 2021-22 ──
    "2021-10-11","2021-11-02","2021-11-25","2021-11-26",
    "2021-12-23","2021-12-24","2021-12-27","2021-12-28","2021-12-29","2021-12-30","2021-12-31",
    "2022-01-17",
    "2022-02-21","2022-02-22","2022-02-23","2022-02-24","2022-02-25",  # Mid-winter recess
    "2022-04-14","2022-04-15","2022-04-18","2022-04-19","2022-04-20","2022-04-21","2022-04-22",
    "2022-05-30",
    # ── 2022-23 ──
    "2022-09-26","2022-10-05","2022-10-10","2022-11-08","2022-11-24","2022-11-25",
    "2022-12-23","2022-12-26","2022-12-27","2022-12-28","2022-12-29","2022-12-30",
    "2023-01-02","2023-01-16",
    "2023-02-20","2023-02-21","2023-02-22","2023-02-23","2023-02-24",  # Mid-winter recess
    "2023-04-05","2023-04-06","2023-04-07","2023-04-10","2023-04-11",
    "2023-04-12","2023-04-13","2023-04-14",  # Spring recess
    "2023-05-29",
    # ── 2023-24 (holdout year) ──
    "2023-09-15","2023-09-16","2023-10-09","2023-11-07","2023-11-23","2023-11-24",
    "2023-12-25","2023-12-26","2023-12-27","2023-12-28","2023-12-29",
    "2024-01-01","2024-01-15",
    "2024-02-19","2024-02-20","2024-02-21","2024-02-22","2024-02-23",  # Mid-winter recess
    "2024-03-29","2024-04-01","2024-04-02","2024-04-03","2024-04-04","2024-04-05",
    "2024-05-27",
}

def is_school_day(date_obj: dt.date) -> int:
    if date_obj.weekday() >= 5:
        return 0
    date_str = date_obj.isoformat()
    if date_str in SCHOOL_CLOSURES:
        return 0
    for start_s, end_s in SCHOOL_SESSIONS:
        if dt.date.fromisoformat(start_s) <= date_obj <= dt.date.fromisoformat(end_s):
            return 1
    return 0  # summer or outside all session windows

# Build daily lookup 2019-01-01 through 2023-12-31
school_rows = []
cursor = dt.date(2019, 1, 1)
end_d  = dt.date(2023, 12, 31)
while cursor <= end_d:
    school_rows.append({"school_date": cursor, "is_school_day": is_school_day(cursor)})
    cursor += dt.timedelta(days=1)

school_pd = pd.DataFrame(school_rows)
SCHOOL_TMP = PIPELINE_DATA / "_school_tmp.parquet"
school_pd.to_parquet(SCHOOL_TMP, index=False)

school_days_count = sum(r["is_school_day"] for r in school_rows)
print(f"  School days in lookup: {school_days_count} / {len(school_rows)} calendar days")
# Expect ~180 school days per 10-month year, ~900 total across 5 years


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — NYC SPECIAL EVENTS  (NYC Open Data download)
# ══════════════════════════════════════════════════════════════════════════════
print("\n── SECTION 4: NYC Special Events ───────────────────────────────────────")

EVENTS_URL  = "https://data.cityofnewyork.us/api/views/bkfu-528j/rows.csv?accessType=DOWNLOAD"
EVENTS_CACHE = PIPELINE_DATA / "_events_cache.parquet"

# Cache to avoid re-downloading on re-runs
if EVENTS_CACHE.exists():
    print("  Loading events from cache...")
    events_raw = pd.read_parquet(EVENTS_CACHE)
else:
    print("  Downloading NYC Permitted Events (~50MB)...")
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
        print(f"  WARNING: Events download failed ({e}). Skipping is_major_event feature.")
        events_raw = None

# Event types that meaningfully raise EMS demand
# Excludes: Construction, Maintenance, Film (these don't crowd streets)
MAJOR_EVENT_TYPES = {
    "Special Event", "Farmers Market", "Fair/Festival", "Festival",
    "Athletic Event", "Concert", "Parade", "Street Fair", "Block Party",
    "Run/Walk/Race", "Demonstration/Rally",
}

# Borough → zone prefix mapping  (matches INCIDENT_DISPATCH_AREA prefix)
BOROUGH_TO_PREFIX = {
    "Manhattan":     "M",
    "Bronx":         "B",
    "Brooklyn":      "K",
    "Queens":        "Q",
    "Staten Island": "S",
}

if events_raw is not None:
    # Parse date columns — try multiple possible column names
    start_col = next((c for c in events_raw.columns if "start" in c and "date" in c), None)
    end_col   = next((c for c in events_raw.columns if "end"   in c and "date" in c), None)
    type_col  = next((c for c in events_raw.columns if "type"  in c), None)
    boro_col  = next((c for c in events_raw.columns if "borough" in c), None)

    if start_col and end_col and boro_col:
        events_raw[start_col] = pd.to_datetime(events_raw[start_col], errors="coerce")
        events_raw[end_col]   = pd.to_datetime(events_raw[end_col],   errors="coerce")

        # Keep only relevant event types if column exists
        if type_col:
            events_raw = events_raw[events_raw[type_col].isin(MAJOR_EVENT_TYPES)]

        # Keep only events overlapping our training window
        events_raw = events_raw[
            (events_raw[start_col] >= pd.Timestamp("2019-01-01")) &
            (events_raw[start_col] <= pd.Timestamp("2023-12-31"))
        ].dropna(subset=[start_col, end_col, boro_col])

        # Expand multi-day events into one row per (date, borough)
        event_day_rows = []
        for _, row in events_raw.iterrows():
            start_d = row[start_col].date()
            end_d   = row[end_col].date()
            boro    = str(row[boro_col]).strip()
            prefix  = BOROUGH_TO_PREFIX.get(boro)
            if prefix is None:
                continue
            cur = start_d
            while cur <= end_d and cur <= dt.date(2023, 12, 31):
                event_day_rows.append({
                    "event_date":   cur,
                    "zone_prefix":  prefix,
                    "is_major_event": 1,
                })
                cur += dt.timedelta(days=1)

        events_pd = (
            pd.DataFrame(event_day_rows)
            .drop_duplicates(subset=["event_date", "zone_prefix"])
        )
        print(f"  Major event (date × borough) combinations: {len(events_pd):,}")
    else:
        print(f"  WARNING: Could not identify required columns. Found: {list(events_raw.columns[:10])}")
        events_pd = pd.DataFrame(columns=["event_date", "zone_prefix", "is_major_event"])
else:
    events_pd = pd.DataFrame(columns=["event_date", "zone_prefix", "is_major_event"])

EVENTS_TMP = PIPELINE_DATA / "_events_tmp.parquet"
events_pd.to_parquet(EVENTS_TMP, index=False)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 5 — MTA SUBWAY MAJOR INCIDENTS  (data.ny.gov download)
# ══════════════════════════════════════════════════════════════════════════════
print("\n── SECTION 5: MTA Subway Major Incidents ───────────────────────────────")

MTA_PRE2020_URL  = "https://data.ny.gov/api/views/i8rn-y4np/rows.csv?accessType=DOWNLOAD"
MTA_POST2020_URL = "https://data.ny.gov/api/views/j6d2-s8m2/rows.csv?accessType=DOWNLOAD"
MTA_CACHE        = PIPELINE_DATA / "_mta_cache.parquet"

if MTA_CACHE.exists():
    print("  Loading MTA incidents from cache...")
    mta_pd = pd.read_parquet(MTA_CACHE)
else:
    print("  Downloading MTA Major Incidents datasets...")
    mta_dfs = []
    for label, url in [("pre-2020", MTA_PRE2020_URL), ("2020+", MTA_POST2020_URL)]:
        try:
            df = pd.read_csv(url, low_memory=False)
            df.columns = (
                df.columns.str.lower()
                .str.replace(r"[^a-z0-9]+", "_", regex=True)
                .str.strip("_")
            )
            mta_dfs.append(df)
            print(f"    {label}: {len(df):,} rows")
        except Exception as e:
            print(f"    WARNING: {label} download failed ({e})")

    if mta_dfs:
        mta_raw = pd.concat(mta_dfs, ignore_index=True)
        mta_raw.to_parquet(MTA_CACHE, index=False)
        mta_pd  = mta_raw
    else:
        mta_pd = pd.DataFrame()

if not mta_pd.empty:
    # Find the month column (might be "month", "period", etc.)
    month_col = next((c for c in mta_pd.columns if "month" in c or "period" in c), None)
    count_col = next(
        (c for c in mta_pd.columns if "count" in c or "incident" in c or "total" in c),
        None
    )

    if month_col and count_col:
        mta_pd["parsed_month"] = pd.to_datetime(mta_pd[month_col], errors="coerce")
        mta_pd = mta_pd.dropna(subset=["parsed_month"])
        mta_pd["year"]      = mta_pd["parsed_month"].dt.year
        mta_pd["month_num"] = mta_pd["parsed_month"].dt.month
        mta_pd[count_col]   = pd.to_numeric(mta_pd[count_col], errors="coerce").fillna(0)

        # Aggregate: sum all incidents per (year, month) across all lines/divisions
        monthly = (
            mta_pd.groupby(["year", "month_num"])[count_col]
            .sum()
            .reset_index()
            .rename(columns={count_col: "monthly_subway_incidents"})
        )

        # Normalize to 0–1 (higher = more disruption that month)
        min_v = monthly["monthly_subway_incidents"].min()
        max_v = monthly["monthly_subway_incidents"].max()
        monthly["subway_disruption_idx"] = (
            (monthly["monthly_subway_incidents"] - min_v) / (max_v - min_v + 1e-9)
        )

        print(f"  Monthly bins: {len(monthly)}  |  "
              f"Range: {monthly['monthly_subway_incidents'].min():.0f}–"
              f"{monthly['monthly_subway_incidents'].max():.0f} incidents/month")
    else:
        print(f"  WARNING: Could not find month/count columns. Found: {list(mta_pd.columns[:10])}")
        monthly = pd.DataFrame(columns=["year","month_num","subway_disruption_idx"])
else:
    print("  WARNING: No MTA data available — subway_disruption_idx will default to 0.5")
    monthly = pd.DataFrame(columns=["year","month_num","subway_disruption_idx"])

MTA_TMP = PIPELINE_DATA / "_mta_tmp.parquet"
monthly.to_parquet(MTA_TMP, index=False)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 6 — SINGLE DUCKDB JOIN PASS
# All 5 enrichment tables joined in one query → one parquet write
# ══════════════════════════════════════════════════════════════════════════════
print("\n── SECTION 6: DuckDB join (all features) ───────────────────────────────")

TMP_OUT = PIPELINE_DATA / "incidents_cleaned_tmp.parquet"
conn    = duckdb.connect()

conn.execute(f"""
COPY (
    SELECT
        -- ── Original incident columns ──────────────────────────────────────
        inc.*,

        -- ── Weather columns ──────────────────────────────────────────────
        COALESCE(w.temperature_2m,     15.0)  AS temperature_2m,
        COALESCE(w.precipitation,       0.0)  AS precipitation,
        COALESCE(w.windspeed_10m,      10.0)  AS windspeed_10m,
        COALESCE(w.weathercode,           0)  AS weathercode,
        COALESCE(w.is_severe_weather,     0)  AS is_severe_weather,
        COALESCE(w.is_extreme_heat,       0)  AS is_extreme_heat,
        COALESCE(w.is_heat_emergency,     0)  AS is_heat_emergency,

        -- ── Holiday flag ─────────────────────────────────────────────────
        -- Join on calendar date only (not hour)
        COALESCE(h.is_holiday,            0)  AS is_holiday,

        -- ── School day flag ───────────────────────────────────────────────
        COALESCE(sc.is_school_day,        0)  AS is_school_day,

        -- ── Special events flag ───────────────────────────────────────────
        -- Join on (calendar date, zone borough prefix)
        COALESCE(ev.is_major_event,       0)  AS is_major_event,

        -- ── MTA disruption index ──────────────────────────────────────────
        -- Monthly resolution; join on (year, month)
        COALESCE(mta.subway_disruption_idx, 0.5) AS subway_disruption_idx

    FROM read_parquet('{PARQUET}') AS inc

    -- ── Weather: join on exact hour ────────────────────────────────────────
    LEFT JOIN read_parquet('{WEATHER_TMP}') AS w
        ON inc.date_hour = w.date_hour

    -- ── Holidays: join on calendar date ──────────────────────────────────
    LEFT JOIN read_parquet('{HOLIDAYS_TMP}') AS h
        ON CAST(inc.date_hour AS DATE) = h.holiday_date

    -- ── School days: join on calendar date ───────────────────────────────
    LEFT JOIN read_parquet('{SCHOOL_TMP}') AS sc
        ON CAST(inc.date_hour AS DATE) = sc.school_date

    -- ── Special events: join on (date, zone prefix) ────────────────────
    -- zone prefix is the first character of INCIDENT_DISPATCH_AREA
    LEFT JOIN read_parquet('{EVENTS_TMP}') AS ev
        ON CAST(inc.date_hour AS DATE) = ev.event_date
        AND LEFT(inc.INCIDENT_DISPATCH_AREA, 1) = ev.zone_prefix

    -- ── MTA: join on (year, month) ─────────────────────────────────────
    LEFT JOIN read_parquet('{MTA_TMP}') AS mta
        ON YEAR(inc.date_hour)  = mta.year
        AND MONTH(inc.date_hour) = mta.month_num

) TO '{TMP_OUT}' (FORMAT PARQUET, COMPRESSION SNAPPY)
""")

# Atomically replace original
TMP_OUT.replace(PARQUET)

# Clean up temp files (keep caches for re-runs)
for tmp in [WEATHER_TMP, HOLIDAYS_TMP, SCHOOL_TMP, EVENTS_TMP, MTA_TMP]:
    tmp.unlink(missing_ok=True)

print("  incidents_cleaned.parquet overwritten with all enrichment columns.")


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 7 — VALIDATION
# ══════════════════════════════════════════════════════════════════════════════
print("\n── SECTION 7: Validation ───────────────────────────────────────────────")

stats = conn.execute(f"""
    SELECT
        COUNT(*)                                                    AS total,

        -- weather nulls
        SUM(CASE WHEN temperature_2m IS NULL THEN 1 ELSE 0 END)    AS null_weather,
        AVG(temperature_2m)                                         AS avg_temp_c,
        AVG(precipitation)                                          AS avg_precip_mm,
        AVG(windspeed_10m)                                          AS avg_wind_kmh,
        AVG(is_severe_weather)                                      AS pct_severe,

        -- heat flags
        AVG(is_extreme_heat)                                        AS pct_extreme_heat,
        AVG(is_heat_emergency)                                      AS pct_heat_emergency,

        -- calendar flags
        AVG(is_holiday)                                             AS pct_holiday,
        AVG(is_school_day)                                          AS pct_school_day,
        AVG(is_major_event)                                         AS pct_major_event,

        -- MTA
        AVG(subway_disruption_idx)                                  AS avg_subway_idx,
        SUM(CASE WHEN subway_disruption_idx = 0.5 THEN 1 ELSE 0 END) AS mta_defaults

    FROM read_parquet('{PARQUET}')
""").fetchone()

(total, null_w, avg_t, avg_p, avg_w, pct_sev,
 pct_xheat, pct_hemg,
 pct_hol, pct_school, pct_event,
 avg_mta, mta_def) = stats

null_pct     = (null_w / total * 100) if total else 0
mta_def_pct  = (mta_def / total * 100) if total else 0

print()
print("=" * 60)
print("  SCRIPT 02 — VALIDATION SUMMARY")
print("=" * 60)
print(f"  Total rows:                {total:>12,}")
print()
print("  WEATHER")
print(f"    Null weather rows:       {null_w:>12,}  ({null_pct:.3f}%)")
print(f"    Avg temperature:         {avg_t:>12.1f}  C")
print(f"    Avg precipitation:       {avg_p:>12.3f}  mm/hr")
print(f"    Avg wind speed:          {avg_w:>12.1f}  km/h")
print(f"    Severe weather rows:     {pct_sev*100:>12.2f}  %")
print(f"    Extreme heat rows:       {pct_xheat*100:>12.2f}  %")
print(f"    Heat emergency rows:     {pct_hemg*100:>12.2f}  %")
print()
print("  CALENDAR")
print(f"    Holiday rows:            {pct_hol*100:>12.2f}  %  (expect 2–4%)")
print(f"    School day rows:         {pct_school*100:>12.2f}  %  (expect 45–60%)")
print(f"    Major event rows:        {pct_event*100:>12.2f}  %  (expect 5–15%)")
print()
print("  MTA")
print(f"    Avg subway disrupt idx:  {avg_mta:>12.3f}  (0=low, 1=high disruption)")
print(f"    MTA default rows:        {mta_def:>12,}  ({mta_def_pct:.1f}%) "
      "(non-zero = MTA join worked)")
print()
print("  CHECKS")

checks_passed = True

if null_pct > 0.1:
    print("  ⚠  WARNING: Null weather > 0.1% — check date_hour type alignment")
    checks_passed = False
else:
    print("  ✓  Null weather < 0.1%")

if pct_hol * 100 < 1.0:
    print("  ⚠  WARNING: Holiday % < 1% — check holiday_date cast (should be DATE)")
    checks_passed = False
else:
    print("  ✓  Holiday % looks reasonable")

if pct_school * 100 < 20:
    print("  ⚠  WARNING: School day % < 20% — school_date join may have failed")
    checks_passed = False
else:
    print("  ✓  School day % looks reasonable")

if pct_event * 100 < 1.0:
    print("  ⚠  WARNING: Major event % < 1% — events join may have failed or download skipped")
    # Non-fatal: events download can fail without breaking the pipeline
else:
    print("  ✓  Major event % looks reasonable")

if mta_def_pct > 99:
    print("  ⚠  WARNING: All MTA rows at default 0.5 — MTA download likely failed (non-fatal)")
else:
    print("  ✓  MTA join populated successfully")

print()
if checks_passed:
    print("  ALL CHECKS PASSED")
else:
    print("  SOME CHECKS FAILED — review warnings above before proceeding")

print()
print("=" * 60)
print("  Next: python pipeline/03_spatial_join.py")
print("=" * 60)