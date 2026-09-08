# FirstWave ML Pipeline — How We Built It

> A plain-English walkthrough of the data pipeline, machine learning models, and impact simulation behind FirstWave. Written for hackathon judges and anyone who wants to understand how the system works end-to-end.

---

## The 30-Second Version

We took 28.7 million real NYC 911 records, cleaned them down to 5.6 million training incidents, trained a model to predict where emergencies will happen next hour, used that prediction to place ambulances optimally, and then proved it works by simulating every high-priority 2023 incident under our system vs. the current one. Result: 8-minute coverage jumps from 64.7% to 86.0%.

---

## Pipeline Overview

The pipeline is 8 Python scripts that run sequentially (with one long step running in parallel). Each script reads the output of the previous one and produces artifacts that the backend API loads at startup.

```
Raw CSV (28.7M rows, 2GB)
    |
    v
[1] Ingest & Clean -----> 7.1M clean rows
    |
    v
[2] Weather Merge ------> + temperature, rain, wind, holidays, events, subway data
    |
    v
[3] SVI Join -----------> + Social Vulnerability Index per zone
    |
    v
[4] Aggregate ----------> Hourly zone-level counts + zone baselines + zone stats
    |                          |                          |
    v                          v                          v
[5] Train XGBoost      zone_baselines.parquet     zone_stats.parquet
    |                  (most important feature)    (historical averages)
    v
demand_model.pkl
                        [6] Drive-Time Matrix (runs in parallel, 30-60 min)
                            |
                            v
                        drive_time_matrix.pkl
    |                       |
    v                       v
[7] Staging Validation (no output, just checks)
    |
    v
[8] Counterfactual Simulation
    |
    v
counterfactual_summary.parquet + counterfactual_raw.parquet
```

**Total runtime:** ~60-90 minutes. Most of that is Script 6 downloading the NYC road network.

---

## Script 1 — Ingest & Clean

**What it does:** Reads the raw NYC EMS CSV and applies 9 quality filters to remove bad data.

**Input:** 28,697,411 rows of NYC EMS Incident Dispatch Data from NYC Open Data (Socrata). This is every 911 EMS call in New York City from 2005 to 2024.

**The 9 filters:**

| Filter | Why | Rows removed |
|---|---|---|
| Valid response time flag = Y | NYC flags rows where timestamps are unreliable | ~1.1M |
| Valid dispatch time flag = Y | Same — ensures dispatch timing is trustworthy | small overlap |
| Reopen indicator = N | Reopened calls are duplicate records | ~50K |
| Transfer indicator = N | Transfers are inter-facility, not 911 calls | ~100K |
| Standby indicator = N | Standby units aren't responding to emergencies | ~30K |
| Response time between 1-7200 seconds | Eliminates zeros (data entry errors) and extreme outliers (>2 hours) | ~200K |
| Borough is not UNKNOWN | UNKNOWN borough rows average 2,626 seconds — clearly bad data | ~5K |
| Dispatch zone is one of 31 valid zones | Drops CAD system entry errors (CW, X1, PD, etc.) | ~50K |
| Zone prefix matches borough | Catches zone K1 recorded under Queens (should be Brooklyn) — CAD typos | ~500 |

**Training split:**
- **Training:** 2019, 2021, 2022 (~5.6 million rows)
- **Holdout:** 2023 (~1.5 million rows) — the model never sees this data during training
- **Excluded:** 2020 (COVID lockdowns distorted demand patterns — would teach the model false seasonal dips)

**Output:** `incidents_cleaned.parquet` — 7.1 million clean incidents with extracted time features (hour, day of week, month, year).

**Why this matters for judges:** Most hackathon projects use a sample or a single year. We used the full 5-year dataset and applied rigorous quality filters. The 96.2% validity rate is unusually high for a public dataset — NYC keeps good records.

---

## Script 2 — Weather & Context Enrichment

**What it does:** Adds 7 new columns to every incident from 5 external data sources. All free, all public.

### Weather (Open-Meteo Historical API)

For every hour from 2019-2023, we pulled NYC weather data:
- **Temperature** (Celsius) — demand increases in extreme heat
- **Precipitation** (mm/hr) — rain/snow increases both demand and travel time
- **Wind speed** (km/h) — high winds cause injuries and slow ambulances
- **Severe weather flag** — 1 when WMO weather code indicates thunderstorms, heavy rain, blizzards, etc.

We also derive two heat flags:
- **Extreme heat:** temperature >= 35C (95F)
- **Heat emergency:** temperature >= 35C now, OR the prior 24-hour max hit >= 32.2C (90F). This captures the "heat wave" effect where sustained heat causes more medical emergencies even after it cools slightly.

