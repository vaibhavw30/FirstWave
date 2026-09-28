"""
Holiday and NYC public-school calendars, Dec 2021 → Jun 2026.

Sources (all checked 2026-09-28):
  Federal holidays: U.S. OPM federal holiday schedule (observed dates).
  School years: official NYC DOE school-year calendar PDFs, schools.nyc.gov/calendar
    2021-22 doe-calendar-sy-21-22.pdf
    2022-23 parent-facing-calendar-2022-23.pdf
    2023-24 school-year-2023-24-calendar-corrected.pdf
    2024-25 school-year-2024-25-calendar-updated.pdf
    2025-26 school-year-2025-26-calendar.pdf
  "Closed" = every day the PDF says schools are closed or students do not attend,
  including clerical days that apply to K-8. Professional-development days that
  only affect high schools are treated as school days.
"""
import datetime as dt

import pandas as pd

ZONE_PREFIXES = ["B", "K", "M", "Q", "S"]


def _days(start: str, end: str) -> list[str]:
    """Every ISO date from start to end inclusive."""
    s, e = dt.date.fromisoformat(start), dt.date.fromisoformat(end)
    return [(s + dt.timedelta(days=i)).isoformat() for i in range((e - s).days + 1)]


# ── Holidays ───────────────────────────────────────────────────────────────────
FEDERAL_HOLIDAYS = {
    "2021-12-24", "2021-12-31",
    "2022-01-17", "2022-02-21", "2022-05-30", "2022-06-20", "2022-07-04",
    "2022-09-05", "2022-10-10", "2022-11-11", "2022-11-24", "2022-12-26",
    "2023-01-02", "2023-01-16", "2023-02-20", "2023-05-29", "2023-06-19",
    "2023-07-04", "2023-09-04", "2023-10-09", "2023-11-10", "2023-11-23", "2023-12-25",
    "2024-01-01", "2024-01-15", "2024-02-19", "2024-05-27", "2024-06-19",
    "2024-07-04", "2024-09-02", "2024-10-14", "2024-11-11", "2024-11-28", "2024-12-25",
    "2025-01-01", "2025-01-20", "2025-02-17", "2025-05-26", "2025-06-19",
    "2025-07-04", "2025-09-01", "2025-10-13", "2025-11-11", "2025-11-27", "2025-12-25",
    "2026-01-01", "2026-01-19", "2026-02-16", "2026-05-25", "2026-06-19",
}

# NYC-observed days with large demand shifts: Election Day, Rosh Hashanah (both
# days), Yom Kippur.
NYC_EXTRA_HOLIDAYS = {
    "2022-11-08", "2023-11-07", "2024-11-05", "2025-11-04",   # Election Day
    "2022-09-26", "2022-09-27", "2023-09-16", "2023-09-17",   # Rosh Hashanah
    "2024-10-03", "2024-10-04", "2025-09-23", "2025-09-24",
    "2022-10-05", "2023-09-25", "2024-10-12", "2025-10-02",   # Yom Kippur
}

ALL_HOLIDAYS = FEDERAL_HOLIDAYS | NYC_EXTRA_HOLIDAYS


# ── School calendar ────────────────────────────────────────────────────────────
SCHOOL_SESSIONS = [
    ("2021-09-13", "2022-06-27"),
    ("2022-09-08", "2023-06-27"),
    ("2023-09-07", "2024-06-26"),
    ("2024-09-05", "2025-06-26"),
    ("2025-09-04", "2026-06-26"),
]

SCHOOL_CLOSURES = set(
    # ── 2021-22 ──
    ["2021-09-16", "2021-10-11", "2021-11-02", "2021-11-11", "2021-11-25", "2021-11-26"]
    + _days("2021-12-24", "2021-12-31")
    + ["2022-01-17", "2022-02-01"]
    + _days("2022-02-21", "2022-02-25")
    + _days("2022-04-15", "2022-04-22")
    + ["2022-05-02", "2022-05-30", "2022-06-07", "2022-06-09", "2022-06-20"]
    # ── 2022-23 ──
    + ["2022-09-26", "2022-09-27", "2022-10-05", "2022-10-10", "2022-11-08",
       "2022-11-11", "2022-11-24", "2022-11-25"]
    + _days("2022-12-26", "2023-01-02")
    + ["2023-01-16"]
    + _days("2023-02-20", "2023-02-24")
    + ["2023-04-06", "2023-04-07"]
    + _days("2023-04-10", "2023-04-14")
    + ["2023-04-21", "2023-05-29", "2023-06-08", "2023-06-09", "2023-06-19"]
    # ── 2023-24 ──
    + ["2023-09-25", "2023-10-09", "2023-11-07", "2023-11-23", "2023-11-24"]
    + _days("2023-12-25", "2024-01-01")
    + ["2024-01-15"]
    + _days("2024-02-19", "2024-02-23")
    + ["2024-03-29", "2024-04-01", "2024-04-10"]
    + _days("2024-04-22", "2024-04-30")
    + ["2024-05-27", "2024-06-06", "2024-06-07", "2024-06-17", "2024-06-19"]
    # ── 2024-25 ──
    + ["2024-10-03", "2024-10-04", "2024-10-14", "2024-11-01", "2024-11-05",
       "2024-11-11", "2024-11-28", "2024-11-29"]
    + _days("2024-12-23", "2025-01-01")
    + ["2025-01-20", "2025-01-29"]
    + _days("2025-02-17", "2025-02-21")
    + ["2025-03-31"]
    + _days("2025-04-14", "2025-04-18")
    + ["2025-05-26", "2025-06-05", "2025-06-06", "2025-06-19"]
    # ── 2025-26 ──
    + ["2025-09-23", "2025-09-24", "2025-10-02", "2025-10-13", "2025-10-20",
       "2025-11-04", "2025-11-11", "2025-11-27", "2025-11-28"]
    + _days("2025-12-24", "2026-01-02")
    + ["2026-01-19"]
    + _days("2026-02-16", "2026-02-20")
    + ["2026-03-20"]
    + _days("2026-04-02", "2026-04-10")
    + ["2026-05-25", "2026-05-27", "2026-06-04", "2026-06-05", "2026-06-19"]
)


def is_holiday(d: dt.date) -> int:
    return int(d.isoformat() in ALL_HOLIDAYS)


def is_school_day(d: dt.date) -> int:
    if d.weekday() >= 5 or d.isoformat() in SCHOOL_CLOSURES:
        return 0
    for start, end in SCHOOL_SESSIONS:
        if dt.date.fromisoformat(start) <= d <= dt.date.fromisoformat(end):
            return 1
    return 0


def build_calendar_daily(start: dt.date, end: dt.date, event_days: pd.DataFrame) -> pd.DataFrame:
    """One row per (date, zone prefix) with holiday, school-day and major-event flags."""
    events = {
        (pd.Timestamp(d).date(), p)
        for d, p in zip(event_days["event_date"], event_days["zone_prefix"])
    }
    rows = []
    for i in range((end - start).days + 1):
        d = start + dt.timedelta(days=i)
        hol, school = is_holiday(d), is_school_day(d)
        for prefix in ZONE_PREFIXES:
            rows.append({
                "date": d,
                "zone_prefix": prefix,
                "is_holiday": hol,
                "is_school_day": school,
                "is_major_event": int((d, prefix) in events),
            })
    return pd.DataFrame(rows, columns=["date", "zone_prefix", "is_holiday", "is_school_day", "is_major_event"])
