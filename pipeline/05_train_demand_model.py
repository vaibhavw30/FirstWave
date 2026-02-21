"""
Script 05 — XGBoost Demand Forecaster
FirstWave | GT Hacklytics 2026

Input:  pipeline/data/incidents_aggregated.parquet  (from Script 04)
        backend/artifacts/zone_baselines.parquet    (from Script 04)
        backend/artifacts/zone_stats.parquet        (from Script 04)
Output: backend/artifacts/demand_model.pkl

Run: python pipeline/05_train_demand_model.py
"""

import math
import pathlib
import sys
import joblib
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import mean_squared_error, mean_absolute_error

# ── Paths ──────────────────────────────────────────────────────────────────────
PIPELINE_DATA = pathlib.Path("pipeline/data")
ARTIFACTS_DIR = pathlib.Path("backend/artifacts")
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

AGGD_PQ     = PIPELINE_DATA / "incidents_aggregated.parquet"
BASELINE_PQ = ARTIFACTS_DIR / "zone_baselines.parquet"
STATS_PQ    = ARTIFACTS_DIR / "zone_stats.parquet"
MODEL_OUT   = ARTIFACTS_DIR / "demand_model.pkl"

for p in [AGGD_PQ, BASELINE_PQ, STATS_PQ]:
    if not p.exists():
        print(f"ERROR: {p} not found. Run 04_aggregate.py first.", file=sys.stderr)
        sys.exit(1)

# ── Feature columns ────────────────────────────────────────────────────────────
# ORDER IS FROZEN after first training — changing order breaks demand_model.pkl.
# Inference in backend/models/demand_forecaster.py must use this exact list.
# New features appended at end to preserve original 15-feature order.

FEATURE_COLS = [
    # ── Original 15 ────────────────────────────────────────────────────────────
    "hour_sin",           # sin(2π × hour / 24)
    "hour_cos",           # cos(2π × hour / 24)
    "dow_sin",            # sin(2π × dayofweek / 7)
    "dow_cos",            # cos(2π × dayofweek / 7)
    "month_sin",          # sin(2π × month / 12)
    "month_cos",          # cos(2π × month / 12)
    "is_weekend",         # 1 if dow in (5, 6)
    "temperature_2m",     # °C from Open-Meteo
    "precipitation",      # mm/hr from Open-Meteo
    "windspeed_10m",      # km/h from Open-Meteo
    "is_severe_weather",  # 1 if WMO weathercode in severe set
    "svi_score",          # CDC SVI RPL_THEMES 0–1 per zone
    "zone_baseline_avg",  # MOST IMPORTANT: rolling avg incidents per (zone, hour, dow)
    "high_acuity_ratio",  # historical pct of Priority 1+2 codes for this zone
    "held_ratio",         # historical pct of held calls for this zone

    # ── New features from Script 02 enrichment (added in priority order) ──────
    "is_holiday",             # 1 on federal + NYC-observed holidays
    "is_major_event",         # 1 if NYC-permitted special event in this zone's borough
    "is_school_day",          # 1 on NYC DOE instructional days
    "is_heat_emergency",      # 1 when sustained temp >= 32.2°C or any hour >= 35°C
    "is_extreme_heat",        # 1 when temperature_2m >= 35°C (95°F)
    "subway_disruption_idx",  # 0–1 normalized monthly MTA major incidents count
]

print(f"Feature columns: {len(FEATURE_COLS)}")
for i, f in enumerate(FEATURE_COLS):
    marker = "  [NEW]" if i >= 15 else ""
    print(f"  [{i:02d}] {f}{marker}")

# ── Step 1: Load data ──────────────────────────────────────────────────────────
print("\nLoading incidents_aggregated...")
agg_pd = pd.read_parquet(AGGD_PQ)
print(f"  Loaded {len(agg_pd):,} rows")
print(f"  Columns: {list(agg_pd.columns)}")

