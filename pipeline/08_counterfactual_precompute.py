"""
Script 08 — Counterfactual Pre-Computation (staging v2)
FirstWave | GT Hacklytics 2026

Produces the before/after impact numbers behind the README's Key Results and the
dashboard's fallback impact panel.

For real 2025 Priority 1+2 calls (up to 150 per hour x weekday slot):
  - BEFORE: the call's recorded response time (dispatch + travel)
  - AFTER:  the same dispatch; travel scaled by (drive from the nearest staging site or
            station) / (drive from the nearest station). Sites are placed for the call's
            own hour by the same optimizer and inputs as /api/staging, with K = 5.

Outputs:
  backend/artifacts/counterfactual_summary.parquet  (168 rows)
  backend/artifacts/counterfactual_raw.parquet      (one row per scored call, K = 5)

Prerequisites: backend/artifacts/{demand_model.pkl, drive_time_matrix.pkl,
  zone_baselines.parquet, zone_stats.parquet, hourly_counts.parquet,
  calendar_daily.parquet, weather_hourly.parquet}, pipeline/data/incidents_cleaned.parquet,
  data/ems_stations.json

Run: pipeline/.venv/bin/python pipeline/08_counterfactual_precompute.py
"""

import pathlib
import sys
from itertools import product

import numpy as np
import pandas as pd

# ── Paths ──────────────────────────────────────────────────────────────────────
PIPELINE_DATA = pathlib.Path("pipeline/data")
ARTIFACTS_DIR = pathlib.Path("backend/artifacts")
CLEANED_PQ    = PIPELINE_DATA / "incidents_cleaned.parquet"
SUMMARY_OUT   = ARTIFACTS_DIR / "counterfactual_summary.parquet"
RAW_OUT       = ARTIFACTS_DIR / "counterfactual_raw.parquet"

REQUIRED = [ARTIFACTS_DIR / name for name in (
    "demand_model.pkl", "drive_time_matrix.pkl", "zone_baselines.parquet", "zone_stats.parquet",
    "hourly_counts.parquet", "calendar_daily.parquet", "weather_hourly.parquet")] + [CLEANED_PQ]
for p in REQUIRED:
    if not p.exists():
        print(f"ERROR: {p} not found.", file=sys.stderr)
        sys.exit(1)

# ── Constants ──────────────────────────────────────────────────────────────────
THRESHOLD             = 480   # 8-minute clinical target in seconds
MAX_INCIDENTS_PER_BIN = 150   # cap per (hour, dow) bin for compute speed
HEADLINE_K            = 5     # the dashboard's default ambulance count
SENSITIVITY_K         = (3, 7, 10)
BOROUGHS = ["BRONX", "BROOKLYN", "MANHATTAN", "QUEENS", "RICHMOND / STATEN ISLAND"]

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from fw_staging import HourlyStager  # noqa: E402
from models.coverage_model import call_level_after  # noqa: E402

# ── Step 1: Load artifacts ─────────────────────────────────────────────────────
print("Loading artifacts...")
stager = HourlyStager(ARTIFACTS_DIR)
coverage = stager.coverage

# ── Step 2: Load 2025 high-acuity incidents ────────────────────────────────────
print("\nLoading 2025 (test split) Priority 1+2 incidents from cleaned parquet...")
inc_all = pd.read_parquet(CLEANED_PQ, columns=[
    "INCIDENT_ID", "BOROUGH", "INCIDENT_DISPATCH_AREA",
    "hour", "dayofweek", "date_hour", "INCIDENT_RESPONSE_SECONDS_QY",
    "INCIDENT_TRAVEL_TM_SECONDS_QY", "svi_score",
    "split", "is_high_acuity", "is_valid_response",
])
incidents_test = inc_all[
    (inc_all["split"] == "test")
    & (inc_all["is_high_acuity"] == 1)
    & (inc_all["is_valid_response"] == 1)
].copy()
del inc_all

incidents_test["svi_quartile"] = pd.qcut(
    incidents_test["svi_score"], q=4, labels=["Q1", "Q2", "Q3", "Q4"]
).astype(str)

