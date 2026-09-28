# Lag Features + 2022–2026 Retrain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Retrain FirstWave's demand model at true (zone, date, hour) grain with seven past-only lag features on 2022–2026 data, and serve it through a replay-by-date API that returns predicted and actual counts.

**Architecture:** Testable logic moves out of the numbered pipeline scripts into small importable modules (`pipeline/fw_*.py`, `backend/models/lag_features.py`, `backend/models/replay.py`). The pipeline builds a gap-free zone × hour grid in DuckDB, computes lags with window functions, and trains XGBoost. The backend recomputes the same lags from a `hourly_counts` artifact. A parity test pins training and serving to identical lag values. Scripts 07 and 08 call the backend forecaster, so there is one inference-row builder.

**Tech Stack:** Python 3.14, DuckDB, pandas 3.0.1, XGBoost 3.2.0, scikit-learn 1.8.0, FastAPI 0.129 + TestClient, pytest; React 19 + Vitest + Testing Library.

**Spec:** `docs/superpowers/specs/2026-09-28-lag-features-design.md`

## Global Constraints

- Data window: 2021-12-01 → 2026-06-30. Splits: `history` Dec 2021, `train` 2022-01-01→2024-09-30, `valid` 2024-10-01→2024-12-31, `test` 2025, `test_recent` 2026-01-01→2026-06-30, `exclude` otherwise.
- Demand label counts every incident passing zone/borough/reopen/transfer/standby filters — **no response-time validity filter**. `is_valid_response` is a column used only by `zone_stats` and script 08.
- Lags (exact names, exact order): `lag_1h, lag_2h, lag_3h, lag_24h, lag_168h, roll_7d_same_hour (mean of t−24h…t−168h step 24, 7 values), roll_4w_same_hour_dow (mean of t−168h, t−336h, t−504h, t−672h)`.
- `FEATURE_COLS` = the existing 21 in existing order + the 7 lags appended (28).
- Early stopping on `valid` only. `test` and `test_recent` scored once.
- Deployment gate: new model replaces `backend/artifacts/demand_model.pkl` only if 2025 RMSE improves on the same-grain no-lag model by ≥ 2%.
- API is additive only: optional `date` param (2025-01-01 → 2026-06-30) on `/api/heatmap` and `/api/staging`; `query_params.date` and per-feature `actual_count` added; nothing renamed. Never crash — mock fallback with `X-Data-Source: mock`.
- Stand-in date when `date` is omitted: lower-median 2025 date with the requested month and dow.
- Demo presets: `friday_peak` 2025-10-10 20:00, `monday_quiet` 2025-10-20 04:00, `storm` 2025-07-30 18:00 (see Deviations).
- `data/mock_api_responses.json` is not modified. `CLAUDE.md` is appended to, never deleted from.
- Pickle compatibility: the pipeline venv pins xgboost 3.2.0 / scikit-learn 1.8.0 / pandas 3.0.1 / numpy 2.4.2 / joblib 1.5.3 / pyarrow 23.0.1 — identical to `backend/.venv`.
- Every commit message ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Deviations from the spec (decided while planning)

1. **Storm preset:** the spec's rule ("Wednesday in Nov 2025 with the highest 18:00 precipitation") yields no rain — all four Wednesdays read 0.0 mm. Using the rainiest 2025 Wednesday 18:00 instead: **2025-07-30 18:00, 8.2 mm/h, WMO 65**.
2. **School calendars:** all five years (2021-22 → 2025-26) were checked against the official NYC DOE PDFs; the old hardcoded 2021-22, 2022-23 and 2023-24 lists had wrong and missing dates (e.g. 2023-24 spring recess was Apr 22–30, not Mar 29–Apr 5). All five are rewritten from the PDFs, not carried over.
3. **`build_lag_features` signature:** vectorized over zones — `build_lag_features(counts_wide, target) -> DataFrame` (index = zone) instead of one call per zone.
4. **Script 02 no longer rewrites `incidents_cleaned.parquet`.** Nothing downstream reads incident-level weather/calendar any more (04 joins the lookup tables to the grid), so 02 only writes `weather_hourly.parquet` and `calendar_daily.parquet`.
5. **Rosh Hashanah / Yom Kippur holiday flags** use the holiday days themselves (old list mixed eves and days).

## Review Focus

1. **DST hours in replay** (2025-03-09 02:00 spring-forward, 2025-11-02 01:00 fall-back): a request for those hours must return lags and a prediction, not a KeyError. Pinned in Task 4 (`test_dst_hours_have_lags`).
2. **Replay range edges** (2025-01-01 00:00, whose 4-week lag reaches 2024-12-04; and 2026-06-30 23:00): both must serve 200 with lags. Pinned in Task 4 (`test_first_replay_hour_reaches_into_december`) and Task 11 (`test_last_replay_hour_serves`).
3. **`date` sent with a contradicting `dow`/`month`**: the date wins and the response echoes the derived dow/month. Pinned in Task 11 (`test_date_overrides_dow_and_month`).
4. **`POST /reload` after artifacts change**: the staging LRU cache must be cleared so old-model staging isn't served. Pinned in Task 11 (`test_reload_clears_staging_cache`).
5. **Rollback to the old 21-feature pickle** with the new artifacts present: heatmap still serves model output with `actual_count`. Pinned in Task 11 (`test_old_21_feature_model_still_serves`).

---

## File Structure

**Pipeline (new modules)**
- `pipeline/fw_config.py` — zones, data window, split boundaries + SQL CASE, feature lists.
- `pipeline/fw_calendar.py` — federal/NYC holidays, DOE school calendars, `build_calendar_daily`.
- `pipeline/fw_grid.py` — DuckDB counts table, gap-free grid, lag columns.
- `pipeline/fw_ingest.py` — raw-CSV column checks and ID-column resolution.
- `pipeline/fw_eval.py` — metrics, per-group RMSE, deployment gate.
- `pipeline/requirements-dev.txt` — pinned venv for pipeline + tests.
- `pipeline/tests/` — `conftest.py`, `synth.py`, unit tests, script smoke tests, lag parity test.

**Pipeline (modified scripts)**
- `01_ingest_clean.py` — rewrite: new window, no validity filter, `is_valid_response`, split, robust datetime parse.
- `02_weather_merge.py` — rewrite: writes `weather_hourly.parquet` + `calendar_daily.parquet` only.
- `04_aggregate.py` — rewrite: grid, lags, enrichment joins, five outputs, parity check.
- `05_train_demand_model.py` — rewrite: two objectives, no-lag reference, metrics, gate.
- `07_staging_optimizer.py`, `08_counterfactual_precompute.py`, `test_artifacts.py` — use backend forecaster and new artifacts.
- `03_spatial_join.py` — unchanged.

**Backend**
- `backend/models/lag_features.py` (new) — `LAG_FEATURES`, `to_wide`, `build_lag_features`, `actual_counts`.
- `backend/models/replay.py` (new) — replay range, stand-in date, request resolution, calendar lookup.
- `backend/models/demand_forecaster.py` — model-driven feature list, lag + calendar integration.
- `backend/main.py` — load new artifacts, generic dummy predict, status helper, cache clear on reload.
- `backend/routers/heatmap.py`, `backend/routers/staging.py` — `date` param, `actual_count`.
- `backend/requirements-dev.txt`, `backend/tests/` (new).

**Frontend**
- `src/utils/replayDate.js`, `src/utils/queryParams.js` (new), `src/components/Controls/DatePicker.jsx` (new).
- `src/constants.js`, `src/App.jsx`, `src/components/Controls/ControlPanel.jsx`, `src/components/Map/ZoneTooltip.jsx`, `src/components/Map/ZoneDetailPanel.jsx`.
- Delete `src/components/Controls/DayPicker.jsx` and its test.

**Baseline test state (before any change):** frontend `npx vitest run` → 13 failing / 158 passing, failures in `App.test.jsx` (4), `CoverageBars.test.jsx` (2), `ImpactPanel.test.jsx` (1), `MapContainer.test.jsx` (3), `StagingPins.test.jsx` (3). These are pre-existing; do not fix them in this plan, and do not add to them. Backend and pipeline have no tests yet.

---

### Task 1: Pipeline test harness and `fw_config`

**Files:**
- Create: `pipeline/requirements-dev.txt`
- Create: `pipeline/fw_config.py`
- Create: `pipeline/tests/conftest.py`
- Test: `pipeline/tests/test_fw_config.py`

**Interfaces:**
- Produces: `VALID_ZONES: list[str]`, `ZONE_PREFIX_BOROUGH: dict[str,str]`, `DATA_START`, `DATA_END`, `HOURLY_COUNTS_START`, `REPLAY_START`, `REPLAY_END` (all `datetime.date`), `SPLIT_STARTS: list[tuple[str, date]]`, `split_case_sql(ts_col: str) -> str`, `BASE_FEATURE_COLS` (21), `LAG_FEATURE_COLS` (7), `FEATURE_COLS` (28).

- [ ] **Step 1: Create the pipeline venv**

`pipeline/requirements-dev.txt`:
```
# Pins match backend/.venv so the pickled model loads there unchanged.
duckdb>=1.1
pandas==3.0.1
numpy==2.4.2
xgboost==3.2.0
scikit-learn==1.8.0
joblib==1.5.3
pyarrow==23.0.1
requests>=2.31.0
pytest>=8.0
```

Run:
```bash
python3 -m venv pipeline/.venv
pipeline/.venv/bin/pip install -r pipeline/requirements-dev.txt
```
Expected: installs cleanly (`.venv/` is already gitignored). If `duckdb` has no wheel for Python 3.14, stop and report — do not downgrade other pins.

- [ ] **Step 2: Write `pipeline/tests/conftest.py`**

```python
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
for path in (REPO / "pipeline", REPO / "backend"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
```

- [ ] **Step 3: Write the failing test** — `pipeline/tests/test_fw_config.py`

```python
import duckdb
import pytest

from fw_config import (
    BASE_FEATURE_COLS, FEATURE_COLS, LAG_FEATURE_COLS, VALID_ZONES, split_case_sql,
)


@pytest.mark.parametrize("ts,expected", [
    ("2021-11-30 23:59:59", "exclude"),
    ("2021-12-01 00:00:00", "history"),
    ("2021-12-31 23:00:00", "history"),
    ("2022-01-01 00:00:00", "train"),
    ("2024-09-30 23:00:00", "train"),
    ("2024-10-01 00:00:00", "valid"),
    ("2024-12-31 23:00:00", "valid"),
    ("2025-01-01 00:00:00", "test"),
    ("2025-12-31 23:00:00", "test"),
    ("2026-01-01 00:00:00", "test_recent"),
    ("2026-06-30 23:00:00", "test_recent"),
    ("2026-07-01 00:00:00", "exclude"),
])
def test_split_case_sql(ts, expected):
    expr = split_case_sql("TIMESTAMP '" + ts + "'")
    assert duckdb.sql(f"SELECT {expr}").fetchone()[0] == expected


def test_feature_lists():
    assert len(BASE_FEATURE_COLS) == 21
    assert LAG_FEATURE_COLS == [
        "lag_1h", "lag_2h", "lag_3h", "lag_24h", "lag_168h",
        "roll_7d_same_hour", "roll_4w_same_hour_dow",
    ]
    assert FEATURE_COLS == BASE_FEATURE_COLS + LAG_FEATURE_COLS
    assert len(set(FEATURE_COLS)) == 28


def test_valid_zones():
    assert len(VALID_ZONES) == 31
    assert len(set(VALID_ZONES)) == 31
```

- [ ] **Step 4: Run test to verify it fails**

Run: `pipeline/.venv/bin/python -m pytest pipeline/tests/test_fw_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'fw_config'`

- [ ] **Step 5: Write `pipeline/fw_config.py`**

```python
"""
Shared constants for the FirstWave pipeline.

The numbered scripts run as `python pipeline/0N_*.py`, which puts pipeline/ on
sys.path, so they import this module directly. pipeline/tests does the same via
conftest.py.
"""
import datetime as dt

VALID_ZONES = [
    'B1', 'B2', 'B3', 'B4', 'B5',
    'K1', 'K2', 'K3', 'K4', 'K5', 'K6', 'K7',
    'M1', 'M2', 'M3', 'M4', 'M5', 'M6', 'M7', 'M8', 'M9',
    'Q1', 'Q2', 'Q3', 'Q4', 'Q5', 'Q6', 'Q7',
    'S1', 'S2', 'S3',
]

ZONE_PREFIX_BOROUGH = {
    'B': 'BRONX',
    'K': 'BROOKLYN',
    'M': 'MANHATTAN',
    'Q': 'QUEENS',
    'S': 'RICHMOND / STATEN ISLAND',
}

# ── Data window ────────────────────────────────────────────────────────────────
DATA_START = dt.date(2021, 12, 1)   # Dec 2021 is lag warm-up only
DATA_END = dt.date(2026, 6, 30)     # last day published as of 2026-09-28

HOURLY_COUNTS_START = dt.date(2024, 12, 1)  # 4+ weeks of history before REPLAY_START
REPLAY_START = dt.date(2025, 1, 1)
REPLAY_END = DATA_END

# (split, first day) in time order; each split runs until the next one starts.
SPLIT_STARTS = [
    ("history", dt.date(2021, 12, 1)),
    ("train", dt.date(2022, 1, 1)),
    ("valid", dt.date(2024, 10, 1)),
    ("test", dt.date(2025, 1, 1)),
    ("test_recent", dt.date(2026, 1, 1)),
]
SPLIT_END = DATA_END + dt.timedelta(days=1)   # exclusive


def split_case_sql(ts_col: str) -> str:
    """DuckDB CASE expression mapping a TIMESTAMP expression to its split name."""
    uppers = [start for _, start in SPLIT_STARTS[1:]] + [SPLIT_END]
    whens = [f"WHEN {ts_col} < TIMESTAMP '{SPLIT_STARTS[0][1]} 00:00:00' THEN 'exclude'"]
    for (name, _), upper in zip(SPLIT_STARTS, uppers):
        whens.append(f"WHEN {ts_col} < TIMESTAMP '{upper} 00:00:00' THEN '{name}'")
    return "CASE " + " ".join(whens) + " ELSE 'exclude' END"


# ── Model features ─────────────────────────────────────────────────────────────
# ORDER IS FROZEN. The first 21 match the previous model; lags are appended.
BASE_FEATURE_COLS = [
    "hour_sin", "hour_cos",
    "dow_sin", "dow_cos",
    "month_sin", "month_cos",
    "is_weekend",
    "temperature_2m",
    "precipitation",
    "windspeed_10m",
    "is_severe_weather",
    "svi_score",
    "zone_baseline_avg",
    "high_acuity_ratio",
    "held_ratio",
    "is_holiday",
    "is_major_event",
    "is_school_day",
    "is_heat_emergency",
    "is_extreme_heat",
    "subway_disruption_idx",
]

# Must equal backend/models/lag_features.py LAG_FEATURES (pinned by test_lag_parity.py).
LAG_FEATURE_COLS = [
    "lag_1h",
    "lag_2h",
    "lag_3h",
    "lag_24h",
    "lag_168h",
    "roll_7d_same_hour",
    "roll_4w_same_hour_dow",
]

FEATURE_COLS = BASE_FEATURE_COLS + LAG_FEATURE_COLS
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pipeline/.venv/bin/python -m pytest pipeline/tests/test_fw_config.py -v`
Expected: 14 passed

- [ ] **Step 7: Commit**

```bash
git add pipeline/requirements-dev.txt pipeline/fw_config.py pipeline/tests/conftest.py pipeline/tests/test_fw_config.py
git commit -m "feat(pipeline): shared config for 2022–2026 window, splits, 28 features

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Holiday and school calendars (`fw_calendar`)

**Files:**
- Create: `pipeline/fw_calendar.py`
- Test: `pipeline/tests/test_fw_calendar.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `is_holiday(d: date) -> int`, `is_school_day(d: date) -> int`, `build_calendar_daily(start: date, end: date, event_days: pd.DataFrame) -> pd.DataFrame` where `event_days` has columns `event_date` (date), `zone_prefix` (str) and the result has columns `date, zone_prefix, is_holiday, is_school_day, is_major_event` (one row per date × prefix in `B,K,M,Q,S`).

- [ ] **Step 1: Write the failing test** — `pipeline/tests/test_fw_calendar.py`

```python
import datetime as dt

import pandas as pd
import pytest

from fw_calendar import (
    ALL_HOLIDAYS, SCHOOL_CLOSURES, SCHOOL_SESSIONS,
    build_calendar_daily, is_holiday, is_school_day,
)

D = dt.date.fromisoformat


@pytest.mark.parametrize("day,expected", [
    ("2025-10-10", 1),  # ordinary Friday in session
    ("2025-10-20", 0),  # Diwali 2025
    ("2025-10-11", 0),  # Saturday
    ("2025-07-30", 0),  # summer
    ("2024-04-24", 0),  # 2023-24 spring recess (old list had this open)
    ("2024-04-03", 1),  # old list wrongly closed this day
    ("2024-06-17", 0),  # Eid al-Adha 2024
    ("2022-02-01", 0),  # Lunar New Year 2022
    ("2021-12-23", 1),  # old list wrongly closed this day
    ("2023-04-21", 0),  # Eid al-Fitr 2023
    ("2026-06-26", 1),  # last day of 2025-26
    ("2026-06-29", 0),  # after last day
    ("2025-09-04", 1),  # first day of 2025-26
])
def test_is_school_day(day, expected):
    assert is_school_day(D(day)) == expected


@pytest.mark.parametrize("day,expected", [
    ("2025-11-04", 1),  # Election Day 2025
    ("2026-06-19", 1),  # Juneteenth 2026
    ("2024-10-03", 1),  # Rosh Hashanah 2024
    ("2025-10-02", 1),  # Yom Kippur 2025
    ("2025-10-10", 0),
])
def test_is_holiday(day, expected):
    assert is_holiday(D(day)) == expected


def test_all_listed_dates_are_valid_iso():
    for s in ALL_HOLIDAYS | SCHOOL_CLOSURES:
        dt.date.fromisoformat(s)
    for start, end in SCHOOL_SESSIONS:
        assert dt.date.fromisoformat(start) < dt.date.fromisoformat(end)


def test_build_calendar_daily_shape_and_events():
    events = pd.DataFrame({
        "event_date": [D("2025-10-10")],
        "zone_prefix": ["K"],
    })
    cal = build_calendar_daily(D("2025-10-09"), D("2025-10-11"), events)
    assert list(cal.columns) == ["date", "zone_prefix", "is_holiday", "is_school_day", "is_major_event"]
    assert len(cal) == 3 * 5
    flagged = cal[cal["is_major_event"] == 1]
    assert flagged[["date", "zone_prefix"]].values.tolist() == [[D("2025-10-10"), "K"]]
    fri_b = cal[(cal["date"] == D("2025-10-10")) & (cal["zone_prefix"] == "B")].iloc[0]
    assert fri_b["is_school_day"] == 1 and fri_b["is_holiday"] == 0


def test_build_calendar_daily_empty_events():
    empty = pd.DataFrame(columns=["event_date", "zone_prefix"])
    cal = build_calendar_daily(D("2025-01-01"), D("2025-01-31"), empty)
    assert len(cal) == 31 * 5
    assert cal["is_major_event"].sum() == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pipeline/.venv/bin/python -m pytest pipeline/tests/test_fw_calendar.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'fw_calendar'`

- [ ] **Step 3: Write `pipeline/fw_calendar.py`**

