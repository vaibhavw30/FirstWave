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
