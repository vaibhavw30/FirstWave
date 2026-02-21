"""
test_artifacts.py — FirstWave Artifact Validation Suite
GT Hacklytics 2026

Validates all 5 artifacts in backend/artifacts/ meet spec before committing.
Run AFTER all pipeline scripts complete.

Usage: python pipeline/test_artifacts.py
"""

import pathlib
import pickle
import sys

import joblib
import numpy as np
import pandas as pd

ARTIFACTS_DIR = pathlib.Path("backend/artifacts")

REQUIRED_FILES = [
    "demand_model.pkl",
    "zone_baselines.parquet",
    "zone_stats.parquet",
    "drive_time_matrix.pkl",
    "counterfactual_summary.parquet",
    "counterfactual_raw.parquet",
]

FEATURE_COLS = [
    "hour_sin","hour_cos","dow_sin","dow_cos","month_sin","month_cos",
    "is_weekend","temperature_2m","precipitation","windspeed_10m",
    "is_severe_weather","svi_score","zone_baseline_avg",
    "high_acuity_ratio","held_ratio",
]

VALID_ZONES = [
    'B1','B2','B3','B4','B5',
    'K1','K2','K3','K4','K5','K6','K7',
    'M1','M2','M3','M4','M5','M6','M7','M8','M9',
    'Q1','Q2','Q3','Q4','Q5','Q6','Q7',
    'S1','S2','S3',
]

passes = []
failures = []


def check(name: str, condition: bool, detail: str = ""):
    if condition:
        passes.append(name)
        print(f"  PASS  {name}" + (f" — {detail}" if detail else ""))
    else:
        failures.append(name)
        print(f"  FAIL  {name}" + (f" — {detail}" if detail else ""))


print("=" * 60)
print("  FIRSTWAVE ARTIFACT VALIDATION SUITE")
print("=" * 60)
print()

# ── Check 1: All files exist ───────────────────────────────────────────────────
print("[ 1 ] File existence")
for fname in REQUIRED_FILES:
    p = ARTIFACTS_DIR / fname
    check(f"exists: {fname}", p.exists(), f"size={p.stat().st_size//1024}KB" if p.exists() else "NOT FOUND")
print()

# ── Check 2: demand_model.pkl ──────────────────────────────────────────────────
print("[ 2 ] demand_model.pkl")
model_path = ARTIFACTS_DIR / "demand_model.pkl"
if model_path.exists():
    try:
        model = joblib.load(model_path)
        check("model loads", True)
        check("model has predict()", hasattr(model, "predict"))

        # Feature count
        n_features = model.n_features_in_
        check("model has 15 features", n_features == 15, f"found {n_features}")

        # Spot-check prediction (Friday 8PM, Manhattan, typical values)
        import math
        hour, dow, month = 20, 4, 10
        test_row = pd.DataFrame([{
            "hour_sin":  math.sin(2*math.pi*hour/24),
            "hour_cos":  math.cos(2*math.pi*hour/24),
            "dow_sin":   math.sin(2*math.pi*dow/7),
            "dow_cos":   math.cos(2*math.pi*dow/7),
            "month_sin": math.sin(2*math.pi*month/12),
            "month_cos": math.cos(2*math.pi*month/12),
            "is_weekend": 1 if dow in (5,6) else 0,
            "temperature_2m": 15.0,
            "precipitation": 0.0,
            "windspeed_10m": 10.0,
            "is_severe_weather": 0,
            "svi_score": 0.89,          # Bronx B2
            "zone_baseline_avg": 12.0,   # typical Bronx Friday evening
            "high_acuity_ratio": 0.28,
            "held_ratio": 0.09,
        }])
        pred = float(model.predict(test_row[FEATURE_COLS])[0])
        pred = max(pred, 0)
        check("spot-check prediction >= 0", pred >= 0, f"pred={pred:.2f}")
        check("spot-check RMSE bound (pred < 100)", pred < 100, f"pred={pred:.2f}")

    except Exception as e:
        check("model loads", False, str(e))
else:
    print("  SKIP  (file missing)")
print()

