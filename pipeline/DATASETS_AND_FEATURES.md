# FirstWave — Feature Expansion Datasets

## Complete Reference for Praneel (Notebooks 02–03 additions)

All datasets below are free, no API key required, directly downloadable.
Add each as a new column in the `incidents_cleaned` Delta table during
Notebook 02 (weather merge) or Notebook 03 (SVI join), then add the feature
to `FEATURE_COLS` in Notebook 05 before re-training.

---

## PRIORITY 1 — NYC Special Events (HIGH VALUE, DO THIS FIRST)

**Why it matters:** Large events create predictable, geolocatable demand spikes.
A Yankee Stadium game on Friday night means extra EMS demand in Bronx zones B1–B2.
This is the most visually compelling demo feature — judges immediately understand it.

**Dataset: NYC Permitted Event Information — Historical**

- URL: `https://data.cityofnewyork.us/api/views/bkfu-528j/rows.csv?accessType=DOWNLOAD`
- Socrata API: `https://data.cityofnewyork.us/resource/bkfu-528j.json`
- Coverage: 2008–present (covers all training years 2019, 2021, 2022, 2023)
- Size: ~400k rows
- Key columns confirmed from raw CSV:
  - `Event ID`, `Event Name`, `Start Date/Time`, `End Date/Time`
  - `Event Agency`, `Event Type`, `Event Borough`, `Event Location`
  - `Community Board`, `Police Precinct`

**Notebook 02 integration code:**

```python
import requests, pandas as pd
from pyspark.sql import functions as F

# Download events
events_url = "https://data.cityofnewyork.us/api/views/bkfu-528j/rows.csv?accessType=DOWNLOAD"
events_pd = pd.read_csv(events_url, parse_dates=["Start Date/Time", "End Date/Time"])
events_pd.columns = [c.lower().replace(" ", "_").replace("/", "") for c in events_pd.columns]

# Only keep "Special Event" type, drop Construction/Maintenance noise
MAJOR_EVENT_TYPES = ["Special Event", "Farmers Market", "Fair/Festival",
                     "Athletic Event", "Concert", "Parade", "Street Fair"]
events_pd = events_pd[events_pd["event_type"].isin(MAJOR_EVENT_TYPES)]

# Create one row per event-day (events can span multiple days)
rows = []
for _, row in events_pd.iterrows():
    start = row["start_datetime"]
    end   = row["end_datetime"]
    if pd.isna(start) or pd.isna(end): continue
    cur = start.date()
    while cur <= end.date():
        rows.append({
            "event_date": cur,
            "event_borough": row["event_borough"],
            "is_major_event": 1
        })
        cur += pd.Timedelta(days=1)

event_days_pd = pd.DataFrame(rows).drop_duplicates()

# Map borough text to our zone prefix
BOROUGH_PREFIX = {
    "Manhattan": "M", "Bronx": "B", "Brooklyn": "K",
    "Queens": "Q", "Staten Island": "S"
}
event_days_pd["event_zone_prefix"] = event_days_pd["event_borough"].map(BOROUGH_PREFIX)

# Create (zone_prefix, date) lookup
event_days_spark = spark.createDataFrame(event_days_pd)

# Join to incidents by date and zone prefix
incidents = spark.table("firstwave.incidents_cleaned")
incidents = incidents.withColumn(
    "incident_date", F.to_date("incident_dt")
).withColumn(
    "zone_prefix", F.substring("INCIDENT_DISPATCH_AREA", 0, 1)
)
incidents = incidents.join(
    event_days_spark,
    on=(
        (F.col("incident_date") == F.col("event_date")) &
        (F.col("zone_prefix") == F.col("event_zone_prefix"))
    ),
    how="left"
).fillna({"is_major_event": 0}) \
 .drop("event_date", "event_borough", "event_zone_prefix", "incident_date", "zone_prefix")

incidents.write.format("delta").mode("overwrite") \
    .save("dbfs:/firstwave/delta/incidents_cleaned")

print(f"Events flagged: {incidents.filter('is_major_event = 1').count():,}")
# Expect 5–15% of rows flagged — if 0, check borough name casing
```

**Add to FEATURE_COLS in Notebook 05:**

