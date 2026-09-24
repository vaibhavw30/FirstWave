-- ════════════════════════════════════════════════════════════════════════════
-- simple_02_join_weather_agg  —  SIMPLIFIED FirstWave, Step 2 (proc_sql_join_agg)
-- Datamorph DuckDB Pipeline: simple_ems_weather
--
-- SQL RELATIONS (input):
--   proc_sql_clean   (output of simple_01_clean_incidents.sql — aka clean_incidents)
--   weather          (Parquet/CSV Source: hourly NYC weather 2023)
-- DOWNSTREAM:         incident_weather_summary (Parquet Sink)
--
-- Answers: "Do wet hours have more EMS calls / slower responses than dry hours?"
-- Joins weather on the exact hour, buckets into wet/dry, aggregates by
-- borough x hour-of-day x weather bucket.
-- ════════════════════════════════════════════════════════════════════════════

SELECT
    c.borough,
    c.hour,
    CASE WHEN w.precipitation > 0 THEN 'wet' ELSE 'dry' END AS weather_bucket,

    COUNT(*)                              AS incident_count,
    ROUND(AVG(c.response_seconds), 1)     AS avg_response_sec,
    ROUND(AVG(w.temperature_2m), 1)       AS avg_temp_c,
    ROUND(AVG(w.precipitation), 2)        AS avg_precip_mm
FROM proc_sql_clean AS c
LEFT JOIN weather AS w
    ON c.date_hour = w.date_hour
GROUP BY c.borough, c.hour, weather_bucket
ORDER BY c.borough, c.hour, weather_bucket
;