```python
"""
Holiday and NYC public-school calendars, Dec 2021 → Jun 2026.

Sources (all checked 2026-09-28):
  Federal holidays: U.S. OPM federal holiday schedule (observed dates).
  School years: official NYC DOE school-year calendar PDFs, schools.nyc.gov/calendar
    2021-22 doe-calendar-sy-21-22.pdf
    2022-23 parent-facing-calendar-2022-23.pdf
    2023-24 school-year-2023-24-calendar-corrected.pdf
    2024-25 school-year-2024-25-calendar-updated.pdf
    2025-26 school-year-2025-26-calendar.pdf
  "Closed" = every day the PDF says schools are closed or students do not attend,
  including clerical days that apply to K-8. Professional-development days that
  only affect high schools are treated as school days.
"""
import datetime as dt

import pandas as pd

ZONE_PREFIXES = ["B", "K", "M", "Q", "S"]


def _days(start: str, end: str) -> list[str]:
    """Every ISO date from start to end inclusive."""
    s, e = dt.date.fromisoformat(start), dt.date.fromisoformat(end)
    return [(s + dt.timedelta(days=i)).isoformat() for i in range((e - s).days + 1)]


# ── Holidays ───────────────────────────────────────────────────────────────────
FEDERAL_HOLIDAYS = {
    "2021-12-24", "2021-12-31",
    "2022-01-17", "2022-02-21", "2022-05-30", "2022-06-20", "2022-07-04",
    "2022-09-05", "2022-10-10", "2022-11-11", "2022-11-24", "2022-12-26",
    "2023-01-02", "2023-01-16", "2023-02-20", "2023-05-29", "2023-06-19",
    "2023-07-04", "2023-09-04", "2023-10-09", "2023-11-10", "2023-11-23", "2023-12-25",
    "2024-01-01", "2024-01-15", "2024-02-19", "2024-05-27", "2024-06-19",
    "2024-07-04", "2024-09-02", "2024-10-14", "2024-11-11", "2024-11-28", "2024-12-25",
    "2025-01-01", "2025-01-20", "2025-02-17", "2025-05-26", "2025-06-19",
    "2025-07-04", "2025-09-01", "2025-10-13", "2025-11-11", "2025-11-27", "2025-12-25",
    "2026-01-01", "2026-01-19", "2026-02-16", "2026-05-25", "2026-06-19",
}

# NYC-observed days with large demand shifts: Election Day, Rosh Hashanah (both
# days), Yom Kippur.
NYC_EXTRA_HOLIDAYS = {
    "2022-11-08", "2023-11-07", "2024-11-05", "2025-11-04",   # Election Day
    "2022-09-26", "2022-09-27", "2023-09-16", "2023-09-17",   # Rosh Hashanah
    "2024-10-03", "2024-10-04", "2025-09-23", "2025-09-24",
    "2022-10-05", "2023-09-25", "2024-10-12", "2025-10-02",   # Yom Kippur
}

ALL_HOLIDAYS = FEDERAL_HOLIDAYS | NYC_EXTRA_HOLIDAYS


# ── School calendar ────────────────────────────────────────────────────────────
SCHOOL_SESSIONS = [
    ("2021-09-13", "2022-06-27"),
    ("2022-09-08", "2023-06-27"),
    ("2023-09-07", "2024-06-26"),
    ("2024-09-05", "2025-06-26"),
    ("2025-09-04", "2026-06-26"),
]

SCHOOL_CLOSURES = set(
    # ── 2021-22 ──
    ["2021-09-16", "2021-10-11", "2021-11-02", "2021-11-11", "2021-11-25", "2021-11-26"]
    + _days("2021-12-24", "2021-12-31")
    + ["2022-01-17", "2022-02-01"]
    + _days("2022-02-21", "2022-02-25")
    + _days("2022-04-15", "2022-04-22")
    + ["2022-05-02", "2022-05-30", "2022-06-07", "2022-06-09", "2022-06-20"]
    # ── 2022-23 ──
    + ["2022-09-26", "2022-09-27", "2022-10-05", "2022-10-10", "2022-11-08",
       "2022-11-11", "2022-11-24", "2022-11-25"]
    + _days("2022-12-26", "2023-01-02")
    + ["2023-01-16"]
    + _days("2023-02-20", "2023-02-24")
    + ["2023-04-06", "2023-04-07"]
    + _days("2023-04-10", "2023-04-14")
    + ["2023-04-21", "2023-05-29", "2023-06-08", "2023-06-09", "2023-06-19"]
    # ── 2023-24 ──
    + ["2023-09-25", "2023-10-09", "2023-11-07", "2023-11-23", "2023-11-24"]
    + _days("2023-12-25", "2024-01-01")
    + ["2024-01-15"]
    + _days("2024-02-19", "2024-02-23")
    + ["2024-03-29", "2024-04-01", "2024-04-10"]
    + _days("2024-04-22", "2024-04-30")
    + ["2024-05-27", "2024-06-06", "2024-06-07", "2024-06-17", "2024-06-19"]
    # ── 2024-25 ──
    + ["2024-10-03", "2024-10-04", "2024-10-14", "2024-11-01", "2024-11-05",
       "2024-11-11", "2024-11-28", "2024-11-29"]
    + _days("2024-12-23", "2025-01-01")
    + ["2025-01-20", "2025-01-29"]
    + _days("2025-02-17", "2025-02-21")
    + ["2025-03-31"]
    + _days("2025-04-14", "2025-04-18")
    + ["2025-05-26", "2025-06-05", "2025-06-06", "2025-06-19"]
    # ── 2025-26 ──
    + ["2025-09-23", "2025-09-24", "2025-10-02", "2025-10-13", "2025-10-20",
       "2025-11-04", "2025-11-11", "2025-11-27", "2025-11-28"]
    + _days("2025-12-24", "2026-01-02")
    + ["2026-01-19"]
    + _days("2026-02-16", "2026-02-20")
    + ["2026-03-20"]
    + _days("2026-04-02", "2026-04-10")
    + ["2026-05-25", "2026-05-27", "2026-06-04", "2026-06-05", "2026-06-19"]
)


def is_holiday(d: dt.date) -> int:
    return int(d.isoformat() in ALL_HOLIDAYS)


def is_school_day(d: dt.date) -> int:
    if d.weekday() >= 5 or d.isoformat() in SCHOOL_CLOSURES:
        return 0
    for start, end in SCHOOL_SESSIONS:
        if dt.date.fromisoformat(start) <= d <= dt.date.fromisoformat(end):
            return 1
    return 0


def build_calendar_daily(start: dt.date, end: dt.date, event_days: pd.DataFrame) -> pd.DataFrame:
    """One row per (date, zone prefix) with holiday, school-day and major-event flags."""
    events = {
        (pd.Timestamp(d).date(), p)
        for d, p in zip(event_days["event_date"], event_days["zone_prefix"])
    }
    rows = []
    for i in range((end - start).days + 1):
        d = start + dt.timedelta(days=i)
        hol, school = is_holiday(d), is_school_day(d)
        for prefix in ZONE_PREFIXES:
            rows.append({
                "date": d,
                "zone_prefix": prefix,
                "is_holiday": hol,
                "is_school_day": school,
                "is_major_event": int((d, prefix) in events),
            })
    return pd.DataFrame(rows, columns=["date", "zone_prefix", "is_holiday", "is_school_day", "is_major_event"])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pipeline/.venv/bin/python -m pytest pipeline/tests/test_fw_calendar.py -v`
Expected: 21 passed

- [ ] **Step 5: Commit**

```bash
git add pipeline/fw_calendar.py pipeline/tests/test_fw_calendar.py
git commit -m "feat(pipeline): holiday + DOE school calendars 2021-26 from official PDFs

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Zone × hour grid with lags (`fw_grid`)

**Files:**
- Create: `pipeline/fw_grid.py`
- Create: `pipeline/tests/synth.py`
- Test: `pipeline/tests/test_fw_grid.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `LAG_SPECS: dict[str, list[int]]` (keys in `LAG_FEATURE_COLS` order), `create_counts(conn, cleaned_path: str) -> None` (table `counts(INCIDENT_DISPATCH_AREA, date_hour, incident_count)`), `create_grid(conn, zones: list[str], start: date, end: date) -> int` (table `grid`, raises `AssertionError` if not gap-free), `add_lags(conn) -> None` (table `grid_lags` = `grid` + 7 lag columns). From `synth.py`: `count_at(zone_idx: int, hour_idx: int) -> int`, `write_incidents(path, zones, start, end) -> None`.

- [ ] **Step 1: Write `pipeline/tests/synth.py`** (test data helper)

```python
"""Deterministic synthetic incidents for grid / lag tests."""
import datetime as dt

import numpy as np
import pandas as pd


def count_at(zone_idx: int, hour_idx: int) -> int:
    """Incidents in zone `zone_idx` during hour `hour_idx` (0 = start). Includes zeros."""
    return (hour_idx * 7 + zone_idx * 3) % 5


def write_incidents(path, zones: list[str], start: dt.date, end: dt.date) -> None:
    """One parquet row per incident with INCIDENT_DISPATCH_AREA and date_hour."""
    hours = pd.date_range(pd.Timestamp(start), pd.Timestamp(end) + pd.Timedelta(hours=23), freq="h")
    zone_col, ts_col = [], []
    for zi, zone in enumerate(zones):
        n = np.array([count_at(zi, hi) for hi in range(len(hours))])
        zone_col.extend([zone] * int(n.sum()))
        ts_col.extend(np.repeat(hours.values, n))
    pd.DataFrame({"INCIDENT_DISPATCH_AREA": zone_col, "date_hour": ts_col}).to_parquet(path, index=False)
```

- [ ] **Step 2: Write the failing test** — `pipeline/tests/test_fw_grid.py`

```python
import datetime as dt
import random

import duckdb
import pandas as pd
import pytest

from fw_config import LAG_FEATURE_COLS
from fw_grid import LAG_SPECS, add_lags, create_counts, create_grid
from synth import count_at, write_incidents

ZONES = ["K7", "B2"]
START, END = dt.date(2025, 1, 1), dt.date(2025, 2, 15)
N_HOURS = ((END - START).days + 1) * 24


@pytest.fixture
def conn(tmp_path):
    path = tmp_path / "incidents.parquet"
    write_incidents(path, ZONES, START, END)
    c = duckdb.connect()
    create_counts(c, str(path))
    create_grid(c, ZONES, START, END)
    add_lags(c)
    return c


def _hour_idx(ts) -> int:
    return int((pd.Timestamp(ts) - pd.Timestamp(START)) / pd.Timedelta(hours=1))


def test_lag_specs_match_feature_order():
    assert list(LAG_SPECS) == LAG_FEATURE_COLS


def test_grid_is_complete_with_zeros(conn):
    n, zeros = conn.execute(
        "SELECT COUNT(*), SUM(CASE WHEN incident_count = 0 THEN 1 ELSE 0 END) FROM grid"
    ).fetchone()
    assert n == len(ZONES) * N_HOURS
    assert zeros > 0


def test_grid_counts_match_source(conn):
    rows = conn.execute("SELECT INCIDENT_DISPATCH_AREA, date_hour, incident_count FROM grid").fetchall()
    for zone, ts, n in rows:
        assert n == count_at(ZONES.index(zone), _hour_idx(ts))


def test_lags_equal_counts_at_past_timestamps(conn):
    df = conn.execute(
        "SELECT * FROM grid_lags WHERE roll_4w_same_hour_dow IS NOT NULL"
    ).df()
    random.seed(0)
    for i in random.sample(range(len(df)), 200):
        row = df.iloc[i]
        zi, hi = ZONES.index(row["INCIDENT_DISPATCH_AREA"]), _hour_idx(row["date_hour"])
        for name, offsets in LAG_SPECS.items():
            assert all(h > 0 for h in offsets)        # past-only
            expected = sum(count_at(zi, hi - h) for h in offsets) / len(offsets)
            assert row[name] == pytest.approx(expected), name


def test_lag_warmup_is_null_then_filled(conn):
    first = conn.execute(
        "SELECT lag_1h, roll_4w_same_hour_dow FROM grid_lags "
        "WHERE INCIDENT_DISPATCH_AREA = 'K7' ORDER BY date_hour LIMIT 1"
    ).fetchone()
    assert first == (None, None)
    at_672 = conn.execute(
        "SELECT roll_4w_same_hour_dow FROM grid_lags WHERE INCIDENT_DISPATCH_AREA = 'K7' "
        "ORDER BY date_hour LIMIT 1 OFFSET 672"
    ).fetchone()[0]
    at_671 = conn.execute(
        "SELECT roll_4w_same_hour_dow FROM grid_lags WHERE INCIDENT_DISPATCH_AREA = 'K7' "
        "ORDER BY date_hour LIMIT 1 OFFSET 671"
    ).fetchone()[0]
    assert at_671 is None and at_672 is not None


def test_create_grid_rejects_duplicate_zones(tmp_path):
    path = tmp_path / "incidents.parquet"
    write_incidents(path, ["K7"], START, START)
    c = duckdb.connect()
    create_counts(c, str(path))
    with pytest.raises(AssertionError):
        create_grid(c, ["K7", "K7"], START, START)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pipeline/.venv/bin/python -m pytest pipeline/tests/test_fw_grid.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'fw_grid'`

- [ ] **Step 4: Write `pipeline/fw_grid.py`**

```python
"""
Gap-free (zone × local hour) grid with past-only lag features, built in DuckDB.

The grid has exactly one row per zone per naive local hour (24 per day, DST days
included), so a window-function row offset of N equals exactly N hours. The
backend recomputes the same lags by timestamp arithmetic in
backend/models/lag_features.py; pipeline/tests/test_lag_parity.py pins them equal.
"""
import datetime as dt

# feature name -> hour offsets averaged (a single offset is a plain lag)
LAG_SPECS = {
    "lag_1h": [1],
    "lag_2h": [2],
    "lag_3h": [3],
    "lag_24h": [24],
    "lag_168h": [168],
    "roll_7d_same_hour": [24 * k for k in range(1, 8)],
    "roll_4w_same_hour_dow": [168 * k for k in range(1, 5)],
}


def _lag_expr(offsets: list[int]) -> str:
    terms = [f"LAG(incident_count, {h}) OVER w" for h in offsets]
    if len(terms) == 1:
        return terms[0]
    return f"({' + '.join(terms)}) / {float(len(terms))}"


def create_counts(conn, cleaned_path: str) -> None:
    conn.execute(f"""
        CREATE OR REPLACE TABLE counts AS
        SELECT INCIDENT_DISPATCH_AREA, date_hour, COUNT(*)::INTEGER AS incident_count
        FROM read_parquet('{cleaned_path}')
        GROUP BY INCIDENT_DISPATCH_AREA, date_hour
    """)


def create_grid(conn, zones: list[str], start: dt.date, end: dt.date) -> int:
    zone_list = ", ".join(f"'{z}'" for z in zones)
    conn.execute(f"""
        CREATE OR REPLACE TABLE grid AS
        SELECT z.INCIDENT_DISPATCH_AREA, h.date_hour,
               COALESCE(c.incident_count, 0) AS incident_count
        FROM (SELECT UNNEST([{zone_list}]) AS INCIDENT_DISPATCH_AREA) z
        CROSS JOIN (
            SELECT generate_series AS date_hour
            FROM generate_series(TIMESTAMP '{start} 00:00:00',
                                 TIMESTAMP '{end} 23:00:00', INTERVAL 1 HOUR)
        ) h
        LEFT JOIN counts c
          ON c.INCIDENT_DISPATCH_AREA = z.INCIDENT_DISPATCH_AREA
         AND c.date_hour = h.date_hour
    """)
    expected = len(zones) * ((end - start).days + 1) * 24
    n = conn.execute("SELECT COUNT(*) FROM grid").fetchone()[0]
    n_distinct = conn.execute(
        "SELECT COUNT(*) FROM (SELECT DISTINCT INCIDENT_DISPATCH_AREA, date_hour FROM grid)"
    ).fetchone()[0]
    if n != expected or n_distinct != expected:
        raise AssertionError(f"grid not gap-free: {n} rows, {n_distinct} distinct, expected {expected}")
    return n


def add_lags(conn) -> None:
    lag_cols = ",\n            ".join(f"{_lag_expr(offs)} AS {name}" for name, offs in LAG_SPECS.items())
    conn.execute(f"""
        CREATE OR REPLACE TABLE grid_lags AS
        SELECT *,
            {lag_cols}
        FROM grid
        WINDOW w AS (PARTITION BY INCIDENT_DISPATCH_AREA ORDER BY date_hour)
    """)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pipeline/.venv/bin/python -m pytest pipeline/tests/test_fw_grid.py -v`
Expected: 6 passed

- [ ] **Step 6: Commit**

```bash
git add pipeline/fw_grid.py pipeline/tests/synth.py pipeline/tests/test_fw_grid.py
git commit -m "feat(pipeline): gap-free zone x hour grid with past-only lag features

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Backend lag features, replay rules, and train/serve parity

**Files:**
- Create: `backend/requirements-dev.txt`
- Create: `backend/models/lag_features.py`
- Create: `backend/models/replay.py`
- Create: `backend/tests/conftest.py`, `backend/tests/fixtures_data.py`
- Test: `backend/tests/test_lag_features.py`, `backend/tests/test_replay.py`, `pipeline/tests/test_lag_parity.py`

**Interfaces:**
- Consumes: `fw_grid.create_counts/create_grid/add_lags`, `synth.write_incidents/count_at`, `fw_config.LAG_FEATURE_COLS` (parity test only).
- Produces (`models.lag_features`): `LAG_FEATURES: list[str]`, `MAX_LOOKBACK_HOURS = 672`, `class MissingHistoryError(LookupError)`, `to_wide(hourly_counts: pd.DataFrame) -> pd.DataFrame` (index DatetimeIndex `date_hour`, columns zones, float), `build_lag_features(counts_wide, target: pd.Timestamp) -> pd.DataFrame` (index zones, columns `LAG_FEATURES`), `actual_counts(counts_wide, target) -> dict[str, int]` (`{}` if target missing).
- Produces (`models.replay`): `REPLAY_START`, `REPLAY_END`, `STANDIN_YEAR = 2025`, `class OutOfReplayRange(ValueError)`, `resolve_standin_date(month: int, dow: int, year: int = 2025) -> date`, `resolve_request(date: date | None, dow: int, month: int) -> tuple[date, int, int]`, `calendar_to_lookup(df) -> dict[tuple[date, str], dict[str, int]]`, `calendar_flags(lookup: dict | None, d: date | None, zone_prefix: str) -> dict[str, int]` (defaults `{"is_holiday": 0, "is_school_day": 1, "is_major_event": 0}`).
- Produces (`backend/tests/fixtures_data.py`): `SYNTH_START = pd.Timestamp("2024-12-01")`, `synthetic_hourly_counts(start="2024-12-01", end="2026-06-30") -> pd.DataFrame` (long format, all 31 zones), `synthetic_count(zone: str, ts) -> int`.

- [ ] **Step 1: Backend dev dependencies**

`backend/requirements-dev.txt`:
```
pytest>=8.0
httpx>=0.27
```
Run: `backend/.venv/bin/pip install -r backend/requirements-dev.txt`
Expected: installs pytest (httpx 0.28.1 already present).

- [ ] **Step 2: Write `backend/tests/conftest.py` and `backend/tests/fixtures_data.py`**

`backend/tests/conftest.py`:
```python
import pathlib
import sys

BACKEND = pathlib.Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
```

`backend/tests/fixtures_data.py`:
```python
"""Deterministic synthetic hourly counts shared by backend tests."""
import numpy as np
import pandas as pd

from models.demand_forecaster import VALID_ZONES

SYNTH_START = pd.Timestamp("2024-12-01")


def synthetic_count(zone: str, ts) -> int:
    hour_idx = int((pd.Timestamp(ts) - SYNTH_START) / pd.Timedelta(hours=1))
    return (hour_idx * 7 + VALID_ZONES.index(zone) * 3) % 5


def synthetic_hourly_counts(start: str = "2024-12-01", end: str = "2026-06-30") -> pd.DataFrame:
    hours = pd.date_range(pd.Timestamp(start), pd.Timestamp(end) + pd.Timedelta(hours=23), freq="h")
    hour_idx = ((hours - SYNTH_START) / pd.Timedelta(hours=1)).astype(int).to_numpy()
    frames = []
    for zi, zone in enumerate(VALID_ZONES):
        frames.append(pd.DataFrame({
            "INCIDENT_DISPATCH_AREA": zone,
            "date_hour": hours,
            "incident_count": (hour_idx * 7 + zi * 3) % 5,
        }))
    return pd.concat(frames, ignore_index=True)
```

- [ ] **Step 3: Write the failing tests** — `backend/tests/test_lag_features.py`

```python
import pandas as pd
import pytest

from fixtures_data import synthetic_count, synthetic_hourly_counts
from models.lag_features import (
    LAG_FEATURES, MissingHistoryError, actual_counts, build_lag_features, to_wide,
)

WIDE = to_wide(synthetic_hourly_counts())
T = pd.Timestamp


def _expected(zone, target, offsets):
    return sum(synthetic_count(zone, target - pd.Timedelta(hours=h)) for h in offsets) / len(offsets)


def test_to_wide_shape():
    assert WIDE.shape[1] == 31
    assert WIDE.index.is_monotonic_increasing
    assert WIDE.index[0] == T("2024-12-01 00:00") and WIDE.index[-1] == T("2026-06-30 23:00")


def test_columns_and_zone_index():
    lags = build_lag_features(WIDE, T("2025-10-10 20:00"))
    assert list(lags.columns) == LAG_FEATURES
    assert len(lags) == 31 and "K7" in lags.index


@pytest.mark.parametrize("target", [
    "2025-10-10 20:00",
    "2025-03-10 00:00",   # midnight: lag_1h is the previous date's 23:00
    "2025-03-09 02:00",   # DST spring-forward label
    "2025-11-02 01:00",   # DST fall-back label
])
def test_lag_values(target):
    target = T(target)
    lags = build_lag_features(WIDE, target)
    for zone in ("K7", "B2", "S3"):
        row = lags.loc[zone]
        assert row["lag_1h"] == synthetic_count(zone, target - pd.Timedelta(hours=1))
        assert row["lag_2h"] == synthetic_count(zone, target - pd.Timedelta(hours=2))
        assert row["lag_3h"] == synthetic_count(zone, target - pd.Timedelta(hours=3))
        assert row["lag_24h"] == synthetic_count(zone, target - pd.Timedelta(hours=24))
        assert row["lag_168h"] == synthetic_count(zone, target - pd.Timedelta(hours=168))
        assert row["roll_7d_same_hour"] == pytest.approx(_expected(zone, target, [24 * k for k in range(1, 8)]))
        assert row["roll_4w_same_hour_dow"] == pytest.approx(_expected(zone, target, [168 * k for k in range(1, 5)]))


def test_dst_hours_have_lags():
    for target in ("2025-03-09 02:00", "2025-03-09 03:00", "2025-11-02 01:00", "2025-11-02 02:00"):
        assert not build_lag_features(WIDE, T(target)).isna().any().any()


def test_first_replay_hour_reaches_into_december():
    lags = build_lag_features(WIDE, T("2025-01-01 00:00"))
    assert lags.loc["K7", "lag_1h"] == synthetic_count("K7", T("2024-12-31 23:00"))
    assert lags.loc["K7", "roll_4w_same_hour_dow"] == pytest.approx(
        _expected("K7", T("2025-01-01 00:00"), [168, 336, 504, 672]))


def test_missing_history_raises():
    with pytest.raises(MissingHistoryError):
        build_lag_features(WIDE, T("2024-12-10 00:00"))


def test_actual_counts():
    got = actual_counts(WIDE, T("2025-10-10 20:00"))
    assert got["K7"] == synthetic_count("K7", T("2025-10-10 20:00"))
    assert isinstance(got["K7"], int)
    assert actual_counts(WIDE, T("2027-01-01 00:00")) == {}
```

`backend/tests/test_replay.py`:
```python
import datetime as dt

import pandas as pd
import pytest

from models.replay import (
    OutOfReplayRange, calendar_flags, calendar_to_lookup,
    resolve_request, resolve_standin_date,
)

D = dt.date


@pytest.mark.parametrize("month,dow,expected", [
    (10, 4, D(2025, 10, 17)),   # 5 Fridays (3,10,17,24,31) -> 3rd
    (10, 0, D(2025, 10, 13)),   # 4 Mondays (6,13,20,27)    -> 2nd
    (2, 5, D(2025, 2, 8)),      # 4 Saturdays (1,8,15,22)   -> 2nd
])
def test_resolve_standin_date(month, dow, expected):
    assert resolve_standin_date(month, dow) == expected


def test_resolve_request_without_date():
    assert resolve_request(None, 4, 10) == (D(2025, 10, 17), 4, 10)


def test_date_overrides_dow_and_month():
    assert resolve_request(D(2025, 10, 10), 0, 1) == (D(2025, 10, 10), 4, 10)


