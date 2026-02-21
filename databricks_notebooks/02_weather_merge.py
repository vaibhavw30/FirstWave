# Databricks notebook source
# MAGIC %md
# MAGIC # Notebook 02 — Weather Merge
# MAGIC **FirstWave | GT Hacklytics 2026**
# MAGIC
# MAGIC Input: `firstwave.incidents_cleaned` (from Notebook 01)
# MAGIC External: Open-Meteo historical API (free, no key required)
# MAGIC Output: `firstwave.incidents_cleaned` updated with weather columns

# COMMAND ----------

# MAGIC %md ## Setup

# COMMAND ----------

import requests
import pandas as pd
from pyspark.sql import functions as F

DELTA_CLEANED = "dbfs:/firstwave/delta/incidents_cleaned"

# COMMAND ----------

# MAGIC %md ## Step 1: Fetch Weather from Open-Meteo

# COMMAND ----------

SEVERE_WEATHER_CODES = {51,53,55,61,63,65,71,73,75,77,80,81,82,85,86,95,96,99}

def fetch_open_meteo(start_date: str, end_date: str) -> pd.DataFrame:
    """
    Fetch hourly weather for NYC from Open-Meteo historical archive.
    Free API, no key required. Single call covers multi-year range.
    """
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": 40.7128,
        "longitude": -74.0060,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": "temperature_2m,precipitation,windspeed_10m,weathercode",
        "timezone": "America/New_York"
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

# COMMAND ----------

# Fetch 2019–2023 in one call (Open-Meteo supports multi-year ranges)
try:
    weather_pd = fetch_open_meteo("2019-01-01", "2023-12-31")
except requests.exceptions.Timeout:
    print("WARNING: Open-Meteo timeout — trying year-by-year fallback...")
    dfs = []
    for year in [2019, 2021, 2022, 2023]:
        try:
            dfs.append(fetch_open_meteo(f"{year}-01-01", f"{year}-12-31"))
        except Exception as e:
            print(f"  Year {year} failed: {e}")
    weather_pd = pd.concat(dfs, ignore_index=True)

print(f"\nTotal weather rows: {len(weather_pd):,}")
print(weather_pd.head())

# COMMAND ----------

# MAGIC %md ## Step 2: Convert to Spark DataFrame

# COMMAND ----------

weather_spark = spark.createDataFrame(weather_pd) \
    .withColumn("date_hour", F.to_timestamp("date_hour"))

# Validate timestamp conversion
sample_timestamps = weather_spark.select("date_hour").limit(3).collect()
print("Sample weather timestamps:")
for row in sample_timestamps:
    print(f"  {row['date_hour']}")

# COMMAND ----------

# MAGIC %md ## Step 3: Join Weather to Incidents

# COMMAND ----------

incidents = spark.table("firstwave.incidents_cleaned")
print(f"Incidents before join: {incidents.count():,} rows")

joined = incidents.join(
    weather_spark.select(
        "date_hour",
        "temperature_2m",
        "precipitation",
        "windspeed_10m",
        "weathercode",
        "is_severe_weather"
    ),
    on="date_hour",
    how="left"
).fillna({
    "temperature_2m": 15.0,
    "precipitation": 0.0,
    "windspeed_10m": 10.0,
    "is_severe_weather": 0
})

# COMMAND ----------

# MAGIC %md ## Step 4: Write Back to Delta (overwrite)

# COMMAND ----------

joined.write.format("delta") \
    .mode("overwrite") \
    .option("overwriteSchema", "true") \
    .save(DELTA_CLEANED)

print("Delta table updated with weather columns.")

# COMMAND ----------

# MAGIC %md ## Step 5: Validation

# COMMAND ----------

df_val = spark.table("firstwave.incidents_cleaned")
total = df_val.count()
null_weather = df_val.filter(F.col("temperature_2m").isNull()).count()
null_pct = null_weather / total * 100

print("=" * 55)
print("  NOTEBOOK 02 — VALIDATION")
print("=" * 55)
print(f"  Total rows:         {total:,}")
print(f"  Null weather rows:  {null_weather:,} ({null_pct:.3f}%)")

if null_pct > 0.1:
    print(f"  ⚠️  WARNING: Null weather > 0.1% — check date_hour type")
    print(f"  ⚠️  Ensure date_hour is timestamp not string in both DataFrames")
else:
    print(f"  ✓ Null weather < 0.1% — OK")

print()
print("  Weather stats (non-null sample):")
df_val.select(
    F.mean("temperature_2m").alias("avg_temp_C"),
    F.mean("precipitation").alias("avg_precip_mm"),
    F.mean("windspeed_10m").alias("avg_wind_kmh"),
    F.mean("is_severe_weather").alias("pct_severe")
).show()

print("  Severe weather event count:")
df_val.filter("is_severe_weather = 1").count()
sev = df_val.filter("is_severe_weather = 1").count()
print(f"  Severe weather incidents: {sev:,} ({sev/total*100:.2f}%)")

print("=" * 55)
print("  Next: Run Notebook 03 (SVI join)")
print("=" * 55)
