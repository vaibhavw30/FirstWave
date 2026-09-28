"""
Script 07 — Staging Optimizer Validation (staging v2)
FirstWave | GT Hacklytics 2026

Validates the coverage optimizer (backend/models/staging_optimizer.py) on 3 replayed
hours, with the same inputs as /api/staging (pipeline/fw_staging.py).
This is a confidence check -- NOT an artifact producer. Exits 1 if a staging check fails.

Prerequisites: backend/artifacts/{demand_model.pkl, drive_time_matrix.pkl,
  zone_baselines.parquet, zone_stats.parquet, hourly_counts.parquet,
  calendar_daily.parquet, weather_hourly.parquet}, data/ems_stations.json

Run: pipeline/.venv/bin/python pipeline/07_staging_optimizer.py
"""

import itertools
import pathlib
import sys

import numpy as np
import pandas as pd

ARTIFACTS_DIR = pathlib.Path("backend/artifacts")
for name in ("demand_model.pkl", "drive_time_matrix.pkl", "zone_baselines.parquet", "zone_stats.parquet",
             "hourly_counts.parquet", "calendar_daily.parquet", "weather_hourly.parquet"):
    if not (ARTIFACTS_DIR / name).exists():
        print(f"ERROR: {ARTIFACTS_DIR / name} not found. Run Scripts 04–06 first.", file=sys.stderr)
        sys.exit(1)

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from fw_staging import HourlyStager  # noqa: E402
from models.coverage_model import pct_within  # noqa: E402
from models.demand_forecaster import VALID_ZONES  # noqa: E402
from models.staging_optimizer import ZONE_BOROUGH_PREFIX  # noqa: E402

K = 5

print("Loading artifacts...")
stager = HourlyStager(ARTIFACTS_DIR)
coverage, optimizer = stager.coverage, stager.optimizer
failures = []


def check(name: str, ok: bool, detail: str = ""):
    print(f"  {'PASS' if ok else 'FAIL'}: {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        failures.append(name)


def brute_force_best(counts: dict, k: int, wf: float) -> float:
    """Best expected calls within 8 min over every k-subset of sites (no borough rule)."""
    n = len(coverage.zones)
    ratio = np.hstack([coverage.ratio, np.ones((n, 1))])
    P = pct_within(coverage.dispatch[:, None] + coverage.travel[:, None] * wf * ratio)
    d = np.array([max(counts[z], 0.01) for z in coverage.zones])
    return max(float((d * P[:, list(S) + [n]].max(axis=1)).sum())
               for S in itertools.combinations(range(n), k))


# ── Step 2: Validate 3 scenarios ──────────────────────────────────────────────
scenarios = [
    ("Monday 4AM (quiet)", pd.Timestamp("2025-10-20 04:00")),
    ("Wednesday Noon",     pd.Timestamp("2025-10-22 12:00")),
    ("Friday 8PM (peak)",  pd.Timestamp("2025-10-10 20:00")),
]

results = {}
for label, ts in scenarios:
    counts, wf = stager.demand(ts)
    staging = stager.staging(ts, K)
    top5 = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:5]
    results[label] = {"ts": ts, "counts": counts, "wf": wf, "staging": staging, "top5": top5}

    print(f"\n{'─'*50}")
    print(f"Scenario: {label}  (weather factor {wf:.3f})")
    print(f"  Top 5 zones by predicted demand:")
    for zone, count in top5:
        bar = "#" * min(int(count), 30)
        print(f"    {zone}: {count:.1f} {bar}")
    print(f"  Total city demand: {sum(counts.values()):.1f} incidents/hr")
    print(f"  Staging sites (K={K}):")
    for p in staging:
        print(f"    [{p['staging_index']}] {p['zone']} ({p['lon']:.4f}, {p['lat']:.4f}) "
              f"improves {p['cluster_zones']} ({p['predicted_demand_coverage']:.1f} demand)")

# ── Step 3: Demand checks (unchanged from v1; informational) ─────────────────
print("\n" + "=" * 55)
print("  SCRIPT 07 -- VALIDATION CHECKS")
print("=" * 55)

fri_top5_zones = [z for z, _ in results["Friday 8PM (peak)"]["top5"]]
bk_in_top5 = sum(1 for z in fri_top5_zones if z.startswith(("B", "K")))
print(f"\n  Check 1: Friday 8PM top-5 = {fri_top5_zones}")
if bk_in_top5 >= 3:
    print(f"  PASS: {bk_in_top5}/5 are B/K zones (Bronx/Brooklyn)")
else:
    print(f"  FAIL: Only {bk_in_top5}/5 are B/K zones -- check zone_baseline_avg merge")

mon_counts = results["Monday 4AM (quiet)"]["counts"]
mon_max = max(mon_counts.values())
mon_mean = sum(mon_counts.values()) / len(mon_counts)
print(f"\n  Check 2: Monday 4AM -- max={mon_max:.2f}, mean={mon_mean:.2f}")
if mon_max < 8.0:
    print(f"  PASS: Monday 4AM max demand < 8 (quiet period)")
else:
    print(f"  WARNING: Monday 4AM max = {mon_max:.1f} -- seems high for quiet period")

fri_total = sum(results["Friday 8PM (peak)"]["counts"].values())
mon_total = sum(results["Monday 4AM (quiet)"]["counts"].values())
ratio = fri_total / mon_total if mon_total > 0 else 0
print(f"\n  Check 3: Demand ratio Friday 8PM / Monday 4AM = {ratio:.1f}x")
if ratio > 2.0:
    print(f"  PASS: Friday peak is {ratio:.1f}x Monday quiet")
else:
    print(f"  FAIL: Ratio < 2x -- model not capturing temporal patterns")

# ── Step 4: Staging checks (hard; exit 1 on failure) ─────────────────────────
print(f"\n  Check 4: coverage optimizer")
for label, r in results.items():
    counts, wf = r["counts"], r["wf"]
    sites = [p["zone"] for p in r["staging"]]
    check(f"{label}: {K} distinct valid sites", len(set(sites)) == K and set(sites) <= set(VALID_ZONES),
          str(sites))
    check(f"{label}: every borough has a site",
          {ZONE_BOROUGH_PREFIX[s[0]] for s in sites} == set(ZONE_BOROUGH_PREFIX.values()))
    staged = optimizer.expected_within(sites, counts, wf)
    stations_only = optimizer.expected_within([], counts, wf)
    check(f"{label}: staged coverage > stations only", staged > stations_only,
          f"{stations_only:.1f} -> {staged:.1f} expected calls within 8 min")
    k3 = [p["zone"] for p in stager.staging(r["ts"], 3)]
    best = brute_force_best(counts, 3, wf)
    check(f"{label}: K=3 matches brute force",
          abs(optimizer.expected_within(k3, counts, wf) - best) <= 1e-6, f"{best:.4f}")

fri = sorted(p["zone"] for p in results["Friday 8PM (peak)"]["staging"])
mon = sorted(p["zone"] for p in results["Monday 4AM (quiet)"]["staging"])
print(f"\n  Placement: Friday 8PM {fri} vs Monday 4AM {mon} "
      f"({'same sites' if fri == mon else 'sites differ'})")

print("\n" + "=" * 55)
if failures:
    print(f"  {len(failures)} staging check(s) FAILED: {failures}")
    print("=" * 55)
    sys.exit(1)
print("  -> All staging checks pass: run pipeline/.venv/bin/python pipeline/08_counterfactual_precompute.py")
print("=" * 55)
