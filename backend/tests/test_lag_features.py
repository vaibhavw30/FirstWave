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
