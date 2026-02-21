# Databricks notebook source
# MAGIC %md
# MAGIC # Notebook 04 — Aggregation
# MAGIC **FirstWave | GT Hacklytics 2026**
# MAGIC
# MAGIC Input: `firstwave.incidents_cleaned` (from Notebooks 01-03)
# MAGIC Outputs:
# MAGIC   - Delta table `firstwave.incidents_aggregated`
# MAGIC   - `dbfs:/firstwave/artifacts/zone_baselines.parquet`
# MAGIC   - `dbfs:/firstwave/artifacts/zone_stats.parquet`

# COMMAND ----------

# MAGIC %md ## Setup

# COMMAND ----------

import math
from pyspark.sql import functions as F

DELTA_AGGD     = "dbfs:/firstwave/delta/incidents_aggregated"
ARTIFACTS      = "dbfs:/firstwave/artifacts/"
BASELINES_PATH = "/dbfs/firstwave/artifacts/zone_baselines.parquet"
STATS_PATH     = "/dbfs/firstwave/artifacts/zone_stats.parquet"

# Ensure artifact directory exists
import os
os.makedirs("/dbfs/firstwave/artifacts/", exist_ok=True)

# COMMAND ----------

# MAGIC %md ## Step 1: Load Cleaned Incidents (train + test only)

# COMMAND ----------

incidents = spark.table("firstwave.incidents_cleaned") \
    .filter(F.col("split").isin("train", "test"))

total = incidents.count()
print(f"Incidents loaded (train+test): {total:,}")

# COMMAND ----------

# MAGIC %md ## Step 2: Hourly Zone-Level Aggregation

# COMMAND ----------

PI = math.pi

agg = incidents.groupBy(
    "INCIDENT_DISPATCH_AREA",
    "BOROUGH",
    "year",
    "month",
    "dayofweek",
    "hour",
    "is_weekend",
    "temperature_2m",
    "precipitation",
    "windspeed_10m",
    "is_severe_weather",
    "svi_score",
    "split"
).agg(
    F.count("CAD_INCIDENT_ID").alias("incident_count"),
    F.mean("INCIDENT_RESPONSE_SECONDS_QY").alias("avg_response_seconds"),
    F.mean("INCIDENT_TRAVEL_TM_SECONDS_QY").alias("avg_travel_seconds"),
    F.mean("DISPATCH_RESPONSE_SECONDS_QY").alias("avg_dispatch_seconds"),
    F.sum("is_high_acuity").alias("high_acuity_count"),
    F.sum("is_held").alias("held_count"),
    F.percentile_approx("INCIDENT_RESPONSE_SECONDS_QY", 0.5).alias("median_response_seconds")
)

# Add cyclical time features for XGBoost
agg = agg \
    .withColumn("hour_sin",  F.sin(2 * F.lit(PI) * F.col("hour") / 24)) \
    .withColumn("hour_cos",  F.cos(2 * F.lit(PI) * F.col("hour") / 24)) \
    .withColumn("dow_sin",   F.sin(2 * F.lit(PI) * F.col("dayofweek") / 7)) \
    .withColumn("dow_cos",   F.cos(2 * F.lit(PI) * F.col("dayofweek") / 7)) \
    .withColumn("month_sin", F.sin(2 * F.lit(PI) * F.col("month") / 12)) \
    .withColumn("month_cos", F.cos(2 * F.lit(PI) * F.col("month") / 12))

agg_count = agg.count()
print(f"Aggregated rows: {agg_count:,}")

# COMMAND ----------

# MAGIC %md ## Step 3: Write incidents_aggregated Delta Table

# COMMAND ----------

agg.write.format("delta") \
    .mode("overwrite") \
    .option("overwriteSchema", "true") \
    .save(DELTA_AGGD)

spark.sql(f"""
    CREATE TABLE IF NOT EXISTS firstwave.incidents_aggregated
    USING DELTA LOCATION '{DELTA_AGGD}'
""")

print(f"Delta table firstwave.incidents_aggregated written: {agg_count:,} rows")

# COMMAND ----------

# MAGIC %md ## Step 4: Zone Baselines (most important artifact for model accuracy)
# MAGIC
# MAGIC Rolling average incidents per (zone, hour, dayofweek) over training years.
# MAGIC This is the single most important XGBoost feature (`zone_baseline_avg`).

# COMMAND ----------

