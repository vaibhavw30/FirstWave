"""
Script 05 — XGBoost demand forecaster with lag features
FirstWave | GT Hacklytics 2026

Input:  $FW_PIPELINE_DATA/training_grid.parquet, $FW_ARTIFACTS_DIR/zone_baselines.parquet,
        $FW_ARTIFACTS_DIR/zone_stats.parquet (all from script 04)
Output: gate passed → $FW_ARTIFACTS_DIR/demand_model.pkl + model_metrics.json (exit 0)
        gate failed → $FW_PIPELINE_DATA/demand_model_candidate.pkl +
                      model_metrics_candidate.json (exit 1; artifacts untouched)

Early stopping and objective choice use the `valid` split only. `test` (2025)
and `test_recent` (2026 H1) are scored once.

Run: python pipeline/05_train_demand_model.py [--max-trees 2000]
"""

import argparse
import datetime as dt
import json
import os
import pathlib
import sys

import joblib
import numpy as np
import pandas as pd
import xgboost as xgb

from fw_config import (
    BASE_FEATURE_COLS, DATA_END, DATA_START, FEATURE_COLS, SPLIT_STARTS, ZONE_PREFIX_BOROUGH,
)
from fw_eval import deployment_gate, rmse_by_group, score

parser = argparse.ArgumentParser()
parser.add_argument("--max-trees", type=int, default=2000)
args = parser.parse_args()

PIPELINE_DATA = pathlib.Path(os.getenv("FW_PIPELINE_DATA", "pipeline/data"))
ARTIFACTS_DIR = pathlib.Path(os.getenv("FW_ARTIFACTS_DIR", "backend/artifacts"))
GRID_PQ = PIPELINE_DATA / "training_grid.parquet"
BASELINE_PQ = ARTIFACTS_DIR / "zone_baselines.parquet"
STATS_PQ = ARTIFACTS_DIR / "zone_stats.parquet"

for p in (GRID_PQ, BASELINE_PQ, STATS_PQ):
    if not p.exists():
        print(f"ERROR: {p} not found. Run 04_aggregate.py first.", file=sys.stderr)
        sys.exit(1)

ZONE = "INCIDENT_DISPATCH_AREA"
OBJECTIVES = ("reg:squarederror", "count:poisson")

# ── Step 1: load + merge ───────────────────────────────────────────────────────
grid = pd.read_parquet(GRID_PQ)
grid = grid.merge(pd.read_parquet(BASELINE_PQ), on=[ZONE, "hour", "dayofweek"], how="left")
grid = grid.merge(
    pd.read_parquet(STATS_PQ)[[ZONE, "svi_score", "high_acuity_ratio", "held_ratio"]],
    on=ZONE, how="left",
)
null_counts = grid[FEATURE_COLS].isna().sum()
if null_counts.any():
    print("ERROR: nulls in features:\n" + null_counts[null_counts > 0].to_string(), file=sys.stderr)
    sys.exit(1)
grid["BOROUGH"] = grid[ZONE].str[0].map(ZONE_PREFIX_BOROUGH)

parts = {s: grid[grid["split"] == s] for s in ("train", "valid", "test", "test_recent")}
for s, df in parts.items():
    print(f"  {s:<12} {len(df):>10,} rows   mean count {df['incident_count'].mean():.3f}")

PARAMS = {
    "n_estimators": args.max_trees,
    "max_depth": 6,
    "learning_rate": 0.05,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "random_state": 42,
    "n_jobs": -1,
    "tree_method": "hist",
    "early_stopping_rounds": 50,
}


def fit(features: list[str], objective: str) -> xgb.XGBRegressor:
    model = xgb.XGBRegressor(objective=objective, **PARAMS)
    model.fit(
        parts["train"][features], parts["train"]["incident_count"],
        eval_set=[(parts["valid"][features], parts["valid"]["incident_count"])],
        verbose=200,
    )
    return model


def predict(model, features, df) -> np.ndarray:
    return np.clip(model.predict(df[features]), 0, None)


# ── Step 2: pick the objective on `valid` ──────────────────────────────────────
candidates, valid_rmse = {}, {}
for obj in OBJECTIVES:
    print(f"\nTraining lag model, objective={obj} ...")
    candidates[obj] = fit(FEATURE_COLS, obj)
    valid_rmse[obj] = score(parts["valid"]["incident_count"],
                            predict(candidates[obj], FEATURE_COLS, parts["valid"]))["rmse"]
    print(f"  valid RMSE {valid_rmse[obj]:.4f}   best_iteration {candidates[obj].best_iteration}")
objective = min(valid_rmse, key=valid_rmse.get)
lag_model = candidates[objective]

print(f"\nTraining no-lag reference, objective={objective} ...")
no_lag_model = fit(BASE_FEATURE_COLS, objective)


# ── Step 3: score test + test_recent ───────────────────────────────────────────
def all_preds(df) -> dict:
    return {
        "lag": predict(lag_model, FEATURE_COLS, df),
        "no_lag": predict(no_lag_model, BASE_FEATURE_COLS, df),
        "naive_168h": df["lag_168h"].to_numpy(dtype=float),
        "baseline_avg": df["zone_baseline_avg"].to_numpy(dtype=float),
    }


