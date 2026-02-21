# Databricks notebook source
# MAGIC %md
# MAGIC # Notebook 01 — Ingest & Clean
# MAGIC **FirstWave | GT Hacklytics 2026**
# MAGIC
# MAGIC Input: `dbfs:/firstwave/data/ems_raw.csv` (~28.7M rows)
# MAGIC Output: Delta table `firstwave.incidents_cleaned`

# COMMAND ----------

# MAGIC %md ## Setup

# COMMAND ----------

from pyspark.sql import functions as F
from pyspark.sql.types import IntegerType, DoubleType

# DBFS paths
RAW_CSV       = "dbfs:/firstwave/data/ems_raw.csv"
DELTA_CLEANED = "dbfs:/firstwave/delta/incidents_cleaned"

# COMMAND ----------

# MAGIC %md ## Constants

# COMMAND ----------

VALID_ZONES = [
    'B1','B2','B3','B4','B5',
    'K1','K2','K3','K4','K5','K6','K7',
    'M1','M2','M3','M4','M5','M6','M7','M8','M9',
    'Q1','Q2','Q3','Q4','Q5','Q6','Q7',
    'S1','S2','S3'
]

# COMMAND ----------

# MAGIC %md ## Step 1: Read Raw CSV

# COMMAND ----------

print(f"Reading raw CSV from {RAW_CSV}...")
df_raw = spark.read.csv(RAW_CSV, header=True, inferSchema=False)

print(f"Raw row count:    {df_raw.count():,}")
print(f"Raw column count: {len(df_raw.columns)}")
print("\nSample columns:")
for col in df_raw.columns[:10]:
    print(f"  {col}")

# COMMAND ----------

# MAGIC %md ## Step 2: Parse Datetime

# COMMAND ----------

# Try format-specific parse first (much faster than inference on 28M rows)
df_raw = df_raw.withColumn(
    "incident_dt",
    F.to_timestamp("INCIDENT_DATETIME", "MM/dd/yyyy hh:mm:ss a")
)

# Validate parse quality — if >1% null, use fallback
total_raw = df_raw.count()
null_dt = df_raw.filter(F.col("incident_dt").isNull()).count()
null_pct = null_dt / total_raw * 100
print(f"Datetime parse: {null_dt:,} nulls ({null_pct:.2f}%)")

if null_pct > 1.0:
    print("WARNING: >1% null datetimes — using fallback (no format string)")
    df_raw = df_raw.withColumn(
        "incident_dt",
        F.to_timestamp("INCIDENT_DATETIME")
    )
    null_dt2 = df_raw.filter(F.col("incident_dt").isNull()).count()
    print(f"After fallback: {null_dt2:,} nulls ({null_dt2/total_raw*100:.2f}%)")

# COMMAND ----------

# MAGIC %md ## Step 3: Feature Engineering (pre-filter)

# COMMAND ----------

df_raw = df_raw \
    .withColumn("year",       F.year("incident_dt")) \
    .withColumn("month",      F.month("incident_dt")) \
    .withColumn("dayofweek",  (F.dayofweek("incident_dt") + 5) % 7) \
    .withColumn("hour",       F.hour("incident_dt")) \
    .withColumn("date_hour",  F.date_trunc("hour", "incident_dt")) \
    .withColumn("is_weekend",
        F.when(F.col("dayofweek").isin(5, 6), 1).otherwise(0)) \
    .withColumn("is_high_acuity",
        F.when(F.col("FINAL_SEVERITY_LEVEL_CODE").isin(1, 2), 1).otherwise(0)) \
    .withColumn("is_held",
        F.when(F.col("HELD_INDICATOR") == "Y", 1).otherwise(0)) \
    .withColumn("is_covid_year",
        F.when(F.col("year") == 2020, 1).otherwise(0)) \
    .withColumn("INCIDENT_RESPONSE_SECONDS_QY",
        F.col("INCIDENT_RESPONSE_SECONDS_QY").cast(DoubleType())) \
    .withColumn("INCIDENT_TRAVEL_TM_SECONDS_QY",
        F.col("INCIDENT_TRAVEL_TM_SECONDS_QY").cast(DoubleType())) \
    .withColumn("DISPATCH_RESPONSE_SECONDS_QY",
        F.col("DISPATCH_RESPONSE_SECONDS_QY").cast(DoubleType())) \
    .withColumn("FINAL_SEVERITY_LEVEL_CODE",
        F.col("FINAL_SEVERITY_LEVEL_CODE").cast(IntegerType())) \
    .withColumn("split",
        F.when(F.col("year") == 2023, "test")
         .when(F.col("year") == 2020, "exclude")
         .when(F.col("year").between(2019, 2022), "train")
         .otherwise("exclude"))