@pytest.mark.parametrize("bad", [D(2024, 12, 31), D(2026, 7, 1)])
def test_out_of_range(bad):
    with pytest.raises(OutOfReplayRange):
        resolve_request(bad, 0, 1)


@pytest.mark.parametrize("ok", [D(2025, 1, 1), D(2026, 6, 30)])
def test_range_edges_ok(ok):
    assert resolve_request(ok, 0, 1)[0] == ok


def test_calendar_lookup_and_defaults():
    df = pd.DataFrame({
        "date": [D(2025, 10, 20)], "zone_prefix": ["K"],
        "is_holiday": [0], "is_school_day": [0], "is_major_event": [1],
    })
    lookup = calendar_to_lookup(df)
    assert calendar_flags(lookup, D(2025, 10, 20), "K") == {
        "is_holiday": 0, "is_school_day": 0, "is_major_event": 1}
    default = {"is_holiday": 0, "is_school_day": 1, "is_major_event": 0}
    assert calendar_flags(lookup, D(2025, 10, 21), "K") == default
    assert calendar_flags(None, D(2025, 10, 20), "K") == default
    assert calendar_flags(lookup, None, "K") == default
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `backend/.venv/bin/python -m pytest backend/tests -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'models.lag_features'`

- [ ] **Step 5: Write `backend/models/lag_features.py`**

```python
"""
Serving-side lag features. Must match pipeline/fw_grid.py LAG_SPECS exactly;
pipeline/tests/test_lag_parity.py compares the two on the same data.

Timestamps are naive local hours (24 per day, DST days included), the same
convention as the training grid, so "t minus N hours" is plain Timedelta math.
"""
import pandas as pd

LAG_FEATURES = [
    "lag_1h",
    "lag_2h",
    "lag_3h",
    "lag_24h",
    "lag_168h",
    "roll_7d_same_hour",
    "roll_4w_same_hour_dow",
]

_OFFSETS = {
    "lag_1h": [1],
    "lag_2h": [2],
    "lag_3h": [3],
    "lag_24h": [24],
    "lag_168h": [168],
    "roll_7d_same_hour": [24 * k for k in range(1, 8)],
    "roll_4w_same_hour_dow": [168 * k for k in range(1, 5)],
}
MAX_LOOKBACK_HOURS = 672


class MissingHistoryError(LookupError):
    """hourly_counts does not cover a timestamp the lags need."""


def to_wide(hourly_counts: pd.DataFrame) -> pd.DataFrame:
    """Long (zone, date_hour, incident_count) -> wide: index date_hour, one column per zone."""
    wide = hourly_counts.pivot(
        index="date_hour", columns="INCIDENT_DISPATCH_AREA", values="incident_count"
    )
    wide.index = pd.DatetimeIndex(wide.index)
    return wide.sort_index().fillna(0).astype(float)


def _row(counts_wide: pd.DataFrame, ts: pd.Timestamp) -> pd.Series:
    if ts not in counts_wide.index:
        raise MissingHistoryError(f"no hourly counts for {ts}")
    return counts_wide.loc[ts]


def build_lag_features(counts_wide: pd.DataFrame, target: pd.Timestamp) -> pd.DataFrame:
    """Lag features for every zone at `target`. Index = zone, columns = LAG_FEATURES."""
    target = pd.Timestamp(target)
    cols = {}
    for name, offsets in _OFFSETS.items():
        rows = [_row(counts_wide, target - pd.Timedelta(hours=h)) for h in offsets]
        cols[name] = sum(rows) / len(rows)
    return pd.DataFrame(cols)[LAG_FEATURES]


def actual_counts(counts_wide: pd.DataFrame, target: pd.Timestamp) -> dict:
    target = pd.Timestamp(target)
    if target not in counts_wide.index:
        return {}
    return {zone: int(v) for zone, v in counts_wide.loc[target].items()}
```

- [ ] **Step 6: Write `backend/models/replay.py`**

```python
"""Replay-by-date rules shared by /api/heatmap and /api/staging."""
import calendar
import datetime as dt

REPLAY_START = dt.date(2025, 1, 1)
REPLAY_END = dt.date(2026, 6, 30)
STANDIN_YEAR = 2025

_DEFAULT_FLAGS = {"is_holiday": 0, "is_school_day": 1, "is_major_event": 0}


class OutOfReplayRange(ValueError):
    pass


def resolve_standin_date(month: int, dow: int, year: int = STANDIN_YEAR) -> dt.date:
    """Lower-median date in (year, month) whose weekday is dow (0 = Monday)."""
    n_days = calendar.monthrange(year, month)[1]
    matches = [dt.date(year, month, d) for d in range(1, n_days + 1)
               if dt.date(year, month, d).weekday() == dow]
    return matches[(len(matches) - 1) // 2]


def resolve_request(date: dt.date | None, dow: int, month: int) -> tuple[dt.date, int, int]:
    """(replay_date, dow, month). A given date wins over dow/month."""
    if date is None:
        return resolve_standin_date(month, dow), dow, month
    if not (REPLAY_START <= date <= REPLAY_END):
        raise OutOfReplayRange(f"date must be between {REPLAY_START} and {REPLAY_END}, got {date}")
    return date, date.weekday(), date.month


def calendar_to_lookup(df) -> dict:
    lookup = {}
    for row in df.itertuples(index=False):
        # pd.Timestamp subclasses datetime (which subclasses date), so test datetime first.
        d = row.date.date() if isinstance(row.date, dt.datetime) else row.date
        lookup[(d, row.zone_prefix)] = {
            "is_holiday": int(row.is_holiday),
            "is_school_day": int(row.is_school_day),
            "is_major_event": int(row.is_major_event),
        }
    return lookup


def calendar_flags(lookup: dict | None, d: dt.date | None, zone_prefix: str) -> dict:
    if lookup is None or d is None:
        return dict(_DEFAULT_FLAGS)
    return dict(lookup.get((d, zone_prefix), _DEFAULT_FLAGS))
```

- [ ] **Step 7: Run backend tests to verify they pass**

Run: `backend/.venv/bin/python -m pytest backend/tests -v`
Expected: all passed (test_lag_features: 10, test_replay: 10)

- [ ] **Step 8: Write the parity test** — `pipeline/tests/test_lag_parity.py`

```python
import datetime as dt
import random

import duckdb
import pandas as pd
import pytest

from fw_config import LAG_FEATURE_COLS
from fw_grid import LAG_SPECS, add_lags, create_counts, create_grid
from models.lag_features import LAG_FEATURES, build_lag_features, to_wide
from synth import write_incidents

ZONES = ["K7", "B2", "S3"]
START, END = dt.date(2024, 12, 1), dt.date(2025, 2, 28)


def test_feature_names_agree():
    assert LAG_FEATURES == LAG_FEATURE_COLS == list(LAG_SPECS)


def test_training_and_serving_lags_match(tmp_path):
    path = tmp_path / "incidents.parquet"
    write_incidents(path, ZONES, START, END)
    conn = duckdb.connect()
    create_counts(conn, str(path))
    create_grid(conn, ZONES, START, END)
    add_lags(conn)

    grid = conn.execute("SELECT * FROM grid_lags").df()
    wide = to_wide(grid[["INCIDENT_DISPATCH_AREA", "date_hour", "incident_count"]])
    trainable = grid[grid["roll_4w_same_hour_dow"].notna()].reset_index(drop=True)

    random.seed(1)
    for i in random.sample(range(len(trainable)), 200):
        row = trainable.iloc[i]
        served = build_lag_features(wide, pd.Timestamp(row["date_hour"])).loc[row["INCIDENT_DISPATCH_AREA"]]
        for name in LAG_FEATURES:
            assert served[name] == pytest.approx(row[name]), (row["date_hour"], name)
```

- [ ] **Step 9: Run the parity test**

Run: `pipeline/.venv/bin/python -m pytest pipeline/tests/test_lag_parity.py -v`
Expected: 2 passed

- [ ] **Step 10: Commit**

```bash
git add backend/requirements-dev.txt backend/models/lag_features.py backend/models/replay.py backend/tests pipeline/tests/test_lag_parity.py
git commit -m "feat(backend): serving-side lag features + replay rules, train/serve parity test

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Evaluation metrics and deployment gate (`fw_eval`)

**Files:**
- Create: `pipeline/fw_eval.py`
- Test: `pipeline/tests/test_fw_eval.py`

**Interfaces:**
- Produces: `score(y, p) -> dict` with keys `rmse, mae, poisson_deviance`; `rmse_by_group(y, p, groups) -> dict[str, float]`; `deployment_gate(lag_rmse: float, no_lag_rmse: float, threshold: float = 0.02) -> dict` with keys `passed: bool, improvement: float, threshold: float`.

- [ ] **Step 1: Write the failing test** — `pipeline/tests/test_fw_eval.py`

```python
import math

import numpy as np
import pytest

from fw_eval import deployment_gate, rmse_by_group, score


def test_score_perfect():
    s = score(np.array([0, 2, 4]), np.array([0.0, 2.0, 4.0]))
    assert s["rmse"] == pytest.approx(0.0, abs=1e-5)
    assert s["mae"] == pytest.approx(0.0, abs=1e-5)
    assert s["poisson_deviance"] == pytest.approx(0.0, abs=1e-4)


def test_score_known_values():
    s = score(np.array([1, 3]), np.array([2.0, 2.0]))
    assert s["rmse"] == pytest.approx(1.0)
    assert s["mae"] == pytest.approx(1.0)
    assert s["poisson_deviance"] > 0


def test_score_clips_negative_predictions():
    s = score(np.array([0, 1]), np.array([-3.0, 1.0]))
    assert math.isfinite(s["poisson_deviance"])
    assert s["rmse"] == pytest.approx(0.0, abs=1e-5)


def test_rmse_by_group():
    got = rmse_by_group(np.array([1, 1, 3]), np.array([1.0, 2.0, 3.0]), np.array(["a", "a", "b"]))
    assert got["a"] == pytest.approx(math.sqrt(0.5))
    assert got["b"] == pytest.approx(0.0)


@pytest.mark.parametrize("lag,no_lag,passed", [
    (0.97, 1.0, True),
    (0.98, 1.0, True),    # exactly 2%
    (0.99, 1.0, False),
    (1.05, 1.0, False),
])
def test_deployment_gate(lag, no_lag, passed):
    g = deployment_gate(lag, no_lag)
    assert g["passed"] is passed
    assert g["threshold"] == 0.02
    assert g["improvement"] == pytest.approx((no_lag - lag) / no_lag)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pipeline/.venv/bin/python -m pytest pipeline/tests/test_fw_eval.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'fw_eval'`

- [ ] **Step 3: Write `pipeline/fw_eval.py`**

```python
"""Metrics and the deployment gate for script 05."""
import numpy as np
from sklearn.metrics import mean_absolute_error, mean_poisson_deviance, mean_squared_error

_EPS = 1e-6   # Poisson deviance needs strictly positive predictions


def _clip(p) -> np.ndarray:
    return np.clip(np.asarray(p, dtype=float), _EPS, None)


def score(y, p) -> dict:
    y = np.asarray(y, dtype=float)
    p = _clip(p)
    return {
        "rmse": float(np.sqrt(mean_squared_error(y, p))),
        "mae": float(mean_absolute_error(y, p)),
        "poisson_deviance": float(mean_poisson_deviance(y, p)),
    }


def rmse_by_group(y, p, groups) -> dict:
    y, p, groups = np.asarray(y, dtype=float), _clip(p), np.asarray(groups)
    return {
        str(g): float(np.sqrt(np.mean((y[groups == g] - p[groups == g]) ** 2)))
        for g in np.unique(groups)
    }


def deployment_gate(lag_rmse: float, no_lag_rmse: float, threshold: float = 0.02) -> dict:
    improvement = (no_lag_rmse - lag_rmse) / no_lag_rmse
    return {"passed": bool(improvement >= threshold), "improvement": float(improvement), "threshold": threshold}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pipeline/.venv/bin/python -m pytest pipeline/tests/test_fw_eval.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add pipeline/fw_eval.py pipeline/tests/test_fw_eval.py
git commit -m "feat(pipeline): evaluation metrics and 2% deployment gate

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Script 01 — ingest and clean

**Files:**
- Create: `pipeline/fw_ingest.py`
- Modify (full rewrite): `pipeline/01_ingest_clean.py`
- Test: `pipeline/tests/test_fw_ingest.py`, `pipeline/tests/test_01_ingest_smoke.py`

**Interfaces:**
- Consumes: `fw_config.VALID_ZONES, DATA_START, DATA_END, split_case_sql`.
- Produces: `fw_ingest.REQUIRED_COLUMNS`, `missing_columns(columns) -> list[str]`, `pick_id_column(columns) -> str`. Script output `$FW_PIPELINE_DATA/incidents_cleaned.parquet` (default `pipeline/data`) with columns: `incident_dt, INCIDENT_ID, INCIDENT_DISPATCH_AREA, BOROUGH, INCIDENT_RESPONSE_SECONDS_QY, INCIDENT_TRAVEL_TM_SECONDS_QY, DISPATCH_RESPONSE_SECONDS_QY, FINAL_SEVERITY_LEVEL_CODE, HELD_INDICATOR, year, month, dayofweek, hour, date_hour, incident_date, is_weekend, is_high_acuity, is_held, is_valid_response, split`.

- [ ] **Step 1: Write the failing unit test** — `pipeline/tests/test_fw_ingest.py`

```python
import pytest

from fw_ingest import REQUIRED_COLUMNS, missing_columns, pick_id_column


def test_pick_id_column_prefers_current_name():
    assert pick_id_column(["INCIDENT_ID", "CAD_INCIDENT_ID"]) == "INCIDENT_ID"
    assert pick_id_column(["cad_incident_id"]) == "cad_incident_id"


def test_pick_id_column_missing():
    with pytest.raises(ValueError):
        pick_id_column(["BOROUGH"])


def test_missing_columns_case_insensitive():
    cols = [c.lower() for c in REQUIRED_COLUMNS]
    assert missing_columns(cols) == []
    assert missing_columns(cols[1:]) == [REQUIRED_COLUMNS[0]]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pipeline/.venv/bin/python -m pytest pipeline/tests/test_fw_ingest.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'fw_ingest'`

- [ ] **Step 3: Write `pipeline/fw_ingest.py`**

```python
"""Raw EMS CSV column checks for script 01."""

# The dataset renamed CAD_INCIDENT_ID -> INCIDENT_ID; accept either.
ID_COLUMN_CANDIDATES = ("INCIDENT_ID", "CAD_INCIDENT_ID")

REQUIRED_COLUMNS = (
    "INCIDENT_DATETIME",
    "INCIDENT_DISPATCH_AREA",
    "BOROUGH",
    "INCIDENT_RESPONSE_SECONDS_QY",
    "INCIDENT_TRAVEL_TM_SECONDS_QY",
    "DISPATCH_RESPONSE_SECONDS_QY",
    "FINAL_SEVERITY_LEVEL_CODE",
    "HELD_INDICATOR",
    "VALID_INCIDENT_RSPNS_TIME_INDC",
    "VALID_DISPATCH_RSPNS_TIME_INDC",
    "REOPEN_INDICATOR",
    "TRANSFER_INDICATOR",
    "STANDBY_INDICATOR",
)


def missing_columns(columns) -> list[str]:
    present = {c.upper() for c in columns}
    return [c for c in REQUIRED_COLUMNS if c not in present]


def pick_id_column(columns) -> str:
    by_upper = {c.upper(): c for c in columns}
    for candidate in ID_COLUMN_CANDIDATES:
        if candidate in by_upper:
            return by_upper[candidate]
    raise ValueError(f"no incident ID column; expected one of {ID_COLUMN_CANDIDATES}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pipeline/.venv/bin/python -m pytest pipeline/tests/test_fw_ingest.py -v`
Expected: 3 passed

- [ ] **Step 5: Write the failing smoke test** — `pipeline/tests/test_01_ingest_smoke.py`

```python
import csv
import os
import pathlib
import subprocess
import sys

import pandas as pd

from fw_ingest import REQUIRED_COLUMNS

REPO = pathlib.Path(__file__).resolve().parents[2]

BASE = {
    "INCIDENT_DISPATCH_AREA": "K7", "BOROUGH": "BROOKLYN",
    "INCIDENT_RESPONSE_SECONDS_QY": "505", "INCIDENT_TRAVEL_TM_SECONDS_QY": "442",
    "DISPATCH_RESPONSE_SECONDS_QY": "63", "FINAL_SEVERITY_LEVEL_CODE": "2",
    "HELD_INDICATOR": "N", "VALID_INCIDENT_RSPNS_TIME_INDC": "Y",
    "VALID_DISPATCH_RSPNS_TIME_INDC": "Y", "REOPEN_INDICATOR": "N",
    "TRANSFER_INDICATOR": "N", "STANDBY_INDICATOR": "N",
}

ROWS = [  # (INCIDENT_ID, INCIDENT_DATETIME, overrides)
    ("1", "10/10/2025 08:05:00 PM", {}),                                   # kept, test, valid
    ("2", "10/10/2025 08:06:00 PM", {"VALID_INCIDENT_RSPNS_TIME_INDC": "N"}),  # kept, not valid
    ("3", "10/10/2025 08:07:00 PM", {"INCIDENT_RESPONSE_SECONDS_QY": "9000"}),  # kept, not valid
    ("4", "10/10/2025 08:08:00 PM", {"REOPEN_INDICATOR": "Y"}),              # dropped
    ("5", "10/10/2025 08:09:00 PM", {"INCIDENT_DISPATCH_AREA": "CW"}),       # dropped
    ("6", "10/10/2025 08:10:00 PM", {"BOROUGH": "BRONX", "INCIDENT_DISPATCH_AREA": "M7"}),  # dropped
    ("7", "11/30/2021 11:00:00 PM", {}),                                   # dropped: before window
    ("8", "12/15/2021 01:00:00 AM", {}),                                   # kept, history
    ("9", "07/01/2026 12:00:00 AM", {}),                                   # dropped: after window
    ("10", "2024-11-05T14:00:00", {}),                                     # kept, valid split, ISO format
    ("11", "03/02/2026 09:00:00 AM", {"BOROUGH": "RICHMOND / STATEN ISLAND",
                                      "INCIDENT_DISPATCH_AREA": "S1"}),     # kept, test_recent
    ("12", "05/05/2023 12:30:00 PM", {"VALID_DISPATCH_RSPNS_TIME_INDC": ""}),  # kept, train, not valid
]


def test_ingest_filters_and_flags(tmp_path):
    csv_path = tmp_path / "raw.csv"
    header = ["INCIDENT_ID", *REQUIRED_COLUMNS]
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        for iid, ts, over in ROWS:
            w.writerow({**BASE, **over, "INCIDENT_ID": iid, "INCIDENT_DATETIME": ts})

    env = {**os.environ, "FW_PIPELINE_DATA": str(tmp_path / "data")}
    r = subprocess.run([sys.executable, "pipeline/01_ingest_clean.py", "--csv", str(csv_path)],
                       cwd=REPO, env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr

    out = pd.read_parquet(tmp_path / "data" / "incidents_cleaned.parquet").set_index("INCIDENT_ID")
    assert sorted(out.index, key=int) == ["1", "2", "3", "8", "10", "11", "12"]
    assert out.loc["1", "split"] == "test"
    assert out.loc["8", "split"] == "history"
    assert out.loc["10", "split"] == "valid"
    assert out.loc["11", "split"] == "test_recent"
    assert out.loc["12", "split"] == "train"
    assert out["is_valid_response"].to_dict() == {
        "1": 1, "2": 0, "3": 0, "8": 1, "10": 1, "11": 1, "12": 0}
    assert (out.loc["1", "dayofweek"], out.loc["1", "hour"]) == (4, 20)
    assert out.loc["1", "is_high_acuity"] == 1
```

- [ ] **Step 6: Run the smoke test to verify it fails**

Run: `pipeline/.venv/bin/python -m pytest pipeline/tests/test_01_ingest_smoke.py -v`
Expected: FAIL — non-zero return code (current script selects `CAD_INCIDENT_ID`, has no `--csv` output override).

- [ ] **Step 7: Rewrite `pipeline/01_ingest_clean.py`**

