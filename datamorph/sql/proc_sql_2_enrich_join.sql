-- ════════════════════════════════════════════════════════════════════════════
-- proc_sql_2  —  Stage ② Weather + Feature Enrichment (single join pass)
-- FirstWave | Datamorph DuckDB Pipeline: weather_enrich
--
-- SQL RELATIONS (input):
--   incidents_cleaned   (Parquet Source, from Stage ①)
--   weather             (Parquet Source, _weather_tmp from fetch_lookups.py)
--   holidays            (Parquet Source, _holidays_tmp)
--   school              (Parquet Source, _school_tmp)
--   events              (Parquet Source, _events_tmp)
--   mta                 (Parquet Source, _mta_tmp)
-- DOWNSTREAM:           proc_quality_2 -> incidents_cleaned (Parquet Sink, overwrite)
--
-- Mirrors: pipeline/02_weather_merge.py  (SECTION 6)
-- Adds 11 feature columns. COALESCE defaults match the original exactly.
-- ════════════════════════════════════════════════════════════════════════════

SELECT
    inc.*,

    -- ── Weather (Open-Meteo, joined on exact hour) ─────────────────────────────
    COALESCE(w.temperature_2m,      15.0) AS temperature_2m,
    COALESCE(w.precipitation,        0.0) AS precipitation,
    COALESCE(w.windspeed_10m,       10.0) AS windspeed_10m,
    COALESCE(w.weathercode,            0) AS weathercode,
    COALESCE(w.is_severe_weather,      0) AS is_severe_weather,
    COALESCE(w.is_extreme_heat,        0) AS is_extreme_heat,
    COALESCE(w.is_heat_emergency,      0) AS is_heat_emergency,

    -- ── Calendar flags ─────────────────────────────────────────────────────────
    COALESCE(h.is_holiday,             0) AS is_holiday,
    COALESCE(sc.is_school_day,         0) AS is_school_day,
    COALESCE(ev.is_major_event,        0) AS is_major_event,

    -- ── MTA monthly disruption index (0=calm, 1=peak; 0.5 = unknown) ───────────
    COALESCE(mta.subway_disruption_idx, 0.5) AS subway_disruption_idx

FROM incidents_cleaned AS inc

-- Weather: exact hour
LEFT JOIN weather AS w
    ON inc.date_hour = w.date_hour

-- Holidays: calendar date
LEFT JOIN holidays AS h
    ON CAST(inc.date_hour AS DATE) = h.holiday_date

-- School days: calendar date
LEFT JOIN school AS sc
    ON CAST(inc.date_hour AS DATE) = sc.school_date

-- Special events: (calendar date, zone borough prefix = first char of zone code)
LEFT JOIN events AS ev
    ON CAST(inc.date_hour AS DATE) = ev.event_date
   AND LEFT(inc.INCIDENT_DISPATCH_AREA, 1) = ev.zone_prefix

-- MTA: (year, month)
LEFT JOIN mta AS mta
    ON YEAR(inc.date_hour)  = mta.year
   AND MONTH(inc.date_hour) = mta.month_num
;