# COMMAND ----------

# MAGIC %md ## Step 4: Quality Filters

# COMMAND ----------

# Borough-zone prefix consistency (catches CAD entry errors)
zone_borough_match = (
    ((F.col("BOROUGH") == "BRONX")                      & F.col("INCIDENT_DISPATCH_AREA").startswith("B")) |
    ((F.col("BOROUGH") == "BROOKLYN")                   & F.col("INCIDENT_DISPATCH_AREA").startswith("K")) |
    ((F.col("BOROUGH") == "MANHATTAN")                  & F.col("INCIDENT_DISPATCH_AREA").startswith("M")) |
    ((F.col("BOROUGH") == "QUEENS")                     & F.col("INCIDENT_DISPATCH_AREA").startswith("Q")) |
    (F.col("BOROUGH").contains("STATEN")                & F.col("INCIDENT_DISPATCH_AREA").startswith("S"))
)

df_clean = df_raw.filter(
    (F.col("VALID_INCIDENT_RSPNS_TIME_INDC") == "Y") &
    (F.col("VALID_DISPATCH_RSPNS_TIME_INDC") == "Y") &
    (F.col("REOPEN_INDICATOR") == "N") &
    (F.col("TRANSFER_INDICATOR") == "N") &
    (F.col("STANDBY_INDICATOR") == "N") &
    F.col("INCIDENT_RESPONSE_SECONDS_QY").between(1, 7200) &
    (F.col("BOROUGH") != "UNKNOWN") &
    F.col("BOROUGH").isNotNull() &
    F.col("INCIDENT_DISPATCH_AREA").isin(VALID_ZONES) &
    zone_borough_match &
    F.col("incident_dt").isNotNull()
)

# COMMAND ----------

# MAGIC %md ## Step 5: Write Delta Table

# COMMAND ----------

# Create database if not exists
spark.sql("CREATE DATABASE IF NOT EXISTS firstwave")

df_clean.write.format("delta") \
    .mode("overwrite") \
    .option("overwriteSchema", "true") \
    .save(DELTA_CLEANED)

spark.sql(f"""
    CREATE TABLE IF NOT EXISTS firstwave.incidents_cleaned
    USING DELTA LOCATION '{DELTA_CLEANED}'
""")

print("Delta table written.")

# COMMAND ----------

# MAGIC %md ## Step 6: Validation

# COMMAND ----------

df_val = spark.table("firstwave.incidents_cleaned")
total = df_val.count()
train = df_val.filter("split = 'train'").count()
test  = df_val.filter("split = 'test'").count()
excl  = df_val.filter("split = 'exclude'").count()

print("=" * 55)
print("  NOTEBOOK 01 — VALIDATION")
print("=" * 55)
print(f"  Total after filters: {total:,}")
print(f"  Training (2019,21,22): {train:,}   ← expect ~5.6M")
print(f"  Holdout  (2023):       {test:,}   ← expect ~1.5M")
print(f"  Excluded (2020+other): {excl:,}")
print()

if train < 3_000_000:
    print("  ⚠️  WARNING: Training rows < 3M — datetime parse may have failed!")
    print("  ⚠️  Try: F.to_timestamp('INCIDENT_DATETIME') without format string")
else:
    print("  ✓ Training row count OK")

if test < 1_000_000:
    print("  ⚠️  WARNING: Test rows < 1M — check year filter")
else:
    print("  ✓ Test row count OK")

print()
print("  Zone distribution (top 10 by volume):")
df_val.groupBy("INCIDENT_DISPATCH_AREA") \
    .count() \
    .orderBy("count", ascending=False) \
    .show(10)

print("  Borough distribution:")
df_val.groupBy("BOROUGH").count().orderBy("count", ascending=False).show()

print("  Year distribution:")
df_val.groupBy("year").count().orderBy("year").show()

print("  Split distribution:")
df_val.groupBy("split").count().show()

print("=" * 55)
print("  Next: Run Notebook 02 (weather merge)")
print("=" * 55)
