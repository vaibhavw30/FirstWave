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
