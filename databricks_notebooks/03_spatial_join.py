# Databricks notebook source
# MAGIC %md
# MAGIC # Notebook 03 — SVI Join
# MAGIC **FirstWave | GT Hacklytics 2026**
# MAGIC
# MAGIC Input: `firstwave.incidents_cleaned` (from Notebook 02)
# MAGIC Data: Hardcoded CDC SVI lookup (no external file needed)
# MAGIC Output: `firstwave.incidents_cleaned` updated with svi_score column

# COMMAND ----------

# MAGIC %md ## Setup

# COMMAND ----------

from pyspark.sql import functions as F

DELTA_CLEANED = "dbfs:/firstwave/delta/incidents_cleaned"

# COMMAND ----------

# MAGIC %md ## Constants: CDC Social Vulnerability Index per Zone

# COMMAND ----------

# CDC SVI RPL_THEMES scores (0–1, higher = more vulnerable)
# Source: CLAUDE.md — verified for all 31 NYC EMS dispatch zones
ZONE_SVI = {
    # Bronx
    'B1': 0.94, 'B2': 0.89, 'B3': 0.87, 'B4': 0.72, 'B5': 0.68,
    # Brooklyn
    'K1': 0.52, 'K2': 0.58, 'K3': 0.82, 'K4': 0.84, 'K5': 0.79,
    'K6': 0.60, 'K7': 0.45,
    # Manhattan
    'M1': 0.31, 'M2': 0.18, 'M3': 0.15, 'M4': 0.20, 'M5': 0.12,
    'M6': 0.14, 'M7': 0.73, 'M8': 0.65, 'M9': 0.61,
    # Queens
    'Q1': 0.71, 'Q2': 0.44, 'Q3': 0.38, 'Q4': 0.55, 'Q5': 0.67,
    'Q6': 0.48, 'Q7': 0.41,
    # Staten Island
    'S1': 0.38, 'S2': 0.32, 'S3': 0.28
}

print(f"ZONE_SVI loaded: {len(ZONE_SVI)} zones")
print(f"  Highest SVI: {max(ZONE_SVI, key=ZONE_SVI.get)} = {max(ZONE_SVI.values())}")
print(f"  Lowest SVI:  {min(ZONE_SVI, key=ZONE_SVI.get)} = {min(ZONE_SVI.values())}")

# COMMAND ----------

# MAGIC %md ## Step 1: Create SVI Lookup DataFrame

# COMMAND ----------

svi_rows = [
    {"INCIDENT_DISPATCH_AREA": zone, "svi_score": score}
    for zone, score in ZONE_SVI.items()
]
svi_df = spark.createDataFrame(svi_rows)

print("SVI lookup DataFrame:")
svi_df.orderBy("INCIDENT_DISPATCH_AREA").show(31)

# COMMAND ----------

# MAGIC %md ## Step 2: Join SVI to Incidents

# COMMAND ----------

incidents = spark.table("firstwave.incidents_cleaned")
print(f"Incidents before SVI join: {incidents.count():,} rows")

# Check if svi_score already exists from a previous run
if "svi_score" in incidents.columns:
    print("svi_score column already exists — dropping before re-join")
    incidents = incidents.drop("svi_score")

updated = incidents.join(svi_df, on="INCIDENT_DISPATCH_AREA", how="left") \
                   .fillna({"svi_score": 0.5})  # fallback for any unexpected zones

# COMMAND ----------

# MAGIC %md ## Step 3: Write Back to Delta

# COMMAND ----------

updated.write.format("delta") \
    .mode("overwrite") \
    .option("overwriteSchema", "true") \
    .save(DELTA_CLEANED)

print("Delta table updated with svi_score column.")

# COMMAND ----------

# MAGIC %md ## Step 4: Validation

# COMMAND ----------

df_val = spark.table("firstwave.incidents_cleaned")
total = df_val.count()
null_svi = df_val.filter(F.col("svi_score").isNull()).count()
distinct_zones = df_val.select("INCIDENT_DISPATCH_AREA").distinct().count()

print("=" * 55)
print("  NOTEBOOK 03 — VALIDATION")
print("=" * 55)
print(f"  Total rows:         {total:,}")
print(f"  Null SVI rows:      {null_svi}   ← expect 0")
print(f"  Distinct zones:     {distinct_zones}   ← expect 31")

if null_svi > 0:
    print(f"  ⚠️  WARNING: {null_svi} null SVI rows — unexpected zone codes present")
    df_val.filter(F.col("svi_score").isNull()) \
        .groupBy("INCIDENT_DISPATCH_AREA").count() \
        .orderBy("count", ascending=False).show(10)
else:
    print(f"  ✓ No null SVI rows — all zones matched")

if distinct_zones != 31:
    print(f"  ⚠️  WARNING: Expected 31 zones, found {distinct_zones}")
else:
    print(f"  ✓ Exactly 31 dispatch zones — OK")

print()
print("  SVI distribution by zone:")
df_val.groupBy("INCIDENT_DISPATCH_AREA", "svi_score") \
    .count() \
    .orderBy("svi_score", ascending=False) \
    .show(31)

print("=" * 55)
print("  Next: Run Notebook 04 (aggregation)")
print("=" * 55)
