# FirstWave — Devpost Submission Content

> Ready to copy-paste into Devpost fields. Each section heading maps to a Devpost form field.

---

## Inspiration

Emergency medical services in New York City respond to over 1.5 million 911 calls every year. Despite that volume, ambulance deployment is still largely reactive — units sit at fixed stations until a call comes in, then race across the borough. The result: the Bronx averages 10.6 minutes per response, well past the 8-minute clinical threshold where cardiac arrest survival drops from ~25% to ~10%.

We looked at the data and realized the problem isn't a shortage of ambulances. It's that they're in the wrong place at the wrong time. Demand is predictable — Friday evenings in the Bronx, summer weekends in Brooklyn — but the system doesn't act on those patterns. FirstWave was built to change that.

---

## What it does

FirstWave is a predictive staging dashboard for NYC EMS dispatchers. It forecasts where 911 calls will cluster over the next hour, then recommends where to pre-position idle ambulances before those calls arrive.

The system has six core capabilities:

**Demand Forecasting** — A 20-feature XGBoost model predicts incident count per dispatch zone per hour using temporal patterns, weather conditions, and zone-level historical baselines. It correctly identifies Friday 8PM in the Bronx as peak demand (~59 predicted incidents).

**Borough-Fair Staging** — A weighted K-Means optimizer places ambulances at the mathematical center of predicted demand, with a fairness constraint that guarantees at least one staging point per borough before allocating extras proportionally.

**Counterfactual Impact Engine** — Compares actual historical response times against simulated drive times from staged locations, adjusted for weather (rain and wind increase travel times). Gives an honest, data-backed answer to "how much faster would we have gotten there?"

**AI Dispatcher** — A GPT-4o-mini chat interface where dispatchers can explore scenarios in natural language. "What about a Friday night Yankees game?" generates a briefing and adjusts the map. "Show me a quiet Monday morning" shifts the controls automatically.

**Equity Analysis** — A Social Vulnerability Index overlay shows which neighborhoods are most at risk. The impact panel breaks down savings by SVI quartile, proving that the most vulnerable communities (Q4) receive the largest benefit.

**Watch the Wave** — An animated 24-hour playback shows demand building across the city, making the case visually that demand is predictable and staging should be proactive.

**Results from 28.7 million real incidents:** 8-minute coverage improves from 64.7% to 86.0%. Median response time drops by 3 minutes 19 seconds. Bronx coverage jumps from 48.2% to 96.7%.

---

## How we built it

**Data Pipeline:** We ingested 28.7 million rows of NYC EMS incident dispatch data from NYC Open Data (Socrata). After applying 9 quality filters — valid response time flags, excluding reopens/transfers/standbys, enforcing zone-borough consistency, dropping 2020 COVID anomalies — we had 5.6 million clean training incidents (2019, 2021, 2022) and 1.5 million holdout incidents (2023). Weather data was merged from the Open-Meteo historical API (hourly temperature, precipitation, windspeed). CDC Social Vulnerability Index scores were aggregated from census tract level to dispatch zone level. The pipeline runs on DuckDB locally, processing the full 28.7M rows without issues.

**Machine Learning:** The demand forecaster is an XGBoost regressor with 20 features including cyclical time encodings (sine/cosine for hour, day-of-week, month), weather conditions, SVI scores, zone-level baseline averages, heat emergency flags, and infrastructure disruption indices. The staging optimizer uses borough-fair weighted K-Means — it guarantees one staging point per borough before distributing extras by demand ratio. Drive times come from OSMnx, which computed shortest paths across the actual NYC road network for all 1,891 zone pairs. The counterfactual engine simulates every historical high-acuity incident with weather-adjusted travel times.

**Backend:** FastAPI serves 7 endpoints. The demand model and staging optimizer run inference in <300ms. Artifacts (trained model, drive-time matrix, zone statistics, precomputed counterfactuals) are loaded at startup from Parquet and pickle files. Zone boundary geometries come from PostGIS. The AI dispatcher endpoint forwards context-enriched prompts to GPT-4o-mini and parses control change recommendations from the response.

**Dashboard:** React 19 with Mapbox GL JS 3.18 renders a dark-themed interactive map. TanStack React Query manages all data fetching with 300ms debounced parameter changes. The choropleth layer colors 31 dispatch zones by predicted demand intensity (teal to red). Staging pins show coverage circles at 3,500m radius. The equity overlay paints ZIP-level SVI scores in a purple gradient. The AI panel supports auto-briefing (updates on every forecast change) and interactive chat with undo functionality for map control changes. Watch the Wave animates the hour slider at 1.5-second intervals.

