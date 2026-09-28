"""Replay-by-date rules shared by /api/heatmap and /api/staging."""
import calendar
import datetime as dt

REPLAY_START = dt.date(2025, 1, 1)
REPLAY_END = dt.date(2026, 6, 30)
STANDIN_YEAR = 2025

_DEFAULT_FLAGS = {"is_holiday": 0, "is_school_day": 1, "is_major_event": 0}


class OutOfReplayRange(ValueError):
    pass


def resolve_standin_date(month: int, dow: int, year: int = STANDIN_YEAR) -> dt.date:
    """Lower-median date in (year, month) whose weekday is dow (0 = Monday)."""
    n_days = calendar.monthrange(year, month)[1]
    matches = [dt.date(year, month, d) for d in range(1, n_days + 1)
               if dt.date(year, month, d).weekday() == dow]
    return matches[(len(matches) - 1) // 2]


def resolve_request(date: dt.date | None, dow: int, month: int) -> tuple[dt.date, int, int]:
    """(replay_date, dow, month). A given date wins over dow/month."""
    if date is None:
        return resolve_standin_date(month, dow), dow, month
    if not (REPLAY_START <= date <= REPLAY_END):
        raise OutOfReplayRange(f"date must be between {REPLAY_START} and {REPLAY_END}, got {date}")
    return date, date.weekday(), date.month


def calendar_to_lookup(df) -> dict:
    lookup = {}
    for row in df.itertuples(index=False):
        # pd.Timestamp subclasses datetime (which subclasses date), so test datetime first.
        d = row.date.date() if isinstance(row.date, dt.datetime) else row.date
        lookup[(d, row.zone_prefix)] = {
            "is_holiday": int(row.is_holiday),
            "is_school_day": int(row.is_school_day),
            "is_major_event": int(row.is_major_event),
        }
    return lookup


def calendar_flags(lookup: dict | None, d: dt.date | None, zone_prefix: str) -> dict:
    if lookup is None or d is None:
        return dict(_DEFAULT_FLAGS)
    return dict(lookup.get((d, zone_prefix), _DEFAULT_FLAGS))
