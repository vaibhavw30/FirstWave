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
