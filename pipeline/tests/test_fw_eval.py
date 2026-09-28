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