```python
"""
Script 01 — Ingest & Clean
FirstWave | GT Hacklytics 2026

Input:  raw EMS CSV (--csv)
        Download: https://data.cityofnewyork.us/api/views/76xm-jjuj/rows.csv?accessType=DOWNLOAD
Output: $FW_PIPELINE_DATA/incidents_cleaned.parquet (default pipeline/data)
        one row per incident, 2021-12-01 → 2026-06-30, with a split column.

The demand label counts every incident that passes the zone/borough/indicator
filters. Response-time validity is NOT a filter here — it is the
is_valid_response column, used only for response-time averages (zone_stats, 08).

Run: python pipeline/01_ingest_clean.py --csv /path/to/ems_raw.csv
"""

import argparse
import datetime as dt
import os
import pathlib
import sys

import duckdb

from fw_config import DATA_END, DATA_START, VALID_ZONES, split_case_sql
from fw_ingest import missing_columns, pick_id_column

# ── Paths ──────────────────────────────────────────────────────────────────────
PIPELINE_DATA = pathlib.Path(os.getenv("FW_PIPELINE_DATA", "pipeline/data"))
PIPELINE_DATA.mkdir(parents=True, exist_ok=True)
OUT_PARQUET = PIPELINE_DATA / "incidents_cleaned.parquet"

VALID_ZONES_SQL = ", ".join(f"'{z}'" for z in VALID_ZONES)
WINDOW_END = DATA_END + dt.timedelta(days=1)

# ── CLI ────────────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument("--csv", required=True, help="Path to raw EMS CSV")
args = parser.parse_args()

csv_path = pathlib.Path(args.csv).resolve()
if not csv_path.exists():
    print(f"ERROR: CSV not found at {csv_path}", file=sys.stderr)
    sys.exit(1)

conn = duckdb.connect()
# all_varchar: no type sniffing, so a mis-typed sample can't silently drop rows.
SRC = f"read_csv('{csv_path}', header=true, all_varchar=true, ignore_errors=true)"

columns = [d[0] for d in conn.execute(f"SELECT * FROM {SRC} LIMIT 0").description]
missing = missing_columns(columns)
if missing:
    print(f"ERROR: raw CSV is missing columns: {missing}", file=sys.stderr)
    print(f"       Found: {columns}", file=sys.stderr)
    sys.exit(1)
id_col = pick_id_column(columns)

raw_count = conn.execute(f"SELECT COUNT(*) FROM {SRC}").fetchone()[0]
print(f"Reading raw CSV: {csv_path}")
print(f"Raw row count: {raw_count:,}   (ID column: {id_col})")

INCIDENT_DT = (
    "COALESCE(TRY_CAST(INCIDENT_DATETIME AS TIMESTAMP), "
    "try_strptime(INCIDENT_DATETIME, '%m/%d/%Y %I:%M:%S %p'))"
)

# dow: DuckDB 0=Sun..6=Sat -> (dow + 6) % 7 gives 0=Mon..6=Sun
conn.execute(f"""
COPY (
    WITH src AS (
        SELECT *, {INCIDENT_DT} AS incident_dt FROM {SRC}
    )
    SELECT
        incident_dt,
        {id_col}                                                 AS INCIDENT_ID,
        INCIDENT_DISPATCH_AREA,
        BOROUGH,
        TRY_CAST(INCIDENT_RESPONSE_SECONDS_QY  AS DOUBLE)        AS INCIDENT_RESPONSE_SECONDS_QY,
        TRY_CAST(INCIDENT_TRAVEL_TM_SECONDS_QY AS DOUBLE)        AS INCIDENT_TRAVEL_TM_SECONDS_QY,
        TRY_CAST(DISPATCH_RESPONSE_SECONDS_QY  AS DOUBLE)        AS DISPATCH_RESPONSE_SECONDS_QY,
        TRY_CAST(FINAL_SEVERITY_LEVEL_CODE     AS INTEGER)       AS FINAL_SEVERITY_LEVEL_CODE,
        HELD_INDICATOR,

        EXTRACT(year  FROM incident_dt)::INTEGER                 AS year,
        EXTRACT(month FROM incident_dt)::INTEGER                 AS month,
        (EXTRACT(dow  FROM incident_dt)::INTEGER + 6) % 7        AS dayofweek,
        EXTRACT(hour  FROM incident_dt)::INTEGER                 AS hour,
        date_trunc('hour', incident_dt)                          AS date_hour,
        CAST(incident_dt AS DATE)                                AS incident_date,

        CASE WHEN (EXTRACT(dow FROM incident_dt)::INTEGER + 6) % 7 IN (5, 6)
             THEN 1 ELSE 0 END                                   AS is_weekend,
        CASE WHEN TRY_CAST(FINAL_SEVERITY_LEVEL_CODE AS INTEGER) IN (1, 2)
             THEN 1 ELSE 0 END                                   AS is_high_acuity,
        CASE WHEN HELD_INDICATOR = 'Y' THEN 1 ELSE 0 END         AS is_held,
        CASE WHEN VALID_INCIDENT_RSPNS_TIME_INDC = 'Y'
              AND VALID_DISPATCH_RSPNS_TIME_INDC = 'Y'
              AND TRY_CAST(INCIDENT_RESPONSE_SECONDS_QY AS DOUBLE) BETWEEN 1 AND 7200
             THEN 1 ELSE 0 END                                   AS is_valid_response,

        {split_case_sql('incident_dt')}                          AS split

    FROM src
    WHERE incident_dt >= TIMESTAMP '{DATA_START} 00:00:00'
      AND incident_dt <  TIMESTAMP '{WINDOW_END} 00:00:00'
      AND REOPEN_INDICATOR   = 'N'
      AND TRANSFER_INDICATOR = 'N'
      AND STANDBY_INDICATOR  = 'N'
      AND BOROUGH IS NOT NULL
      AND BOROUGH != 'UNKNOWN'
      AND INCIDENT_DISPATCH_AREA IN ({VALID_ZONES_SQL})
      AND (
             (BOROUGH = 'BRONX'       AND INCIDENT_DISPATCH_AREA LIKE 'B%')
          OR (BOROUGH = 'BROOKLYN'    AND INCIDENT_DISPATCH_AREA LIKE 'K%')
          OR (BOROUGH = 'MANHATTAN'   AND INCIDENT_DISPATCH_AREA LIKE 'M%')
          OR (BOROUGH = 'QUEENS'      AND INCIDENT_DISPATCH_AREA LIKE 'Q%')
          OR (BOROUGH LIKE '%STATEN%' AND INCIDENT_DISPATCH_AREA LIKE 'S%')
      )
) TO '{OUT_PARQUET}' (FORMAT PARQUET, COMPRESSION SNAPPY)
""")

print(f"\nParquet written: {OUT_PARQUET}")

# ── Validation ─────────────────────────────────────────────────────────────────
summary = conn.execute(f"""
    SELECT split, year, COUNT(*) AS incidents,
           ROUND(AVG(is_valid_response) * 100, 1) AS pct_valid_response
    FROM read_parquet('{OUT_PARQUET}')
    GROUP BY split, year ORDER BY year, split
""").fetchdf()
zones = conn.execute(
    f"SELECT COUNT(DISTINCT INCIDENT_DISPATCH_AREA) FROM read_parquet('{OUT_PARQUET}')"
).fetchone()[0]

print()
print("=" * 60)
print("  SCRIPT 01 — VALIDATION")
print("=" * 60)
print(summary.to_string(index=False))
print(f"\n  Distinct zones: {zones}   <- expect 31")
print("  Expect ~1.5M+ incidents per full year and pct_valid_response")
print("  falling over time (~97% in 2022 to ~89% in mid-2026).")
if zones != 31:
    print(f"  WARNING: expected 31 zones, found {zones}")
print("=" * 60)
print("  Next: python pipeline/02_weather_merge.py")
```

- [ ] **Step 8: Run both tests to verify they pass**

Run: `pipeline/.venv/bin/python -m pytest pipeline/tests/test_fw_ingest.py pipeline/tests/test_01_ingest_smoke.py -v`
Expected: 4 passed

- [ ] **Step 9: Commit**

```bash
git add pipeline/fw_ingest.py pipeline/01_ingest_clean.py pipeline/tests/test_fw_ingest.py pipeline/tests/test_01_ingest_smoke.py
git commit -m "feat(pipeline): 01 keeps all incidents for the demand label, flags valid responses

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Script 02 — weather and calendar lookup tables

**Files:**
- Modify (full rewrite): `pipeline/02_weather_merge.py`

**Interfaces:**
- Consumes: `fw_config.DATA_START, DATA_END`, `fw_calendar.build_calendar_daily`.
- Produces: `$FW_PIPELINE_DATA/weather_hourly.parquet` — columns `date_hour, temperature_2m, precipitation, windspeed_10m, weathercode, is_severe_weather, is_extreme_heat, is_heat_emergency`, exactly one row per local hour 2021-12-01 00:00 → 2026-06-30 23:00 (40,152 rows). `$FW_PIPELINE_DATA/calendar_daily.parquet` — columns `date, zone_prefix, is_holiday, is_school_day, is_major_event` (1,673 days × 5 = 8,365 rows).

This script calls external APIs, so it has no automated test; its outputs are validated by its own checks here and by script 04's null checks (Task 8). It runs for real in Task 15.

- [ ] **Step 1: Rewrite `pipeline/02_weather_merge.py`**

```python
"""
Script 02 — Weather + calendar lookup tables
FirstWave | GT Hacklytics 2026

External:
  - Open-Meteo historical archive API (free, no key)
  - NYC Permitted Events CSV (NYC Open Data bkfu-528j)
  - Holidays + DOE school calendars (pipeline/fw_calendar.py)

Outputs ($FW_PIPELINE_DATA, default pipeline/data):
  weather_hourly.parquet  — one row per local hour, 2021-12-01 → 2026-06-30
  calendar_daily.parquet  — one row per (date, zone prefix)

Script 04 joins both onto the full zone × hour grid, so zero-incident hours get
weather too. This script no longer rewrites incidents_cleaned.parquet.

MTA: both source datasets (data.ny.gov i8rn-y4np, j6d2-s8m2) are gone, so
subway_disruption_idx is the constant 0.5 set in script 04.

Run: python pipeline/02_weather_merge.py
"""

import datetime as dt
import os
import pathlib
import sys

import pandas as pd
import requests

from fw_calendar import build_calendar_daily
from fw_config import DATA_END, DATA_START

PIPELINE_DATA = pathlib.Path(os.getenv("FW_PIPELINE_DATA", "pipeline/data"))
PIPELINE_DATA.mkdir(parents=True, exist_ok=True)
WEATHER_OUT = PIPELINE_DATA / "weather_hourly.parquet"
CALENDAR_OUT = PIPELINE_DATA / "calendar_daily.parquet"
EVENTS_CACHE = PIPELINE_DATA / "_events_cache.parquet"

SEVERE_WEATHER_CODES = {51, 53, 55, 61, 63, 65, 71, 73, 75, 77, 80, 81, 82, 85, 86, 95, 96, 99}


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — WEATHER (Open-Meteo)
# ══════════════════════════════════════════════════════════════════════════════

def fetch_open_meteo(start_date: dt.date, end_date: dt.date) -> pd.DataFrame:
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": 40.7128,
        "longitude": -74.0060,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "hourly": "temperature_2m,precipitation,windspeed_10m,weathercode",
        "timezone": "America/New_York",
    }
    print(f"  Fetching weather {start_date} → {end_date} ...")
    resp = requests.get(url, params=params, timeout=180)
    resp.raise_for_status()
    df = pd.DataFrame(resp.json()["hourly"])
    df["date_hour"] = pd.to_datetime(df.pop("time"))
    return df


def add_weather_flags(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values("date_hour").reset_index(drop=True)
    df["is_severe_weather"] = df["weathercode"].isin(SEVERE_WEATHER_CODES).astype(int)
    # is_extreme_heat: any hour >= 35 °C (95 °F)
    df["is_extreme_heat"] = (df["temperature_2m"] >= 35.0).astype(int)
    # is_heat_emergency approximation: temp >= 35 °C or prior-24h max >= 32.2 °C
    prior_24h_max = df["temperature_2m"].rolling(window=24, min_periods=1).max()
    df["is_heat_emergency"] = ((df["temperature_2m"] >= 35.0) | (prior_24h_max >= 32.2)).astype(int)
    return df


print("\n── SECTION 1: Weather ──────────────────────────────────────────────────")
chunks = []
for year in range(DATA_START.year, DATA_END.year + 1):
    start = max(DATA_START, dt.date(year, 1, 1))
    end = min(DATA_END, dt.date(year, 12, 31))
    chunks.append(fetch_open_meteo(start, end))
# Flags are computed after concatenation so the 24h rolling max spans year ends.
weather = add_weather_flags(pd.concat(chunks, ignore_index=True))

expected_hours = ((DATA_END - DATA_START).days + 1) * 24
if len(weather) != expected_hours or weather["date_hour"].duplicated().any():
    print(f"ERROR: weather has {len(weather):,} rows "
          f"({weather['date_hour'].duplicated().sum()} duplicate hours), "
          f"expected {expected_hours:,} unique local hours", file=sys.stderr)
    sys.exit(1)
if weather[["temperature_2m", "precipitation", "windspeed_10m"]].isna().any().any():
    print("ERROR: weather has null values", file=sys.stderr)
    sys.exit(1)

weather[[
    "date_hour", "temperature_2m", "precipitation", "windspeed_10m", "weathercode",
    "is_severe_weather", "is_extreme_heat", "is_heat_emergency",
]].to_parquet(WEATHER_OUT, index=False)
print(f"  weather_hourly.parquet: {len(weather):,} rows "
      f"| severe {weather['is_severe_weather'].mean():.1%} "
      f"| heat emergency {weather['is_heat_emergency'].mean():.1%}")


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — NYC SPECIAL EVENTS (NYC Open Data)
# ══════════════════════════════════════════════════════════════════════════════
print("\n── SECTION 2: NYC Special Events ───────────────────────────────────────")

EVENTS_URL = "https://data.cityofnewyork.us/api/views/bkfu-528j/rows.csv?accessType=DOWNLOAD"

if EVENTS_CACHE.exists():
    print("  Loading events from cache...")
    events_raw = pd.read_parquet(EVENTS_CACHE)
else:
    print("  Downloading NYC Permitted Events...")
    try:
        events_raw = pd.read_csv(EVENTS_URL, low_memory=False)
        events_raw.columns = (
            events_raw.columns.str.lower()
            .str.replace(r"[^a-z0-9]+", "_", regex=True)
            .str.strip("_")
        )
        events_raw.to_parquet(EVENTS_CACHE, index=False)
        print(f"  Downloaded {len(events_raw):,} rows, cached to {EVENTS_CACHE.name}")
    except Exception as e:
        print(f"  WARNING: events download failed ({e}); is_major_event will be 0 everywhere.")
        events_raw = None

# Event types that meaningfully raise EMS demand (no construction/maintenance/film).
MAJOR_EVENT_TYPES = {
    "Special Event", "Farmers Market", "Fair/Festival", "Festival",
    "Athletic Event", "Concert", "Parade", "Street Fair", "Block Party",
    "Run/Walk/Race", "Demonstration/Rally",
}
BOROUGH_TO_PREFIX = {
    "Manhattan": "M", "Bronx": "B", "Brooklyn": "K", "Queens": "Q", "Staten Island": "S",
}

event_days = pd.DataFrame(columns=["event_date", "zone_prefix"])
if events_raw is not None:
    start_col = next((c for c in events_raw.columns if "start" in c and "date" in c), None)
    end_col = next((c for c in events_raw.columns if "end" in c and "date" in c), None)
    type_col = next((c for c in events_raw.columns if "type" in c), None)
    boro_col = next((c for c in events_raw.columns if "borough" in c), None)

    if start_col and end_col and boro_col:
        ev = events_raw.copy()
        ev[start_col] = pd.to_datetime(ev[start_col], errors="coerce")
        ev[end_col] = pd.to_datetime(ev[end_col], errors="coerce")
        if type_col:
            ev = ev[ev[type_col].isin(MAJOR_EVENT_TYPES)]
        ev = ev.dropna(subset=[start_col, end_col, boro_col])
        ev = ev[(ev[end_col] >= pd.Timestamp(DATA_START)) & (ev[start_col] <= pd.Timestamp(DATA_END))]

        rows = set()
        for s, e, boro in zip(ev[start_col], ev[end_col], ev[boro_col]):
            prefix = BOROUGH_TO_PREFIX.get(str(boro).strip())
            if prefix is None:
                continue
            day = max(s.date(), DATA_START)
            while day <= min(e.date(), DATA_END):
                rows.add((day, prefix))
                day += dt.timedelta(days=1)
        event_days = pd.DataFrame(sorted(rows), columns=["event_date", "zone_prefix"])
        print(f"  Major event (date × borough) combinations: {len(event_days):,}")
    else:
        print(f"  WARNING: could not identify event columns. Found: {list(events_raw.columns[:10])}")


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — CALENDAR TABLE
# ══════════════════════════════════════════════════════════════════════════════
print("\n── SECTION 3: calendar_daily ───────────────────────────────────────────")
calendar = build_calendar_daily(DATA_START, DATA_END, event_days)
calendar.to_parquet(CALENDAR_OUT, index=False)

per_day = calendar[calendar["zone_prefix"] == "B"]
weekdays = per_day[pd.to_datetime(per_day["date"]).dt.dayofweek < 5]
print(f"  calendar_daily.parquet: {len(calendar):,} rows")
print(f"  Holidays: {per_day['is_holiday'].sum()} days")
print(f"  School days: {per_day['is_school_day'].sum()} "
      f"({weekdays['is_school_day'].mean():.0%} of weekdays; expect ~65–75%)")
print(f"  Major-event rows: {calendar['is_major_event'].mean():.1%}")

print()
print("=" * 60)
print("  Next: python pipeline/03_spatial_join.py")
print("=" * 60)
```

- [ ] **Step 2: Syntax check**

Run: `pipeline/.venv/bin/python -m py_compile pipeline/02_weather_merge.py && echo OK`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add pipeline/02_weather_merge.py
git commit -m "feat(pipeline): 02 writes weather_hourly + calendar_daily lookup tables

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Script 04 — grid, lags, artifacts

**Files:**
- Modify (full rewrite): `pipeline/04_aggregate.py`
- Test: `pipeline/tests/test_04_05_smoke.py` (first half; Task 9 extends it)

**Interfaces:**
- Consumes: `fw_config.*`, `fw_grid.create_counts/create_grid/add_lags`, `models.lag_features.to_wide/build_lag_features` (via backend on `sys.path`). Inputs: `incidents_cleaned.parquet` (with `svi_score` from script 03), `weather_hourly.parquet`, `calendar_daily.parquet`.
- Produces:
  - `$FW_PIPELINE_DATA/training_grid.parquet` — `INCIDENT_DISPATCH_AREA, date_hour, incident_count, <7 lags>, date, year, month, dayofweek, hour, is_weekend, hour_sin, hour_cos, dow_sin, dow_cos, month_sin, month_cos, temperature_2m, precipitation, windspeed_10m, is_severe_weather, is_extreme_heat, is_heat_emergency, is_holiday, is_school_day, is_major_event, subway_disruption_idx, split`. 1,223,880 rows on the real window.
  - `$FW_ARTIFACTS_DIR/zone_baselines.parquet` (5,208 rows), `zone_stats.parquet` (31), `hourly_counts.parquet` (429,288), `calendar_daily.parquet` (2,730).

- [ ] **Step 1: Write the failing smoke test** — `pipeline/tests/test_04_05_smoke.py`

```python
"""
End-to-end smoke test for scripts 04 and 05 on synthetic data spanning the real
data window. Incidents follow a zone-level day-to-day random walk so lags carry
signal.
"""
import datetime as dt
import os
import pathlib
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

from fw_calendar import build_calendar_daily
from fw_config import DATA_END, DATA_START, VALID_ZONES, ZONE_PREFIX_BOROUGH

REPO = pathlib.Path(__file__).resolve().parents[2]
SVI = {z: 0.2 + 0.02 * i for i, z in enumerate(VALID_ZONES)}


def _write_inputs(data_dir: pathlib.Path) -> None:
    rng = np.random.default_rng(0)
    hours = pd.date_range(pd.Timestamp(DATA_START), pd.Timestamp(DATA_END) + pd.Timedelta(hours=23), freq="h")
    n_days = len(hours) // 24
    hour_profile = 0.5 + 0.5 * np.sin(2 * np.pi * (hours.hour.to_numpy() - 8) / 24) + 0.5

    frames = []
    for zi, zone in enumerate(VALID_ZONES):
        walk = np.exp(np.cumsum(rng.normal(0, 0.08, n_days)))
        rate = (0.3 + 0.05 * zi) * hour_profile * np.repeat(walk / walk.mean(), 24)
        n = rng.poisson(rate)
        ts = np.repeat(hours.values, n)
        k = len(ts)
        frames.append(pd.DataFrame({
            "INCIDENT_DISPATCH_AREA": zone,
            "BOROUGH": ZONE_PREFIX_BOROUGH[zone[0]],
            "date_hour": ts,
            "INCIDENT_RESPONSE_SECONDS_QY": rng.uniform(200, 900, k),
            "INCIDENT_TRAVEL_TM_SECONDS_QY": rng.uniform(100, 600, k),
            "DISPATCH_RESPONSE_SECONDS_QY": rng.uniform(20, 300, k),
            "is_high_acuity": rng.integers(0, 2, k),
            "is_held": rng.integers(0, 2, k),
            "is_valid_response": (rng.random(k) < 0.95).astype(int),
            "svi_score": SVI[zone],
        }))
    inc = pd.concat(frames, ignore_index=True)
    ts = pd.to_datetime(inc["date_hour"])
    split = np.select(
        [ts < "2022-01-01", ts < "2024-10-01", ts < "2025-01-01", ts < "2026-01-01"],
        ["history", "train", "valid", "test"], default="test_recent")
    inc["split"] = split
    inc.to_parquet(data_dir / "incidents_cleaned.parquet", index=False)

    pd.DataFrame({
        "date_hour": hours,
        "temperature_2m": 15.0, "precipitation": 0.0, "windspeed_10m": 10.0, "weathercode": 0,
        "is_severe_weather": 0, "is_extreme_heat": 0, "is_heat_emergency": 0,
    }).to_parquet(data_dir / "weather_hourly.parquet", index=False)

    build_calendar_daily(DATA_START, DATA_END, pd.DataFrame(columns=["event_date", "zone_prefix"])) \
        .to_parquet(data_dir / "calendar_daily.parquet", index=False)


@pytest.fixture(scope="module")
def run_dirs(tmp_path_factory):
    root = tmp_path_factory.mktemp("smoke")
    data_dir, art_dir = root / "data", root / "artifacts"
    data_dir.mkdir()
    art_dir.mkdir()
    _write_inputs(data_dir)
    env = {**os.environ, "FW_PIPELINE_DATA": str(data_dir), "FW_ARTIFACTS_DIR": str(art_dir)}
    r = subprocess.run([sys.executable, "pipeline/04_aggregate.py"],
                       cwd=REPO, env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-4000:] + r.stderr[-4000:]
    return data_dir, art_dir, env


def test_04_outputs(run_dirs):
    data_dir, art_dir, _ = run_dirs
    grid = pd.read_parquet(data_dir / "training_grid.parquet")
    assert len(grid) == 1_223_880
    assert grid["split"].value_counts().to_dict() == {
        "train": 746_976, "test": 271_560, "test_recent": 134_664,
        "valid": 68_448, "history": 2_232}
    assert grid.drop(columns=["split"]).isna().sum().sum() == 0
    assert len(pd.read_parquet(art_dir / "zone_baselines.parquet")) == 5_208
    assert len(pd.read_parquet(art_dir / "zone_stats.parquet")) == 31
    hc = pd.read_parquet(art_dir / "hourly_counts.parquet")
    assert len(hc) == 429_288
    assert hc["date_hour"].min() == pd.Timestamp("2024-12-01 00:00")
    assert hc["date_hour"].max() == pd.Timestamp("2026-06-30 23:00")
    assert len(pd.read_parquet(art_dir / "calendar_daily.parquet")) == 2_730
```

- [ ] **Step 2: Run the smoke test to verify it fails**

Run: `pipeline/.venv/bin/python -m pytest pipeline/tests/test_04_05_smoke.py -v`
Expected: FAIL — script 04 exits non-zero (old script expects enrichment columns in incidents).

- [ ] **Step 3: Rewrite `pipeline/04_aggregate.py`**

```python
"""
Script 04 — Zone × hour grid, lag features, artifacts
FirstWave | GT Hacklytics 2026

Inputs ($FW_PIPELINE_DATA, default pipeline/data):
  incidents_cleaned.parquet (01 + 03), weather_hourly.parquet, calendar_daily.parquet (02)
Outputs:
  $FW_PIPELINE_DATA/training_grid.parquet          one row per (zone, local hour), lags + features
  $FW_ARTIFACTS_DIR/zone_baselines.parquet         mean hourly count (incl. zeros), train split
  $FW_ARTIFACTS_DIR/zone_stats.parquet             per-zone response stats, train + valid responses
  $FW_ARTIFACTS_DIR/hourly_counts.parquet          replay lag source, 2024-12-01 → 2026-06-30
  $FW_ARTIFACTS_DIR/calendar_daily.parquet         replay calendar flags, 2025-01-01 → 2026-06-30

Run: python pipeline/04_aggregate.py
"""

import math
import os
import pathlib
import sys

import duckdb
import pandas as pd

from fw_config import (
    DATA_END, DATA_START, HOURLY_COUNTS_START, LAG_FEATURE_COLS, REPLAY_START,
    VALID_ZONES, split_case_sql,
)
from fw_grid import add_lags, create_counts, create_grid

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "backend"))
from models.lag_features import build_lag_features, to_wide  # noqa: E402  (parity check)