```python
# Insert after "is_weekend":
"is_major_event",    # 1 if permitted special event in this zone's borough on this date
```

**Expected signal:** Friday/Saturday demand in B zones should be ~8–12% higher on
game/event days vs same day-of-week without events. Top event names to verify:
"Yankee Stadium", "Bronx Week", "Rucker Park Basketball Tournament".

---

## PRIORITY 2 — Federal Holidays (10 MINUTES, HARDCODE IT)

**Why it matters:** Holidays break the day-of-week pattern completely.
July 4th EMS demand is totally different from a typical Thursday.
No download needed — just Python.

**No dataset URL needed. Hardcode directly in Notebook 02:**

```python
from pyspark.sql import functions as F

# All US Federal Holidays 2019–2023 (dates when NYSE is closed)
# Source: OPM.gov federal holiday schedule, confirmed for each year
FEDERAL_HOLIDAYS = {
    # 2019
    "2019-01-01", "2019-01-21", "2019-02-18", "2019-05-27",
    "2019-07-04", "2019-09-02", "2019-10-14", "2019-11-11",
    "2019-11-28", "2019-12-25",
    # 2020 (included for context — but split='exclude' so won't affect training)
    "2020-01-01", "2020-01-20", "2020-02-17", "2020-05-25",
    "2020-07-03", "2020-09-07", "2020-10-12", "2020-11-11",
    "2020-11-26", "2020-12-25",
    # 2021
    "2021-01-01", "2021-01-18", "2021-02-15", "2021-05-31",
    "2021-06-19", "2021-07-05", "2021-09-06", "2021-10-11",
    "2021-11-11", "2021-11-25", "2021-12-24",
    # 2022
    "2022-01-17", "2022-02-21", "2022-05-30",
    "2022-06-20", "2022-07-04", "2022-09-05", "2022-10-10",
    "2022-11-11", "2022-11-24", "2022-12-26",
    # 2023 (holdout year — still add feature so model can use it at inference time)
    "2023-01-02", "2023-01-16", "2023-02-20", "2023-05-29",
    "2023-06-19", "2023-07-04", "2023-09-04", "2023-10-09",
    "2023-11-10", "2023-11-23", "2023-12-25",
}

# Also add NYC-observed holidays not in federal list
NYC_EXTRA_HOLIDAYS = {
    "2019-11-05", "2020-11-03", "2021-11-02", "2022-11-08", "2023-11-07",  # Election Day
    # Rosh Hashanah, Yom Kippur (public school closures — big NYC EMS signal)
    "2019-09-29", "2019-09-30", "2019-10-08", "2019-10-09",
    "2021-09-06", "2021-09-07", "2021-09-15", "2021-09-16",
    "2022-09-25", "2022-09-26", "2022-10-04", "2022-10-05",
    "2023-09-15", "2023-09-16", "2023-09-24", "2023-09-25",
}

ALL_HOLIDAYS = FEDERAL_HOLIDAYS | NYC_EXTRA_HOLIDAYS

holiday_list = [{"date_str": d, "is_holiday": 1} for d in ALL_HOLIDAYS]
holiday_df = spark.createDataFrame(pd.DataFrame(holiday_list)) \
    .withColumn("holiday_date", F.to_date("date_str", "yyyy-MM-dd"))

incidents = spark.table("firstwave.incidents_cleaned") \
    .withColumn("incident_date", F.to_date("incident_dt"))

incidents = incidents.join(
    holiday_df.select("holiday_date", "is_holiday"),
    on=incidents["incident_date"] == holiday_df["holiday_date"],
    how="left"
).fillna({"is_holiday": 0}).drop("incident_date", "holiday_date")

incidents.write.format("delta").mode("overwrite") \
    .save("dbfs:/firstwave/delta/incidents_cleaned")

print(f"Holiday rows: {incidents.filter('is_holiday = 1').count():,}")
# Expect roughly 2–3% of training rows
```

**Add to FEATURE_COLS:**

```python
"is_holiday",        # 1 on federal + NYC-observed holidays
```

---

## PRIORITY 3 — NYC School Calendar (30 MINUTES)

**Why it matters:** School days vs non-school days significantly affect daytime
demand (pediatric calls, school-zone incidents). Summer + holidays = different pattern.

