"""
Download SMALL sample datasets for the simple_ems_weather pipeline.
FirstWave | GT Hacklytics 2026

Pulls a few hundred EMS incident rows (via the NYC Open Data Socrata API, so we
filter server-side instead of downloading the 2GB CSV) plus matching hourly NYC
weather for the same date window. Perfect for building/smoke-testing the datamorph
pipeline before pointing it at the full dataset.

Outputs (into datamorph/samples/):
  ems_incidents_sample.csv     ~ a few hundred rows, UPPERCASE headers (match full CSV)
  weather_sample.parquet       hourly weather for the window  (Parquet Source)
  weather_sample.csv           same, CSV (handy for previewing in datamorph)

Defaults: a full week (Mon-Sun) in October 2023, ~75 rows/day => ~525 rows total,
which gives day-of-week spread for the model. All tunable via CLI flags.

Run:
  python datamorph/python/download_sample_data.py
  python datamorph/python/download_sample_data.py --start 2023-10-02 --end 2023-10-08 --rows-per-day 75

Optional: set a Socrata app token to avoid throttling:
  export NYC_APP_TOKEN=xxxxxxxx
"""

import argparse
import datetime as dt
import os
import pathlib

import pandas as pd
import requests

# ── Paths ──────────────────────────────────────────────────────────────────────
OUT = pathlib.Path("datamorph/samples")
OUT.mkdir(parents=True, exist_ok=True)
EMS_OUT = OUT / "ems_incidents_sample.csv"
WX_PARQUET = OUT / "weather_sample.parquet"
WX_CSV = OUT / "weather_sample.csv"

# ── EMS (Socrata) ───────────────────────────────────────────────────────────────
EMS_RESOURCE = "https://data.cityofnewyork.us/resource/76xm-jjuj.csv"
# Lowercase Socrata field names; we UPPERCASE them after download so the existing
# pipeline SQL (which expects the full-download UPPERCASE headers) just works.
EMS_FIELDS = [
    # Socrata calls it incident_id; the full CSV download names it CAD_INCIDENT_ID,
    # which the pipeline SQL expects — alias it so headers match after UPPERCASE.
    "incident_id AS cad_incident_id", "incident_datetime", "incident_dispatch_area", "borough",
    "incident_response_seconds_qy", "incident_travel_tm_seconds_qy",
    "dispatch_response_seconds_qy", "final_severity_level_code", "held_indicator",
    "valid_incident_rspns_time_indc", "valid_dispatch_rspns_time_indc",
    "reopen_indicator", "transfer_indicator", "standby_indicator",
]

# ── Weather (Open-Meteo) ────────────────────────────────────────────────────────
OPEN_METEO = "https://archive-api.open-meteo.com/v1/archive"


def daterange(start: dt.date, end: dt.date):
    cur = start
    while cur <= end:
        yield cur
        cur += dt.timedelta(days=1)


def fetch_ems(start: dt.date, end: dt.date, rows_per_hour: int) -> pd.DataFrame:
    """One small request per (day, hour) so we get BOTH hour-of-day and day-of-week
    spread. Ordering by time within a single day pulls only midnight incidents, which
    gives the model no hourly signal — so we slice by hour explicitly instead."""
    from io import StringIO
    headers = {}
    token = os.environ.get("NYC_APP_TOKEN")
    if token:
        headers["X-App-Token"] = token

    frames = []
    for day in daterange(start, end):
        day_total = 0
        for hour in range(24):
            lo = f"{day.isoformat()}T{hour:02d}:00:00"
            hi = f"{day.isoformat()}T{hour:02d}:59:59"
            params = {
                "$select": ",".join(EMS_FIELDS),
                "$where": f"incident_datetime between '{lo}' and '{hi}' "
                          f"and valid_incident_rspns_time_indc = 'Y' and borough is not null",
                "$order": "incident_datetime",
                "$limit": rows_per_hour,
            }
            r = requests.get(EMS_RESOURCE, params=params, headers=headers, timeout=60)
            r.raise_for_status()
            df = pd.read_csv(StringIO(r.text))
            if len(df):
                frames.append(df)
                day_total += len(df)
        print(f"  {day}: {day_total} rows across 24 hours")

    ems = pd.concat(frames, ignore_index=True)
    ems.columns = [c.upper() for c in ems.columns]   # match full-download headers
    return ems


def fetch_weather(start: dt.date, end: dt.date) -> pd.DataFrame:
    params = {
        "latitude": 40.7128, "longitude": -74.0060,
        "start_date": start.isoformat(), "end_date": end.isoformat(),
        "hourly": "temperature_2m,precipitation,weathercode",
        "timezone": "America/New_York",
    }
    d = requests.get(OPEN_METEO, params=params, timeout=120).json()["hourly"]
    wx = pd.DataFrame(d)
    wx["date_hour"] = pd.to_datetime(wx.pop("time"))
    return wx[["date_hour", "temperature_2m", "precipitation", "weathercode"]]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2023-10-02", help="window start (YYYY-MM-DD)")
    ap.add_argument("--end", default="2023-10-08", help="window end (YYYY-MM-DD)")
    ap.add_argument("--rows-per-hour", type=int, default=3,
                    help="EMS rows to pull per (day, hour) — gives hour-of-day spread")
    args = ap.parse_args()

    start = dt.date.fromisoformat(args.start)
    end = dt.date.fromisoformat(args.end)
    if end < start:
        raise SystemExit("--end must be on or after --start")

    print(f"Window: {start} -> {end}")
    print("Fetching EMS incidents (Socrata, per-day-per-hour)...")
    ems = fetch_ems(start, end, args.rows_per_hour)
    ems.to_csv(EMS_OUT, index=False)
    print(f"  wrote {len(ems):,} rows -> {EMS_OUT}")

    print("Fetching weather (Open-Meteo)...")
    wx = fetch_weather(start, end)
    wx.to_csv(WX_CSV, index=False)
    weather_target = WX_CSV
    try:
        wx.to_parquet(WX_PARQUET, index=False)
        weather_target = WX_PARQUET
        print(f"  wrote {len(wx):,} hourly rows -> {WX_PARQUET} (+ .csv)")
    except ImportError:
        print(f"  wrote {len(wx):,} hourly rows -> {WX_CSV} "
              "(pyarrow not installed — skipped .parquet; CSV works fine as a Source)")

    print("\nDone. Point your datamorph Sources at:")
    print(f"  incidents_csv -> {EMS_OUT}")
    print(f"  weather       -> {weather_target}")
    print("\nNote: this sample spans a short window, so zone_baseline_avg and the model")
    print("are illustrative only — use it to verify the pipeline runs, not for real numbers.")


if __name__ == "__main__":
    main()