print("\nLoading zone_baselines.parquet...")
baselines = pd.read_parquet(BASELINE_PQ)
print(f"  {len(baselines)} rows, columns: {list(baselines.columns)}")

print("\nLoading zone_stats.parquet...")
zone_stats = pd.read_parquet(STATS_PQ)
print(f"  {len(zone_stats)} rows, columns: {list(zone_stats.columns)}")

# ── Step 2: Validate enrichment columns are present ───────────────────────────
NEW_FEATURE_COLS = FEATURE_COLS[15:]  # everything after the original 15
missing = [c for c in NEW_FEATURE_COLS if c not in agg_pd.columns]
if missing:
    print(f"\nERROR: Missing new feature columns: {missing}", file=sys.stderr)
    print("       Re-run pipeline/04_aggregate.py (which requires 02_weather_merge.py)", file=sys.stderr)
    sys.exit(1)
print(f"\nAll {len(NEW_FEATURE_COLS)} new feature columns present in aggregated data ✓")

# ── Step 3: Merge baseline features ───────────────────────────────────────────
agg_pd = agg_pd.merge(
    baselines[["INCIDENT_DISPATCH_AREA", "hour", "dayofweek", "zone_baseline_avg"]],
    on=["INCIDENT_DISPATCH_AREA", "hour", "dayofweek"],
    how="left",
)
agg_pd = agg_pd.merge(
    zone_stats[["INCIDENT_DISPATCH_AREA", "high_acuity_ratio", "held_ratio"]],
    on="INCIDENT_DISPATCH_AREA",
    how="left",
)

# Fill nulls — these should not be needed if pipeline ran cleanly
FILL_DEFAULTS = {
    "zone_baseline_avg":     1.0,
    "high_acuity_ratio":     0.23,
    "held_ratio":            0.06,
    # New features: 0 is the correct default for binary flags
    "is_holiday":            0,
    "is_major_event":        0,
    "is_school_day":         0,
    "is_heat_emergency":     0,
    "is_extreme_heat":       0,
    "subway_disruption_idx": 0.5,  # median; 0.5 signals "unknown", not "no disruption"
}
for col, default in FILL_DEFAULTS.items():
    if col in agg_pd.columns:
        n_nulls = agg_pd[col].isnull().sum()
        if n_nulls > 0:
            print(f"  Filling {n_nulls:,} nulls in '{col}' with {default}")
        agg_pd[col] = agg_pd[col].fillna(default)

print(f"\nAfter merge: {len(agg_pd):,} rows")
print(f"  Training rows: {(agg_pd['split']=='train').sum():,}")
print(f"  Test rows:     {(agg_pd['split']=='test').sum():,}")

print("\nNull counts in FEATURE_COLS (should all be 0):")
null_counts = agg_pd[FEATURE_COLS].isnull().sum()
any_nulls = null_counts[null_counts > 0]
if len(any_nulls):
    print(any_nulls.to_string())
    if "zone_baseline_avg" in any_nulls.index:
        print("\nERROR: zone_baseline_avg has nulls -- merge failed!")
        print("Check that column name is 'INCIDENT_DISPATCH_AREA' (not 'zone_code')")
        sys.exit(1)
else:
    print("  All zeros ✓")

# ── Step 4: Train/test split ───────────────────────────────────────────────────
train = agg_pd[agg_pd["split"] == "train"].copy()
test  = agg_pd[agg_pd["split"] == "test"].copy()

X_train, y_train = train[FEATURE_COLS], train["incident_count"]
X_test,  y_test  = test[FEATURE_COLS],  test["incident_count"]

print(f"\nX_train: {X_train.shape}")
print(f"X_test:  {X_test.shape}")

print(f"\ny_train stats:")
print(y_train.describe().to_string())

# Quick feature distribution check for new columns
print(f"\nNew feature distributions in train set:")
for col in NEW_FEATURE_COLS:
    if col in train.columns:
        pct = train[col].mean() * 100
        print(f"  {col:<26} mean={train[col].mean():.4f}  "
              f"({pct:.1f}%  min={train[col].min():.3f}  max={train[col].max():.3f})")