results = {}
for split in ("test", "test_recent"):
    y = parts[split]["incident_count"]
    results[split] = {name: score(y, p) for name, p in all_preds(parts[split]).items()}

test_df = parts["test"]
test_preds = all_preds(test_df)
by_borough = {n: rmse_by_group(test_df["incident_count"], test_preds[n], test_df["BOROUGH"])
              for n in ("lag", "no_lag")}
by_hour = {n: [rmse_by_group(test_df["incident_count"], test_preds[n], test_df["hour"])[str(h)]
               for h in range(24)] for n in ("lag", "no_lag")}
gate = deployment_gate(results["test"]["lag"]["rmse"], results["test"]["no_lag"]["rmse"])

split_bounds = [start for _, start in SPLIT_STARTS[1:]] + [DATA_END + dt.timedelta(days=1)]
metrics = {
    "trained_at": dt.datetime.now().isoformat(timespec="seconds"),
    "objective": objective,
    "best_iteration": int(lag_model.best_iteration),
    "feature_cols": FEATURE_COLS,
    "splits": {name: [str(start), str(end - dt.timedelta(days=1))]
               for (name, start), end in zip(SPLIT_STARTS, split_bounds)},
    "data_window": [str(DATA_START), str(DATA_END)],
    "valid_rmse_by_objective": valid_rmse,
    "test": results["test"],
    "test_recent": results["test_recent"],
    "test_rmse_by_borough": by_borough,
    "test_rmse_by_hour": by_hour,
    "gate": gate,
}

# ── Step 4: report ─────────────────────────────────────────────────────────────
print()
print("=" * 72)
print("  FIRSTWAVE DEMAND MODEL — RESULTS")
print("=" * 72)
print(f"  objective {objective}   best_iteration {lag_model.best_iteration}")
for split in ("test", "test_recent"):
    print(f"\n  {split}:")
    print(f"    {'model':<14}{'RMSE':>10}{'MAE':>10}{'Poisson dev':>14}")
    for name, s in results[split].items():
        print(f"    {name:<14}{s['rmse']:>10.4f}{s['mae']:>10.4f}{s['poisson_deviance']:>14.4f}")
print("\n  2025 RMSE by borough (lag / no_lag):")
for b in sorted(by_borough["lag"]):
    print(f"    {b:<26}{by_borough['lag'][b]:>8.4f}{by_borough['no_lag'][b]:>10.4f}")
fi = pd.Series(lag_model.feature_importances_, index=FEATURE_COLS).sort_values(ascending=False)
print("\n  Top 10 features by gain share:")
print(fi.head(10).to_string())
print(f"\n  Deployment gate: improvement {gate['improvement']:.2%} "
      f"(need ≥ {gate['threshold']:.0%}) → {'PASSED' if gate['passed'] else 'FAILED'}")

if not gate["passed"]:
    joblib.dump(lag_model, PIPELINE_DATA / "demand_model_candidate.pkl")
    (PIPELINE_DATA / "model_metrics_candidate.json").write_text(json.dumps(metrics, indent=2))
    print("\n  Gate failed: backend/artifacts untouched. Candidate saved to pipeline/data/.")
    sys.exit(1)

joblib.dump(lag_model, ARTIFACTS_DIR / "demand_model.pkl")
(ARTIFACTS_DIR / "model_metrics.json").write_text(json.dumps(metrics, indent=2))
print(f"\n  Saved {ARTIFACTS_DIR / 'demand_model.pkl'} and model_metrics.json")

# ── Step 5: replay sanity check through the serving code path ─────────────────
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "backend"))
from models.demand_forecaster import DemandForecaster  # noqa: E402
from models.lag_features import actual_counts, to_wide  # noqa: E402
from models.replay import calendar_to_lookup  # noqa: E402

wide = to_wide(pd.read_parquet(ARTIFACTS_DIR / "hourly_counts.parquet"))
cal = calendar_to_lookup(pd.read_parquet(ARTIFACTS_DIR / "calendar_daily.parquet"))
forecaster = DemandForecaster(lag_model)
zone_stats = pd.read_parquet(STATS_PQ)
baselines = pd.read_parquet(BASELINE_PQ)
totals = {}
for label, day, hour in (("Fri 2025-10-10 20:00", dt.date(2025, 10, 10), 20),
                         ("Mon 2025-10-20 04:00", dt.date(2025, 10, 20), 4)):
    preds = forecaster.predict_all_zones(hour, day.weekday(), day.month, 15.0, 0.0, 10.0,
                                         zone_stats, baselines, replay_date=day,
                                         counts_wide=wide, calendar=cal)
    actual = actual_counts(wide, pd.Timestamp(day) + pd.Timedelta(hours=hour))
    totals[label] = sum(preds.values())
    top = sorted(preds.items(), key=lambda kv: kv[1], reverse=True)[:5]
    print(f"\n  {label}: city total predicted {sum(preds.values()):.1f}, actual {sum(actual.values())}")
    for zone, p in top:
        print(f"    {zone}: predicted {p:.1f}   actual {actual.get(zone)}")
ratio = totals["Fri 2025-10-10 20:00"] / max(totals["Mon 2025-10-20 04:00"], 1e-9)
print(f"\n  {'✓' if ratio > 2 else '⚠'} Friday 8 PM / Monday 4 AM demand ratio: {ratio:.1f}x (expect > 2)")
print("=" * 72)
