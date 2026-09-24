-- ════════════════════════════════════════════════════════════════════════════
-- proc_sql_1  —  Stage ① Ingest & Clean
-- FirstWave | Datamorph DuckDB Pipeline: duckdb_pipeline_01_ingest
--
-- SQL RELATIONS (input):  ems_raw_csv      (CSV Source: NYC EMS 76xm-jjuj)
-- DOWNSTREAM:             proc_quality_1 -> incidents_cleaned (Parquet Sink)
--
-- Mirrors: pipeline/01_ingest_clean.py
-- 28.7M raw rows -> ~7.1M clean rows, with time features + train/test/exclude split.
-- DuckDB dayofweek(): 0=Sun..6=Sat ; (dow + 6) % 7 rebases to 0=Mon..6=Sun.
-- ════════════════════════════════════════════════════════════════════════════

SELECT
    INCIDENT_DATETIME                                       AS incident_dt,
    CAD_INCIDENT_ID,
    INCIDENT_DISPATCH_AREA,
    BOROUGH,
    INCIDENT_RESPONSE_SECONDS_QY::DOUBLE                    AS INCIDENT_RESPONSE_SECONDS_QY,
    INCIDENT_TRAVEL_TM_SECONDS_QY::DOUBLE                   AS INCIDENT_TRAVEL_TM_SECONDS_QY,
    DISPATCH_RESPONSE_SECONDS_QY::DOUBLE                    AS DISPATCH_RESPONSE_SECONDS_QY,
    FINAL_SEVERITY_LEVEL_CODE::INTEGER                      AS FINAL_SEVERITY_LEVEL_CODE,
    HELD_INDICATOR,

    -- ── time features ──────────────────────────────────────────────────────────
    EXTRACT(year  FROM INCIDENT_DATETIME)::INTEGER          AS year,
    EXTRACT(month FROM INCIDENT_DATETIME)::INTEGER          AS month,
    (EXTRACT(dow  FROM INCIDENT_DATETIME)::INTEGER + 6) % 7 AS dayofweek,
    EXTRACT(hour  FROM INCIDENT_DATETIME)::INTEGER          AS hour,
    date_trunc('hour', INCIDENT_DATETIME)                  AS date_hour,
    CAST(INCIDENT_DATETIME AS DATE)                        AS incident_date,

    -- ── derived flags ──────────────────────────────────────────────────────────
    CASE WHEN (EXTRACT(dow FROM INCIDENT_DATETIME)::INTEGER + 6) % 7 IN (5, 6)
         THEN 1 ELSE 0 END                                  AS is_weekend,
    CASE WHEN FINAL_SEVERITY_LEVEL_CODE::INTEGER IN (1, 2)
         THEN 1 ELSE 0 END                                  AS is_high_acuity,
    CASE WHEN HELD_INDICATOR = 'Y' THEN 1 ELSE 0 END        AS is_held,
    CASE WHEN EXTRACT(year FROM INCIDENT_DATETIME) = 2020
         THEN 1 ELSE 0 END                                  AS is_covid_year,

    -- ── train / test / exclude split ───────────────────────────────────────────
    CASE
        WHEN EXTRACT(year FROM INCIDENT_DATETIME) = 2023 THEN 'test'
        WHEN EXTRACT(year FROM INCIDENT_DATETIME) = 2020 THEN 'exclude'
        WHEN EXTRACT(year FROM INCIDENT_DATETIME) BETWEEN 2019 AND 2022 THEN 'train'
        ELSE 'exclude'
    END                                                     AS split

FROM ems_raw_csv
WHERE
    -- ── quality flags ──────────────────────────────────────────────────────────
    VALID_INCIDENT_RSPNS_TIME_INDC = 'Y'
    AND VALID_DISPATCH_RSPNS_TIME_INDC = 'Y'
    AND REOPEN_INDICATOR   = 'N'
    AND TRANSFER_INDICATOR = 'N'
    AND STANDBY_INDICATOR  = 'N'
    -- ── response-time range ────────────────────────────────────────────────────
    AND TRY_CAST(INCIDENT_RESPONSE_SECONDS_QY AS DOUBLE) BETWEEN 1 AND 7200
    -- ── valid borough ──────────────────────────────────────────────────────────
    AND BOROUGH IS NOT NULL
    AND BOROUGH != 'UNKNOWN'
    -- ── valid dispatch zone (31 clean zones) ───────────────────────────────────
    AND INCIDENT_DISPATCH_AREA IN (
        'B1','B2','B3','B4','B5',
        'K1','K2','K3','K4','K5','K6','K7',
        'M1','M2','M3','M4','M5','M6','M7','M8','M9',
        'Q1','Q2','Q3','Q4','Q5','Q6','Q7',
        'S1','S2','S3'
    )
    -- ── zone-borough prefix must match ─────────────────────────────────────────
    AND (
           (BOROUGH = 'BRONX'       AND INCIDENT_DISPATCH_AREA LIKE 'B%')
        OR (BOROUGH = 'BROOKLYN'    AND INCIDENT_DISPATCH_AREA LIKE 'K%')
        OR (BOROUGH = 'MANHATTAN'   AND INCIDENT_DISPATCH_AREA LIKE 'M%')
        OR (BOROUGH = 'QUEENS'      AND INCIDENT_DISPATCH_AREA LIKE 'Q%')
        OR (BOROUGH LIKE '%STATEN%' AND INCIDENT_DISPATCH_AREA LIKE 'S%')
    )
    -- ── datetime must parse ────────────────────────────────────────────────────
    AND INCIDENT_DATETIME IS NOT NULL
;
