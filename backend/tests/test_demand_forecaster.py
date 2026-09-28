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


def test_explicit_weather_flags_override_request_rules():
    flags = {"is_severe_weather": 1, "is_extreme_heat": 0, "is_heat_emergency": 1}
    frame = DemandForecaster(MODEL_21).build_feature_frame(
        18, 2, 7, 28.2, 0.0, 5.8, None, None, weather_flags=flags)
    assert (frame["is_severe_weather"] == 1).all()
    assert (frame["is_heat_emergency"] == 1).all()
    assert (frame["is_extreme_heat"] == 0).all()


def test_light_rain_is_severe_like_training():
    # Training flags any WMO drizzle/rain/snow code as severe, so any measurable
    # precipitation must count at serving time too.
    frame = DemandForecaster(MODEL_21).build_feature_frame(20, 4, 10, 12.0, 2.0, 15.0, None, None)
    assert (frame["is_severe_weather"] == 1).all()
    dry = DemandForecaster(MODEL_21).build_feature_frame(20, 4, 10, 12.0, 0.0, 15.0, None, None)
    assert (dry["is_severe_weather"] == 0).all()