# Compute daily incident counts per (zone, hour, dow), then average across days
# This gives us: "on a typical Monday at 8pm, how many incidents does B2 see?"
train_incidents = incidents.filter("split = 'train'")

daily = train_incidents \
    .withColumn("date", F.to_date("incident_dt")) \
    .groupBy("INCIDENT_DISPATCH_AREA", "hour", "dayofweek", "date") \
    .agg(F.count("CAD_INCIDENT_ID").alias("daily_count"))

zone_baselines = daily.groupBy("INCIDENT_DISPATCH_AREA", "hour", "dayofweek") \
    .agg(F.mean("daily_count").alias("zone_baseline_avg"))

baseline_count = zone_baselines.count()
max_expected = 31 * 24 * 7  # 5,208

print(f"Zone baselines: {baseline_count} rows (max possible: {max_expected})")

# Write to DBFS as Parquet
zone_baselines.toPandas().to_parquet(BASELINES_PATH, index=False)
print(f"zone_baselines.parquet written to {BASELINES_PATH}")

# COMMAND ----------

# MAGIC %md ## Step 5: Zone Stats (per-zone historical averages)

# COMMAND ----------

zone_stats = train_incidents \
    .groupBy("INCIDENT_DISPATCH_AREA", "BOROUGH", "svi_score") \
    .agg(
        F.mean("INCIDENT_RESPONSE_SECONDS_QY").alias("avg_response_seconds"),
        F.mean("INCIDENT_TRAVEL_TM_SECONDS_QY").alias("avg_travel_seconds"),
        F.mean("DISPATCH_RESPONSE_SECONDS_QY").alias("avg_dispatch_seconds"),
        F.mean("is_high_acuity").alias("high_acuity_ratio"),
        F.mean("is_held").alias("held_ratio"),
        F.count("CAD_INCIDENT_ID").alias("total_incidents")
    )

stats_count = zone_stats.count()
print(f"Zone stats: {stats_count} rows (expect 31)")

# Write to DBFS as Parquet
zone_stats.toPandas().to_parquet(STATS_PATH, index=False)
print(f"zone_stats.parquet written to {STATS_PATH}")

# COMMAND ----------

# MAGIC %md ## Step 6: Validation

# COMMAND ----------

import pandas as pd

baselines_pd = pd.read_parquet(BASELINES_PATH)
stats_pd     = pd.read_parquet(STATS_PATH)

print("=" * 55)
print("  NOTEBOOK 04 — VALIDATION")
print("=" * 55)
print(f"  incidents_aggregated: {agg_count:,} rows")
print(f"  zone_baselines:       {len(baselines_pd)} rows (expect ≤ {max_expected})")
print(f"  zone_stats:           {len(stats_pd)} rows (expect 31)")
print()

if len(baselines_pd) < 31:
    print("  ⚠️  WARNING: zone_baselines has < 31 rows — join key may be wrong")
elif len(baselines_pd) > max_expected:
    print(f"  ⚠️  WARNING: zone_baselines has > {max_expected} rows — unexpected duplicates")
else:
    print(f"  ✓ zone_baselines row count OK")

if len(stats_pd) != 31:
    print(f"  ⚠️  WARNING: zone_stats has {len(stats_pd)} rows, expected 31")
    print(f"  ⚠️  Zones present: {sorted(stats_pd['INCIDENT_DISPATCH_AREA'].tolist())}")
else:
    print(f"  ✓ zone_stats = 31 rows — all zones present")

print()
print("  zone_baselines sample (top 5 highest baseline):")
print(baselines_pd.sort_values("zone_baseline_avg", ascending=False).head(5).to_string())

print()
print("  zone_stats (sorted by avg_response_seconds):")
print(stats_pd[["INCIDENT_DISPATCH_AREA","BOROUGH","avg_response_seconds",
                 "high_acuity_ratio","held_ratio"]].sort_values(
                     "avg_response_seconds", ascending=False).to_string())

print()
print("  ← Check: Bronx avg_response should be ~638s, Manhattan ~630s")
print("  ← Check: B1, B2, B3 should dominate highest zone_baseline_avg")

print()
print("  DBFS artifacts written:")
print(f"    {BASELINES_PATH}")
print(f"    {STATS_PATH}")
print()
print("  Download these + demand_model.pkl after Notebook 05 and commit to backend/artifacts/")
print("=" * 55)
print("  Next: Run Notebooks 05 (XGBoost) and 06 (OSMnx) — can run in parallel")
print("=" * 55)
