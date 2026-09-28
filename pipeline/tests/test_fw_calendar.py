import datetime as dt

import pandas as pd
import pytest

from fw_calendar import (
    ALL_HOLIDAYS, SCHOOL_CLOSURES, SCHOOL_SESSIONS,
    build_calendar_daily, is_holiday, is_school_day,
)

D = dt.date.fromisoformat


@pytest.mark.parametrize("day,expected", [
    ("2025-10-10", 1),  # ordinary Friday in session
    ("2025-10-20", 0),  # Diwali 2025
    ("2025-10-11", 0),  # Saturday
    ("2025-07-30", 0),  # summer
    ("2024-04-24", 0),  # 2023-24 spring recess (old list had this open)
    ("2024-04-03", 1),  # old list wrongly closed this day
    ("2024-06-17", 0),  # Eid al-Adha 2024
    ("2022-02-01", 0),  # Lunar New Year 2022
    ("2021-12-23", 1),  # old list wrongly closed this day
    ("2023-04-21", 0),  # Eid al-Fitr 2023
    ("2026-06-26", 1),  # last day of 2025-26
    ("2026-06-29", 0),  # after last day
    ("2025-09-04", 1),  # first day of 2025-26
])
def test_is_school_day(day, expected):
    assert is_school_day(D(day)) == expected


@pytest.mark.parametrize("day,expected", [
    ("2025-11-04", 1),  # Election Day 2025
    ("2026-06-19", 1),  # Juneteenth 2026
    ("2024-10-03", 1),  # Rosh Hashanah 2024
    ("2025-10-02", 1),  # Yom Kippur 2025
    ("2025-10-10", 0),
])
def test_is_holiday(day, expected):
    assert is_holiday(D(day)) == expected


def test_all_listed_dates_are_valid_iso():
    for s in ALL_HOLIDAYS | SCHOOL_CLOSURES:
        dt.date.fromisoformat(s)
    for start, end in SCHOOL_SESSIONS:
        assert dt.date.fromisoformat(start) < dt.date.fromisoformat(end)


def test_build_calendar_daily_shape_and_events():
    events = pd.DataFrame({
        "event_date": [D("2025-10-10")],
        "zone_prefix": ["K"],
    })
    cal = build_calendar_daily(D("2025-10-09"), D("2025-10-11"), events)
    assert list(cal.columns) == ["date", "zone_prefix", "is_holiday", "is_school_day", "is_major_event"]
    assert len(cal) == 3 * 5
    flagged = cal[cal["is_major_event"] == 1]
    assert flagged[["date", "zone_prefix"]].values.tolist() == [[D("2025-10-10"), "K"]]
    fri_b = cal[(cal["date"] == D("2025-10-10")) & (cal["zone_prefix"] == "B")].iloc[0]
    assert fri_b["is_school_day"] == 1 and fri_b["is_holiday"] == 0


def test_build_calendar_daily_empty_events():
    empty = pd.DataFrame(columns=["event_date", "zone_prefix"])
    cal = build_calendar_daily(D("2025-01-01"), D("2025-01-31"), empty)
    assert len(cal) == 31 * 5
    assert cal["is_major_event"].sum() == 0
