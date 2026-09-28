-- ════════════════════════════════════════════════════════════════════════════
-- proc_sql_4c  —  Stage ④ Zone Stats  (per-zone historical averages)
-- FirstWave | Datamorph DuckDB Pipeline: duckdb_pipeline_04_aggregate
--
-- SQL RELATIONS (input):  incidents_cleaned  (Parquet Source, from Stage ③)
-- DOWNSTREAM:             zone_stats (Parquet Sink -> backend/artifacts/)
--                         Feeds /api/historical, /api/breakdown, and model features
--                         high_acuity_ratio + held_ratio.
--
-- Mirrors: pipeline/04_aggregate.py  (Step 3)
-- TRAIN split only. Expect exactly 31 rows. Bronx avg_response_seconds ~ 638.
-- ════════════════════════════════════════════════════════════════════════════

SELECT
    INCIDENT_DISPATCH_AREA,
    BOROUGH,
    AVG(svi_score)                     AS svi_score,
    AVG(INCIDENT_RESPONSE_SECONDS_QY)  AS avg_response_seconds,
    AVG(INCIDENT_TRAVEL_TM_SECONDS_QY) AS avg_travel_seconds,
    AVG(DISPATCH_RESPONSE_SECONDS_QY)  AS avg_dispatch_seconds,
    AVG(is_high_acuity)                AS high_acuity_ratio,
    AVG(is_held)                       AS held_ratio,
    COUNT(CAD_INCIDENT_ID)             AS total_incidents
FROM incidents_cleaned
WHERE split = 'train'
GROUP BY INCIDENT_DISPATCH_AREA, BOROUGH
;
