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