usable = np.isfinite(call_level_after(
    incidents_test["INCIDENT_RESPONSE_SECONDS_QY"], incidents_test["INCIDENT_TRAVEL_TM_SECONDS_QY"], 1.0))
print(f"2025 Priority 1+2 incidents: {len(incidents_test):,}")
print(f"  excluded (travel time missing, <= 0, or > response): {(~usable).sum():,} ({(~usable).mean():.2%})")
incidents_test = incidents_test[usable]
assert incidents_test["INCIDENT_DISPATCH_AREA"].isin(list(coverage.index)).all()

# ── Step 3: Sample up to 150 calls per (hour x dow) bin ───────────────────────
samples = []
for hour, dow in product(range(24), range(7)):
    b = incidents_test[(incidents_test["hour"] == hour) & (incidents_test["dayofweek"] == dow)]
    if len(b) > MAX_INCIDENTS_PER_BIN:
        b = b.sample(MAX_INCIDENTS_PER_BIN, random_state=42)
    samples.append(b)
calls = pd.concat(samples, ignore_index=True)
response = calls["INCIDENT_RESPONSE_SECONDS_QY"].to_numpy(dtype=float)
travel = calls["INCIDENT_TRAVEL_TM_SECONDS_QY"].to_numpy(dtype=float)
zone_idx = calls["INCIDENT_DISPATCH_AREA"].map(coverage.index).to_numpy(dtype=int)
hours = calls.groupby("date_hour").indices
print(f"\nScoring {len(calls):,} calls across {len(hours):,} distinct hours...")


def staged_response(K: int) -> np.ndarray:
    """Call-level staged response with K sites placed for each call's own hour."""
    ratio = np.empty(len(calls))
    for i, (ts, idx) in enumerate(hours.items()):
        sites = [p["zone"] for p in stager.staging(ts, K)]
        ratio[idx] = coverage.ratios(sites)[zone_idx[idx]]
        if (i + 1) % 1000 == 0:
            print(f"  K={K}: {i + 1:,}/{len(hours):,} hours placed", flush=True)
    return call_level_after(response, travel, ratio)


staged = staged_response(HEADLINE_K)
assert not np.isnan(staged).any()

# ── Step 4: Save parquet files (schemas unchanged) ────────────────────────────
raw_df = pd.DataFrame({
    "hour":                 calls["hour"].astype(int).to_numpy(),
    "dayofweek":            calls["dayofweek"].astype(int).to_numpy(),
    "incident_zone":        calls["INCIDENT_DISPATCH_AREA"].to_numpy(),
    "borough":              calls["BOROUGH"].to_numpy(),
    "svi_quartile":         calls["svi_quartile"].to_numpy(),
    "baseline_drive_sec":   response,   # name kept for the API; it is the full real response
    "staged_drive_sec":     staged,
    "seconds_saved":        response - staged,
    "baseline_within_8min": (response <= THRESHOLD).astype(int),
    "staged_within_8min":   (staged <= THRESHOLD).astype(int),
})
g = raw_df.groupby(["hour", "dayofweek"])
summary_df = pd.DataFrame({
    "median_seconds_saved":   g["seconds_saved"].median(),
    "pct_within_8min_static": g["baseline_within_8min"].mean() * 100,
    "pct_within_8min_staged": g["staged_within_8min"].mean() * 100,
    "n_incidents":            g.size(),
}).reindex(pd.MultiIndex.from_product([range(24), range(7)], names=["hour", "dayofweek"])).reset_index()
summary_df["n_incidents"] = summary_df["n_incidents"].fillna(0).astype(int)

summary_df.to_parquet(SUMMARY_OUT, index=False)
raw_df.to_parquet(RAW_OUT, index=False)
print(f"counterfactual_summary.parquet: {len(summary_df)} rows -> {SUMMARY_OUT}")
print(f"counterfactual_raw.parquet:     {len(raw_df):,} rows -> {RAW_OUT}")

# ── Step 5: Print key results ──────────────────────────────────────────────────
saved = raw_df["seconds_saved"]
static_pct = raw_df["baseline_within_8min"].mean() * 100
staged_pct = raw_df["staged_within_8min"].mean() * 100