### Holidays (hardcoded)

Federal holidays plus NYC-specific closures (Rosh Hashanah, Yom Kippur, Election Day). About 85 holiday dates across 5 years. Holidays change demand patterns — fewer commuter injuries, more domestic incidents.

### School Calendar (hardcoded)

NYC Department of Education instructional days. School days see different demand patterns than summer/breaks — more pediatric calls, different geographic distribution (around schools vs. residential areas).

### NYC Special Events (NYC Open Data)

Permitted events like parades, concerts, athletic events, block parties, and street fairs. We filter to event types that plausibly affect EMS demand and map each event to its borough. The NYC Marathon, Fourth of July fireworks, and large concerts all generate EMS call spikes.

### Subway Disruptions (MTA Open Data)

Monthly count of major MTA incidents, normalized to a 0-1 index. Subway disruptions push people to surface transport, increasing pedestrian and vehicle incidents in affected boroughs.

**How the join works:** All 5 enrichment tables are joined in a single DuckDB pass — weather by hour, holidays and school days by date, events by date + borough, and subway disruption by year + month. Missing values get sensible defaults (15C for temperature, 0 for precipitation, etc.).

---

## Script 3 — Social Vulnerability Index Join

**What it does:** Adds a CDC Social Vulnerability Index score (0 to 1) to every incident based on its dispatch zone.

The SVI measures how vulnerable a community is based on socioeconomic status, household composition, minority status, and housing type. Higher score = more vulnerable.

**Key values:**

| Zone | Neighborhood | SVI Score |
|---|---|---|
| B1 | South Bronx, Hunts Point | 0.94 (most vulnerable) |
| B2 | West/Central Bronx | 0.89 |
| K4 | East New York | 0.84 |
| M5 | Upper East Side South | 0.12 (least vulnerable) |
| M3 | Midtown | 0.15 |
| S3 | South Shore, Staten Island | 0.28 |

**Why this matters:** The Bronx has the highest SVI scores AND the longest response times. This isn't a coincidence — it's a systemic equity gap that FirstWave is designed to close. The SVI score is both a model feature (vulnerable areas have different demand patterns) and an impact metric (we measure improvement by vulnerability quartile).

---

## Script 4 — Aggregation

**What it does:** Groups 7.1 million individual incidents into hourly zone-level bins and produces two critical artifacts.

### Hourly Zone Bins

Every incident gets grouped by (zone, hour, day of week, month, year). For each bin, we compute:
- **Incident count** — the number we're trying to predict
- **Average response/travel/dispatch seconds** — how long it actually took
- **High-acuity count** — Priority 1 and 2 incidents
- **Held count** — calls where no ambulance was immediately available (demand overload signal)
- **Cyclical time encodings** — sine and cosine transforms of hour, day, and month (explained in Script 5)

Result: ~168,000 rows (31 zones x 24 hours x 7 days x ~3 years).

### Zone Baselines (the most important feature)

For each (zone, hour, day of week) combination, we compute the average incident count across all training dates.

**Example:** "On a typical Friday at 8 PM, zone B2 in the Bronx averages 16.2 incidents."

This single number — `zone_baseline_avg` — carries **47% of the model's predictive power**. It encodes the core demand pattern: which zones are busy, when they're busy, and how busy they typically get.

Result: up to 5,208 rows (31 zones x 24 hours x 7 days).

### Zone Stats

Per-zone historical averages computed from all training data:
- Average response time (total, travel, dispatch breakdown)
- High-acuity ratio (% of Priority 1+2 calls)
- Held ratio (% of calls where no unit was available)
- SVI score
- Total incident count

Result: exactly 31 rows (one per zone). Used by the backend for the `/api/historical` and `/api/breakdown` endpoints.

---

## Script 5 — XGBoost Demand Forecaster

**What it does:** Trains a gradient-boosted decision tree model to predict how many 911 calls a given zone will receive in a given hour.

### The Prediction Task

**Input:** A zone (e.g., B2), a time (e.g., Friday 8 PM in October), and current conditions (weather, events, etc.)

**Output:** A number — predicted incident count for that zone in that hour (e.g., 16.4 incidents)

### The 20 Features

The model sees 20 input features for each prediction. Here's what each one means and why it's included:

**Cyclical time encodings (6 features):**

We can't feed raw numbers like "hour = 20" into the model because the model would think hour 23 and hour 0 are far apart, when they're actually adjacent (11 PM and midnight). Instead, we encode time on a circle using sine and cosine:

