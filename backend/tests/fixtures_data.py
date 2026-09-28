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