print()
print("=" * 60)
print(f"  FIRSTWAVE COUNTERFACTUAL RESULTS (K={HEADLINE_K}, call level)")
print("=" * 60)
print(f"  Calls scored:                {len(raw_df):,}")
print(f"  Within 8 min -- before:      {static_pct:.1f}%")
print(f"  Within 8 min -- after:       {staged_pct:.1f}%  (+{staged_pct - static_pct:.1f} pp)")
print(f"  Median seconds saved:        {saved.median():.0f} s")
print(f"  Mean seconds saved:          {saved.mean():.0f} s")
print(f"  Calls whose zone improves:   {(saved > 0).mean() * 100:.1f}%")

print("\n  By Borough (before -> after, median / mean seconds saved):")
borough_pct = {}
for borough in BOROUGHS:
    bdf = raw_df[raw_df["borough"] == borough]
    b_pct = bdf["baseline_within_8min"].mean() * 100
    s_pct = bdf["staged_within_8min"].mean() * 100
    borough_pct[borough] = (b_pct, s_pct)
    print(f"    {borough[:25]:25s}: {b_pct:.1f}% -> {s_pct:.1f}%, "
          f"{bdf['seconds_saved'].median():.0f}s / {bdf['seconds_saved'].mean():.0f}s")

print("\n  By SVI Quartile (equity, informational):")
svi_saved = {}
for q in ["Q1", "Q2", "Q3", "Q4"]:
    qdf = raw_df[raw_df["svi_quartile"] == q]
    svi_saved[q] = (qdf["seconds_saved"].median(), qdf["seconds_saved"].mean())
    print(f"    {q}: {qdf['baseline_within_8min'].mean()*100:.1f}% -> {qdf['staged_within_8min'].mean()*100:.1f}%, "
          f"median {svi_saved[q][0]:.0f}s, mean {svi_saved[q][1]:.0f}s saved")

layouts = pd.Series([tuple(sorted(p["zone"] for p in stager.staging(ts, HEADLINE_K))) for ts in hours])
top = layouts.value_counts()
print(f"\n  Placement stability: {layouts.nunique()} distinct {HEADLINE_K}-site layouts over "
      f"{len(layouts):,} hours; most common {list(top.index[0])} in {top.iloc[0] / len(layouts):.0%} of hours")

print("\n  Sensitivity (same calls, sites re-placed each hour):")
sens = {HEADLINE_K: staged_pct}
for K in SENSITIVITY_K:
    sens[K] = (staged_response(K) <= THRESHOLD).mean() * 100
for K in sorted(sens):
    print(f"    K={K:2d}: {static_pct:.1f}% -> {sens[K]:.1f}% within 8 min")

readme = {
    "N_CALLS": f"{len(raw_df):,}",
    "STATIC_PCT": f"{static_pct:.1f}",
    "STAGED_PCT": f"{staged_pct:.1f}",
    "MEDIAN_SAVED": f"{saved.median():.0f}",
    "MEAN_SAVED": f"{saved.mean():.0f}",
    "IMPROVED_PCT": f"{(saved > 0).mean() * 100:.1f}",
    "BRONX_STATIC": f"{borough_pct['BRONX'][0]:.1f}",
    "BRONX_STAGED": f"{borough_pct['BRONX'][1]:.1f}",
    "N_HOURS": f"{len(layouts):,}",
    "N_SITE_SETS": f"{layouts.nunique()}",
    "TOP_SET": ", ".join(top.index[0]),
    "TOP_SET_PCT": f"{top.iloc[0] / len(layouts) * 100:.0f}",
    **{f"{q}_MEDIAN_SAVED": f"{svi_saved[q][0]:.0f}" for q in svi_saved},
    **{f"{q}_MEAN_SAVED": f"{svi_saved[q][1]:.0f}" for q in svi_saved},
    **{f"K{K}_PCT": f"{sens[K]:.1f}" for K in SENSITIVITY_K},
}
print("\n  README VALUES")
for k, v in readme.items():
    print(f"    {k}={v}")
print("=" * 60)
