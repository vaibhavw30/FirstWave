-- ════════════════════════════════════════════════════════════════════════════
-- proc_sql_4b  —  Stage ④ Zone Baselines  (the #1 XGBoost feature)
-- FirstWave | Datamorph DuckDB Pipeline: duckdb_pipeline_04_aggregate
--
-- SQL RELATIONS (input):  incidents_cleaned  (Parquet Source, from Stage ③)
-- DOWNSTREAM:             zone_baselines (Parquet Sink -> backend/artifacts/)
--
-- Mirrors: pipeline/04_aggregate.py  (Step 2)
-- "On a typical Monday at 8PM, how many incidents does B2 see?"
-- = avg of per-DAY counts for each (zone, hour, dayofweek), TRAIN split only.
-- Max possible rows = 31 zones x 24 hours x 7 days = 5208.
-- ════════════════════════════════════════════════════════════════════════════

SELECT
    INCIDENT_DISPATCH_AREA,
    hour,
    dayofweek,
    AVG(daily_count) AS zone_baseline_avg
FROM (
    SELECT
        INCIDENT_DISPATCH_AREA,
        hour,
        dayofweek,
        incident_date,
        COUNT(CAD_INCIDENT_ID) AS daily_count
    FROM incidents_cleaned
    WHERE split = 'train'
    GROUP BY INCIDENT_DISPATCH_AREA, hour, dayofweek, incident_date
) AS daily
GROUP BY INCIDENT_DISPATCH_AREA, hour, dayofweek
;
