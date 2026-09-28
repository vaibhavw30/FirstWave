"""CoverageModel on a hand-built 3-zone / 1-station network (numbers worked by hand)."""
import pathlib
import pickle

import numpy as np
import pandas as pd
import pytest
from scipy.stats import lognorm

from models.coverage_model import (
    CoverageModel, build_coverage_model, call_level_after, pct_within, weather_travel_factor)

ART = pathlib.Path(__file__).resolve().parents[1] / "artifacts"
ZONES = ["B1", "B2", "K1"]
# Symmetric zone-to-zone drive seconds; the one station "ST" sits next to K1.
_ZZ = {("B1", "B2"): 100, ("B1", "K1"): 300, ("B2", "K1"): 240}
_ST = {"B1": 400, "B2": 500, "K1": 60}


def matrix():
    m = {}
    for a in ZONES:
        for b in ZONES:
            m[(a, b)] = 0 if a == b else _ZZ.get((a, b), _ZZ.get((b, a)))
    for z, t in _ST.items():
        m[("ST", z)] = t
    return m


def stats():
    return pd.DataFrame({"INCIDENT_DISPATCH_AREA": ZONES,
                         "avg_dispatch_seconds": 200.0, "avg_travel_seconds": 300.0})


@pytest.fixture
def cm():
    return CoverageModel(matrix(), ["ST"], stats(), zones=ZONES)


def test_intra_zone_travel_is_half_the_nearest_neighbour_drive(cm):
    # B1: min(100, 300)/2   B2: min(100, 240)/2   K1: min(300, 240)/2
    np.testing.assert_allclose(cm.intra, [50, 50, 120])


def test_station_drive_includes_intra_zone_travel(cm):
    np.testing.assert_allclose(cm.station_drive, [450, 550, 180])


def test_site_in_its_own_zone_is_not_instant(cm):
    # The matrix diagonal is 0 s; the within-zone term replaces it.
    assert cm.site_drive[0, 0] == 50
    assert cm.ratios(["B1"])[0] == pytest.approx(50 / 450)


def test_no_sites_changes_nothing(cm):
    np.testing.assert_allclose(cm.ratios([]), 1.0)
    for before, after in cm.zone_times([]).values():
        assert before == after == 500


def test_site_ratios_against_the_nearest_station(cm):
    # B1 from B1: 50/450; B2 from B1: (100+50)/550; K1: station (180) beats B1 (300+120)
    np.testing.assert_allclose(cm.ratios(["B1"]), [50 / 450, 150 / 550, 1.0])


def test_best_open_site_wins(cm):
    # B2 from B2 (50/550) beats B2 from B1; K1 from K1: 120/180
    np.testing.assert_allclose(cm.ratios(["B1", "B2", "K1"]), [50 / 450, 50 / 550, 120 / 180])


def test_weather_scales_travel_not_dispatch(cm):
    before, after = cm.zone_times(["B1"], weather_factor=1.5)["B1"]
    assert before == pytest.approx(200 + 450)
    assert after == pytest.approx(200 + 450 * 50 / 450)


def test_weather_travel_factor():
    assert weather_travel_factor(0, 10) == 1.0
    assert weather_travel_factor(10, 25) == pytest.approx(1.14)


@pytest.mark.parametrize("mean", [300, 480, 641, 1200])
def test_pct_within_is_the_cv095_lognormal(mean):
    sigma = np.sqrt(np.log(1 + 0.95 ** 2))
    expected = lognorm.cdf(480, s=sigma, scale=np.exp(np.log(mean) - sigma ** 2 / 2))
    assert float(pct_within(mean)) == pytest.approx(expected, rel=1e-9)


def test_pct_within_falls_as_mean_rises():
    p = pct_within(np.array([300.0, 480.0, 700.0]))
    assert p[0] > p[1] > p[2]


def test_call_level_after_shrinks_only_travel():
    after = call_level_after([600, 600, 600, 600, 600],
                             [300, 0, 700, np.nan, 300],
                             [0.5, 0.5, 0.5, 0.5, 1.0])
    assert after[0] == 450            # 600 − 300 × (1 − 0.5)
    assert np.isnan(after[1:4]).all()  # travel 0, travel > response, travel missing
    assert after[4] == 600            # ratio 1: unchanged


def test_incomplete_matrix_is_rejected():
    m = matrix()
    del m[("ST", "K1")]
    with pytest.raises(ValueError, match="missing 1 pairs"):
        CoverageModel(m, ["ST"], stats(), zones=ZONES)


def test_build_returns_none_when_inputs_missing(tmp_path):
    assert build_coverage_model(None, stats()) is None
    assert build_coverage_model(matrix(), None) is None
    assert build_coverage_model(matrix(), stats(), stations_path=tmp_path / "nope.json") is None


def test_build_returns_none_when_zone_stats_incomplete():
    with open(ART / "drive_time_matrix.pkl", "rb") as f:
        drive_time = pickle.load(f)
    zs = pd.read_parquet(ART / "zone_stats.parquet")
    assert build_coverage_model(drive_time, zs) is not None
    assert build_coverage_model(drive_time, zs[zs["INCIDENT_DISPATCH_AREA"] != "Q1"]) is None
