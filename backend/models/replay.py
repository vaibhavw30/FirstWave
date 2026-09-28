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


# Request defaults when neither the request nor the weather artifact supplies a value.
DEFAULT_WEATHER = {"temperature": 15.0, "precipitation": 0.0, "windspeed": 10.0}
WEATHER_FLAG_COLS = ("is_severe_weather", "is_extreme_heat", "is_heat_emergency")


def weather_to_lookup(df) -> dict:
    """weather_hourly rows -> {pd.Timestamp hour: {temperature, precipitation, windspeed, flags...}}."""
    import pandas as pd
    lookup = {}
    for row in df.itertuples(index=False):
        lookup[pd.Timestamp(row.date_hour)] = {
            "temperature": float(row.temperature_2m),
            "precipitation": float(row.precipitation),
            "windspeed": float(row.windspeed_10m),
            **{c: int(getattr(row, c)) for c in WEATHER_FLAG_COLS},
        }
    return lookup


def resolve_weather(lookup: dict | None, d: dt.date, hour: int,
                    temperature: float | None, precipitation: float | None,
                    windspeed: float | None) -> tuple[dict, dict | None, str]:
    """(values, flags, source). If the request gives no weather at all and the
    artifact has this hour, use the real weather and its training-defined flags
    ("actual"). Otherwise it is a what-if: request values, defaults for any
    missing, and flags derived by the forecaster ("request")."""
    import pandas as pd
    requested = {"temperature": temperature, "precipitation": precipitation, "windspeed": windspeed}
    if all(v is None for v in requested.values()) and lookup is not None:
        row = lookup.get(pd.Timestamp(d) + pd.Timedelta(hours=hour))
        if row is not None:
            values = {k: row[k] for k in DEFAULT_WEATHER}
            flags = {c: row[c] for c in WEATHER_FLAG_COLS}
            return values, flags, "actual"
    values = {k: float(v) if v is not None else DEFAULT_WEATHER[k] for k, v in requested.items()}
    return values, None, "request"