PIPELINE_DATA = pathlib.Path(os.getenv("FW_PIPELINE_DATA", "pipeline/data"))
ARTIFACTS_DIR = pathlib.Path(os.getenv("FW_ARTIFACTS_DIR", "backend/artifacts"))
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

CLEANED = PIPELINE_DATA / "incidents_cleaned.parquet"
WEATHER = PIPELINE_DATA / "weather_hourly.parquet"
CALENDAR = PIPELINE_DATA / "calendar_daily.parquet"
GRID_OUT = PIPELINE_DATA / "training_grid.parquet"
BASELINE = ARTIFACTS_DIR / "zone_baselines.parquet"
STATS = ARTIFACTS_DIR / "zone_stats.parquet"
HOURLY_OUT = ARTIFACTS_DIR / "hourly_counts.parquet"
CAL_OUT = ARTIFACTS_DIR / "calendar_daily.parquet"

for p in (CLEANED, WEATHER, CALENDAR):
    if not p.exists():
        print(f"ERROR: {p} not found. Run scripts 01–03 first.", file=sys.stderr)
        sys.exit(1)

conn = duckdb.connect()
cols = [d[0] for d in conn.execute(f"SELECT * FROM read_parquet('{CLEANED}') LIMIT 0").description]
for needed in ("is_valid_response", "svi_score", "split", "date_hour"):
    if needed not in cols:
        print(f"ERROR: incidents_cleaned is missing '{needed}' — re-run 01 and 03.", file=sys.stderr)
        sys.exit(1)

PI = math.pi

# ── Step 1: counts → gap-free grid → lags ─────────────────────────────────────
print("Step 1: zone × hour grid with lags...")
create_counts(conn, str(CLEANED))
n_grid = create_grid(conn, VALID_ZONES, DATA_START, DATA_END)
add_lags(conn)
print(f"  grid: {n_grid:,} rows (31 zones × every local hour, zeros included)")

# ── Step 2: training grid (features joined onto every hour) ───────────────────
print("Step 2: joining weather + calendar onto the grid...")
lag_select = ", ".join(f"g.{c}" for c in LAG_FEATURE_COLS)
conn.execute(f"""
COPY (
    WITH t AS (
        SELECT g.INCIDENT_DISPATCH_AREA, g.date_hour, g.incident_count, {lag_select},
               CAST(g.date_hour AS DATE)                          AS date,
               EXTRACT(year  FROM g.date_hour)::INTEGER           AS year,
               EXTRACT(month FROM g.date_hour)::INTEGER           AS month,
               (EXTRACT(dow  FROM g.date_hour)::INTEGER + 6) % 7  AS dayofweek,
               EXTRACT(hour  FROM g.date_hour)::INTEGER           AS hour
        FROM grid_lags g
        WHERE g.roll_4w_same_hour_dow IS NOT NULL
    )
    SELECT t.*,
           CASE WHEN t.dayofweek IN (5, 6) THEN 1 ELSE 0 END AS is_weekend,
           SIN(2 * {PI} * t.hour / 24)       AS hour_sin,
           COS(2 * {PI} * t.hour / 24)       AS hour_cos,
           SIN(2 * {PI} * t.dayofweek / 7)   AS dow_sin,
           COS(2 * {PI} * t.dayofweek / 7)   AS dow_cos,
           SIN(2 * {PI} * t.month / 12)      AS month_sin,
           COS(2 * {PI} * t.month / 12)      AS month_cos,
           w.temperature_2m, w.precipitation, w.windspeed_10m,
           w.is_severe_weather, w.is_extreme_heat, w.is_heat_emergency,
           c.is_holiday, c.is_school_day, c.is_major_event,
           0.5 AS subway_disruption_idx,
           {split_case_sql('t.date_hour')} AS split
    FROM t
    LEFT JOIN read_parquet('{WEATHER}') w ON w.date_hour = t.date_hour
    LEFT JOIN read_parquet('{CALENDAR}') c
           ON c.date = t.date AND c.zone_prefix = LEFT(t.INCIDENT_DISPATCH_AREA, 1)
) TO '{GRID_OUT}' (FORMAT PARQUET, COMPRESSION SNAPPY)
""")

nulls = conn.execute(f"""
    SELECT SUM(CASE WHEN temperature_2m IS NULL THEN 1 ELSE 0 END),
           SUM(CASE WHEN is_school_day  IS NULL THEN 1 ELSE 0 END),
           COUNT(*)
    FROM read_parquet('{GRID_OUT}')
""").fetchone()
if nulls[0] or nulls[1]:
    print(f"ERROR: {nulls[0]:,} rows missing weather, {nulls[1]:,} missing calendar — "
          "check date_hour alignment with 02 outputs.", file=sys.stderr)
    sys.exit(1)
print(f"  training_grid.parquet: {nulls[2]:,} rows, no missing weather/calendar")

# ── Step 3: zone_baselines (train only, zeros included) ───────────────────────
conn.execute(f"""
COPY (
    SELECT INCIDENT_DISPATCH_AREA, hour, dayofweek,
           AVG(incident_count) AS zone_baseline_avg
    FROM read_parquet('{GRID_OUT}')
    WHERE split = 'train'
    GROUP BY INCIDENT_DISPATCH_AREA, hour, dayofweek
) TO '{BASELINE}' (FORMAT PARQUET, COMPRESSION SNAPPY)
""")

# ── Step 4: zone_stats (train incidents with a valid response time) ───────────
conn.execute(f"""
COPY (
    SELECT INCIDENT_DISPATCH_AREA, BOROUGH,
           AVG(svi_score)                     AS svi_score,
           AVG(INCIDENT_RESPONSE_SECONDS_QY)  AS avg_response_seconds,
           AVG(INCIDENT_TRAVEL_TM_SECONDS_QY) AS avg_travel_seconds,
           AVG(DISPATCH_RESPONSE_SECONDS_QY)  AS avg_dispatch_seconds,
           AVG(is_high_acuity)                AS high_acuity_ratio,
           AVG(is_held)                       AS held_ratio,
           COUNT(*)                           AS total_incidents
    FROM read_parquet('{CLEANED}')
    WHERE split = 'train' AND is_valid_response = 1
    GROUP BY INCIDENT_DISPATCH_AREA, BOROUGH
) TO '{STATS}' (FORMAT PARQUET, COMPRESSION SNAPPY)
""")

# ── Step 5: replay artifacts ───────────────────────────────────────────────────
conn.execute(f"""
COPY (
    SELECT INCIDENT_DISPATCH_AREA, date_hour, incident_count
    FROM grid
    WHERE date_hour >= TIMESTAMP '{HOURLY_COUNTS_START} 00:00:00'
    ORDER BY INCIDENT_DISPATCH_AREA, date_hour
) TO '{HOURLY_OUT}' (FORMAT PARQUET, COMPRESSION SNAPPY)
""")
conn.execute(f"""
COPY (
    SELECT * FROM read_parquet('{CALENDAR}') WHERE date >= DATE '{REPLAY_START}'
) TO '{CAL_OUT}' (FORMAT PARQUET, COMPRESSION SNAPPY)
""")

# ── Step 6: validation ─────────────────────────────────────────────────────────
counts = {
    "zone_baselines": conn.execute(f"SELECT COUNT(*) FROM read_parquet('{BASELINE}')").fetchone()[0],
    "zone_stats": conn.execute(f"SELECT COUNT(*) FROM read_parquet('{STATS}')").fetchone()[0],
    "hourly_counts": conn.execute(f"SELECT COUNT(*) FROM read_parquet('{HOURLY_OUT}')").fetchone()[0],
    "calendar_daily": conn.execute(f"SELECT COUNT(*) FROM read_parquet('{CAL_OUT}')").fetchone()[0],
}
expected = {"zone_baselines": 31 * 24 * 7, "zone_stats": 31,
            "hourly_counts": 31 * ((DATA_END - HOURLY_COUNTS_START).days + 1) * 24,
            "calendar_daily": 5 * ((DATA_END - REPLAY_START).days + 1)}

print()
print("=" * 60)
print("  SCRIPT 04 — VALIDATION")
print("=" * 60)
ok = True
for name, n in counts.items():
    flag = "✓" if n == expected[name] else "⚠"
    ok &= n == expected[name]
    print(f"  {flag} {name:<16} {n:>10,}  (expect {expected[name]:,})")

by_split = conn.execute(f"""
    SELECT split, COUNT(*) AS rows, ROUND(AVG(incident_count), 3) AS mean_count
    FROM read_parquet('{GRID_OUT}') GROUP BY split ORDER BY MIN(date_hour)
""").fetchdf()
print("\n  Rows and mean hourly count by split (mean should NOT trend down):")
print(by_split.to_string(index=False))

# Train/serve parity on the real data: serving-side lags from the hourly_counts
# artifact must equal the training grid's lag columns.
wide = to_wide(pd.read_parquet(HOURLY_OUT))
# Filter in a subquery: DuckDB applies USING SAMPLE before WHERE.
sample = conn.execute(f"""
    SELECT * FROM (
        SELECT INCIDENT_DISPATCH_AREA, date_hour, {', '.join(LAG_FEATURE_COLS)}
        FROM read_parquet('{GRID_OUT}') WHERE split IN ('test', 'test_recent')
    ) USING SAMPLE reservoir(200 ROWS) REPEATABLE (42)
""").df()
mismatches = 0
for row in sample.itertuples(index=False):
    served = build_lag_features(wide, pd.Timestamp(row.date_hour)).loc[row.INCIDENT_DISPATCH_AREA]
    for c in LAG_FEATURE_COLS:
        if abs(served[c] - getattr(row, c)) > 1e-9:
            mismatches += 1
print(f"\n  {'✓' if mismatches == 0 else '⚠'} train/serve lag parity on 200 rows: {mismatches} mismatches")
ok &= mismatches == 0

if not ok:
    print("\nERROR: validation failed — see ⚠ lines above.", file=sys.stderr)
    sys.exit(1)
print("=" * 60)
print("  Next: python pipeline/05_train_demand_model.py")
```

- [ ] **Step 4: Run the smoke test to verify it passes**

Run: `pipeline/.venv/bin/python -m pytest pipeline/tests/test_04_05_smoke.py -v`
Expected: 1 passed (`test_04_outputs`)

- [ ] **Step 5: Commit**

```bash
git add pipeline/04_aggregate.py pipeline/tests/test_04_05_smoke.py
git commit -m "feat(pipeline): 04 builds hourly training grid with lags + replay artifacts

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Script 05 — train, compare, gate

**Files:**
- Modify (full rewrite): `pipeline/05_train_demand_model.py`
- Modify: `pipeline/tests/test_04_05_smoke.py` (add `test_05_trains_and_reports`)

**Interfaces:**
- Consumes: `fw_config.FEATURE_COLS, BASE_FEATURE_COLS, ZONE_PREFIX_BOROUGH, SPLIT_STARTS, DATA_START, DATA_END`, `fw_eval.score/rmse_by_group/deployment_gate`, `models.demand_forecaster.DemandForecaster` (Task 10 signature; the replay check is guarded so this task does not depend on Task 10 landing first — see Step 3), Task 8 outputs.
- Produces: on gate pass, `$FW_ARTIFACTS_DIR/demand_model.pkl` (XGBRegressor, `feature_names_in_` = `FEATURE_COLS`) and `$FW_ARTIFACTS_DIR/model_metrics.json`, exit 0. On gate fail, `$FW_PIPELINE_DATA/demand_model_candidate.pkl` and `$FW_PIPELINE_DATA/model_metrics_candidate.json`, exit 1. Metrics JSON keys: `trained_at, objective, best_iteration, feature_cols, splits, valid_rmse_by_objective, test, test_recent, test_rmse_by_borough, test_rmse_by_hour, gate`.

- [ ] **Step 1: Add the failing test to `pipeline/tests/test_04_05_smoke.py`**

```python
import json

import joblib


def test_05_trains_and_reports(run_dirs):
    data_dir, art_dir, env = run_dirs
    r = subprocess.run([sys.executable, "pipeline/05_train_demand_model.py", "--max-trees", "40"],
                       cwd=REPO, env=env, capture_output=True, text=True)
    assert r.returncode in (0, 1), r.stdout[-4000:] + r.stderr[-4000:]
    if r.returncode == 0:
        metrics = json.loads((art_dir / "model_metrics.json").read_text())
        model = joblib.load(art_dir / "demand_model.pkl")
        assert list(model.feature_names_in_) == metrics["feature_cols"]
        assert len(metrics["feature_cols"]) == 28
        assert metrics["gate"]["passed"] is True
    else:
        metrics = json.loads((data_dir / "model_metrics_candidate.json").read_text())
        assert (data_dir / "demand_model_candidate.pkl").exists()
        assert not (art_dir / "demand_model.pkl").exists()
        assert metrics["gate"]["passed"] is False
    assert set(metrics["test"]) == {"lag", "no_lag", "naive_168h", "baseline_avg"}
    assert set(metrics["test"]["lag"]) == {"rmse", "mae", "poisson_deviance"}
    assert len(metrics["test_rmse_by_hour"]["lag"]) == 24
    assert metrics["objective"] in ("reg:squarederror", "count:poisson")
```

- [ ] **Step 2: Run to verify it fails**

Run: `pipeline/.venv/bin/python -m pytest pipeline/tests/test_04_05_smoke.py::test_05_trains_and_reports -v`
Expected: FAIL — old script reads `incidents_aggregated.parquet` and exits 1 without a metrics file.

- [ ] **Step 3: Rewrite `pipeline/05_train_demand_model.py`**

```python
"""
Script 05 — XGBoost demand forecaster with lag features
FirstWave | GT Hacklytics 2026

Input:  $FW_PIPELINE_DATA/training_grid.parquet, $FW_ARTIFACTS_DIR/zone_baselines.parquet,
        $FW_ARTIFACTS_DIR/zone_stats.parquet (all from script 04)
Output: gate passed → $FW_ARTIFACTS_DIR/demand_model.pkl + model_metrics.json (exit 0)
        gate failed → $FW_PIPELINE_DATA/demand_model_candidate.pkl +
                      model_metrics_candidate.json (exit 1; artifacts untouched)

Early stopping and objective choice use the `valid` split only. `test` (2025)
and `test_recent` (2026 H1) are scored once.

Run: python pipeline/05_train_demand_model.py [--max-trees 2000]
"""

import argparse
import datetime as dt
import json
import os
import pathlib
import sys

import joblib
import numpy as np
import pandas as pd
import xgboost as xgb

from fw_config import (
    BASE_FEATURE_COLS, DATA_END, DATA_START, FEATURE_COLS, SPLIT_STARTS, ZONE_PREFIX_BOROUGH,
)
from fw_eval import deployment_gate, rmse_by_group, score

parser = argparse.ArgumentParser()
parser.add_argument("--max-trees", type=int, default=2000)
args = parser.parse_args()

PIPELINE_DATA = pathlib.Path(os.getenv("FW_PIPELINE_DATA", "pipeline/data"))
ARTIFACTS_DIR = pathlib.Path(os.getenv("FW_ARTIFACTS_DIR", "backend/artifacts"))
GRID_PQ = PIPELINE_DATA / "training_grid.parquet"
BASELINE_PQ = ARTIFACTS_DIR / "zone_baselines.parquet"
STATS_PQ = ARTIFACTS_DIR / "zone_stats.parquet"

for p in (GRID_PQ, BASELINE_PQ, STATS_PQ):
    if not p.exists():
        print(f"ERROR: {p} not found. Run 04_aggregate.py first.", file=sys.stderr)
        sys.exit(1)

ZONE = "INCIDENT_DISPATCH_AREA"
OBJECTIVES = ("reg:squarederror", "count:poisson")

# ── Step 1: load + merge ───────────────────────────────────────────────────────
grid = pd.read_parquet(GRID_PQ)
grid = grid.merge(pd.read_parquet(BASELINE_PQ), on=[ZONE, "hour", "dayofweek"], how="left")
grid = grid.merge(
    pd.read_parquet(STATS_PQ)[[ZONE, "svi_score", "high_acuity_ratio", "held_ratio"]],
    on=ZONE, how="left",
)
null_counts = grid[FEATURE_COLS].isna().sum()
if null_counts.any():
    print("ERROR: nulls in features:\n" + null_counts[null_counts > 0].to_string(), file=sys.stderr)
    sys.exit(1)
grid["BOROUGH"] = grid[ZONE].str[0].map(ZONE_PREFIX_BOROUGH)

parts = {s: grid[grid["split"] == s] for s in ("train", "valid", "test", "test_recent")}
for s, df in parts.items():
    print(f"  {s:<12} {len(df):>10,} rows   mean count {df['incident_count'].mean():.3f}")

PARAMS = {
    "n_estimators": args.max_trees,
    "max_depth": 6,
    "learning_rate": 0.05,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "random_state": 42,
    "n_jobs": -1,
    "tree_method": "hist",
    "early_stopping_rounds": 50,
}


def fit(features: list[str], objective: str) -> xgb.XGBRegressor:
    model = xgb.XGBRegressor(objective=objective, **PARAMS)
    model.fit(
        parts["train"][features], parts["train"]["incident_count"],
        eval_set=[(parts["valid"][features], parts["valid"]["incident_count"])],
        verbose=200,
    )
    return model


def predict(model, features, df) -> np.ndarray:
    return np.clip(model.predict(df[features]), 0, None)


# ── Step 2: pick the objective on `valid` ──────────────────────────────────────
candidates, valid_rmse = {}, {}
for obj in OBJECTIVES:
    print(f"\nTraining lag model, objective={obj} ...")
    candidates[obj] = fit(FEATURE_COLS, obj)
    valid_rmse[obj] = score(parts["valid"]["incident_count"],
                            predict(candidates[obj], FEATURE_COLS, parts["valid"]))["rmse"]
    print(f"  valid RMSE {valid_rmse[obj]:.4f}   best_iteration {candidates[obj].best_iteration}")
objective = min(valid_rmse, key=valid_rmse.get)
lag_model = candidates[objective]

print(f"\nTraining no-lag reference, objective={objective} ...")
no_lag_model = fit(BASE_FEATURE_COLS, objective)


# ── Step 3: score test + test_recent ───────────────────────────────────────────
def all_preds(df) -> dict:
    return {
        "lag": predict(lag_model, FEATURE_COLS, df),
        "no_lag": predict(no_lag_model, BASE_FEATURE_COLS, df),
        "naive_168h": df["lag_168h"].to_numpy(dtype=float),
        "baseline_avg": df["zone_baseline_avg"].to_numpy(dtype=float),
    }


results = {}
for split in ("test", "test_recent"):
    y = parts[split]["incident_count"]
    results[split] = {name: score(y, p) for name, p in all_preds(parts[split]).items()}

test_df = parts["test"]
test_preds = all_preds(test_df)
by_borough = {n: rmse_by_group(test_df["incident_count"], test_preds[n], test_df["BOROUGH"])
              for n in ("lag", "no_lag")}
by_hour = {n: [rmse_by_group(test_df["incident_count"], test_preds[n], test_df["hour"])[str(h)]
               for h in range(24)] for n in ("lag", "no_lag")}
gate = deployment_gate(results["test"]["lag"]["rmse"], results["test"]["no_lag"]["rmse"])

split_bounds = [start for _, start in SPLIT_STARTS[1:]] + [DATA_END + dt.timedelta(days=1)]
metrics = {
    "trained_at": dt.datetime.now().isoformat(timespec="seconds"),
    "objective": objective,
    "best_iteration": int(lag_model.best_iteration),
    "feature_cols": FEATURE_COLS,
    "splits": {name: [str(start), str(end - dt.timedelta(days=1))]
               for (name, start), end in zip(SPLIT_STARTS, split_bounds)},
    "data_window": [str(DATA_START), str(DATA_END)],
    "valid_rmse_by_objective": valid_rmse,
    "test": results["test"],
    "test_recent": results["test_recent"],
    "test_rmse_by_borough": by_borough,
    "test_rmse_by_hour": by_hour,
    "gate": gate,
}

# ── Step 4: report ─────────────────────────────────────────────────────────────
print()
print("=" * 72)
print("  FIRSTWAVE DEMAND MODEL — RESULTS")
print("=" * 72)
print(f"  objective {objective}   best_iteration {lag_model.best_iteration}")
for split in ("test", "test_recent"):
    print(f"\n  {split}:")
    print(f"    {'model':<14}{'RMSE':>10}{'MAE':>10}{'Poisson dev':>14}")
    for name, s in results[split].items():
        print(f"    {name:<14}{s['rmse']:>10.4f}{s['mae']:>10.4f}{s['poisson_deviance']:>14.4f}")
print("\n  2025 RMSE by borough (lag / no_lag):")
for b in sorted(by_borough["lag"]):
    print(f"    {b:<26}{by_borough['lag'][b]:>8.4f}{by_borough['no_lag'][b]:>10.4f}")
fi = pd.Series(lag_model.feature_importances_, index=FEATURE_COLS).sort_values(ascending=False)
print("\n  Top 10 features by gain share:")
print(fi.head(10).to_string())
print(f"\n  Deployment gate: improvement {gate['improvement']:.2%} "
      f"(need ≥ {gate['threshold']:.0%}) → {'PASSED' if gate['passed'] else 'FAILED'}")

if not gate["passed"]:
    joblib.dump(lag_model, PIPELINE_DATA / "demand_model_candidate.pkl")
    (PIPELINE_DATA / "model_metrics_candidate.json").write_text(json.dumps(metrics, indent=2))
    print("\n  Gate failed: backend/artifacts untouched. Candidate saved to pipeline/data/.")
    sys.exit(1)

joblib.dump(lag_model, ARTIFACTS_DIR / "demand_model.pkl")
(ARTIFACTS_DIR / "model_metrics.json").write_text(json.dumps(metrics, indent=2))
print(f"\n  Saved {ARTIFACTS_DIR / 'demand_model.pkl'} and model_metrics.json")

# ── Step 5: replay sanity check through the serving code path ─────────────────
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "backend"))
from models.demand_forecaster import DemandForecaster  # noqa: E402
from models.lag_features import actual_counts, to_wide  # noqa: E402
from models.replay import calendar_to_lookup  # noqa: E402

wide = to_wide(pd.read_parquet(ARTIFACTS_DIR / "hourly_counts.parquet"))
cal = calendar_to_lookup(pd.read_parquet(ARTIFACTS_DIR / "calendar_daily.parquet"))
forecaster = DemandForecaster(lag_model)
zone_stats = pd.read_parquet(STATS_PQ)
baselines = pd.read_parquet(BASELINE_PQ)
totals = {}
for label, day, hour in (("Fri 2025-10-10 20:00", dt.date(2025, 10, 10), 20),
                         ("Mon 2025-10-20 04:00", dt.date(2025, 10, 20), 4)):
    preds = forecaster.predict_all_zones(hour, day.weekday(), day.month, 15.0, 0.0, 10.0,
                                         zone_stats, baselines, replay_date=day,
                                         counts_wide=wide, calendar=cal)
    actual = actual_counts(wide, pd.Timestamp(day) + pd.Timedelta(hours=hour))
    totals[label] = sum(preds.values())
    top = sorted(preds.items(), key=lambda kv: kv[1], reverse=True)[:5]
    print(f"\n  {label}: city total predicted {sum(preds.values()):.1f}, actual {sum(actual.values())}")
    for zone, p in top:
        print(f"    {zone}: predicted {p:.1f}   actual {actual.get(zone)}")
ratio = totals["Fri 2025-10-10 20:00"] / max(totals["Mon 2025-10-20 04:00"], 1e-9)
print(f"\n  {'✓' if ratio > 2 else '⚠'} Friday 8 PM / Monday 4 AM demand ratio: {ratio:.1f}x (expect > 2)")
print("=" * 72)
```