# ── Step 5: Train XGBoost ─────────────────────────────────────────────────────
PARAMS = {
    "n_estimators":          300,
    "max_depth":             6,
    "learning_rate":         0.05,
    "subsample":             0.8,
    "colsample_bytree":      0.8,
    "random_state":          42,
    "n_jobs":               -1,
    "tree_method":          "hist",  # fast on CPU
    "early_stopping_rounds": 20,     # XGBoost 3.x: must be in constructor
}

print(f"\nTraining XGBoost with {len(FEATURE_COLS)} features...")
print("(this takes 5–10 minutes on CPU)")

model = xgb.XGBRegressor(**PARAMS)
model.fit(
    X_train, y_train,
    eval_set=[(X_test, y_test)],
    verbose=50,
)

# ── Step 6: Evaluate ──────────────────────────────────────────────────────────
preds = np.clip(model.predict(X_test), 0, None)
rmse  = np.sqrt(mean_squared_error(y_test, preds))
mae   = mean_absolute_error(y_test, preds)

# Per-borough RMSE
test_eval = test.copy()
test_eval["predicted"] = preds
test_eval["sq_err"]    = (test_eval["incident_count"] - test_eval["predicted"]) ** 2

borough_rmse = {}
for borough in test_eval["BOROUGH"].unique():
    b_mask = test_eval["BOROUGH"] == borough
    b_rmse = np.sqrt(test_eval.loc[b_mask, "sq_err"].mean())
    borough_rmse[borough[:20]] = round(b_rmse, 3)

# Feature importance (all 21 features)
fi = pd.DataFrame({
    "feature":    FEATURE_COLS,
    "importance": model.feature_importances_,
}).sort_values("importance", ascending=False).reset_index(drop=True)

# ── Step 7: Save model ────────────────────────────────────────────────────────
joblib.dump(model, MODEL_OUT)
print(f"\nModel saved: {MODEL_OUT}")

# ── Step 8: Print results ─────────────────────────────────────────────────────
print()
print("=" * 60)
print("  FIRSTWAVE DEMAND MODEL — TRAINING COMPLETE")
print("=" * 60)
print(f"  Features used:  {len(FEATURE_COLS)} (15 original + 6 new)")
print(f"  Test RMSE:      {rmse:.3f} incidents/zone/hour   <- target < 4.0")
print(f"  Test MAE:       {mae:.3f}")
print()
print("  Per-Borough RMSE:")
for k, v in sorted(borough_rmse.items()):
    print(f"    {k}: {v}")
print()
print(f"  Feature importances (top 10 of {len(FEATURE_COLS)}):")
for _, row in fi.head(10).iterrows():
    marker = "  [NEW]" if row["feature"] in NEW_FEATURE_COLS else ""
    print(f"    {row['feature']:<28} {row['importance']:.4f}{marker}")
print()
print(f"  Model saved: {MODEL_OUT}")
print()

if rmse > 6.0:
    print("  ⚠  WARNING: RMSE > 6.0 — zone_baseline_avg is likely missing from features")
    print("     Fix: check merge keys (INCIDENT_DISPATCH_AREA + hour + dayofweek)")
elif rmse > 4.0:
    print("  ⚠  WARNING: RMSE > 4.0 — acceptable but not ideal.")
    print("     Check per-borough RMSE. If Bronx is the outlier, that's expected.")
else:
    print("  ✓  RMSE < 4.0 — target met!")

if "zone_baseline_avg" not in fi.head(3)["feature"].values:
    print("  ⚠  WARNING: zone_baseline_avg not in top 3 features.")
    print("     This is unexpected — double-check the merge keys in Step 3.")
else:
    print("  ✓  zone_baseline_avg in top 3 features — merge was correct")

# Check that new features contribute something (not all zero importance)
new_fi = fi[fi["feature"].isin(NEW_FEATURE_COLS)]
if new_fi["importance"].sum() < 0.001:
    print("  ⚠  WARNING: All new features have near-zero importance.")
    print("     Check Script 02 ran fully and Script 04 carried columns through.")