```
hour_sin = sin(2*pi * hour / 24)     hour_cos = cos(2*pi * hour / 24)
dow_sin  = sin(2*pi * dayofweek / 7) dow_cos  = cos(2*pi * dayofweek / 7)
month_sin = sin(2*pi * month / 12)   month_cos = cos(2*pi * month / 12)
```

This way, hour 23 and hour 0 have similar feature values, Friday and Saturday are close, and December and January are neighbors.

**Weekend flag (1 feature):**

`is_weekend` = 1 if Saturday or Sunday. Weekend demand patterns differ significantly from weekday — fewer commuter injuries, more nightlife-related calls.

**Weather features (4 features):**

- `temperature_2m` — degrees Celsius. Extreme heat causes heat stroke, cardiac events.
- `precipitation` — mm/hr. Rain and snow cause traffic accidents, slips and falls.
- `windspeed_10m` — km/h. High winds cause injuries and slow ambulances.
- `is_severe_weather` — 1 during thunderstorms, blizzards, heavy rain. Multiple injury types spike.

**Zone-level features (3 features):**

- `svi_score` — Social Vulnerability Index (0-1). Higher-vulnerability zones have different demand patterns.
- `zone_baseline_avg` — **The most important feature.** Historical average incidents for this exact (zone, hour, day of week) combination. Carries 47% of predictive power.
- `high_acuity_ratio` — What fraction of this zone's calls are Priority 1 or 2. Zones with more serious incidents need different coverage.
- `held_ratio` — What fraction of calls in this zone had no ambulance immediately available. A demand overload signal.

**Calendar features (3 features):**

- `is_holiday` — Federal and NYC holidays change demand patterns.
- `is_school_day` — School days vs. summer/breaks affect geographic demand distribution.
- `is_major_event` — NYC-permitted events (parades, concerts, etc.) spike demand locally.

**Heat emergency features (2 features):**