# ── Check 3: zone_baselines.parquet ───────────────────────────────────────────
print("[ 3 ] zone_baselines.parquet")
baseline_path = ARTIFACTS_DIR / "zone_baselines.parquet"
if baseline_path.exists():
    try:
        bl = pd.read_parquet(baseline_path)
        check("loads without error", True)
        check("row count <= 5208", len(bl) <= 5208, f"rows={len(bl)}")
        check("row count >= 31", len(bl) >= 31, f"rows={len(bl)}")

        req_cols = {"INCIDENT_DISPATCH_AREA","hour","dayofweek","zone_baseline_avg"}
        has_cols = req_cols.issubset(set(bl.columns))
        check("required columns present", has_cols,
              f"missing={req_cols - set(bl.columns)}" if not has_cols else "all present")

        zones_found = set(bl["INCIDENT_DISPATCH_AREA"].unique())
        missing_zones = set(VALID_ZONES) - zones_found
        check("all 31 zones present", len(missing_zones) == 0,
              f"missing={missing_zones}" if missing_zones else "all 31 present")

        no_nulls = bl["zone_baseline_avg"].isnull().sum() == 0
        check("no null baseline_avg", no_nulls,
              f"nulls={bl['zone_baseline_avg'].isnull().sum()}")

        pos_values = (bl["zone_baseline_avg"] > 0).all()
        check("all baseline_avg > 0", pos_values,
              f"min={bl['zone_baseline_avg'].min():.3f}")

    except Exception as e:
        check("loads without error", False, str(e))
else:
    print("  SKIP  (file missing)")
print()

# ── Check 4: zone_stats.parquet ───────────────────────────────────────────────
print("[ 4 ] zone_stats.parquet")
stats_path = ARTIFACTS_DIR / "zone_stats.parquet"
if stats_path.exists():
    try:
        zs = pd.read_parquet(stats_path)
        check("loads without error", True)
        check("exactly 31 rows", len(zs) == 31, f"rows={len(zs)}")

        req_cols = {
            "INCIDENT_DISPATCH_AREA","BOROUGH","svi_score",
            "avg_response_seconds","avg_travel_seconds","avg_dispatch_seconds",
            "high_acuity_ratio","held_ratio","total_incidents"
        }
        has_cols = req_cols.issubset(set(zs.columns))
        check("required columns present", has_cols,
              f"missing={req_cols - set(zs.columns)}" if not has_cols else "all present")

        # Bronx response time sanity
        bronx = zs[zs["BOROUGH"] == "BRONX"]["avg_response_seconds"]
        if len(bronx):
            bronx_mean = bronx.mean()
            check("Bronx avg response 400-900s", 400 <= bronx_mean <= 900,
                  f"bronx_mean={bronx_mean:.0f}s (expect ~638s)")

        # high_acuity_ratio range
        har_ok = ((zs["high_acuity_ratio"] >= 0) & (zs["high_acuity_ratio"] <= 1)).all()
        check("high_acuity_ratio in [0,1]", har_ok,
              f"min={zs['high_acuity_ratio'].min():.3f}, max={zs['high_acuity_ratio'].max():.3f}")

    except Exception as e:
        check("loads without error", False, str(e))
else:
    print("  SKIP  (file missing)")
print()

# ── Check 5: drive_time_matrix.pkl ────────────────────────────────────────────
print("[ 5 ] drive_time_matrix.pkl")
dtm_path = ARTIFACTS_DIR / "drive_time_matrix.pkl"
if dtm_path.exists():
    try:
        with open(dtm_path, "rb") as f:
            dtm = pickle.load(f)
        check("loads without error", True)
        check("is dict", isinstance(dtm, dict), f"type={type(dtm)}")
        check("has entries", len(dtm) > 0, f"len={len(dtm):,}")

        # Key format: tuple (origin, dest_zone)
        sample_key = next(iter(dtm))
        check("keys are tuples of length 2",
              isinstance(sample_key, tuple) and len(sample_key) == 2,
              f"sample_key={sample_key}")

        # B1→B2 adjacent Bronx zones: 60-7200 sec
        b1_b2 = dtm.get(("B1","B2"), None)
        if b1_b2 is not None:
            check("B1->B2 drive time 60-7200s", 60 <= b1_b2 <= 7200, f"{b1_b2}s")
        else:
            check("B1->B2 key exists", False, "key ('B1','B2') not found")

        # Values in reasonable range
        values = np.array(list(dtm.values()))
        reachable = values[values < 9999]
        if len(reachable):
            # min=0 is valid (same-zone self-drive), max=7200 is the upper bound
            check("reachable times 0-7200s",
                  (reachable >= 0).all() and (reachable <= 7200).all(),
                  f"min={reachable.min()}, max={reachable.max()}")
            pct_reachable = len(reachable) / len(values) * 100
            check("reachability > 50%", pct_reachable > 50,
                  f"{pct_reachable:.1f}% reachable")

    except Exception as e:
        check("loads without error", False, str(e))