**No structured dataset — scrape from PDFs or use this hardcoded approach:**

NYC DOE publishes PDF calendars. Rather than parse PDFs, hardcode the
school session ranges (faster and more reliable for historical years):

```python
# NYC DOE academic years — first and last instructional day
# Source: schools.nyc.gov/calendar (verified per year)
SCHOOL_SESSIONS = [
    # (start, end, year_label)
    # Note: these are the ACTUAL start/end of student attendance
    ("2019-09-05", "2020-06-26", "2019-20"),   # COVID ended this early
    # 2020-21 is in excluded year
    ("2021-09-13", "2022-06-27", "2021-22"),
    ("2022-09-08", "2023-06-27", "2022-23"),
    ("2023-09-07", "2024-06-26", "2023-24"),
]

# School CLOSURE dates within sessions (breaks + holidays)
# These are days when school is in session range but closed
SCHOOL_CLOSURES = {
    # 2019-20 closures (within Sep 2019 – Jun 2020)
    "2019-10-14","2019-11-05","2019-11-11","2019-11-27","2019-11-28","2019-11-29",
    "2019-12-24","2019-12-25","2019-12-26","2019-12-27","2019-12-28","2019-12-31",
    "2020-01-01","2020-01-20","2020-02-17","2020-02-18","2020-02-19","2020-02-20","2020-02-21",
    "2020-04-09","2020-04-10","2020-04-13","2020-04-14","2020-04-15","2020-04-16","2020-04-17",
    # 2021-22 closures
    "2021-10-11","2021-11-02","2021-11-25","2021-11-26","2021-12-23","2021-12-24",
    "2021-12-27","2021-12-28","2021-12-29","2021-12-30","2021-12-31",
    "2022-01-17","2022-02-21","2022-02-22","2022-02-23","2022-02-24","2022-02-25",
    "2022-04-14","2022-04-15","2022-04-18","2022-04-19","2022-04-20","2022-04-21","2022-04-22",
    "2022-05-30",
    # 2022-23 closures
    "2022-09-26","2022-10-05","2022-10-10","2022-11-08","2022-11-24","2022-11-25",
    "2022-12-23","2022-12-26","2022-12-27","2022-12-28","2022-12-29","2022-12-30",
    "2023-01-02","2023-01-16","2023-02-20","2023-02-21","2023-02-22","2023-02-23","2023-02-24",
    "2023-04-05","2023-04-06","2023-04-07","2023-04-10","2023-04-11","2023-04-12","2023-04-13","2023-04-14",
    "2023-05-29",
    # 2023-24 (holdout year)
    "2023-09-15","2023-09-16","2023-10-09","2023-11-07","2023-11-23","2023-11-24",
    "2023-12-25","2023-12-26","2023-12-27","2023-12-28","2023-12-29",
}

import datetime as dt

def is_school_day(date_str: str) -> int:
    d = dt.date.fromisoformat(date_str)
    if d.weekday() >= 5: return 0               # Weekend
    if date_str in SCHOOL_CLOSURES: return 0    # Official closure
    for start, end, _ in SCHOOL_SESSIONS:
        if dt.date.fromisoformat(start) <= d <= dt.date.fromisoformat(end):
            return 1
    return 0  # Summer or outside all sessions

# Build lookup: 2019-01-01 through 2023-12-31
start_dt = dt.date(2019, 1, 1)
end_dt   = dt.date(2023, 12, 31)

school_rows = []
cur = start_dt
while cur <= end_dt:
    school_rows.append({"date_str": cur.isoformat(), "is_school_day": is_school_day(cur.isoformat())})
    cur += dt.timedelta(days=1)

school_df = spark.createDataFrame(pd.DataFrame(school_rows)) \
    .withColumn("school_date", F.to_date("date_str", "yyyy-MM-dd"))

incidents = spark.table("firstwave.incidents_cleaned") \
    .withColumn("incident_date", F.to_date("incident_dt"))

incidents = incidents.join(
    school_df.select("school_date", "is_school_day"),
    on=incidents["incident_date"] == school_df["school_date"],
    how="left"
).fillna({"is_school_day": 0}).drop("incident_date", "school_date")

incidents.write.format("delta").mode("overwrite") \
    .save("dbfs:/firstwave/delta/incidents_cleaned")

print(f"School day rows: {incidents.filter('is_school_day = 1').count():,}")
# Expect ~55-60% of training rows (roughly 180 school days/year)
```