The replay sanity check uses the Task 10 forecaster signature. If Task 10 has not landed yet when this task is executed, run Task 10 first — the smoke test exercises Step 5 on the gate-pass path.

- [ ] **Step 4: Run to verify it passes**

Run: `pipeline/.venv/bin/python -m pytest pipeline/tests/test_04_05_smoke.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add pipeline/05_train_demand_model.py pipeline/tests/test_04_05_smoke.py
git commit -m "feat(pipeline): 05 trains lag model on valid-set early stopping, scores refs, gates deploy

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Backend forecaster with lags and calendar

**Execute this task before Task 9** (Task 9's replay check calls it).

**Files:**
- Modify: `backend/models/demand_forecaster.py` (replace the `DemandForecaster` class; add imports, `FEATURE_COLS_WITH_LAGS`, `LagArtifactMissing`)
- Test: `backend/tests/test_demand_forecaster.py`

**Interfaces:**
- Consumes: `models.lag_features.LAG_FEATURES, build_lag_features`, `models.replay.calendar_flags`.
- Produces: `FEATURE_COLS` (unchanged 21), `FEATURE_COLS_WITH_LAGS` (28), `class LagArtifactMissing(RuntimeError)`, `DemandForecaster(model)` with attributes `feature_names: list[str]`, `uses_lags: bool` and methods
  - `build_feature_frame(hour, dow, month, temperature, precipitation, windspeed, zone_stats_df, baselines_df, replay_date=None, counts_wide=None, calendar=None) -> pd.DataFrame` (index = zone)
  - `predict_all_zones(<same params>) -> dict[str, float]`

- [ ] **Step 1: Write the failing test** — `backend/tests/test_demand_forecaster.py`

```python
import datetime as dt

import numpy as np
import pandas as pd
import pytest
import xgboost as xgb

from fixtures_data import synthetic_count, synthetic_hourly_counts
from models.demand_forecaster import (
    FEATURE_COLS, FEATURE_COLS_WITH_LAGS, VALID_ZONES, DemandForecaster, LagArtifactMissing,
)
from models.lag_features import to_wide
from models.replay import calendar_to_lookup

WIDE = to_wide(synthetic_hourly_counts())


def tiny_model(features):
    rng = np.random.default_rng(0)
    X = pd.DataFrame(rng.random((200, len(features))), columns=features)
    m = xgb.XGBRegressor(n_estimators=5, max_depth=2)
    m.fit(X, rng.poisson(3, 200))
    return m


MODEL_21, MODEL_28 = tiny_model(FEATURE_COLS), tiny_model(FEATURE_COLS_WITH_LAGS)
ARGS = (20, 4, 10, 15.0, 0.0, 10.0, None, None)


def test_feature_names_come_from_model():
    assert DemandForecaster(MODEL_21).feature_names == FEATURE_COLS
    assert DemandForecaster(MODEL_21).uses_lags is False
    assert DemandForecaster(MODEL_28).feature_names == FEATURE_COLS_WITH_LAGS
    assert DemandForecaster(MODEL_28).uses_lags is True


def test_old_model_predicts_without_history():
    preds = DemandForecaster(MODEL_21).predict_all_zones(*ARGS)
    assert set(preds) == set(VALID_ZONES)
    assert all(v >= 0 for v in preds.values())


def test_lag_model_requires_history():
    with pytest.raises(LagArtifactMissing):
        DemandForecaster(MODEL_28).predict_all_zones(*ARGS)
    with pytest.raises(LagArtifactMissing):
        DemandForecaster(MODEL_28).predict_all_zones(*ARGS, replay_date=dt.date(2025, 10, 10))


def test_lag_frame_uses_replay_history():
    day = dt.date(2025, 10, 10)
    frame = DemandForecaster(MODEL_28).build_feature_frame(*ARGS, replay_date=day, counts_wide=WIDE)
    target = pd.Timestamp("2025-10-10 20:00")
    assert frame.loc["K7", "lag_1h"] == synthetic_count("K7", target - pd.Timedelta(hours=1))
    assert frame.loc["B2", "lag_168h"] == synthetic_count("B2", target - pd.Timedelta(hours=168))
    assert set(FEATURE_COLS_WITH_LAGS) <= set(frame.columns)
    preds = DemandForecaster(MODEL_28).predict_all_zones(*ARGS, replay_date=day, counts_wide=WIDE)
    assert set(preds) == set(VALID_ZONES)


def test_calendar_flags_applied_per_borough():
    cal = calendar_to_lookup(pd.DataFrame({
        "date": [dt.date(2025, 10, 20)] * 2, "zone_prefix": ["K", "B"],
        "is_holiday": [0, 0], "is_school_day": [0, 0], "is_major_event": [1, 0],
    }))
    frame = DemandForecaster(MODEL_21).build_feature_frame(
        4, 0, 10, 15.0, 0.0, 10.0, None, None, replay_date=dt.date(2025, 10, 20), calendar=cal)
    assert frame.loc["K7", "is_major_event"] == 1
    assert frame.loc["B2", "is_major_event"] == 0
    assert frame.loc["K7", "is_school_day"] == 0
    assert frame.loc["M3", "is_school_day"] == 1     # no row for M -> default


def test_defaults_without_calendar():
    frame = DemandForecaster(MODEL_21).build_feature_frame(*ARGS)
    assert (frame["is_school_day"] == 1).all()
    assert (frame["is_holiday"] == 0).all()
```

- [ ] **Step 2: Run to verify it fails**

Run: `backend/.venv/bin/python -m pytest backend/tests/test_demand_forecaster.py -v`
Expected: FAIL — `ImportError: cannot import name 'FEATURE_COLS_WITH_LAGS'`

- [ ] **Step 3: Update `backend/models/demand_forecaster.py`**

Replace the three import lines at the top with:
```python
import math

import numpy as np
import pandas as pd

from models.lag_features import LAG_FEATURES, build_lag_features
from models.replay import calendar_flags
```

Directly after the `FEATURE_COLS = [...]` list add:
```python
FEATURE_COLS_WITH_LAGS = FEATURE_COLS + LAG_FEATURES
```

Replace the whole `class DemandForecaster` (from `class DemandForecaster:` to the end of the file) with:
```python
class LagArtifactMissing(RuntimeError):
    """The model expects lag features but no replay date / hourly counts were given."""


class DemandForecaster:
    def __init__(self, model):
        self.model = model
        names = getattr(model, "feature_names_in_", None)
        self.feature_names = [str(n) for n in names] if names is not None else list(FEATURE_COLS)
        self.uses_lags = any(name in LAG_FEATURES for name in self.feature_names)

    def build_feature_frame(
        self,
        hour: int,
        dow: int,
        month: int,
        temperature: float,
        precipitation: float,
        windspeed: float,
        zone_stats_df,
        baselines_df,
        replay_date=None,
        counts_wide=None,
        calendar=None,
    ) -> pd.DataFrame:
        """31-row feature frame indexed by zone."""
        hour_sin = math.sin(2 * math.pi * hour / 24)
        hour_cos = math.cos(2 * math.pi * hour / 24)
        dow_sin = math.sin(2 * math.pi * dow / 7)
        dow_cos = math.cos(2 * math.pi * dow / 7)
        month_sin = math.sin(2 * math.pi * month / 12)
        month_cos = math.cos(2 * math.pi * month / 12)
        is_weekend = 1 if dow in (5, 6) else 0
        is_severe_weather = 1 if precipitation > 5 else 0

        rows = []
        for zone in VALID_ZONES:
            svi = SVI_DEFAULTS[zone]
            high_acuity = HIGH_ACUITY_DEFAULTS[zone]
            held = HELD_RATIO_DEFAULTS[zone]
            baseline = 5.0

            if zone_stats_df is not None:
                row = zone_stats_df[zone_stats_df["INCIDENT_DISPATCH_AREA"] == zone]
                if not row.empty:
                    svi = float(row["svi_score"].iloc[0]) if "svi_score" in row.columns else svi
                    high_acuity = float(row["high_acuity_ratio"].iloc[0]) if "high_acuity_ratio" in row.columns else high_acuity
                    held = float(row["held_ratio"].iloc[0]) if "held_ratio" in row.columns else held

            if baselines_df is not None:
                bl_row = baselines_df[
                    (baselines_df["INCIDENT_DISPATCH_AREA"] == zone) &
                    (baselines_df["hour"] == hour) &
                    (baselines_df["dayofweek"] == dow)
                ]
                if not bl_row.empty:
                    baseline = float(bl_row["zone_baseline_avg"].iloc[0])

            rows.append({
                "zone": zone,
                "hour_sin": hour_sin,
                "hour_cos": hour_cos,
                "dow_sin": dow_sin,
                "dow_cos": dow_cos,
                "month_sin": month_sin,
                "month_cos": month_cos,
                "is_weekend": is_weekend,
                "temperature_2m": temperature,
                "precipitation": precipitation,
                "windspeed_10m": windspeed,
                "is_severe_weather": is_severe_weather,
                "svi_score": svi,
                "zone_baseline_avg": baseline,
                "high_acuity_ratio": high_acuity,
                "held_ratio": held,
                **calendar_flags(calendar, replay_date, zone[0]),
                "is_heat_emergency": int(temperature >= 35.0),
                "is_extreme_heat": int(temperature >= 35.0),
                "subway_disruption_idx": 0.5,
            })

        df = pd.DataFrame(rows).set_index("zone")
        if self.uses_lags:
            if replay_date is None or counts_wide is None:
                raise LagArtifactMissing("model expects lag features: pass replay_date and counts_wide")
            target = pd.Timestamp(replay_date) + pd.Timedelta(hours=hour)
            df = df.join(build_lag_features(counts_wide, target).reindex(VALID_ZONES))
        return df

    def predict_all_zones(
        self,
        hour: int,
        dow: int,
        month: int,
        temperature: float,
        precipitation: float,
        windspeed: float,
        zone_stats_df,
        baselines_df,
        replay_date=None,
        counts_wide=None,
        calendar=None,
    ) -> dict:
        """Returns {zone_code: predicted_count}."""
        df = self.build_feature_frame(
            hour, dow, month, temperature, precipitation, windspeed,
            zone_stats_df, baselines_df, replay_date, counts_wide, calendar,
        )
        preds = np.clip(self.model.predict(df[self.feature_names]), 0, None)
        return {zone: float(p) for zone, p in zip(df.index, preds)}
```

- [ ] **Step 4: Run all backend tests**

Run: `backend/.venv/bin/python -m pytest backend/tests -v`
Expected: all passed (6 new + 20 from Task 4)

- [ ] **Step 5: Commit**

```bash
git add backend/models/demand_forecaster.py backend/tests/test_demand_forecaster.py
git commit -m "feat(backend): forecaster builds lag + calendar features from replay artifacts

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Backend API — `date` param, `actual_count`, artifacts

**Files:**
- Modify: `backend/main.py`
- Modify: `backend/routers/heatmap.py`
- Modify: `backend/routers/staging.py`
- Test: `backend/tests/test_api.py`

**Interfaces:**
- Consumes: `DemandForecaster`, `LagArtifactMissing` (Task 10); `to_wide`, `actual_counts` (Task 4); `resolve_request`, `OutOfReplayRange`, `calendar_to_lookup` (Task 4).
- Produces: `ARTIFACTS` keys `hourly_counts` (wide DataFrame), `calendar_daily` (lookup dict), `model_metrics` (dict); `/health` and `/reload` add `hourly_counts`, `calendar_daily` booleans and `model_metrics`; heatmap/staging accept `date`.

- [ ] **Step 1: Write the failing test** — `backend/tests/test_api.py`

```python
import datetime as dt
import os

import joblib
import numpy as np
import pandas as pd
import pytest
import xgboost as xgb

from fixtures_data import synthetic_count, synthetic_hourly_counts
from models.demand_forecaster import FEATURE_COLS, FEATURE_COLS_WITH_LAGS, VALID_ZONES


def tiny_model(features):
    rng = np.random.default_rng(0)
    X = pd.DataFrame(rng.random((200, len(features))), columns=features)
    m = xgb.XGBRegressor(n_estimators=5, max_depth=2)
    m.fit(X, rng.poisson(3, 200))
    return m


def _write_artifacts(art):
    joblib.dump(tiny_model(FEATURE_COLS_WITH_LAGS), art / "demand_model.pkl")
    pd.DataFrame([
        {"INCIDENT_DISPATCH_AREA": z, "hour": h, "dayofweek": d, "zone_baseline_avg": 2.0}
        for z in VALID_ZONES for h in range(24) for d in range(7)
    ]).to_parquet(art / "zone_baselines.parquet", index=False)
    pd.DataFrame([{
        "INCIDENT_DISPATCH_AREA": z, "BOROUGH": "BRONX", "svi_score": 0.5,
        "avg_response_seconds": 600.0, "avg_travel_seconds": 400.0, "avg_dispatch_seconds": 200.0,
        "high_acuity_ratio": 0.2, "held_ratio": 0.05, "total_incidents": 1000,
    } for z in VALID_ZONES]).to_parquet(art / "zone_stats.parquet", index=False)
    synthetic_hourly_counts().to_parquet(art / "hourly_counts.parquet", index=False)
    pd.DataFrame({
        "date": [dt.date(2025, 10, 10)] * 5, "zone_prefix": list("BKMQS"),
        "is_holiday": 0, "is_school_day": 1, "is_major_event": 0,
    }).to_parquet(art / "calendar_daily.parquet", index=False)
    (art / "model_metrics.json").write_text('{"objective": "count:poisson"}')


@pytest.fixture(scope="module")
def api(tmp_path_factory):
    art = tmp_path_factory.mktemp("artifacts")
    _write_artifacts(art)
    os.environ["ARTIFACTS_DIR"] = str(art)
    os.environ["DATABASE_URL"] = ""
    import main
    main.ARTIFACTS_DIR = art
    from fastapi.testclient import TestClient
    with TestClient(main.app) as client:
        yield client, main


def test_health_reports_new_artifacts(api):
    client, _ = api
    body = client.get("/health").json()
    assert body["artifacts"]["hourly_counts"] is True
    assert body["artifacts"]["calendar_daily"] is True
    assert body["model_metrics"] == {"objective": "count:poisson"}


def test_heatmap_with_date(api):
    client, _ = api
    r = client.get("/api/heatmap", params={"hour": 20, "dow": 4, "month": 10, "date": "2025-10-10"})
    assert r.status_code == 200 and r.headers["X-Data-Source"] == "model"
    body = r.json()
    assert body["query_params"] == {"hour": 20, "dow": 4, "month": 10, "date": "2025-10-10"}
    assert len(body["features"]) == 31
    k7 = next(f for f in body["features"] if f["properties"]["zone"] == "K7")["properties"]
    assert k7["actual_count"] == synthetic_count("K7", pd.Timestamp("2025-10-10 20:00"))


def test_heatmap_without_date_uses_standin(api):
    client, _ = api
    body = client.get("/api/heatmap", params={"hour": 20, "dow": 4, "month": 10}).json()
    assert body["query_params"]["date"] == "2025-10-17"


def test_date_overrides_dow_and_month(api):
    client, _ = api
    body = client.get("/api/heatmap", params={"hour": 20, "dow": 0, "month": 1, "date": "2025-10-10"}).json()
    assert (body["query_params"]["dow"], body["query_params"]["month"]) == (4, 10)


@pytest.mark.parametrize("bad", ["2024-06-01", "2026-07-01", "2025-13-01", "tomorrow"])
def test_bad_dates_are_422(api, bad):
    client, _ = api
    r = client.get("/api/heatmap", params={"hour": 20, "dow": 4, "month": 10, "date": bad})
    assert r.status_code == 422


def test_last_replay_hour_serves(api):
    client, _ = api
    r = client.get("/api/heatmap", params={"hour": 23, "dow": 1, "month": 6, "date": "2026-06-30"})
    assert r.status_code == 200 and r.headers["X-Data-Source"] == "model"


def test_staging_with_date(api):
    client, _ = api
    r = client.get("/api/staging", params={"hour": 20, "dow": 4, "month": 10, "date": "2025-10-10", "ambulances": 5})
    assert r.status_code == 200 and r.headers["X-Data-Source"] == "model"
    assert len(r.json()["features"]) == 5


def test_lag_model_without_hourly_counts_falls_back_to_mock(api):
    client, main = api
    saved = main.ARTIFACTS["hourly_counts"]
    main.ARTIFACTS["hourly_counts"] = None
    try:
        r = client.get("/api/heatmap", params={"hour": 20, "dow": 4, "month": 10, "date": "2025-10-10"})
        assert r.headers["X-Data-Source"] == "mock"
        assert r.headers["X-Warning"] == "lag-artifact-missing"
        r = client.get("/api/staging", params={"hour": 20, "dow": 4, "month": 10, "date": "2025-10-10"})
        assert r.headers["X-Warning"] == "lag-artifact-missing"
    finally:
        main.ARTIFACTS["hourly_counts"] = saved


def test_old_21_feature_model_still_serves(api):
    client, main = api
    saved = main.ARTIFACTS["demand_model"]
    main.ARTIFACTS["demand_model"] = tiny_model(FEATURE_COLS)
    try:
        r = client.get("/api/heatmap", params={"hour": 20, "dow": 4, "month": 10, "date": "2025-10-10"})
        assert r.headers["X-Data-Source"] == "model"
        assert "actual_count" in r.json()["features"][0]["properties"]
    finally:
        main.ARTIFACTS["demand_model"] = saved


def test_reload_clears_staging_cache(api):
    client, _ = api
    from routers.staging import _cached_heatmap_and_staging
    client.get("/api/staging", params={"hour": 8, "dow": 1, "month": 3, "date": "2025-03-04"})
    assert _cached_heatmap_and_staging.cache_info().currsize > 0
    assert client.post("/reload").status_code == 200
    assert _cached_heatmap_and_staging.cache_info().currsize == 0
```

- [ ] **Step 2: Run to verify it fails**

Run: `backend/.venv/bin/python -m pytest backend/tests/test_api.py -v`
Expected: FAIL — `KeyError: 'hourly_counts'` / missing `model_metrics` in `/health`.

- [ ] **Step 3: Update `backend/main.py`**

Add to the `ARTIFACTS` dict:
```python
    "hourly_counts": None,     # wide: index date_hour, one column per zone
    "calendar_daily": None,    # {(date, zone_prefix): flags}
    "model_metrics": None,     # dict from model_metrics.json
```

In `load_all_artifacts`, extend `artifact_configs`:
```python
        ("hourly_counts", ARTIFACTS_DIR / "hourly_counts.parquet", "parquet"),
        ("calendar_daily", ARTIFACTS_DIR / "calendar_daily.parquet", "parquet"),
        ("model_metrics", ARTIFACTS_DIR / "model_metrics.json", "json"),
```