else:
    top_new = new_fi.iloc[0]
    print(f"  ✓  Best new feature: {top_new['feature']} ({top_new['importance']:.4f})")

# ── Step 9: Scenario sanity checks ───────────────────────────────────────────
# Shared lookup tables needed by build_prediction_df
ZONE_CENTROIDS = {
    'B1':(-73.9101,40.8116),'B2':(-73.9196,40.8448),'B3':(-73.8784,40.8189),
    'B4':(-73.8600,40.8784),'B5':(-73.9056,40.8651),
    'K1':(-73.9857,40.5995),'K2':(-73.9442,40.6501),'K3':(-73.9075,40.6929),
    'K4':(-73.9015,40.6501),'K5':(-73.9283,40.6801),'K6':(-73.9645,40.6401),
    'K7':(-73.9573,40.7201),
    'M1':(-74.0060,40.7128),'M2':(-74.0000,40.7484),'M3':(-73.9857,40.7580),
    'M4':(-73.9784,40.7484),'M5':(-73.9584,40.7701),'M6':(-73.9484,40.7884),
    'M7':(-73.9428,40.8048),'M8':(-73.9373,40.8284),'M9':(-73.9312,40.8484),
    'Q1':(-73.7840,40.6001),'Q2':(-73.8284,40.7501),'Q3':(-73.8784,40.7201),
    'Q4':(-73.9073,40.7101),'Q5':(-73.8073,40.6901),'Q6':(-73.9173,40.7701),
    'Q7':(-73.8373,40.7701),
    'S1':(-74.1115,40.6401),'S2':(-74.1515,40.5901),'S3':(-74.1915,40.5301),
}
ZONE_SVI = {
    'B1':0.94,'B2':0.89,'B3':0.87,'B4':0.72,'B5':0.68,
    'K1':0.52,'K2':0.58,'K3':0.82,'K4':0.84,'K5':0.79,'K6':0.60,'K7':0.45,
    'M1':0.31,'M2':0.18,'M3':0.15,'M4':0.20,'M5':0.12,
    'M6':0.14,'M7':0.73,'M8':0.65,'M9':0.61,
    'Q1':0.71,'Q2':0.44,'Q3':0.38,'Q4':0.55,'Q5':0.67,'Q6':0.48,'Q7':0.41,
    'S1':0.38,'S2':0.32,'S3':0.28,
}
VALID_ZONES = list(ZONE_CENTROIDS.keys())


