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
