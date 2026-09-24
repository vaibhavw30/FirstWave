-- ════════════════════════════════════════════════════════════════════════════
-- simple_01_clean_incidents  —  SIMPLIFIED FirstWave, Step 1 (proc_sql_clean)
-- Datamorph DuckDB Pipeline: simple_ems_weather
--
-- SQL RELATIONS (input):  incidents_csv   (CSV Source: NYC EMS 76xm-jjuj)
-- DOWNSTREAM:             proc_sql_join_agg
--
-- Minimal clean: keep only what a weather-vs-demand question needs.
-- Filtered to 2023 so the build runs fast on the holdout year (~1.5M rows).
-- ════════════════════════════════════════════════════════════════════════════

SELECT
    CAD_INCIDENT_ID,
    INCIDENT_DISPATCH_AREA                       AS zone,
    BOROUGH                                      AS borough,
    INCIDENT_RESPONSE_SECONDS_QY::DOUBLE         AS response_seconds,
    date_trunc('hour', INCIDENT_DATETIME)        AS date_hour,
    EXTRACT(hour FROM INCIDENT_DATETIME)::INTEGER AS hour
FROM incidents_csv
WHERE
    VALID_INCIDENT_RSPNS_TIME_INDC = 'Y'
    AND BOROUGH IS NOT NULL
    AND BOROUGH != 'UNKNOWN'
    AND TRY_CAST(INCIDENT_RESPONSE_SECONDS_QY AS DOUBLE) BETWEEN 1 AND 7200
    AND EXTRACT(year FROM INCIDENT_DATETIME) = 2023
    AND INCIDENT_DATETIME IS NOT NULL
;
