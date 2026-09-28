-- ════════════════════════════════════════════════════════════════════════════
-- proc_sql_3  —  Stage ③ SVI Spatial Join
-- FirstWave | Datamorph DuckDB Pipeline: duckdb_pipeline_03_svi
--
-- SQL RELATIONS (input):
--   incidents_cleaned   (Parquet Source, from Stage ②)
--   zone_svi_lookup     (JSON Source, seeds/zone_svi_lookup.json — 31 rows)
-- DOWNSTREAM:           proc_quality_3 -> incidents_cleaned (Parquet Sink, overwrite)
--
-- Mirrors: pipeline/03_spatial_join.py
-- Attaches CDC SVI RPL_THEMES (0-1, higher = more vulnerable) per dispatch zone.
-- COALESCE 0.5 guards against any unexpected zone code.
-- ════════════════════════════════════════════════════════════════════════════

SELECT
    inc.*,
    COALESCE(s.svi_score, 0.5) AS svi_score
FROM incidents_cleaned AS inc
LEFT JOIN zone_svi_lookup AS s
    USING (INCIDENT_DISPATCH_AREA)
;

-- ── Alternative: inline the SVI table as a VALUES CTE (no JSON Source needed) ──
-- WITH zone_svi_lookup(INCIDENT_DISPATCH_AREA, svi_score) AS (
--     VALUES
--       ('B1',0.94),('B2',0.89),('B3',0.87),('B4',0.72),('B5',0.68),
--       ('K1',0.52),('K2',0.58),('K3',0.82),('K4',0.84),('K5',0.79),('K6',0.60),('K7',0.45),
--       ('M1',0.31),('M2',0.18),('M3',0.15),('M4',0.20),('M5',0.12),
--       ('M6',0.14),('M7',0.73),('M8',0.65),('M9',0.61),
--       ('Q1',0.71),('Q2',0.44),('Q3',0.38),('Q4',0.55),('Q5',0.67),('Q6',0.48),('Q7',0.41),
--       ('S1',0.38),('S2',0.32),('S3',0.28)
-- )
-- SELECT inc.*, COALESCE(s.svi_score, 0.5) AS svi_score
-- FROM incidents_cleaned inc
-- LEFT JOIN zone_svi_lookup s USING (INCIDENT_DISPATCH_AREA);
