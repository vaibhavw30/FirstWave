# FirstWave on Datamorph.ai — Rebuild Kit

Everything needed to reconstruct the FirstWave EMS staging pipeline as a
**datamorph.ai** workflow (`test_predictive_ems_staging`) on `app-v2.datamorph.ai`.

Companion design doc (diagrams + node-by-node walkthrough):
[`../DATAMORPH_PIPELINE_SIMULATION.md`](../DATAMORPH_PIPELINE_SIMULATION.md)

---

## Folder layout

```
datamorph/
├── README.md                         ← you are here (build guide)
├── constants.py                      ← shared zone tables (centroids, SVI, feature order)
├── sql/                              ← paste-ready SQL processor bodies
│   ├── proc_sql_1_ingest_clean.sql       Stage ① clean + split
│   ├── proc_sql_2_enrich_join.sql        Stage ② 5-way feature join
│   ├── proc_sql_3_svi_join.sql           Stage ③ SVI lookup join
│   ├── proc_sql_4a_aggregate.sql         Stage ④ hourly zone aggregate
│   ├── proc_sql_4b_zone_baselines.sql    Stage ④ zone_baselines artifact
│   └── proc_sql_4c_zone_stats.sql        Stage ④ zone_stats artifact
├── python/                           ← datamorph "Python" action scripts
│   ├── fetch_lookups.py                  Stage ② prep: weather/holiday/school/events/MTA
│   ├── train_demand_model.py             Stage ⑤ XGBoost
│   ├── osmnx_drive_matrix.py             Stage ⑥ OSMnx drive-time matrix (parallel)
│   ├── staging_optimizer_validate.py     Stage ⑦ KMeans gate
│   └── counterfactual_precompute.py      Stage ⑧ before/after simulation
├── seeds/
│   └── zone_svi_lookup.json              31-row CDC SVI seed (JSON Source for Stage ③)
├── quality/
│   └── quality_checks.yaml               Quality Check node rules per stage
└── workflow/
    └── test_predictive_ems_staging.json  full workflow manifest (tasks, nodes, edges, relations)
```

---

## Datamorph node mapping (recap)

| Stage | Task name | Datamorph task | Key nodes |
|-------|-----------|----------------|-----------|
| ① | `duckdb_pipeline_01_ingest` | DuckDB Pipeline | CSV → `proc_sql_1` → Quality → Parquet |
| ② | `fetch_lookups` + `weather_enrich` | Python + DuckDB Pipeline | 6 Parquet → `proc_sql_2` → Quality → Parquet |
| ③ | `duckdb_pipeline_03_svi` | DuckDB Pipeline | Parquet+JSON → `proc_sql_3` → Quality → Parquet |
| ④ | `duckdb_pipeline_04_aggregate` | DuckDB Pipeline | Parquet → `proc_sql_4a/4b/4c` → 3 Sinks |
| ⑤ | `train_demand_model` | Python | → `demand_model.pkl` |
| ⑥ | `osmnx_drive_matrix` | Python (parallel) | → `drive_time_matrix.pkl` |
| ⑦ | `staging_optimizer_validate` | Python + Branch | gate only |
| ⑧ | `counterfactual_precompute` | Python | → `counterfactual_*.parquet` |

---

## Build order on datamorph

1. **Create workflow** `test_predictive_ems_staging` (dev project).
2. **Seed the SVI source** — upload `seeds/zone_svi_lookup.json` as a JSON Source (or `Import` the manifest).
3. **Stage ① pipeline** — add a *DuckDB Pipeline* task `duckdb_pipeline_01_ingest`:
   - `Source ▾ → CSV` named `ems_raw_csv`, path = the NYC Open Data URL (see below).
   - `Processor ▾ → SQL` named `proc_sql_1`; paste `sql/proc_sql_1_ingest_clean.sql`; set **SQL Relations** = `ems_raw_csv`.
   - `Processor ▾ → Quality Check` named `proc_quality_1` (rules from `quality/quality_checks.yaml`).
   - `Sink ▾ → Parquet` named `incidents_cleaned`.
4. **Stage ②** — add `fetch_lookups` (Python action, paste `python/fetch_lookups.py`), then a DuckDB Pipeline `weather_enrich`:
   - 6 Parquet Sources: `incidents_cleaned, weather, holidays, school, events, mta`.
   - `proc_sql_2` (paste `sql/proc_sql_2_enrich_join.sql`), Relations = all six.
   - `proc_quality_2` + Parquet sink (overwrite `incidents_cleaned`).
5. **Stage ③** — DuckDB Pipeline `duckdb_pipeline_03_svi`: Parquet `incidents_cleaned` + JSON `zone_svi_lookup` → `proc_sql_3` → Quality → sink.
6. **Stage ④** — DuckDB Pipeline `duckdb_pipeline_04_aggregate`: one Parquet source fans into `proc_sql_4a/4b/4c` → three Parquet sinks (`incidents_aggregated`, `zone_baselines`, `zone_stats`).
7. **Stage ⑤** — Python action `train_demand_model` (paste `python/train_demand_model.py`).
8. **Stage ⑥** — Python action `osmnx_drive_matrix` (paste `python/osmnx_drive_matrix.py`), wired **parallel** (no upstream dep).
9. **Stage ⑦** — Python action `staging_optimizer_validate` + a `Control → Branch` on its exit code.
10. **Stage ⑧** — Python action `counterfactual_precompute`.
11. **Notify** — `Notifications → Slack` with the counterfactual summary.
12. `Validate` → `Save` → `Run`.

---

## Source paths to configure

| Datamorph Source | Type | Path / URL |
|------------------|------|-----------|
| `ems_raw_csv` | CSV | `https://data.cityofnewyork.us/api/views/76xm-jjuj/rows.csv?accessType=DOWNLOAD` |
| `incidents_cleaned` | Parquet | `pipeline/data/incidents_cleaned.parquet` |
| `zone_svi_lookup` | JSON | `datamorph/seeds/zone_svi_lookup.json` |
| `ems_stations` | JSON | `data/ems_stations.json` |
| `incidents_aggregated` | Parquet | `pipeline/data/incidents_aggregated.parquet` |
| `zone_baselines` | Parquet | `backend/artifacts/zone_baselines.parquet` |
| `zone_stats` | Parquet | `backend/artifacts/zone_stats.parquet` |
| `demand_model` | Pickle | `backend/artifacts/demand_model.pkl` |
| `drive_time_matrix` | Pickle | `backend/artifacts/drive_time_matrix.pkl` |

---

## Notes

- The SQL files use ANSI/DuckDB syntax (`PI()`, `MEDIAN()`, `TRY_CAST`, `LEFT()`), which the
  DuckDB Pipeline executes directly. They reference **relation names**, not file paths —
  datamorph binds each relation to its Source/Processor node.
- The Python actions are self-contained (zone tables inlined, matching the original
  `pipeline/*.py` style) so they run in datamorph's sandbox without local imports.
- `constants.py` is provided for reference / DRY reuse if your datamorph project supports
  shared modules; the Python actions do **not** require it.
- Every SQL filter, the 21-feature order, and all thresholds are copied verbatim from
  `pipeline/01..08_*.py` so the rebuild stays byte-faithful.