Replace the loop body so a missing file clears stale state, JSON loads, the dummy predict uses the model's own feature names, and the two replay artifacts are post-processed:
```python
    from models.lag_features import to_wide
    from models.replay import calendar_to_lookup
    postprocess = {"hourly_counts": to_wide, "calendar_daily": calendar_to_lookup}

    for key, path, loader in artifact_configs:
        if not path.exists():
            logger.warning("⚠  %s not found at %s — using mock", key, path)
            ARTIFACTS[key] = None
            continue
        try:
            if loader == "joblib":
                obj = joblib.load(path)
            elif loader == "pickle":
                with open(path, "rb") as f:
                    obj = pickle.load(f)
            elif loader == "json":
                with open(path) as f:
                    obj = json.load(f)
            else:
                obj = pd.read_parquet(path)

            if loader == "joblib" and hasattr(obj, "predict"):
                names = getattr(obj, "feature_names_in_", None)
                if names is None:
                    raise ValueError("model has no feature_names_in_")
                _ = obj.predict(pd.DataFrame([[0.0] * len(names)], columns=list(names)))
            elif loader == "parquet" and isinstance(obj, pd.DataFrame):
                assert len(obj) > 0, f"{key} parquet is empty"

            if key in postprocess:
                obj = postprocess[key](obj)

            ARTIFACTS[key] = obj
            logger.info("✓  loaded %s", key)

        except Exception as exc:
            logger.error("⚠  failed to load %s: %s — using mock", key, exc)
            ARTIFACTS[key] = None
```

Replace `health()` and `reload_artifacts()` with a shared status helper:
```python
def _artifact_status() -> dict:
    return {
        "demand_model": ARTIFACTS["demand_model"] is not None,
        "drive_time": ARTIFACTS["drive_time"] is not None,
        "baselines": ARTIFACTS["baselines"] is not None,
        "zone_stats": ARTIFACTS["zone_stats"] is not None,
        "counterfactual": ARTIFACTS["counterfactual_summary"] is not None,
        "hourly_counts": ARTIFACTS["hourly_counts"] is not None,
        "calendar_daily": ARTIFACTS["calendar_daily"] is not None,
    }


@app.get("/health")
async def health():
    return {"status": "ok", "artifacts": _artifact_status(), "model_metrics": ARTIFACTS["model_metrics"]}


@app.post("/reload")
async def reload_artifacts():
    from routers.staging import _cached_heatmap_and_staging
    load_all_artifacts()
    _cached_heatmap_and_staging.cache_clear()
    _populate_zone_geom_cache()
    return {"status": "reloaded", "artifacts": _artifact_status(), "model_metrics": ARTIFACTS["model_metrics"]}
```

- [ ] **Step 4: Update `backend/routers/heatmap.py`**

Imports at the top become:
```python
import asyncio
import datetime as dt
import logging
from typing import Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
```

Change `_build_heatmap_from_predictions` signature and its two output spots:
```python
def _build_heatmap_from_predictions(
    predicted_counts: dict,
    hour: int, dow: int, month: int,
    zone_geom_cache: dict,
    zone_stats_df,
    replay_date: dt.date,
    actual: dict,
) -> dict:
```
Inside the per-zone `properties` dict add, after `"high_acuity_ratio": high_acuity,`:
```python
                "actual_count": actual.get(zone),
```
And the return's `query_params` becomes:
```python
        "query_params": {"hour": hour, "dow": dow, "month": month, "date": replay_date.isoformat()},
```

Replace `get_heatmap` with:
```python
@router.get("/heatmap")
async def get_heatmap(
    hour: int = Query(..., ge=0, le=23),
    dow: int = Query(..., ge=0, le=6),
    month: int = Query(..., ge=1, le=12),
    temperature: float = Query(default=15.0),
    precipitation: float = Query(default=0.0),
    windspeed: float = Query(default=10.0),
    ambulances: int = Query(default=5, ge=1, le=10),
    date: Optional[dt.date] = Query(default=None),
):
    from main import ARTIFACTS, MOCK_DATA, ZONE_GEOM_CACHE
    from models.demand_forecaster import DemandForecaster
    from models.lag_features import actual_counts
    from models.replay import OutOfReplayRange, resolve_request

    try:
        replay_date, dow, month = resolve_request(date, dow, month)
    except OutOfReplayRange as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    if ARTIFACTS["demand_model"] is None or ARTIFACTS["baselines"] is None:
        logger.info("Heatmap: model not loaded, returning mock data")
        return JSONResponse(content=MOCK_DATA["heatmap"], headers={"X-Data-Source": "mock"})

    forecaster = DemandForecaster(ARTIFACTS["demand_model"])
    if forecaster.uses_lags and ARTIFACTS["hourly_counts"] is None:
        logger.warning("Heatmap: lag model loaded but hourly_counts missing")
        return JSONResponse(
            content=MOCK_DATA["heatmap"],
            headers={"X-Data-Source": "mock", "X-Warning": "lag-artifact-missing"},
        )

    try:
        predicted_counts = await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(
                None,
                lambda: forecaster.predict_all_zones(
                    hour, dow, month,
                    temperature, precipitation, windspeed,
                    ARTIFACTS["zone_stats"],
                    ARTIFACTS["baselines"],
                    replay_date=replay_date,
                    counts_wide=ARTIFACTS["hourly_counts"],
                    calendar=ARTIFACTS["calendar_daily"],
                ),
            ),
            timeout=5.0,
        )

        actual = {}
        if ARTIFACTS["hourly_counts"] is not None:
            actual = actual_counts(ARTIFACTS["hourly_counts"],
                                   pd.Timestamp(replay_date) + pd.Timedelta(hours=hour))

        result = _build_heatmap_from_predictions(
            predicted_counts, hour, dow, month,
            ZONE_GEOM_CACHE, ARTIFACTS["zone_stats"],
            replay_date, actual,
        )
        return JSONResponse(content=result, headers={"X-Data-Source": "model"})

    except asyncio.TimeoutError:
        logger.error("Heatmap inference timed out")
        return JSONResponse(
            content=MOCK_DATA["heatmap"],
            headers={"X-Data-Source": "mock", "X-Warning": "inference-timeout"},
        )
    except Exception as exc:
        logger.exception("Heatmap inference error: %s", exc)
        return JSONResponse(
            content=MOCK_DATA["heatmap"],
            headers={"X-Data-Source": "mock", "X-Warning": "inference-error"},
        )
```

- [ ] **Step 5: Update `backend/routers/staging.py`**

Imports:
```python
import asyncio
import datetime as dt
import logging
from functools import lru_cache
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
```

Cached function gains the replay date (ISO string — hashable, part of the cache key):
```python
@lru_cache(maxsize=168)
def _cached_heatmap_and_staging(
    hour: int, dow: int, month: int,
    temperature: float, precipitation: float, windspeed: float,
    ambulances: int,
    replay_date_iso: str,
):
    """
    Cached combined heatmap+staging computation keyed by param tuple.
    Cleared by POST /reload.
    """
    from main import ARTIFACTS
    from models.demand_forecaster import DemandForecaster
    from models.staging_optimizer import StagingOptimizer

    forecaster = DemandForecaster(ARTIFACTS["demand_model"])
    predicted_counts = forecaster.predict_all_zones(
        hour, dow, month,
        temperature, precipitation, windspeed,
        ARTIFACTS["zone_stats"],
        ARTIFACTS["baselines"],
        replay_date=dt.date.fromisoformat(replay_date_iso),
        counts_wide=ARTIFACTS["hourly_counts"],
        calendar=ARTIFACTS["calendar_daily"],
    )

    optimizer = StagingOptimizer()
    staging_points = optimizer.compute_staging(predicted_counts, K=ambulances)
    return staging_points
```

In `get_staging`, add the parameter `date: Optional[dt.date] = Query(default=None),` after `ambulances`, and replace the top of the body (through the existing mock check) with:
```python
    from main import ARTIFACTS, MOCK_DATA
    from models.demand_forecaster import DemandForecaster
    from models.replay import OutOfReplayRange, resolve_request

    try:
        replay_date, dow, month = resolve_request(date, dow, month)
    except OutOfReplayRange as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    if ARTIFACTS["demand_model"] is None or ARTIFACTS["baselines"] is None:
        logger.info("Staging: model not loaded, returning mock data")
        return JSONResponse(content=MOCK_DATA["staging"], headers={"X-Data-Source": "mock"})

    if DemandForecaster(ARTIFACTS["demand_model"]).uses_lags and ARTIFACTS["hourly_counts"] is None:
        logger.warning("Staging: lag model loaded but hourly_counts missing")
        return JSONResponse(
            content=MOCK_DATA["staging"],
            headers={"X-Data-Source": "mock", "X-Warning": "lag-artifact-missing"},
        )
```
and pass the date into the cached call:
```python
                lambda: _cached_heatmap_and_staging(
                    hour, dow, month,
                    round(temperature, 1), round(precipitation, 1), round(windspeed, 1),
                    ambulances,
                    replay_date.isoformat(),
                ),
```

- [ ] **Step 6: Run all backend tests**

Run: `backend/.venv/bin/python -m pytest backend/tests -v`
Expected: all passed (15 new in test_api.py + earlier suites)

- [ ] **Step 7: Commit**

```bash
git add backend/main.py backend/routers/heatmap.py backend/routers/staging.py backend/tests/test_api.py
git commit -m "feat(backend): replay date param, actual_count, lag artifacts, cache clear on reload

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 12: Scripts 07, 08 and `test_artifacts.py` on the shared forecaster

**Files:**
- Modify: `pipeline/07_staging_optimizer.py`
- Modify: `pipeline/08_counterfactual_precompute.py`
- Modify: `pipeline/test_artifacts.py`

**Interfaces:**
- Consumes: `DemandForecaster.predict_all_zones(..., replay_date, counts_wide, calendar)`, `to_wide`, `actual_counts`, `calendar_to_lookup`, `fw_config.FEATURE_COLS`. Artifacts from Tasks 8–9, `pipeline/data/weather_hourly.parquet`.
- Produces: unchanged output schemas for `counterfactual_summary.parquet` and `counterfactual_raw.parquet`.

These scripts need the real artifacts (drive-time matrix, stations) to run, so their verification is the real run in Task 15.

- [ ] **Step 1: Script 07 — replace the constants/loader/`build_features` block**

In `pipeline/07_staging_optimizer.py`:
- Add `import datetime as dt` to the imports.
- Delete the `FEATURE_COLS = [...]` list (15 stale features).
- After the `STATS_PQ = ...` line add:
```python
HOURLY_PQ = ARTIFACTS_DIR / "hourly_counts.parquet"
CAL_PQ    = ARTIFACTS_DIR / "calendar_daily.parquet"
```
  and add `HOURLY_PQ, CAL_PQ` to the existence-check list.
- Replace the whole `def build_features(...)` function with:
```python
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "backend"))
from models.demand_forecaster import DemandForecaster  # noqa: E402
from models.lag_features import to_wide  # noqa: E402
from models.replay import calendar_to_lookup  # noqa: E402

counts_wide = to_wide(pd.read_parquet(HOURLY_PQ))
calendar = calendar_to_lookup(pd.read_parquet(CAL_PQ))
forecaster = DemandForecaster(model)


def build_features(replay_date: dt.date, hour: int, temp=15.0, precip=0.0, wind=10.0) -> dict:
    """Predicted demand for all 31 zones at a replayed date + hour."""
    return forecaster.predict_all_zones(
        hour, replay_date.weekday(), replay_date.month, temp, precip, wind,
        zone_stats, baselines,
        replay_date=replay_date, counts_wide=counts_wide, calendar=calendar,
    )
```
- Replace the `scenarios` list and loop header with:
```python
scenarios = [
    ("Monday 4AM (quiet)", dt.date(2025, 10, 20), 4),
    ("Wednesday Noon",     dt.date(2025, 10, 22), 12),
    ("Friday 8PM (peak)",  dt.date(2025, 10, 10), 20),
]

results = {}
for label, replay_date, hour in scenarios:
    counts  = build_features(replay_date, hour)
```
  (the rest of the loop body is unchanged).

- [ ] **Step 2: Script 08 — incidents, per-incident-hour staging**

In `pipeline/08_counterfactual_precompute.py`:
- Add `import datetime as dt` to imports.
- After the `DTM_PKL`/`STATIONS_JSON` path constants add:
```python
HOURLY_PQ  = ARTIFACTS_DIR / "hourly_counts.parquet"
CAL_PQ     = ARTIFACTS_DIR / "calendar_daily.parquet"
WEATHER_PQ = PIPELINE_DATA / "weather_hourly.parquet"
```
  and add them to the prerequisite existence check.
- Delete the `FEATURE_COLS = [...]` list and the whole `def predict_counts(...)` function.
- Replace "Step 2: Load 2023 high-acuity incidents" block through the `svi_quartile` assignment with:
```python
# ── Step 2: Load 2025 high-acuity incidents ────────────────────────────────────
print("\nLoading 2025 (test split) Priority 1+2 incidents from cleaned parquet...")
inc_all = pd.read_parquet(CLEANED_PQ, columns=[
    "INCIDENT_ID", "BOROUGH", "INCIDENT_DISPATCH_AREA",
    "hour", "dayofweek", "date_hour", "INCIDENT_RESPONSE_SECONDS_QY",
    "INCIDENT_TRAVEL_TM_SECONDS_QY", "svi_score",
    "split", "is_high_acuity", "is_valid_response",
])
incidents_test = inc_all[
    (inc_all["split"] == "test")
    & (inc_all["is_high_acuity"] == 1)
    & (inc_all["is_valid_response"] == 1)
].copy()
del inc_all

print(f"2025 Priority 1+2 incidents: {len(incidents_test):,}")
print("Borough distribution:")
print(incidents_test["BOROUGH"].value_counts().to_string())

incidents_test["svi_quartile"] = pd.qcut(
    incidents_test["svi_score"], q=4, labels=["Q1", "Q2", "Q3", "Q4"]
).astype(str)
```
- After `get_staging_zones` is defined, add:
```python
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "backend"))
from models.demand_forecaster import DemandForecaster  # noqa: E402
from models.lag_features import to_wide  # noqa: E402
from models.replay import calendar_to_lookup  # noqa: E402

forecaster  = DemandForecaster(model)
counts_wide = to_wide(pd.read_parquet(HOURLY_PQ))
calendar    = calendar_to_lookup(pd.read_parquet(CAL_PQ))
weather     = pd.read_parquet(WEATHER_PQ).set_index("date_hour")
_staging_cache: dict = {}


def staging_for(date_hour) -> list:
    """K=10 staging zones from the model's forecast for this incident's own hour."""
    date_hour = pd.Timestamp(date_hour)
    if date_hour not in _staging_cache:
        w = weather.loc[date_hour]
        day = date_hour.date()
        counts = forecaster.predict_all_zones(
            date_hour.hour, day.weekday(), day.month,
            float(w["temperature_2m"]), float(w["precipitation"]), float(w["windspeed_10m"]),
            zone_stats, baselines,
            replay_date=day, counts_wide=counts_wide, calendar=calendar,
        )
        _staging_cache[date_hour] = get_staging_zones(counts, K=10)
    return _staging_cache[date_hour]
```
- In the main loop: rename `incidents_2023` → `incidents_test` (both references), delete the two lines
```python
    # Use October as representative month for staging prediction
    predicted_counts = predict_counts(hour, dow, month=10)
    staging_zones    = get_staging_zones(predicted_counts, K=10)
```
  and inside the per-incident loop replace `s_time = get_staged_drive(zone, staging_zones)` with
```python
        s_time = get_staged_drive(zone, staging_for(inc["date_hour"]))
```
- Update the docstring line `BASELINE: nearest fixed FDNY station drive time to each 2023 Priority 1+2 incident` to say `2025`.

Run: `grep -n "incidents_2023\|predict_counts\|CAD_INCIDENT_ID\|FEATURE_COLS" pipeline/08_counterfactual_precompute.py pipeline/07_staging_optimizer.py`
Expected: no output.

- [ ] **Step 3: `test_artifacts.py`**

- Replace the `FEATURE_COLS = [...]` block with:
```python
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "backend"))
from fw_config import FEATURE_COLS  # noqa: E402
```
- Extend `REQUIRED_FILES` with `"hourly_counts.parquet"`, `"calendar_daily.parquet"`, `"model_metrics.json"`.
- Replace the body of Check 2 from `# Feature count` through the two spot-check `check(...)` calls with:
```python
        n_features = model.n_features_in_
        check(f"model has {len(FEATURE_COLS)} features", n_features == len(FEATURE_COLS), f"found {n_features}")
        check("feature order matches fw_config", list(model.feature_names_in_) == FEATURE_COLS)

        import datetime as dt
        from models.demand_forecaster import DemandForecaster
        from models.lag_features import to_wide
        from models.replay import calendar_to_lookup
        preds = DemandForecaster(model).predict_all_zones(
            20, 4, 10, 15.0, 0.0, 10.0,
            pd.read_parquet(ARTIFACTS_DIR / "zone_stats.parquet"),
            pd.read_parquet(ARTIFACTS_DIR / "zone_baselines.parquet"),
            replay_date=dt.date(2025, 10, 10),
            counts_wide=to_wide(pd.read_parquet(ARTIFACTS_DIR / "hourly_counts.parquet")),
            calendar=calendar_to_lookup(pd.read_parquet(ARTIFACTS_DIR / "calendar_daily.parquet")),
        )
        check("replay prediction covers 31 zones", len(preds) == 31)
        check("replay predictions in [0, 100)", all(0 <= v < 100 for v in preds.values()),
              f"max={max(preds.values()):.2f}")
```
- Before the summary section, add a replay-artifact check block:
```python
print("[ R ] replay artifacts")
hc_path = ARTIFACTS_DIR / "hourly_counts.parquet"
if hc_path.exists():
    hc = pd.read_parquet(hc_path)
    check("hourly_counts rows", len(hc) == 429_288, f"rows={len(hc):,}")
    check("hourly_counts zones", hc["INCIDENT_DISPATCH_AREA"].nunique() == 31)
    check("hourly_counts range",
          hc["date_hour"].min() == pd.Timestamp("2024-12-01") and
          hc["date_hour"].max() == pd.Timestamp("2026-06-30 23:00"))
cal_path = ARTIFACTS_DIR / "calendar_daily.parquet"
if cal_path.exists():
    check("calendar_daily rows", len(pd.read_parquet(cal_path)) == 2_730)
metrics_path = ARTIFACTS_DIR / "model_metrics.json"
if metrics_path.exists():
    import json
    m = json.loads(metrics_path.read_text())
    check("model_metrics gate passed", m["gate"]["passed"] is True,
          f"improvement={m['gate']['improvement']:.2%}")
print()
```

- [ ] **Step 4: Syntax check all three**

Run: `pipeline/.venv/bin/python -m py_compile pipeline/07_staging_optimizer.py pipeline/08_counterfactual_precompute.py pipeline/test_artifacts.py && echo OK`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add pipeline/07_staging_optimizer.py pipeline/08_counterfactual_precompute.py pipeline/test_artifacts.py
git commit -m "feat(pipeline): 07/08/test_artifacts use the backend forecaster on replay dates

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 13: Frontend replay date control

**Files:**
- Create: `frontend/src/utils/replayDate.js`, `frontend/src/utils/queryParams.js`, `frontend/src/components/Controls/DatePicker.jsx`
- Modify: `frontend/src/constants.js`, `frontend/src/components/Controls/ControlPanel.jsx`, `frontend/src/App.jsx`
- Delete: `frontend/src/components/Controls/DayPicker.jsx`, `frontend/src/components/Controls/__tests__/DayPicker.test.jsx`
- Test: `frontend/src/utils/__tests__/replayDate.test.js`, `frontend/src/utils/__tests__/queryParams.test.js`, `frontend/src/components/Controls/__tests__/DatePicker.test.jsx`, updates to `ControlPanel.test.jsx` and `src/__tests__/App.test.jsx`

**Interfaces:**
- Produces: `REPLAY_MIN_DATE = '2025-01-01'`, `REPLAY_MAX_DATE = '2026-06-30'` (constants.js); `dowFromDate(iso) -> 0..6 (Mon=0)`, `monthFromDate(iso) -> 1..12`, `isReplayDate(iso) -> bool` (replayDate.js); `buildQueryParams(controls) -> {date, hour, dow, month, temperature, precipitation, windspeed, ambulances}` (queryParams.js); `<DatePicker value onChange />` with label text `Replay Date`. Controls shape becomes `{ date, hour, weather, ambulances }`.

All frontend commands run from `frontend/`.

- [ ] **Step 1: Write the failing tests**

`frontend/src/utils/__tests__/replayDate.test.js`:
```js
import { describe, it, expect } from 'vitest';
import { dowFromDate, monthFromDate, isReplayDate } from '../replayDate';
import { DEMO_SCENARIOS } from '../../constants';

describe('replayDate', () => {
  it('maps dates to Mon=0 weekdays without timezone drift', () => {
    expect(dowFromDate('2025-10-10')).toBe(4);
    expect(dowFromDate('2025-10-20')).toBe(0);
    expect(dowFromDate('2025-10-12')).toBe(6);
    expect(dowFromDate('2025-01-01')).toBe(2);
  });

  it('extracts the month', () => {
    expect(monthFromDate('2025-07-30')).toBe(7);
  });

  it('accepts only in-range ISO dates', () => {
    expect(isReplayDate('2025-01-01')).toBe(true);
    expect(isReplayDate('2026-06-30')).toBe(true);
    expect(isReplayDate('2024-12-31')).toBe(false);
    expect(isReplayDate('2026-07-01')).toBe(false);
    expect(isReplayDate('')).toBe(false);
  });

  it('demo presets fall on the weekdays their names promise', () => {
    expect(dowFromDate(DEMO_SCENARIOS.friday_peak.date)).toBe(4);
    expect(dowFromDate(DEMO_SCENARIOS.monday_quiet.date)).toBe(0);
    expect(dowFromDate(DEMO_SCENARIOS.storm.date)).toBe(2);
  });
});
```

`frontend/src/utils/__tests__/queryParams.test.js`:
```js
import { describe, it, expect } from 'vitest';
import { buildQueryParams } from '../queryParams';

describe('buildQueryParams', () => {
  it('derives dow and month from the date and expands weather', () => {
    expect(buildQueryParams({ date: '2025-10-10', hour: 20, weather: 'heavy', ambulances: 7 })).toEqual({
      date: '2025-10-10', hour: 20, dow: 4, month: 10,
      temperature: 8, precipitation: 8, windspeed: 30, ambulances: 7,
    });
  });

  it('falls back to clear weather for unknown presets', () => {
    expect(buildQueryParams({ date: '2025-10-20', hour: 4, weather: 'bogus', ambulances: 5 }).precipitation).toBe(0);
  });
});
```

