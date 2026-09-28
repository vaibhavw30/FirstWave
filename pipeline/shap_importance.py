"""
SHAP feature importance for the shipped demand model.
FirstWave | GT Hacklytics 2026

Exact TreeSHAP (XGBoost's built-in pred_contribs) on the 2025 test split, the
same rows 05 scores the model on. Values are in log space (count:poisson), so a
feature's SHAP value multiplies the prediction by exp(value).

Input:  pipeline/data/training_grid.parquet, backend/artifacts/{demand_model.pkl,
        zone_baselines.parquet, zone_stats.parquet}
Output: docs/images/shap_importance.png (bar chart of mean |SHAP|), table on stdout

Run: python pipeline/shap_importance.py
"""
import pathlib

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import numpy as np
import pandas as pd
import xgboost as xgb

from fw_config import FEATURE_COLS, LAG_FEATURE_COLS

PIPELINE_DATA = pathlib.Path("pipeline/data")
ARTIFACTS_DIR = pathlib.Path("backend/artifacts")
PNG_OUT = pathlib.Path("docs/images/shap_importance.png")
ZONE = "INCIDENT_DISPATCH_AREA"

GROUPS = {
    "Long-run baseline": ["zone_baseline_avg"],
    "Recent history (lags)": LAG_FEATURE_COLS,
    "Weather": ["temperature_2m", "precipitation", "windspeed_10m", "is_severe_weather",
                "is_extreme_heat", "is_heat_emergency", "subway_disruption_idx"],
    "Time": ["hour_sin", "hour_cos", "dow_sin", "dow_cos", "month_sin", "month_cos", "is_weekend"],
    "Calendar": ["is_holiday", "is_school_day", "is_major_event"],
    "Zone character": ["svi_score", "high_acuity_ratio", "held_ratio"],
}
GROUP_COLORS = {
    "Long-run baseline": "#C62828",
    "Recent history (lags)": "#FB8C00",
    "Weather": "#1E88E5",
    "Time": "#00897B",
    "Calendar": "#8E24AA",
    "Zone character": "#757575",
}
FEATURE_GROUP = {f: g for g, fs in GROUPS.items() for f in fs}

# ── Load the 2025 test rows exactly as 05 builds them ─────────────────────────
grid = pd.read_parquet(PIPELINE_DATA / "training_grid.parquet")
grid = grid[grid["split"] == "test"]
grid = grid.merge(pd.read_parquet(ARTIFACTS_DIR / "zone_baselines.parquet"),
                  on=[ZONE, "hour", "dayofweek"], how="left")
grid = grid.merge(
    pd.read_parquet(ARTIFACTS_DIR / "zone_stats.parquet")[[ZONE, "svi_score", "high_acuity_ratio", "held_ratio"]],
    on=ZONE, how="left",
)
X = grid[FEATURE_COLS].astype(float)
model = joblib.load(ARTIFACTS_DIR / "demand_model.pkl")

rmse = float(np.sqrt(np.mean((np.clip(model.predict(X), 0, None) - grid["incident_count"]) ** 2)))
print(f"2025 test rows: {len(X):,}   RMSE {rmse:.4f} (should match model_metrics.json test.lag.rmse)")

# ── TreeSHAP ──────────────────────────────────────────────────────────────────
# iteration_range matches model.predict, which stops at best_iteration.
contrib = model.get_booster().predict(
    xgb.DMatrix(X), pred_contribs=True, iteration_range=(0, model.best_iteration + 1))
phi = contrib[:, :-1]
bias = float(contrib[0, -1])
mean_abs = np.abs(phi).mean(axis=0)
share = mean_abs / mean_abs.sum()
order = np.argsort(-mean_abs)

print(f"Start value exp(bias) = {np.exp(bias):.2f} calls/zone-hour\n")
print(f"{'feature':<24}{'mean|SHAP|':>11}{'typical effect':>16}{'share':>8}")
for i in order:
    print(f"{FEATURE_COLS[i]:<24}{mean_abs[i]:>11.4f}{f'x/÷{np.exp(mean_abs[i]):.3f}':>16}{share[i]:>8.1%}")

idx = {f: i for i, f in enumerate(FEATURE_COLS)}
group_abs = {g: np.abs(phi[:, [idx[f] for f in fs]].sum(axis=1)).mean() for g, fs in GROUPS.items()}
total = sum(group_abs.values())
print("\nBy group (SHAP summed within group per row, then mean |.|):")
for g, v in group_abs.items():
    print(f"  {g:<24}{v / total:>7.1%}")

# ── Bar chart ─────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(10, 8.5), dpi=150)
names = [FEATURE_COLS[i] for i in order][::-1]
vals = mean_abs[order][::-1]
shares = share[order][::-1]
bars = ax.barh(names, vals, color=[GROUP_COLORS[FEATURE_GROUP[n]] for n in names])
for bar, v, s_ in zip(bars, vals, shares):
    ax.text(bar.get_width() + 0.004, bar.get_y() + bar.get_height() / 2,
            f"{v:.3f} ({s_:.1%})", va="center", fontsize=8)
ax.set_xlim(0, vals.max() * 1.22)
ax.set_xlabel("mean |SHAP value|  (log space: a value v scales the prediction by $e^v$)")
ax.set_title(f"Demand model feature importance — mean |SHAP| on 2025 test set\n"
             f"{len(X):,} zone-hours · exact TreeSHAP · XGBoost count:poisson",
             fontsize=11, loc="left")
ax.tick_params(axis="y", labelsize=8.5)
ax.spines[["top", "right"]].set_visible(False)
ax.legend(
    handles=[Patch(color=GROUP_COLORS[g], label=f"{g} ({v / total:.0%})") for g, v in group_abs.items()],
    title="Feature group (share)", loc="lower right", fontsize=8, title_fontsize=8.5, frameon=False,
)
fig.tight_layout()
PNG_OUT.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(PNG_OUT, facecolor="white")
print(f"\nWrote {PNG_OUT}")
