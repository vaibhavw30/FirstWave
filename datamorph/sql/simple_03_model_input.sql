-- ════════════════════════════════════════════════════════════════════════════
-- simple_03_model_input  —  SIMPLIFIED FirstWave, Step 3 (proc_sql_model_input)
-- Datamorph DuckDB Pipeline: simple_ems_weather
--
-- SQL RELATIONS (input):
--   proc_sql_clean   (cleaned 2023 incidents, from simple_01)
--   weather          (hourly NYC weather 2023)
-- DOWNSTREAM:         incidents_model_input (Parquet Sink) -> Python XGBoost
--
-- Builds the model training table the XGBoost step consumes.
-- Grain = one row per (zone, hour, dayofweek, calendar date) with that hour's
-- weather, plus zone_baseline_avg (the strong per-zone demand prior — the single
-- most important feature, same idea as the full pipeline's zone_baselines).
-- ════════════════════════════════════════════════════════════════════════════

WITH daily AS (
    SELECT
        c.zone,
        c.hour,
        (EXTRACT(dow FROM c.date_hour)::INTEGER + 6) % 7 AS dayofweek,   -- 0=Mon..6=Sun
        EXTRACT(month FROM c.date_hour)::INTEGER         AS month,
        CAST(c.date_hour AS DATE)                        AS incident_date,
        COUNT(*)                                         AS incident_count,
        AVG(w.temperature_2m)                            AS temperature_2m,
        AVG(w.precipitation)                             AS precipitation,
        MAX(CASE WHEN w.weathercode IN
                 (51,53,55,61,63,65,71,73,75,77,80,81,82,85,86,95,96,99)
                 THEN 1 ELSE 0 END)                      AS is_severe_weather
    FROM proc_sql_clean AS c
    LEFT JOIN weather AS w
        ON c.date_hour = w.date_hour
    GROUP BY c.zone, c.hour, dayofweek, month, incident_date
),
baseline AS (
    -- typical demand for this (zone, hour, dayofweek) across the year
    SELECT zone, hour, dayofweek,
           AVG(incident_count) AS zone_baseline_avg
    FROM daily
    GROUP BY zone, hour, dayofweek
)
SELECT
    d.zone,
    d.hour,
    d.dayofweek,
    d.month,
    d.incident_date,
    d.incident_count,                                    -- ← target
    d.temperature_2m,
    d.precipitation,
    d.is_severe_weather,
    b.zone_baseline_avg,
    CASE WHEN d.dayofweek IN (5, 6) THEN 1 ELSE 0 END    AS is_weekend
FROM daily AS d
JOIN baseline AS b
    USING (zone, hour, dayofweek)
;