**Add to FEATURE_COLS:**

```python
"is_school_day",     # 1 on NYC DOE instructional days (Mon–Fri, no breaks/holidays)
```

---

## PRIORITY 4 — MTA Subway Major Incidents (MEDIUM VALUE)

**Why it matters:** Major subway disruptions (50+ trains delayed) push people to
street-level transport and correlate with surface EMS spikes (crowding, heat exposure,
medical emergencies in stations). Two separate datasets cover the full 2019–2023 range.

**Dataset A: MTA Subway Major Incidents 2015–2019**

- URL: `https://data.ny.gov/resource/i8rn-y4np.json` (Socrata)
- Direct CSV: `https://data.ny.gov/api/views/i8rn-y4np/rows.csv?accessType=DOWNLOAD`
- Columns: `month`, `day_type` (weekday/weekend), `division`, `line`, `category`,
  `total_count` (incidents per month per line)

**Dataset B: MTA Subway Major Incidents 2020–present**

- URL: `https://data.ny.gov/resource/j6d2-s8m2.json` (Socrata)
- Direct CSV: `https://data.ny.gov/api/views/j6d2-s8m2/rows.csv?accessType=DOWNLOAD`
- Columns: same schema as Dataset A

**Note:** These are _monthly_ aggregates by line — not incident-level datetimes.
Best use: create a `monthly_major_incidents` lookup and join on (year, month, borough).

```python
import requests, pandas as pd
from pyspark.sql import functions as F

# Download and combine both datasets
mta_old = pd.read_csv("https://data.ny.gov/api/views/i8rn-y4np/rows.csv?accessType=DOWNLOAD")
mta_new = pd.read_csv("https://data.ny.gov/api/views/j6d2-s8m2/rows.csv?accessType=DOWNLOAD")

for df in [mta_old, mta_new]:
    df.columns = [c.lower().replace(" ", "_") for c in df.columns]

mta_all = pd.concat([mta_old, mta_new], ignore_index=True)

# The 'month' column is typically formatted as "January 2019" or "2019-01"
# Normalize to year and month integers
mta_all["parsed_month"] = pd.to_datetime(mta_all["month"], errors="coerce")
mta_all = mta_all.dropna(subset=["parsed_month"])
mta_all["year"]  = mta_all["parsed_month"].dt.year
mta_all["month_num"] = mta_all["parsed_month"].dt.month

# Map subway lines to boroughs (approximate — A/C/E serve many boroughs)
SUBWAY_BOROUGH = {
    "1": "Manhattan", "2": "Bronx/Manhattan", "3": "Brooklyn/Manhattan",
    "4": "Bronx/Manhattan/Brooklyn", "5": "Bronx/Brooklyn", "6": "Bronx/Manhattan",
    "7": "Queens/Manhattan", "A": "Manhattan/Brooklyn/Queens",
    "B": "Manhattan/Brooklyn", "C": "Manhattan/Brooklyn",
    "D": "Bronx/Manhattan/Brooklyn", "E": "Queens/Manhattan",
    "F": "Queens/Brooklyn/Manhattan", "G": "Queens/Brooklyn",
    "J": "Manhattan/Brooklyn", "L": "Manhattan/Brooklyn",
    "M": "Queens/Manhattan/Brooklyn", "N": "Queens/Manhattan/Brooklyn",
    "Q": "Manhattan/Brooklyn", "R": "Queens/Manhattan/Brooklyn",
}

# Aggregate to monthly incident count per borough
monthly_agg = mta_all.groupby(["year","month_num"])["total_count"].sum().reset_index()
monthly_agg.rename(columns={"total_count": "monthly_subway_incidents"}, inplace=True)

# Normalize to 0–1 (high incident month = 1)
min_inc = monthly_agg["monthly_subway_incidents"].min()
max_inc = monthly_agg["monthly_subway_incidents"].max()
monthly_agg["subway_disruption_idx"] = (
    (monthly_agg["monthly_subway_incidents"] - min_inc) / (max_inc - min_inc)
)

monthly_spark = spark.createDataFrame(monthly_agg[["year","month_num","subway_disruption_idx"]])

incidents = spark.table("firstwave.incidents_cleaned") \
    .withColumn("inc_year", F.year("incident_dt")) \
    .withColumn("inc_month", F.month("incident_dt"))

incidents = incidents.join(
    monthly_spark,
    on=(F.col("inc_year") == F.col("year")) & (F.col("inc_month") == F.col("month_num")),
    how="left"
).fillna({"subway_disruption_idx": 0.5}).drop("year", "month_num", "inc_year", "inc_month")

incidents.write.format("delta").mode("overwrite") \
    .save("dbfs:/firstwave/delta/incidents_cleaned")
```