def build_prediction_df(
    hour:    int,
    dow:     int,
    month:   int,
    # Weather params (with sensible defaults)
    temperature_2m:     float = 15.0,
    precipitation:      float = 0.0,
    windspeed_10m:      float = 10.0,
    is_severe_weather:  int   = 0,
    # New feature params (default = "normal weekday, no special conditions")
    is_holiday:             int   = 0,
    is_major_event:         int   = 0,
    is_school_day:          int   = 1,   # default true — model saw mostly school days
    subway_disruption_idx:  float = 0.5, # median disruption
) -> pd.DataFrame:
    """
    Build a 31-row prediction DataFrame (one row per zone) for the given
    hour/dow/month combination.

    All new feature parameters can be overridden to model different scenarios,
    e.g. is_holiday=1 for Thanksgiving, is_major_event=1 for game nights.
    """
    # Derive heat flags from temperature (same logic as Script 02)
    is_extreme_heat  = int(temperature_2m >= 35.0)
    is_heat_emergency = int(temperature_2m >= 35.0)  # simplified; full logic needs rolling window

    rows = []
    for zone in VALID_ZONES:
        # Zone baseline from precomputed artifact
        brow = baselines[
            (baselines["INCIDENT_DISPATCH_AREA"] == zone) &
            (baselines["hour"] == hour) &
            (baselines["dayofweek"] == dow)
        ]
        baseline_avg = float(brow["zone_baseline_avg"].iloc[0]) if len(brow) else 3.0

        # Per-zone stats from artifact
        zrow = zone_stats[zone_stats["INCIDENT_DISPATCH_AREA"] == zone]
        har  = float(zrow["high_acuity_ratio"].iloc[0]) if len(zrow) else 0.23
        hdr  = float(zrow["held_ratio"].iloc[0])        if len(zrow) else 0.06

        rows.append({
            "zone": zone,
            # ── Original 15 features ─────────────────────────────────────────
            "hour_sin":              math.sin(2 * math.pi * hour  / 24),
            "hour_cos":              math.cos(2 * math.pi * hour  / 24),
            "dow_sin":               math.sin(2 * math.pi * dow   / 7),
            "dow_cos":               math.cos(2 * math.pi * dow   / 7),
            "month_sin":             math.sin(2 * math.pi * month / 12),
            "month_cos":             math.cos(2 * math.pi * month / 12),
            "is_weekend":            1 if dow in (5, 6) else 0,
            "temperature_2m":        temperature_2m,
            "precipitation":         precipitation,
            "windspeed_10m":         windspeed_10m,
            "is_severe_weather":     is_severe_weather,
            "svi_score":             ZONE_SVI[zone],
            "zone_baseline_avg":     baseline_avg,
            "high_acuity_ratio":     har,
            "held_ratio":            hdr,
            # ── New features ─────────────────────────────────────────────────
            "is_holiday":            is_holiday,
            "is_major_event":        is_major_event,
            "is_school_day":         is_school_day,
            "is_heat_emergency":     is_heat_emergency,
            "is_extreme_heat":       is_extreme_heat,
            "subway_disruption_idx": subway_disruption_idx,
        })

    return pd.DataFrame(rows)


# ── Scenario 1: Friday 8PM (dow=4, month=10, hour=20) ─────────────────────────
# "Baseline busy night — school day, no special event"
print()
print("  SANITY CHECK A — Friday 8PM (normal, school day)")
print("  " + "-" * 50)
df_fri = build_prediction_df(
    hour=20, dow=4, month=10,
    is_school_day=0,      # Friday evening — school is not in session at 8PM
    is_major_event=0,
    is_holiday=0,
)
preds_fri = np.clip(model.predict(df_fri[FEATURE_COLS]), 0, None)
df_fri["predicted"] = preds_fri

top10_fri = df_fri.sort_values("predicted", ascending=False).head(10)
for _, row in top10_fri.iterrows():
    print(f"    {row['zone']}: {row['predicted']:.1f} incidents/hr")
print("  PASS if B and K zones dominate top 5")

# ── Scenario 2: Friday 8PM — with Yankee game (is_major_event=1 in Bronx zones) ──
# To model a Bronx-specific event we run two predictions and compare
print()
print("  SANITY CHECK B — Friday 8PM vs Friday 8PM + Yankee game (Bronx event)")
print("  " + "-" * 50)
df_fri_game = build_prediction_df(
    hour=20, dow=4, month=10,
    is_school_day=0,
    is_major_event=1,   # game in Bronx — affects ALL zones here (simplification)
    is_holiday=0,
)
# More precise: only flag Bronx zones
for idx, row in df_fri_game.iterrows():
    if not row["zone"].startswith("B"):
        df_fri_game.at[idx, "is_major_event"] = 0

preds_fri_game = np.clip(model.predict(df_fri_game[FEATURE_COLS]), 0, None)
df_fri_game["predicted"] = preds_fri_game

bronx_zones   = [z for z in VALID_ZONES if z.startswith("B")]
base_bronx    = df_fri["predicted"][df_fri["zone"].isin(bronx_zones)].mean()
game_bronx    = df_fri_game["predicted"][df_fri_game["zone"].isin(bronx_zones)].mean()
delta_bronx   = game_bronx - base_bronx