`frontend/src/components/Controls/__tests__/DatePicker.test.jsx`:
```jsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import DatePicker from '../DatePicker';

describe('DatePicker', () => {
  it('renders a labelled date input bounded to the replay range', () => {
    render(<DatePicker value="2025-10-10" onChange={() => {}} />);
    const input = screen.getByLabelText('Replay Date');
    expect(input).toHaveAttribute('type', 'date');
    expect(input).toHaveAttribute('min', '2025-01-01');
    expect(input).toHaveAttribute('max', '2026-06-30');
    expect(input.value).toBe('2025-10-10');
  });

  it('shows the weekday of the selected date', () => {
    render(<DatePicker value="2025-10-10" onChange={() => {}} />);
    expect(screen.getByText('Fri')).toBeInTheDocument();
  });

  it('calls onChange with a valid date', () => {
    const onChange = vi.fn();
    render(<DatePicker value="2025-10-10" onChange={onChange} />);
    fireEvent.change(screen.getByLabelText('Replay Date'), { target: { value: '2025-10-20' } });
    expect(onChange).toHaveBeenCalledWith('2025-10-20');
  });

  it('ignores out-of-range dates', () => {
    const onChange = vi.fn();
    render(<DatePicker value="2025-10-10" onChange={onChange} />);
    fireEvent.change(screen.getByLabelText('Replay Date'), { target: { value: '2024-05-01' } });
    expect(onChange).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run to verify they fail**

Run: `npx vitest run src/utils src/components/Controls/__tests__/DatePicker.test.jsx`
Expected: FAIL — cannot resolve `../replayDate`, `../queryParams`, `../DatePicker`.

- [ ] **Step 3: Implement utils, constants, DatePicker**

`frontend/src/utils/replayDate.js`:
```js
import { REPLAY_MIN_DATE, REPLAY_MAX_DATE } from '../constants';

// Parse YYYY-MM-DD as a local date (new Date('YYYY-MM-DD') would be UTC midnight).
function parseIsoDate(iso) {
  const [y, m, d] = iso.split('-').map(Number);
  return new Date(y, m - 1, d);
}

export function dowFromDate(iso) {
  return (parseIsoDate(iso).getDay() + 6) % 7; // 0 = Monday
}

export function monthFromDate(iso) {
  return Number(iso.split('-')[1]);
}

export function isReplayDate(iso) {
  return /^\d{4}-\d{2}-\d{2}$/.test(iso) && iso >= REPLAY_MIN_DATE && iso <= REPLAY_MAX_DATE;
}
```

`frontend/src/utils/queryParams.js`:
```js
import { WEATHER_PRESETS } from '../constants';
import { dowFromDate, monthFromDate } from './replayDate';

export function buildQueryParams(controls) {
  const preset = WEATHER_PRESETS[controls.weather] || WEATHER_PRESETS.none;
  return {
    date: controls.date,
    hour: controls.hour,
    dow: dowFromDate(controls.date),
    month: monthFromDate(controls.date),
    temperature: preset.temperature,
    precipitation: preset.precipitation,
    windspeed: preset.windspeed,
    ambulances: controls.ambulances,
  };
}
```

In `frontend/src/constants.js`, replace `DEMO_SCENARIOS` and add the range constants above it:
```js
export const REPLAY_MIN_DATE = '2025-01-01';
export const REPLAY_MAX_DATE = '2026-06-30';

export const DEMO_SCENARIOS = {
  friday_peak: { date: '2025-10-10', hour: 20, temperature: 15, precipitation: 0, windspeed: 10, ambulances: 5 },
  monday_quiet: { date: '2025-10-20', hour: 4, temperature: 15, precipitation: 0, windspeed: 10, ambulances: 5 },
  // Rainiest Wednesday 6 PM of 2025 per Open-Meteo: 8.2 mm/h, WMO 65 (heavy rain).
  storm: { date: '2025-07-30', hour: 18, temperature: 8, precipitation: 8, windspeed: 30, ambulances: 7 },
};
```

`frontend/src/components/Controls/DatePicker.jsx`:
```jsx
import { DOW_LABELS, REPLAY_MIN_DATE, REPLAY_MAX_DATE } from '../../constants';
import { dowFromDate, isReplayDate } from '../../utils/replayDate';

export default function DatePicker({ value, onChange }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <label
        htmlFor="replay-date"
        style={{ fontSize: 11, color: '#aaa', textTransform: 'uppercase', letterSpacing: 1, display: 'block', marginBottom: 6 }}
      >Replay Date</label>
      <input
        id="replay-date"
        type="date"
        min={REPLAY_MIN_DATE}
        max={REPLAY_MAX_DATE}
        value={value}
        onChange={(e) => { if (isReplayDate(e.target.value)) onChange(e.target.value); }}
        style={{
          width: '100%', padding: '8px', fontSize: 12, color: '#fff',
          background: '#1a1a2e', border: '1px solid #333', borderRadius: 4,
          colorScheme: 'dark', boxSizing: 'border-box',
        }}
      />
      <div style={{ fontSize: 11, color: '#888', marginTop: 4 }}>{DOW_LABELS[dowFromDate(value)]}</div>
    </div>
  );
}
```

- [ ] **Step 4: Run the new tests**

Run: `npx vitest run src/utils src/components/Controls/__tests__/DatePicker.test.jsx`
Expected: all passed (4 + 2 + 4)

- [ ] **Step 5: Wire ControlPanel and App; update their tests**

`ControlPanel.jsx`: replace `import DayPicker from './DayPicker';` with `import DatePicker from './DatePicker';`, replace the `getActivePreset` condition with
```js
    if (
      controls.date === scenario.date &&
      controls.hour === scenario.hour &&
      controls.ambulances === scenario.ambulances
    ) {
```
and replace the DayPicker line with
```jsx
      <DatePicker value={controls.date} onChange={(v) => onControlChange('date', v)} />
```

`App.jsx`:
- Replace `import { DEMO_SCENARIOS, WEATHER_PRESETS } from './constants';` with
```js
import { DEMO_SCENARIOS } from './constants';
import { buildQueryParams } from './utils/queryParams';
```
- Replace `DEFAULT_CONTROLS` and delete `resolveWeather`:
```js
const DEFAULT_CONTROLS = {
  date: '2025-10-10',
  hour: 20,
  weather: 'none',
  ambulances: 5,
};
```
- In `handleApplyScenario`, the `next` object becomes:
```js
    const next = {
      date: scenario.date,
      hour: scenario.hour,
      weather: scenario.precipitation > 5 ? 'heavy' : scenario.precipitation > 0 ? 'light' : 'none',
      ambulances: scenario.ambulances,
    };
```
- Replace `const params = resolveWeather(queryControls);` with `const params = buildQueryParams(queryControls);` and the counterfactual call's argument with `{ hour: params.hour, dow: params.dow }`.

Delete the old picker:
```bash
git rm src/components/Controls/DayPicker.jsx src/components/Controls/__tests__/DayPicker.test.jsx
```

`ControlPanel.test.jsx`: change `defaultControls` to `{ date: '2025-10-10', hour: 20, weather: 'none', ambulances: 5 }`; in "renders all child control components" replace `expect(screen.getByText('Day of Week'))` with `expect(screen.getByText('Replay Date'))`; add:
```jsx
  it('highlights the preset matching the current controls', () => {
    render(
      <ControlPanel
        controls={defaultControls}
        onControlChange={() => {}}
        layerVisibility={defaultVisibility}
        onLayerChange={() => {}}
        onApplyScenario={() => {}}
      />
    );
    expect(screen.getByText('Fri 8PM Peak')).toHaveStyle({ backgroundColor: '#1565C0' });
    expect(screen.getByText('Storm')).toHaveStyle({ backgroundColor: '#333' });
  });
```

`src/__tests__/App.test.jsx`:
- line with `getByText('Day of Week')` → `getByText('Replay Date')`.
- Replace test `'defaults to Friday (dow 4) selected'` with:
```jsx
  it('defaults to replaying Friday 2025-10-10', () => {
    renderApp();
    expect(screen.getByLabelText('Replay Date').value).toBe('2025-10-10');
    expect(screen.getByText('Fri')).toBeInTheDocument();
  });
```
- In `'applies Monday Quiet demo scenario'` replace the two `mon` lines with:
```jsx
    expect(screen.getByLabelText('Replay Date').value).toBe('2025-10-20');
```
- Replace `'updates day of week when clicking a day button'` with:
```jsx
  it('updates the replay date', () => {
    renderApp();
    fireEvent.change(screen.getByLabelText('Replay Date'), { target: { value: '2025-10-13' } });
    expect(screen.getByLabelText('Replay Date').value).toBe('2025-10-13');
    expect(screen.getByText('Mon')).toBeInTheDocument();
  });
```

- [ ] **Step 6: Run the full frontend suite**

Run: `npx vitest run`
Expected: the only failures are the pre-existing ones listed in "Baseline test state" (at most 13, same test names). Any other failure is a regression to fix before committing.

- [ ] **Step 7: Commit**

```bash
git add src/utils src/constants.js src/components/Controls src/App.jsx src/__tests__/App.test.jsx
git commit -m "feat(frontend): replay date picker replaces day-of-week; presets on 2025 dates

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 14: Frontend predicted vs actual

**Files:**
- Modify: `frontend/src/components/Map/ZoneTooltip.jsx`, `frontend/src/components/Map/ZoneDetailPanel.jsx`, `frontend/src/App.jsx`
- Test: `frontend/src/components/Map/__tests__/ZoneTooltip.test.jsx`, `frontend/src/components/Map/__tests__/ZoneDetailPanel.test.jsx`

**Interfaces:**
- Consumes: heatmap feature `properties.actual_count` (int or null) and `query_params.date` / `query_params.hour` (Task 11).
- Produces: `ZoneDetailPanel` optional prop `replay: { date: string, hour: number, predicted: number, actual: number } | null`.

- [ ] **Step 1: Write the failing tests**

Append to `ZoneTooltip.test.jsx` inside the `describe`:
```jsx
  const base = {
    zone: 'K7', zone_name: 'Williamsburg', borough: 'BROOKLYN',
    normalized_intensity: 0.4, predicted_count: 7.9, svi_score: 0.45,
    historical_avg_response_sec: 542,
  };

  it('shows the actual count when the API returns one', () => {
    render(<ZoneTooltip info={{ x: 0, y: 0, properties: { ...base, actual_count: 9 } }} />);
    expect(screen.getByText(/Actual:/)).toBeInTheDocument();
    expect(screen.getByText('9')).toBeInTheDocument();
  });

  it('omits the actual line in mock mode', () => {
    render(<ZoneTooltip info={{ x: 0, y: 0, properties: base }} />);
    expect(screen.queryByText(/Actual:/)).not.toBeInTheDocument();
  });

  it('shows an actual count of zero', () => {
    render(<ZoneTooltip info={{ x: 0, y: 0, properties: { ...base, actual_count: 0 } }} />);
    expect(screen.getByText(/Actual:/)).toBeInTheDocument();
  });
```

Append to `ZoneDetailPanel.test.jsx` inside the `describe`:
```jsx
  it('shows the replay comparison when given', () => {
    render(<ZoneDetailPanel data={mockZoneData} onClose={() => {}}
      replay={{ date: '2025-10-10', hour: 20, predicted: 7.94, actual: 9 }} />);
    expect(screen.getByText(/2025-10-10 20:00/)).toBeInTheDocument();
    expect(screen.getByText(/predicted 7\.9 · actual 9/)).toBeInTheDocument();
  });

  it('hides the replay comparison without an actual count', () => {
    render(<ZoneDetailPanel data={mockZoneData} onClose={() => {}}
      replay={{ date: '2025-10-10', hour: 20, predicted: 7.9, actual: null }} />);
    expect(screen.queryByText(/· actual/)).not.toBeInTheDocument();
  });
```

- [ ] **Step 2: Run to verify they fail**

Run: `npx vitest run src/components/Map/__tests__/ZoneTooltip.test.jsx src/components/Map/__tests__/ZoneDetailPanel.test.jsx`
Expected: the 4 new "shows…" tests FAIL (no Actual / replay text rendered).

- [ ] **Step 3: Implement**

`ZoneTooltip.jsx` — after the `Predicted:` row `</div>` add:
```jsx
      {p.actual_count !== undefined && p.actual_count !== null && (
        <div style={{ marginBottom: 4 }}>
          Actual: <b style={{ fontFamily: "'DM Mono', monospace" }}>{p.actual_count}</b> calls
        </div>
      )}
```

`ZoneDetailPanel.jsx` — change the signature to `export default function ZoneDetailPanel({ data, onClose, replay = null })`, and directly under the panel's zone title block add:
```jsx
      {replay && replay.actual !== null && replay.actual !== undefined && (
        <div style={{ fontSize: 12, color: '#ccc', margin: '4px 0 8px' }}>
          Replay {replay.date} {String(replay.hour).padStart(2, '0')}:00 —{' '}
          <span style={{ fontFamily: "'DM Mono', monospace" }}>
            predicted {Number(replay.predicted).toFixed(1)} · actual {replay.actual}
          </span>
        </div>
      )}
```
(Find the title block by the element rendering `{data.zone}`; insert right after its closing tag.)

`App.jsx` — before the `return`, add:
```jsx
  const selectedProps = heatmapData?.features?.find((f) => f.properties.zone === selectedZone)?.properties;
  const replay = selectedProps
    ? {
        date: heatmapData.query_params?.date,
        hour: heatmapData.query_params?.hour,
        predicted: selectedProps.predicted_count,
        actual: selectedProps.actual_count ?? null,
      }
    : null;
```
and pass `replay={replay}` to `<ZoneDetailPanel ... />`.

- [ ] **Step 4: Run the full frontend suite**

Run: `npx vitest run`
Expected: new tests pass; failures limited to the pre-existing baseline set.

- [ ] **Step 5: Commit**

```bash
git add src/components/Map src/App.jsx
git commit -m "feat(frontend): show predicted vs actual for replayed hours

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 15: Real data run (user-gated)

**Files:** produces `pipeline/data/*` (gitignored) and `backend/artifacts/*`.

- [ ] **Step 1: Ask the user before downloading (STOP until they say yes)**

Get the size first:
```bash
curl -sI "https://data.cityofnewyork.us/api/views/76xm-jjuj/rows.csv?accessType=DOWNLOAD" | grep -i -E "content-length|content-type"
```
Then ask, in chat: download (a) the full NYC EMS incident CSV from data.cityofnewyork.us (`76xm-jjuj`, size from the HEAD response, or "unknown — ~30M rows, several GB" if no Content-Length) to `pipeline/data/raw/ems_raw.csv`; (b) the NYC Permitted Events CSV (`bkfu-528j`); plus ~5 Open-Meteo archive API calls. Do not continue without an explicit yes.

- [ ] **Step 2: Download the EMS CSV (background)**

```bash
mkdir -p pipeline/data/raw
curl -L --fail -o pipeline/data/raw/ems_raw.csv "https://data.cityofnewyork.us/api/views/76xm-jjuj/rows.csv?accessType=DOWNLOAD"
```
Run with `run_in_background: true`. When done: `head -1 pipeline/data/raw/ems_raw.csv` and confirm it contains every name in `fw_ingest.REQUIRED_COLUMNS` plus `INCIDENT_ID` or `CAD_INCIDENT_ID`. If header names differ (e.g. spaces instead of underscores), stop and report the header to the user.

- [ ] **Step 3: Run 01 → 03**

```bash
pipeline/.venv/bin/python pipeline/01_ingest_clean.py --csv pipeline/data/raw/ems_raw.csv
pipeline/.venv/bin/python pipeline/02_weather_merge.py
pipeline/.venv/bin/python pipeline/03_spatial_join.py
```
Checks: 01 prints ~1.5M+ incidents for each full year 2022–2025 and 31 zones; if any full year is under 1.0M, the datetime parse failed — stop and inspect `SELECT INCIDENT_DATETIME FROM read_csv(...) LIMIT 5`. 02 exits 0 (it hard-fails on anything other than 40,152 unique weather hours). 03 reports 0 null SVI rows.

- [ ] **Step 4: Run 04**

```bash
pipeline/.venv/bin/python pipeline/04_aggregate.py
```
Expected: all ✓ lines, parity 0 mismatches, and a mean hourly count by split that does not fall year over year (if it drops, the validity filter leaked back in — stop).

- [ ] **Step 5: Run 05**

```bash
pipeline/.venv/bin/python pipeline/05_train_demand_model.py
```
- Exit 0 → continue.
- Exit 1 (gate failed) → **STOP.** Report the printed comparison table to the user and ask how to proceed. Do not run 07/08, do not touch backend code paths further, do not commit artifacts.

- [ ] **Step 6: Run 07, 08, artifact tests**

```bash
pipeline/.venv/bin/python pipeline/07_staging_optimizer.py
pipeline/.venv/bin/python pipeline/08_counterfactual_precompute.py
pipeline/.venv/bin/python pipeline/test_artifacts.py
```
Expected: 07 checks PASS; 08 writes 168-row summary; `test_artifacts.py` reports 0 FAIL.

- [ ] **Step 7: Full test suites green**

```bash
pipeline/.venv/bin/python -m pytest pipeline/tests -v
backend/.venv/bin/python -m pytest backend/tests -v
```
Expected: all passed.

---

### Task 16: End-to-end check, docs, artifact commit

**Files:**
- Create: `.claude/launch.json`
- Modify: `CLAUDE.md` (append only)
- Commit: `backend/artifacts/{demand_model.pkl, zone_baselines.parquet, zone_stats.parquet, hourly_counts.parquet, calendar_daily.parquet, model_metrics.json, counterfactual_summary.parquet, counterfactual_raw.parquet}`

- [ ] **Step 1: Launch config**

`.claude/launch.json`:
```json
{
  "version": "0.0.1",
  "configurations": [
    {
      "name": "backend",
      "runtimeExecutable": "bash",
      "runtimeArgs": ["-c", "cd backend && .venv/bin/uvicorn main:app --port 8000"],
      "port": 8000
    },
    {
      "name": "frontend",
      "runtimeExecutable": "npm",
      "runtimeArgs": ["--prefix", "frontend", "run", "dev"],
      "port": 3000
    }
  ]
}
```

- [ ] **Step 2: API check**

Start `backend` via `preview_start`, then:
```bash
curl -s localhost:8000/health
curl -si "localhost:8000/api/heatmap?hour=20&dow=4&month=10&date=2025-10-10" | head -20
```
Expected: `/health` shows `hourly_counts: true`, `calendar_daily: true`, and `model_metrics` with the real objective; heatmap returns `X-Data-Source: model`, `query_params.date = "2025-10-10"`, and numeric `actual_count` values.

- [ ] **Step 3: Browser check**

Start `frontend` via `preview_start`. In the browser pane: click **Fri 8PM Peak**, confirm the Replay Date input shows 2025-10-10, hover a Bronx zone and confirm the tooltip shows both "Predicted" and "Actual", click the zone and confirm the detail panel shows "Replay 2025-10-10 20:00 — predicted X · actual Y". Take a screenshot. Then click **Storm** and confirm the date becomes 2025-07-30 and the map re-renders.

- [ ] **Step 4: Append to `CLAUDE.md`**

Print the numbers to fill in:
```bash
backend/.venv/bin/python -c "import json;m=json.load(open('backend/artifacts/model_metrics.json'));print(m['objective'],m['best_iteration']);[print(s,n,round(v['rmse'],3),round(v['mae'],3)) for s in ('test','test_recent') for n,v in m[s].items()];print(m['gate'])"
```
Append this section at the end of `CLAUDE.md`, replacing each `<…>` with the printed values:
```markdown
---

## Model A v2 — Lag Features (added 2026-09-28)

Spec: `docs/superpowers/specs/2026-09-28-lag-features-design.md` · Plan: `docs/superpowers/plans/2026-09-28-lag-features.md`

**Grain:** one row per (zone, local hour), zeros included. **Label:** incidents per zone-hour, counting every incident that passes zone/borough/reopen/transfer/standby filters (response-time validity is NOT a filter for the label).

**Splits:** history Dec 2021 (lag warm-up) · train 2022-01-01→2024-09-30 · valid 2024-10-01→2024-12-31 (early stopping) · test 2025 · test_recent 2026-01-01→2026-06-30.

**FEATURE_COLS (28):** the 21 above, then `lag_1h, lag_2h, lag_3h, lag_24h, lag_168h, roll_7d_same_hour, roll_4w_same_hour_dow`. Canonical list: `pipeline/fw_config.py`.

**Objective:** `<objective>`, best_iteration `<n>`.

| 2025 test | RMSE | MAE |
|---|---|---|
| lag model | `<>` | `<>` |
| no-lag model | `<>` | `<>` |
| naive same-hour-last-week | `<>` | `<>` |
| zone_baseline_avg | `<>` | `<>` |

Deployment gate: improvement `<x>%` vs no-lag (threshold 2%).

**API (additive):** `/api/heatmap` and `/api/staging` accept optional `date=YYYY-MM-DD` (2025-01-01 → 2026-06-30). With a date, dow/month come from it and lags come from history; without one, the lower-median 2025 date for (month, dow) is used. Heatmap responses add `query_params.date` and per-zone `actual_count`. `/health` adds `hourly_counts`, `calendar_daily`, `model_metrics`.

**New artifacts:** `hourly_counts.parquet` (zone, date_hour, incident_count; 2024-12-01→2026-06-30), `calendar_daily.parquet` (date, zone_prefix, is_holiday, is_school_day, is_major_event; 2025-01-01→2026-06-30), `model_metrics.json`.

**Scale change:** `zone_baselines.zone_baseline_avg` is now a true mean hourly count (≈ 1/4 of the old month-summed values).
```

- [ ] **Step 5: Commit artifacts and docs**

```bash
git add .claude/launch.json CLAUDE.md backend/artifacts/demand_model.pkl backend/artifacts/zone_baselines.parquet backend/artifacts/zone_stats.parquet backend/artifacts/hourly_counts.parquet backend/artifacts/calendar_daily.parquet backend/artifacts/model_metrics.json backend/artifacts/counterfactual_summary.parquet backend/artifacts/counterfactual_raw.parquet
git commit -m "feat: lag-feature demand model trained on 2022–2026, replay artifacts, docs

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## Execution order

1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → **10** → 9 → 11 → 12 → 13 → 14 → 15 → 16. (Task 10 precedes 9 because 05's replay check calls the new forecaster.)