---

## Challenges we ran into

**Data quality at scale.** 28.7 million rows sounds great until you find mismatched borough/zone codes, COVID-distorted 2020 data, and 3.8% of rows with invalid response time flags. We built 9 sequential quality filters and a 41-check validation suite to catch issues before they reached the model.

**Modeling at dispatch zone granularity.** With only 31 zones, the model needs to capture fine-grained temporal and weather patterns within each zone. The zone_baseline_avg feature (rolling historical average per zone/hour/day) turned out to carry 47% of feature importance — without it, predictions were nearly random.

**Drive-time computation.** OSMnx needs to build the full NYC road network graph and compute shortest paths for 1,891 zone pairs. This took 30-60 minutes and had to be done before the hackathon started. We pre-computed and cached the matrix as a pickle file.

**Databricks to DuckDB pivot.** We started on Databricks Community Edition but hit cluster memory limits on the 28.7M-row dataset. Mid-hackathon, we pivoted the entire pipeline to local DuckDB. The switch took about 2 hours but the pipeline ran faster locally than it did on the free Databricks cluster.

**CORS debugging during integration.** The frontend and backend initially couldn't communicate due to port mismatches in CORS configuration. We added all likely dev server ports (3000, 3004, 5173, 5174) to the backend's allowed origins list.

---

## Accomplishments we're proud of

**86% 8-minute coverage** — up from 64.7% baseline. That's roughly 340,000 additional incidents per year arriving within the clinical survival window.

**3 minutes 19 seconds median saved** — across all zones, weighted by predicted demand. In cardiac arrest terms, that's a meaningful shift in survival probability.

**Borough-fair equity** — the staging algorithm doesn't just optimize for speed; it guarantees every borough gets coverage. The most vulnerable communities (SVI Q4) save the most time: 299 seconds.

**AI Dispatcher** — natural language scenario exploration that actually modifies the dashboard. Dispatchers can ask "What about a storm on Tuesday evening?" and see the map update in real time.

**Full end-to-end pipeline in 36 hours** — from 28.7M raw rows through 8 pipeline scripts, 20-feature model training, 7 API endpoints, and a full interactive dashboard with AI chat, equity overlay, station markers, and animated playback.

---

## What we learned

Building FirstWave taught us that the gap between a working model and a useful tool is enormous. Our XGBoost model was functional within hours, but making it useful meant building a counterfactual engine that honestly quantifies impact, a staging optimizer that respects equity constraints, and a dashboard that lets dispatchers explore scenarios intuitively.

We also learned that data quality work is the real bottleneck. The 9-filter pipeline and borough-zone consistency checks took more engineering time than the ML model itself. Bad data in, bad predictions out — and at 28.7M rows, even a 0.1% error rate means 28,000 corrupted records.

The Databricks-to-DuckDB pivot taught us to always have a local fallback. Cloud compute is powerful but unreliable under hackathon time pressure. DuckDB handled the full dataset on a laptop without breaking a sweat.

Finally, integrating GPT-4o-mini as a dispatcher interface showed us how natural language can bridge the gap between ML predictions and operational decisions. The AI doesn't replace the dispatcher — it translates model output into actionable briefings.

---

## What's next for FirstWave

**Real-time 911 feed integration.** The current system uses historical data with a time slider. Connecting to NYC's real-time CAD system would make FirstWave a live operational tool.

**Hospital destination and turnaround time modeling.** Right now we optimize for getting to the scene. The next step is optimizing the full cycle: scene arrival, hospital transport, and unit availability.

**Reinforcement learning for dynamic re-staging.** As calls come in and units deploy, the optimal staging configuration changes. An RL agent could continuously re-position remaining idle units.

**Multi-city deployment.** The pipeline is parameterized by zone geometry, centroids, and SVI scores. Any city with open EMS dispatch data could be onboarded by swapping the configuration.

**Mobile dispatcher app.** A simplified mobile interface for field supervisors to see staging recommendations and demand forecasts on the go.

---

## Technologies

Python, JavaScript, React, FastAPI, XGBoost, scikit-learn, Mapbox GL JS, DuckDB, PostgreSQL, PostGIS, OSMnx, Plotly.js, OpenAI GPT-4o-mini, Vite, TanStack React Query, Tailwind CSS, Axios

---

## Tracks

- Healthcare (primary)
- SafetyKit: Best AI for Human Safety (secondary)