- `is_heat_emergency` — 1 during sustained heat waves (NYC's threshold: 32.2C / 90F for 24h+).
- `is_extreme_heat` — 1 when temperature hits 35C (95F). Heat emergencies are a distinct demand driver beyond normal temperature effects.

**Infrastructure (1 feature):**

- `subway_disruption_idx` — Normalized MTA major incident count for the month. Subway problems push people to surface transit, increasing pedestrian and vehicle incidents.

### Training

**Algorithm:** XGBoost (Extreme Gradient Boosting) — an ensemble of 300 decision trees, each learning from the mistakes of the previous ones.

**Key hyperparameters:**
- 300 trees, max depth 6 (shallow trees prevent overfitting)
- Learning rate 0.05 (slow learning for stability)
- 80% row sampling and 80% feature sampling per tree (regularization)
- Early stopping after 20 rounds without improvement

**Training set:** 2019, 2021, 2022 (~5.6M incidents, aggregated to ~130K hourly bins)
**Test set:** 2023 (~1.5M incidents, ~38K hourly bins) — completely held out from training

### Results

**RMSE: ~6.0 incidents/zone/hour on 2023 holdout**

This means: on average, the model's prediction is off by about 6 incidents per zone per hour. For zones that see 15-20 incidents at peak times, this is reasonable. More importantly, the model correctly ranks which zones are busiest — and that's what the staging optimizer needs.

**Feature importance (top 5):**

1. `zone_baseline_avg` — 47% (historical demand pattern dominates)
2. `hour_sin` / `hour_cos` — ~18% (time of day is the second strongest signal)
3. `is_school_day` — ~7% (school schedule significantly affects demand)
4. `is_holiday` — ~5% (holidays shift demand patterns)
5. `month_sin` / `month_cos` — ~4% (seasonal effects)

**Sanity checks the model passes:**
- Friday 8 PM in the Bronx shows ~59 total predicted incidents (correctly identifies peak demand)
- Monday 4 AM shows all zones under 5 incidents (correctly identifies quiet periods)
- Holiday + summer combinations show higher demand than typical weekdays
- Storm scenarios show elevated demand compared to clear weather

---

## Script 6 — Drive-Time Matrix (OSMnx)

**What it does:** Computes actual driving times between every pair of zones (and every FDNY station to every zone) using the real NYC road network. This is the longest step — 30 to 60 minutes.

### Why Not Just Use Straight-Line Distance?

In NYC, straight-line distance is misleading. The grid street layout, one-way streets, bridges, and tunnels mean the actual driving route is typically 1.35x longer than the direct path. Getting from the Bronx to Staten Island requires crossing multiple bridges. OSMnx gives us realistic driving times that account for all of this.

### How It Works

1. **Download the NYC road network** from OpenStreetMap via OSMnx. This produces a graph with ~500,000 intersections (nodes) and ~1.2 million road segments (edges), including speed limits and turn restrictions.

2. **Map each zone centroid and FDNY station to the nearest road intersection.** The centroid of zone B2 (West/Central Bronx) sits at coordinates (-73.9196, 40.8448) — we find the closest actual intersection on the road network.

3. **Run Dijkstra's shortest path algorithm** from each origin (31 zone centroids + ~31 FDNY stations) to every destination zone. For each origin, we compute the fastest route to all 31 zones simultaneously.

4. **Store as a lookup dictionary:**
   ```
   drive_time_matrix[("B1", "B2")] = 312   # 5 min 12 sec between adjacent Bronx zones
   drive_time_matrix[("S1", "B1")] = 2840  # 47 min from Staten Island to South Bronx
   drive_time_matrix[("EMS_M01", "M3")] = 180  # 3 min from Midtown station to Midtown zone
   ```

**Result:** ~2,000 origin-destination pairs with realistic drive times in seconds.

**Fallback:** If the road network download fails, we use straight-line distance with a 1.35x circuity factor and 25 km/h average speed. Less accurate (~15% error) but ensures the pipeline always completes.

---

## Script 7 — Staging Optimizer Validation

**What it does:** Runs the staging algorithm on test scenarios to verify it produces sensible results. No artifacts are produced — this is a confidence check.

### The Borough-Fair Staging Algorithm

Given predicted demand across 31 zones and K available ambulances, place them optimally:

**Phase 1 — Guaranteed coverage:** Allocate 1 ambulance to each of the 5 boroughs. This ensures every borough has at least one staged unit, even if its demand is relatively low. The single unit is placed at the demand-weighted centroid of that borough's zones.

**Phase 2 — Demand-proportional extras:** The remaining K-5 ambulances are allocated one at a time to whichever borough has the highest demand-per-ambulance ratio. Within a borough with multiple units, K-Means clustering (weighted by demand) finds the optimal placement.

**Coverage radius:** 3,500 meters (~8-minute drive at NYC urban speeds of ~25 km/h).

**Why borough-fair matters:** Without the fairness constraint, all 5 ambulances might cluster in the Bronx and Brooklyn during peak hours, leaving Manhattan, Queens, and Staten Island uncovered. The two-phase approach guarantees baseline coverage everywhere while still concentrating resources where demand is highest.

### Validation Scenarios

The script tests:
- **Friday 8 PM:** Bronx and Brooklyn should dominate the top demand zones. Staging should weight toward those boroughs.
- **Monday 4 AM:** All zones should be quiet (<5 incidents/hr). Staging should be more evenly spread.
- **Peak-to-quiet ratio:** Friday 8 PM total demand should be at least 2x Monday 4 AM (confirming the model captures temporal patterns).

---

## Script 8 — Counterfactual Simulation

**What it does:** This is the script that produces the numbers in the demo. It answers: "If FirstWave had been running in 2023, how much faster would ambulances have reached patients?"

### The Setup

We take every high-acuity (Priority 1 and 2) incident from 2023 — about 300,000 calls where every second matters — and simulate two scenarios:

**Baseline (current system):** The actual recorded response time for each incident. This includes dispatch delay + travel time from the nearest fixed FDNY station. This is what actually happened in 2023.

**Staged (FirstWave):** We ask: "If we had predicted this hour's demand and pre-staged ambulances optimally, what's the shortest drive time from any staging location to this incident's zone?" We look up the drive time from the nearest staging point using the real road network matrix from Script 6.

### The Simulation Loop

For each of the 168 (hour, day of week) combinations:

1. **Pull all 2023 Priority 1+2 incidents** from that time slot (up to 150 per slot for compute efficiency).

2. **Predict demand** for all 31 zones using the trained XGBoost model with that hour and day of week.

3. **Run the staging optimizer** with K=10 ambulances to find optimal staging locations.

4. **For each incident:**
   - Baseline time = the actual historical response time (what really happened)
   - Staged time = minimum drive time from any of the 10 staging locations to the incident's zone
   - Seconds saved = baseline - staged

5. **Aggregate:** Compute median seconds saved, % within 8-minute threshold for both scenarios.

### Weather Adjustment

The counterfactual endpoint also applies a weather travel factor at query time:

```
factor = 1.0 + (0.012 * precipitation_mm) + (0.002 * max(0, windspeed - 15))
```

This means:
- 10 mm/hr rain adds 12% to travel times
- 40 km/h wind (25 km/h above threshold) adds 5% to travel times
- A heavy storm (12mm rain, 40km/h wind) adds ~19% to travel times

Both baseline and staged times are adjusted, but staged times improve more because ambulances start closer to where they're needed.

### The Equity Analysis

Every incident carries its zone's SVI score. We split incidents into 4 quartiles:
- **Q1:** Least vulnerable communities (SVI 0.12-0.38)
- **Q2:** (SVI 0.38-0.55)
- **Q3:** (SVI 0.55-0.73)
- **Q4:** Most vulnerable communities (SVI 0.73-0.94)

The key finding: **Q4 benefits the most.** The most vulnerable neighborhoods see 299 seconds saved vs. 89 seconds for Q1. This happens because high-vulnerability zones (South Bronx, East New York, Harlem) are also the highest-demand zones — so the staging algorithm naturally places more ambulances near them.

### Results

| Metric | Baseline (current system) | With FirstWave |
|---|---|---|
| % within 8-min clinical window | 64.7% | **86.0%** |
| Median response time saved | — | **3 min 19 sec** |

**By borough:**

| Borough | Baseline 8-min % | Staged 8-min % | Median seconds saved |
|---|---|---|---|
| Bronx | 48.2% | 96.7% | 213 sec |
| Brooklyn | 58.4% | 81.2% | 159 sec |
| Manhattan | 71.3% | 89.1% | 118 sec |
| Queens | 63.1% | 84.9% | 141 sec |
| Staten Island | 75.0% | 88.3% | 89 sec |

**By vulnerability quartile:**

| SVI Quartile | Communities | Median seconds saved |
|---|---|---|
| Q1 (least vulnerable) | Upper East Side, Midtown, Staten Island South | 89 sec |
| Q2 | Flushing, Forest Hills, Borough Park | 118 sec |
| Q3 | Harlem, Washington Heights, Jamaica | 159 sec |
| Q4 (most vulnerable) | South Bronx, East New York, Bushwick | **299 sec** |

---

## Artifact Validation (test_artifacts.py)

After all 8 scripts complete, a 41-check validation suite verifies every artifact:

- All 6 files exist and load without errors
- The XGBoost model has the correct number of features and produces reasonable predictions
- Zone baselines cover all 31 zones with positive values
- Zone stats have exactly 31 rows with Bronx response time near the validated 638 seconds
- Drive-time matrix has >90% reachable pairs with times in the 60-7200 second range
- Counterfactual summary shows positive improvement in >60% of time slots
- Counterfactual raw data contains all 5 boroughs and all 4 SVI quartiles
- The equity check passes: Q4 saves more seconds than Q1

**Exit code 0** means everything is ready to deploy. **Exit code 1** means something needs fixing.

---

## Key Design Decisions (for Q&A)

**Why XGBoost and not a neural network?**
XGBoost handles tabular data with mixed feature types (continuous + categorical) extremely well. It trains in minutes, not hours. It's interpretable — we can show feature importance. And with 168K training rows and 20 features, it's the right tool for the job. A neural network would be overkill and harder to debug during a hackathon.

**Why dispatch zones and not ZIP codes?**
NYC has ~180 ZIP codes but only 31 dispatch zones. Zones are how EMS actually organizes the city — they're operationally meaningful. More incidents per zone means more robust statistics. And the zone system is stable (ZIPs change, zones don't).

**Why exclude 2020?**
COVID lockdowns reduced 911 call volume by ~100K incidents in 2020. Including it would teach the model a false seasonal dip that doesn't represent normal operations. We keep 2019, 2021, and 2022 for training, and hold out 2023 entirely.

**Why the 8-minute threshold?**
480 seconds is the clinical standard for EMS response to cardiac arrest. Response within 4 minutes: ~50% survival. Within 8 minutes: ~25% survival. At 10+ minutes (the Bronx average): ~10% survival. This is the number that matters clinically.

**Why borough-fair staging?**
Without the fairness constraint, the optimizer would put all ambulances in the Bronx and Brooklyn at peak times (where demand is highest). That's mathematically optimal but operationally unacceptable — Queens and Staten Island still need coverage. The two-phase approach balances efficiency with equity.

**Why DuckDB instead of Databricks?**
We started on Databricks Community Edition but hit memory limits on the 28.7M-row dataset. DuckDB runs the same SQL queries locally without any cluster management, and processed the full dataset faster than the free Databricks tier. The pivot took about 2 hours.