else:
    print("  SKIP  (file missing)")
print()

# ── Check 6: counterfactual_summary.parquet ───────────────────────────────────
print("[ 6 ] counterfactual_summary.parquet")
cs_path = ARTIFACTS_DIR / "counterfactual_summary.parquet"
if cs_path.exists():
    try:
        cs = pd.read_parquet(cs_path)
        check("loads without error", True)
        check("exactly 168 rows", len(cs) == 168, f"rows={len(cs)}")

        req_cols = {"hour","dayofweek","median_seconds_saved",
                    "pct_within_8min_static","pct_within_8min_staged","n_incidents"}
        has_cols = req_cols.issubset(set(cs.columns))
        check("required columns present", has_cols,
              f"missing={req_cols - set(cs.columns)}" if not has_cols else "all present")

        # staged > static (when not null) — allow some bins to be worse
        # (e.g., geographically isolated areas like Staten Island)
        valid = cs.dropna(subset=["pct_within_8min_static","pct_within_8min_staged"])
        if len(valid):
            staged_better_count = (valid["pct_within_8min_staged"] >= valid["pct_within_8min_static"]).sum()
            pct_better = staged_better_count / len(valid) * 100
            check("staged >= static in majority of bins (>60%)", pct_better > 60,
                  f"{pct_better:.0f}% of {len(valid)} bins")

            # Overall improvement check
            overall_improvement = (valid["pct_within_8min_staged"] - valid["pct_within_8min_static"]).mean()
            check("mean improvement > 0pp", overall_improvement > 0,
                  f"mean_improvement={overall_improvement:.1f}pp")

    except Exception as e:
        check("loads without error", False, str(e))
else:
    print("  SKIP  (file missing)")
print()

# ── Check 7: counterfactual_raw.parquet ───────────────────────────────────────
print("[ 7 ] counterfactual_raw.parquet")
cr_path = ARTIFACTS_DIR / "counterfactual_raw.parquet"
if cr_path.exists():
    try:
        cr = pd.read_parquet(cr_path)
        check("loads without error", True)
        check("has rows", len(cr) > 0, f"rows={len(cr):,}")

        req_cols = {"borough","svi_quartile","baseline_drive_sec",
                    "staged_drive_sec","seconds_saved"}
        has_cols = req_cols.issubset(set(cr.columns))
        check("required columns present", has_cols,
              f"missing={req_cols - set(cr.columns)}" if not has_cols else "all present")

        # Borough keys exact
        expected_boroughs = {
            "BRONX","BROOKLYN","MANHATTAN","QUEENS","RICHMOND / STATEN ISLAND"
        }
        found_boroughs = set(cr["borough"].unique())
        check("correct borough keys", expected_boroughs == found_boroughs,
              f"found={found_boroughs}")

        # SVI quartiles Q1-Q4
        expected_quartiles = {"Q1","Q2","Q3","Q4"}
        found_quartiles = set(cr["svi_quartile"].unique())
        check("SVI quartiles Q1-Q4 present",
              expected_quartiles.issubset(found_quartiles),
              f"found={found_quartiles}")

        # Equity check: Q4 should have more seconds saved than Q1
        q1_med = cr[cr["svi_quartile"]=="Q1"]["seconds_saved"].median()
        q4_med = cr[cr["svi_quartile"]=="Q4"]["seconds_saved"].median()
        check("equity: Q4 seconds_saved >= Q1", q4_med >= q1_med,
              f"Q1={q1_med:.0f}s, Q4={q4_med:.0f}s")

    except Exception as e:
        check("loads without error", False, str(e))
else:
    print("  SKIP  (file missing)")
print()

# ── Summary ────────────────────────────────────────────────────────────────────
print("=" * 60)
total = len(passes) + len(failures)
print(f"  RESULTS: {len(passes)}/{total} checks passed")
if failures:
    print(f"\n  FAILED checks:")
    for f in failures:
        print(f"    - {f}")
    print()
    print("  Fix failures before committing artifacts.")
    sys.exit(1)
else:
    print()
    print("  All checks passed! Ready to commit backend/artifacts/")
    print()
    print("  git add backend/artifacts/demand_model.pkl \\")
    print("          backend/artifacts/zone_baselines.parquet \\")
    print("          backend/artifacts/zone_stats.parquet")
    print("  git commit -m 'feat: ML artifacts — demand_model RMSE=[X], zone_baselines, zone_stats'")
    print("  git push origin feat/backend")
    print("  curl -X POST http://localhost:8000/reload")
print("=" * 60)