**Add to FEATURE_COLS:**

```python
"subway_disruption_idx",  # 0–1, normalized monthly major incidents count
```

**Caveats:** Monthly resolution means this feature applies to all rows in a month —
it cannot capture individual incident days. Useful for seasonality but not pinpoint.
If RMSE doesn't improve, drop this feature — it's not worth the complexity.

---

## PRIORITY 5 — NYC Heat Emergency Days (DERIVE FROM WEATHER)

**Why it matters:** The NYC Heat Emergency threshold (Heat Index ≥ 95°F for 2+
consecutive days, or HI ≥ 100°F on any single day) is already capturable from
Open-Meteo weather data you already have. No new dataset needed.

**Derive in Notebook 02 after weather merge:**

```python
from pyspark.sql import functions as F
from pyspark.sql.window import Window

# Open-Meteo WMO codes — these are already in is_severe_weather
# But heat emergency needs Heat Index, not just temperature
# Approximate Heat Index from temp + dewpoint (Open-Meteo provides dewpoint_2m)
# If you fetched dewpoint_2m in Notebook 02, use it. Otherwise use this approximation:

# Heat Index formula (simplified Rothfusz, valid for temp > 80°F / 26.7°C)
# HI ≈ -42.379 + 2.04901523T + 10.14333127R - 0.22475541TR - 0.00683783T²
# - 0.05481717R² + 0.00122874T²R + 0.00085282TR² - 0.00000199T²R²
# where T = temp in °F, R = relative_humidity_%

# Simpler: if you only have temperature, flag days >= 95°F (35°C) as heat-risk
incidents = spark.table("firstwave.incidents_cleaned")

# Flag extreme heat: temperature_2m >= 35°C (95°F)
incidents = incidents.withColumn(
    "is_extreme_heat",
    F.when(F.col("temperature_2m") >= 35.0, 1).otherwise(0)
)

# Flag sustained heat: 2+ consecutive days >= 32°C (90°F) in same zone
# Use a rolling window over date_hour
w = Window.partitionBy("INCIDENT_DISPATCH_AREA") \
    .orderBy("date_hour") \
    .rowsBetween(-24, 0)   # look back 24 hours (1 day at hourly grain)

incidents = incidents.withColumn(
    "prior_24h_max_temp",
    F.max("temperature_2m").over(w)
).withColumn(
    "is_heat_emergency",
    F.when(
        (F.col("temperature_2m") >= 35.0) | (F.col("prior_24h_max_temp") >= 32.2),
        1
    ).otherwise(0)
).drop("prior_24h_max_temp")

incidents.write.format("delta").mode("overwrite") \
    .save("dbfs:/firstwave/delta/incidents_cleaned")

print(f"Heat emergency rows: {incidents.filter('is_heat_emergency = 1').count():,}")
# Expect 3–8% of rows (summer months only)
```

**Add to FEATURE_COLS:**

```python
"is_heat_emergency",  # 1 when temp conditions meet NYC heat emergency threshold
"is_extreme_heat",    # 1 when temperature_2m >= 35°C
```

**Note:** `is_severe_weather` already captures storms. `is_heat_emergency` captures
the opposite extreme. Together they bracket the worst-demand weather scenarios.

---

## PRIORITY 6 — MTA Service Alerts (LOW PRIORITY — complex join)

**Dataset A: MTA Service Alerts 2012–2020**