print(f"    Bronx avg without game:  {base_bronx:.2f}")
print(f"    Bronx avg with game:     {game_bronx:.2f}")
print(f"    Delta:                   {delta_bronx:+.2f}")
print(f"  PASS if delta > 0 (game raises Bronx predictions)")

# ── Scenario 3: Monday 4AM (dow=0, month=10, hour=4) ─────────────────────────
print()
print("  SANITY CHECK C — Monday 4AM (quiet baseline)")
print("  " + "-" * 50)
df_mon = build_prediction_df(
    hour=4, dow=0, month=10,
    is_school_day=0,    # 4AM — not a school hour
    is_major_event=0,
    is_holiday=0,
)
preds_mon = np.clip(model.predict(df_mon[FEATURE_COLS]), 0, None)
print(f"    Mean: {preds_mon.mean():.2f}  Max: {preds_mon.max():.2f}")
print(f"  PASS if all zones < 5 incidents/hr")

# ── Scenario 4: July 4th Friday 10PM (holiday + summer heat) ─────────────────
print()
print("  SANITY CHECK D — July 4th, 10PM (holiday + peak summer)")
print("  " + "-" * 50)
df_july4 = build_prediction_df(
    hour=22, dow=4, month=7,
    temperature_2m=28.0,
    precipitation=0.0,
    windspeed_10m=8.0,
    is_holiday=1,
    is_major_event=1,   # Fourth of July events citywide
    is_school_day=0,    # summer
)
preds_july4 = np.clip(model.predict(df_july4[FEATURE_COLS]), 0, None)
df_july4["predicted"] = preds_july4
print(f"    All-zone mean: {preds_july4.mean():.2f}")
top5_july4 = df_july4.sort_values("predicted", ascending=False).head(5)
for _, row in top5_july4.iterrows():
    print(f"    {row['zone']}: {row['predicted']:.1f}")
print(f"  vs. normal Friday 8PM mean: {preds_fri.mean():.2f}")
print(f"  PASS if July 4th mean >= Friday 8PM mean (holiday drives demand up)")

# ── Scenario 5: January blizzard, Monday noon ────────────────────────────────
print()
print("  SANITY CHECK E — January blizzard, Monday noon (severe weather)")
print("  " + "-" * 50)
df_blizzard = build_prediction_df(
    hour=12, dow=0, month=1,
    temperature_2m=-5.0,
    precipitation=15.0,
    windspeed_10m=45.0,
    is_severe_weather=1,
    is_school_day=0,    # schools typically closed in blizzard
    is_holiday=0,
    is_major_event=0,
)
preds_blizzard = np.clip(model.predict(df_blizzard[FEATURE_COLS]), 0, None)
df_normal_mon_noon = build_prediction_df(hour=12, dow=0, month=1)
preds_normal_mon   = np.clip(model.predict(df_normal_mon_noon[FEATURE_COLS]), 0, None)
print(f"    Blizzard mean: {preds_blizzard.mean():.2f}")
print(f"    Normal Monday noon mean: {preds_normal_mon.mean():.2f}")
print(f"  PASS if blizzard mean >= normal Monday noon (severe weather raises demand)")

# ── Final summary ─────────────────────────────────────────────────────────────
print()
print("=" * 60)
print("  Next: python pipeline/07_staging_optimizer.py")
print("         (after 06_osmnx_matrix.py is also complete)")
print("         python pipeline/08_counterfactual_precompute.py  (after 07 passes)")
print()
print("  ⚠  IMPORTANT: If you changed FEATURE_COLS, update inference wrapper:")
print("     backend/models/demand_forecaster.py — FEATURE_COLS and build_feature_dataframe()")
print("     New feature defaults for inference:")
print("       is_holiday            = 0")
print("       is_major_event        = 0")
print("       is_school_day         = 1  (conservative default)")
print("       is_heat_emergency     = derived from temperature_2m >= 35.0")
print("       is_extreme_heat       = derived from temperature_2m >= 35.0")
print("       subway_disruption_idx = 0.5  (median)")
print("=" * 60) 