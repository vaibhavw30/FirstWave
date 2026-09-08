-- ════════════════════════════════════════════════════════════════════════════
-- proc_sql_4a  —  Stage ④ Hourly Zone Aggregation
-- FirstWave | Datamorph DuckDB Pipeline: duckdb_pipeline_04_aggregate
--
-- SQL RELATIONS (input):  incidents_cleaned  (Parquet Source, from Stage ③)
-- DOWNSTREAM:             incidents_aggregated (Parquet Sink) — the model training table
--
-- Mirrors: pipeline/04_aggregate.py  (Step 1)
-- Aggregation rules:
--   Weather metrics  -> AVG  (continuous)
--   Categorical flags-> MAX  (hour-level facts: any incident in the bin sets it)
--   subway/svi       -> AVG  (constant within a bin; AVG == MIN == MAX)
-- ════════════════════════════════════════════════════════════════════════════

SELECT
    INCIDENT_DISPATCH_AREA, BOROUGH, year, month, dayofweek, hour,
    is_weekend, split,

    -- ── Weather (average over incidents in this zone-hour bin) ─────────────────
    ROUND(AVG(temperature_2m), 2)        AS temperature_2m,
    ROUND(AVG(precipitation),  3)        AS precipitation,
    ROUND(AVG(windspeed_10m),  2)        AS windspeed_10m,

    -- ── Categorical weather / calendar flags (MAX) ─────────────────────────────
    MAX(is_severe_weather)               AS is_severe_weather,
    MAX(is_extreme_heat)                 AS is_extreme_heat,
    MAX(is_heat_emergency)               AS is_heat_emergency,
    MAX(is_holiday)                      AS is_holiday,
    MAX(is_school_day)                   AS is_school_day,
    MAX(is_major_event)                  AS is_major_event,

    -- ── MTA disruption + zone equity ───────────────────────────────────────────
    ROUND(AVG(subway_disruption_idx), 4) AS subway_disruption_idx,
    ROUND(AVG(svi_score), 4)             AS svi_score,

    -- ── Demand metrics ─────────────────────────────────────────────────────────
    COUNT(CAD_INCIDENT_ID)               AS incident_count,
    AVG(INCIDENT_RESPONSE_SECONDS_QY)    AS avg_response_seconds,
    AVG(INCIDENT_TRAVEL_TM_SECONDS_QY)   AS avg_travel_seconds,
    AVG(DISPATCH_RESPONSE_SECONDS_QY)    AS avg_dispatch_seconds,
    SUM(is_high_acuity)                  AS high_acuity_count,
    SUM(is_held)                         AS held_count,
    MEDIAN(INCIDENT_RESPONSE_SECONDS_QY) AS median_response_seconds,

    -- ── Cyclical time features for XGBoost ─────────────────────────────────────
    SIN(2 * PI() * hour / 24)            AS hour_sin,
    COS(2 * PI() * hour / 24)            AS hour_cos,
    SIN(2 * PI() * dayofweek / 7)        AS dow_sin,
    COS(2 * PI() * dayofweek / 7)        AS dow_cos,
    SIN(2 * PI() * month / 12)           AS month_sin,
    COS(2 * PI() * month / 12)           AS month_cos

FROM incidents_cleaned
WHERE split IN ('train', 'test')
GROUP BY
    INCIDENT_DISPATCH_AREA, BOROUGH, year, month, dayofweek,
    hour, is_weekend, split
;