- URL: `https://data.ny.gov/resource/3h5b-5ktz.json`
- Direct CSV: `https://data.ny.gov/api/views/3h5b-5ktz/rows.csv?accessType=DOWNLOAD`
- Columns: `alert_type`, `agency`, `affected_key`, `header_text`, `created_at`

**Dataset B: MTA Service Alerts 2020–present**

- URL: `https://data.ny.gov/resource/7kct-peq7.json`
- Direct CSV: `https://data.ny.gov/api/views/7kct-peq7/rows.csv?accessType=DOWNLOAD`

**Why this is low priority:** Alert text needs NLP to determine severity. Alert timing
is noisy (alerts often precede actual disruption). The monthly MTA Major Incidents
dataset (Priority 4) is a cleaner proxy. Skip this unless Priorities 1–5 are done
and you still have time.

---

## UPDATED FEATURE_COLS (after all additions)

```python
FEATURE_COLS = [
    # ORIGINAL 15 FEATURES
    "hour_sin", "hour_cos",          # cyclical hour
    "dow_sin", "dow_cos",            # cyclical day of week
    "month_sin", "month_cos",        # cyclical month
    "is_weekend",                    # binary
    "temperature_2m",                # Open-Meteo
    "precipitation",                 # Open-Meteo
    "windspeed_10m",                 # Open-Meteo
    "is_severe_weather",             # from WMO weather codes
    "svi_score",                     # CDC SVI per zone
    "zone_baseline_avg",             # rolling avg (zone, hour, dow)
    "high_acuity_ratio",             # historical zone stat
    "held_ratio",                    # historical zone stat

    # NEW FEATURES (add in order of priority — test RMSE after each)
    "is_major_event",                # Priority 1: NYC special event in borough
    "is_holiday",                    # Priority 2: federal + NYC holiday
    "is_school_day",                 # Priority 3: NYC DOE instructional day
    "subway_disruption_idx",         # Priority 4: monthly MTA major incidents (0–1)
    "is_heat_emergency",             # Priority 5: heat index threshold met
    "is_extreme_heat",               # Priority 5: temperature >= 35°C
]
```

**IMPORTANT:** Add features one group at a time and check RMSE after each.
If RMSE increases after adding a feature, remove it — it's adding noise.
Expected improvement order: is_holiday > is_major_event > is_school_day > is_heat_emergency > subway_disruption_idx

---

## Download Summary — What to Run Before Notebooks

```bash
# From DBFS — run these wget commands in a Databricks notebook first cell

# Special Events Historical CSV (~50MB)
%sh wget -O /dbfs/firstwave/data/nyc_events_historical.csv \
  "https://data.cityofnewyork.us/api/views/bkfu-528j/rows.csv?accessType=DOWNLOAD"

# MTA Major Incidents Pre-2020
%sh wget -O /dbfs/firstwave/data/mta_incidents_2015_2019.csv \
  "https://data.ny.gov/api/views/i8rn-y4np/rows.csv?accessType=DOWNLOAD"

# MTA Major Incidents 2020+
%sh wget -O /dbfs/firstwave/data/mta_incidents_2020_present.csv \
  "https://data.ny.gov/api/views/j6d2-s8m2/rows.csv?accessType=DOWNLOAD"

# Verify all three downloaded
%sh ls -lh /dbfs/firstwave/data/
```

The holidays and school calendar are hardcoded — no download needed for those.
The heat emergency feature is derived from weather data already in the pipeline — no download needed.

---

## Time Estimates (during pipeline wait)

| Feature                 | Download          | Code   | Expected RMSE Δ |
| ----------------------- | ----------------- | ------ | --------------- |
| `is_holiday`            | 0 min (hardcoded) | 10 min | −0.3 to −0.6    |
| `is_major_event`        | 5 min             | 25 min | −0.2 to −0.4    |
| `is_school_day`         | 0 min (hardcoded) | 15 min | −0.1 to −0.3    |
| `is_heat_emergency`     | 0 min (derived)   | 10 min | −0.1 to −0.2    |
| `subway_disruption_idx` | 5 min             | 20 min | −0.0 to −0.1    |

Total: ~85 minutes to add all 5 — well within the pipeline wait time.
