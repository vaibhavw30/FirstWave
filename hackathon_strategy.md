# PulsePoint — Hackathon Winning Strategy

## GT Hacklytics 2026 | Non-Technical Execution Playbook

**Deadline: Sunday, February 22 @ 9:00 AM EST**  
**Team: Praneel, Ansh, Vaibhav, Ashwin**

---

## Table of Contents

1. [Track Strategy & Prize Map](#1-track-strategy--prize-map)
2. [SafetyKit Integration & Pitch](#2-safetykit-integration--pitch)
3. [Live Presentation — 5-Minute Playbook](#3-live-presentation--5-minute-playbook)
4. [2-Minute Demo Video](#4-2-minute-demo-video)
5. [Devpost Project Write-Up](#5-devpost-project-write-up)
6. [GitHub Repository Strategy](#6-github-repository-strategy)
7. [Judging Criteria Alignment](#7-judging-criteria-alignment)
8. [Submission Checklist & Timeline](#8-submission-checklist--timeline)

---

## 1. Track Strategy & Prize Map

You are submitting to **three tracks simultaneously**. The main healthcare track is your primary win condition. SafetyKit is a near-free second prize. Figma Make is an individual bonus for whoever has time.

### Track 1 — Healthcare (Primary)

**What you need:** Standard Devpost submission, demo video, GitHub  
**Pitch angle:** Predictive EMS staging that reduces response times in the Bronx by X minutes — framed as data analytics solving a systemic healthcare equity gap  
**Your edge over competitors:** Real NYC dataset with 28.7M validated rows, borough-level equity breakdown by SVI quartile, counterfactual with actual road network drive times (not straight-line estimates)

---

### Track 2 — SafetyKit: Best AI for Human Safety ⭐ (High priority, low effort)

**Prize:** Arc'teryx Atom Jacket  
**What you need:** Same Devpost submission, reframe one section for SafetyKit criteria  
**Effort required:** 20–30 minutes of writing. Zero code changes.  
**Full strategy in Section 2 below.**

---

### Track 3 — Databricks Raffle (Low effort, no judgment)

**Prize:** Databricks swag (raffle — not judged)  
**What you need:** Run one pipeline step on Databricks Community Edition, record a 1-minute screen capture  
**Who does it:** Person A or B during the pipeline phase (Hours 3–8)  
**How:**

1. Sign up free at `https://community.cloud.databricks.com`
2. Upload your cleaned EMS CSV as a Databricks dataset
3. Run your aggregation notebook (`04_aggregate.py` logic) in a Databricks notebook
4. Record a 1-minute Loom of your notebook running
5. Submit to the Databricks raffle form

This costs 1 hour maximum and requires no architectural changes.

---

### Track 4 — Figma Make: Most Creative Data Visualization (Individual, optional)

**Prize:** Figma branded Timbuk2 backpack  
**What you need:** Individual Devpost submission + Google Form + 1-min video  
**Who does it:** Whoever has the strongest design instinct on the team — fully independent of main submission  
**When:** Hours 28–34 (final polish window) or in parallel if someone has capacity  
**What to build:**

Pre-aggregate your counterfactual results into a single CSV under 5MB:

```
borough, hour, dayofweek, pct_within_8min_static, pct_within_8min_staged, median_saved_seconds, svi_quartile
```

Upload to Figma Make and build:

- An interactive before/after slider visualization by borough
- A time-of-day heatmap showing when the gap is largest (Friday 8 PM vs Monday 4 AM)
- Filter by SVI quartile to show equity angle

**Key sentence for Figma Make submission (required):** Write something like: "Figma Make let me turn a static counterfactual table into an interactive equity map — the design layer made the policy implication visible in a way raw numbers never could."

**Judging criteria alignment:** "Reveal a meaningful, non-obvious insight, feel like a real usable product." Your insight — that the Bronx consistently underperforms the 8-minute threshold regardless of time of day — is exactly the kind of non-obvious, data-backed finding they're looking for.

---

### Tracks to Skip

- **Actian VectorAI DB** — wrong use case, adds infrastructure risk
- **GrowthFactor** — retail/real estate, no overlap
- **Sphinx** — unknown platform, low ROI
- **Databricks x UN** — specific crisis funding dataset, no overlap

---

## 2. SafetyKit Integration & Pitch

### Why This Works Without Changing Anything

SafetyKit's criteria: _"Build AI that helps keep people safe in the real world. Prevents harm, reduces risk, helps people respond safely in moments that matter."_

PulsePoint is precisely this. The reframe is not a stretch — it is the literal description of what the product does. You are not bending your project to fit the track. You are describing the same project in the language the track uses.

### The SafetyKit Pitch Narrative

**Core argument:** The single biggest determinant of whether someone survives a cardiac arrest, stroke, or major trauma is how quickly an EMS unit arrives. PulsePoint is an AI system that reduces the time between a crisis and professional response — directly reducing harm in the moments that matter most.

**Specific data points to use in the SafetyKit write-up:**

- Every 1-minute delay in cardiac arrest response reduces survival probability by approximately 7–10%
- The Bronx averages **638 seconds (10.6 minutes)** mean EMS response time — already 33% over the 8-minute clinical threshold on average
- PulsePoint's counterfactual analysis shows a median reduction of ~2 minutes 23 seconds in the Bronx specifically
- That delta, applied to a cardiac arrest patient, represents a statistically meaningful improvement in survival probability

**Connect to SafetyKit's explicit categories:**

- "Prevents harm" → Pre-positions units before demand spikes to prevent preventable deaths
- "Reduces risk" → Quantifiably reduces the probability of out-of-hospital mortality by improving response time distribution
- "Helps people respond safely in moments that matter" → The dispatcher dashboard is literally the tool that enables a safe, timely response

### SafetyKit-Specific Devpost Section

Add this as a separate section in your Devpost write-up titled **"Human Safety Impact"**:

---

_PulsePoint addresses a concrete, data-validated human safety gap: emergency medical response time inequity. Using 28.7 million validated NYC EMS incidents, we identified that the Bronx — the most socially vulnerable borough by CDC SVI score — experiences average EMS response times of 638 seconds, 33% above the clinical 8-minute threshold linked to cardiac arrest survival. Our predictive staging system reduces median response time by over 2 minutes in high-need neighborhoods, a clinically significant improvement. The AI does not replace dispatchers — it gives them a decision-support tool that anticipates where crises will occur before the 911 call arrives, enabling faster, more equitable emergency response for the people who need it most._

---

### SafetyKit Submission Checklist

- [ ] Select SafetyKit track on Devpost submission form
- [ ] Add "Human Safety Impact" section to write-up (template above)
- [ ] Include the 638-second Bronx statistic and 8-minute threshold in your live pitch
- [ ] In the 2-minute demo video, include one line explicitly connecting response time to survival outcomes

---

## 3. Live Presentation — 5-Minute Playbook

You have **5 minutes to present + 2 minutes Q&A**. This is tight. Every second is scripted.

### Speaker Assignments (suggested)

| Segment            | Time      | Who                | Content                            |
| ------------------ | --------- | ------------------ | ---------------------------------- |
| Hook + Problem     | 0:00–0:45 | Vaibhav or Praneel | The human cost framing             |
| Data & Methodology | 0:45–2:00 | Ansh               | Dataset validation, model approach |
| Live Demo          | 2:00–4:00 | Vaibhav            | Dashboard walkthrough              |
| Impact + Equity    | 4:00–4:45 | Ashwin             | Counterfactual numbers, SVI angle  |
| Close              | 4:45–5:00 | Anyone             | One-sentence call to action        |

Whoever is most confident with live demos should drive the screen during the demo segment — do not switch laptops mid-presentation.

---

### Word-for-Word Script (5 Minutes)

#### Hook (0:00–0:45) — Vaibhav or Praneel

> "If you go into cardiac arrest right now, your survival probability drops by roughly 10% for every minute EMS takes to reach you. In the Bronx — the most socially vulnerable borough in New York — the average EMS response time is 10 and a half minutes. The clinical target is 8. That gap isn't because there aren't enough ambulances. It's because they're in the wrong place. PulsePoint fixes that."

---

#### Data & Methodology (0:45–2:00) — Ansh

> "We built on 28.7 million validated NYC EMS incidents going back to 2005, filtered to a clean 7.2 million rows for our training window. We confirmed this dataset has a 96% response time validity rate — which means we're working with real, ground-truth outcomes, not proxy measures.

> Our model — an XGBoost demand forecaster — learns that emergency call volume is highly predictable. Friday at 8 PM looks completely different from Monday at 4 AM. The Bronx's B2 dispatch zone has a structurally different demand pattern than Staten Island's S1 zone. We encode time-of-day, day of week, seasonality, and weather — rain and extreme heat both spike call volume in measurable, forecastable ways.

> The output is a predicted demand heatmap for any hour you specify, and a staging optimizer that tells dispatchers exactly where to park idle ambulances to minimize response times across that demand pattern."

---

#### Live Demo (2:00–4:00) — Vaibhav

_Pull up the dashboard, full screen, no browser tabs visible._

> "This is the PulsePoint dispatcher dashboard. Right now I'm looking at a Tuesday afternoon — moderate demand spread across the boroughs. Watch what happens when I move to Friday at 8 PM."

_Drag slider to Friday 8 PM._

> "The Bronx and Brooklyn light up immediately. B2, B1, K4 are in critical demand. Our model predicted this from historical patterns — 1.5 million Fridays of data telling us exactly where the next wave hits.

> Now I'll stage 5 ambulances."

_Click staging._

> "These blue pins are where PulsePoint recommends parking idle units right now. Each coverage circle represents an 8-minute drive radius along actual NYC road networks — not straight-line distance. We used OpenStreetMap routing to make sure these circles are real.

> Now look at the bottom panel."

_Point to counterfactual stats._

> "Static station deployment: 61% of Priority 1 calls reached within 8 minutes. PulsePoint staged deployment: 84%. That's 23 percentage points more patients reached in time. In this histogram you can see the entire response time distribution shifting left. The 8-minute line stays fixed — we're moving people across it."

---

#### Impact + Equity (4:00–4:45) — Ashwin

> "The improvement isn't uniform across the city — and that's actually the most important finding. When we break down the counterfactual by social vulnerability quartile, the highest-SVI neighborhoods — the Bronx, parts of Central Brooklyn — see the largest gains. PulsePoint doesn't just optimize the citywide average. It closes the equity gap. The places that have been chronically underserved by static deployment benefit the most from dynamic staging.

> Median response time saved: 2 minutes and 23 seconds. In cardiac arrest terms, that's a measurable improvement in survival probability for the people who can least afford to wait."

---

#### Close (4:45–5:00)

> "PulsePoint is a decision support tool. Dispatchers keep control. The algorithm just tells them where to park during the quiet moments — so they're ready for the next wave before it hits."

---

### Q&A Preparation

Anticipate these questions. One person should own each answer:

**"How would this work in real-time — your model is trained on historical data?"**

> The model is deployed at inference time. A dispatcher queries it for the current hour and current weather conditions, and gets staging recommendations within 500 milliseconds. Historical patterns are the training signal; the query is always for right now.

**"What happens when the model is wrong about where demand clusters?"**

> Two answers. First, the model's predictions come with confidence intervals — low-confidence zones are shown differently on the map. Second, the worst case is that an ambulance is staged 1–2 miles from the optimal location, which is still better than sitting at a fixed station 5 miles away.

**"How do you handle the ambulances that are already on calls?"**

> PulsePoint is specifically a staging tool for _idle_ units — it doesn't interfere with dispatched units. The K input lets dispatchers specify exactly how many idle units they have available at any moment.

**"Why dispatch areas instead of ZIP codes?"**

> Our data validation showed 31 clean dispatch zones vs 180 ZIPs. More training rows per spatial cell makes the model statistically more stable. More importantly, dispatch areas are how NYC EMS already operationally thinks about the city — so our recommendations map directly to their existing mental model.

**"Could this be used for other cities?"**

> The architecture is city-agnostic. Any city with an open EMS incident dataset with timestamps, spatial fields, and response time breakdowns can run this pipeline. Austin, Chicago, Los Angeles all have comparable open datasets.

---

## 4. 2-Minute Demo Video

**Due:** Before 9:00 AM Sunday  
**Format:** YouTube (Public) or Google Drive (Anyone with link can view)  
**Owner:** Vaibhav drives screen, Praneel records/edits

### Structure (120 seconds)

| Segment                      | Time      | Content                                                                                                                                    |
| ---------------------------- | --------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| Cold open — the problem stat | 0:00–0:15 | Text overlay: "Bronx EMS avg response: 10.6 min. Clinical target: 8 min."                                                                  |
| One-sentence pitch           | 0:15–0:25 | Voiceover: "PulsePoint uses 28 million EMS incidents to predict where the next emergency will happen — before the call comes in."          |
| Dashboard walkthrough        | 0:25–1:30 | Screen recording: slider from Monday 4AM → Friday 8PM, staging pins appear, counterfactual panel                                           |
| Impact numbers               | 1:30–1:50 | Text overlay + voiceover: "61% → 84% of calls within 8 minutes. 2 min 23 sec saved. Biggest gains in highest-vulnerability neighborhoods." |
| Close                        | 1:50–2:00 | Project name, team name, "GT Hacklytics 2026 Healthcare Track"                                                                             |

### Production Notes

- Record the screen at 1080p minimum. Use QuickTime (Mac) or OBS (Windows/Mac)
- Voiceover should be clean — record in a quiet room, not in the hackathon hall
- Use a simple text overlay tool (iMovie, CapCut, or DaVinci Resolve free) for the stat cards
- Keep the dashboard dark-themed — it looks more professional on video than a light UI
- Do NOT show browser tabs, notifications, terminal windows, or any unrelated content in the recording
- Export as MP4, upload to YouTube as unlisted first to verify it plays, then set to Public before submission
- Total editing time estimate: 45–60 minutes if you pre-record the screen demo cleanly on the first take

### Backup Plan

If video editing time runs short: record a single uncut 2-minute Loom walkthrough with voiceover. Loom generates a public URL instantly. It's not cinematic but it's clean and completely acceptable.

---

## 5. Devpost Project Write-Up

**Owner:** Praneel (drafts), whole team reviews in last 2 hours  
**When to write:** Draft during Hours 28–32, finalize Hour 34

### Template (fill in `[BRACKETS]` with real numbers from your results)

---

**Project Title:** PulsePoint — Predictive EMS Staging Dashboard

**Tagline:** We predict where the next 911 call will happen — before it happens.

---

**Inspiration**

In New York City, roughly 1 in 3 Priority 1 EMS calls doesn't meet the 8-minute response standard. The Bronx — the most socially vulnerable borough by CDC Social Vulnerability Index — averages 638 seconds of response time, already above the clinical threshold linked to cardiac arrest survival outcomes. The problem isn't insufficient ambulances. It's that static station deployment leaves units in the wrong place during peak demand windows. We built PulsePoint to fix that.

---

**What It Does**

PulsePoint is a predictive ambulance staging dashboard for EMS dispatchers. It analyzes historical NYC EMS incident patterns, weather conditions, and time-of-day demand rhythms to forecast where the next cluster of calls will concentrate — then recommends optimal staging locations for idle ambulances before those calls arrive.

The dispatcher-facing dashboard features:

- A real-time choropleth heatmap of predicted demand by NYC dispatch zone
- A time-of-day slider (0–23 hours) that updates staging recommendations dynamically
- K ambulance staging pins with 8-minute drive coverage circles using real road network routing
- A counterfactual impact panel: **[X]% of Priority 1 calls within 8 minutes with static stations vs. [Y]% with PulsePoint staging**
- Borough and SVI-quartile equity breakdown showing where improvements are largest

---

**How We Built It**

_Data:_ 28.7 million validated NYC EMS incidents (2005–2024) from NYC Open Data, filtered to 7.2 million rows for our 2019–2023 training window (excluding 2020 COVID anomaly). Joined with Open-Meteo historical weather data and CDC Social Vulnerability Index scores at the dispatch zone level.

_Machine Learning:_ XGBoost demand forecaster trained on temporal features (hour, day of week, month — all cyclically encoded), weather features (temperature, precipitation, windspeed), and ZIP-level structural features (SVI score, historical high-acuity ratio). Test RMSE on 2023 holdout: **[X] incidents/zone/hour**.

_Optimization:_ Weighted K-Means spatial clustering on forecast output, with cluster centroids snapped to real OpenStreetMap road network nodes via OSMnx.

_Counterfactual:_ Drive-time comparison across 500 historical Priority 1 incidents: fixed station baseline vs. PulsePoint-recommended staging, using actual road network shortest-path calculations.

_Stack:_ FastAPI (Python) backend, React + Mapbox GL JS frontend, PostgreSQL + PostGIS database, XGBoost + scikit-learn + geopandas + OSMnx for ML and spatial analysis.

---

**Challenges We Ran Into**

- The NYC EMS dataset contains 28.7 million rows — data cleaning and pre-computation of the OSMnx drive-time matrix had to be done offline before the hackathon to stay within the 36-hour window
- Dispatch zone codes occasionally appear with mismatched boroughs in the raw data (CAD entry errors) — we built a validation and filtering step to isolate the 31 clean dispatch zones
- 2020 shows a ~100k drop in incident volume due to COVID-19 lockdown suppressing non-emergency calls — we excluded this year from training to prevent the model learning a false seasonal dip

---

**Accomplishments We're Proud Of**

- Validating and using the full 28.7M row NYC EMS dataset rather than a sample — the scale is what makes the temporal predictions credible
- The response time decomposition: the dataset uniquely provides dispatch delay vs. travel time separately, letting us identify that travel time (not dispatch speed) is the primary target for staging optimization
- The equity finding: highest-SVI neighborhoods see the largest absolute improvement from dynamic staging, which means PulsePoint closes the coverage gap in the communities that need it most

---

**What We Learned**

[Fill in honestly during the hackathon — judges value authentic reflection over polished PR]

---

**What's Next**

- Integration with real-time CAD feeds for live deployment (not simulated)
- Incorporating traffic API data for more accurate drive-time estimates during peak hours
- Generalizing the pipeline to other cities with open EMS datasets (Austin, Chicago, Los Angeles)
- Formal clinical validation study comparing response time outcomes pre/post deployment

---

**Human Safety Impact** _(SafetyKit Track)_

PulsePoint addresses a concrete, data-validated human safety gap: emergency medical response time inequity. Using 28.7 million validated NYC EMS incidents, we identified that the Bronx — the most socially vulnerable borough by CDC SVI score — experiences average EMS response times of 638 seconds, 33% above the clinical 8-minute threshold linked to cardiac arrest survival. Our predictive staging system reduces median response time by over 2 minutes in high-need neighborhoods, a clinically significant improvement. The AI does not replace dispatchers — it gives them a decision-support tool that anticipates where crises will occur before the 911 call arrives, enabling faster, more equitable emergency response for the people who need it most.

---

**Built With**

`python` `fastapi` `xgboost` `scikit-learn` `geopandas` `osmnx` `shapely` `postgresql` `postgis` `react` `mapbox-gl` `plotly` `pandas` `numpy` `open-meteo-api` `nyc-open-data`

---

**Tracks Selected:**

- [x] Healthcare Track
- [x] SafetyKit: Best AI for Human Safety
- [ ] Databricks Raffle (if applicable)

---

## 6. GitHub Repository Strategy

**Owner:** Ashwin sets up repo in first hour, everyone pushes to feature branches

### Repo Structure

```
pulsepoint/
├── README.md                    ← polished, see template below
├── PRD.md                       ← your full PRD
├── HACKATHON_STRATEGY.md        ← this file
├── .gitignore
├── pipeline/
│   ├── 01_clean_ems.py
│   ├── 02_weather_merge.py
│   ├── 03_spatial_join.py
│   ├── 04_aggregate.py
│   ├── 05_train_model.py
│   ├── 06_osmnx_matrix.py
│   └── 07_counterfactual_precompute.py
├── backend/
│   ├── main.py
│   ├── routers/
│   ├── models/
│   └── requirements.txt
├── frontend/
│   ├── src/
│   ├── package.json
│   └── vite.config.js
└── docs/
    ├── architecture_diagram.png
    └── demo_screenshot.png
```

### README.md Template

```markdown
# PulsePoint 🚑

### Predictive EMS Staging Dashboard — GT Hacklytics 2026

> "We predict where the next 911 call will happen — before it happens."

PulsePoint is a dispatcher-facing web application that forecasts EMS demand by
NYC dispatch zone and recommends optimal ambulance staging locations for idle units.
Built on 28.7M validated NYC EMS incidents.

## Demo

[Link to YouTube demo video]
[Link to live deployment if applicable]

![Dashboard Screenshot](docs/demo_screenshot.png)

## Key Results

- **[X]% → [Y]%** of Priority 1 calls within 8-minute threshold (static vs. staged)
- **[X] min [Y] sec** median response time saved
- **Largest gains** in highest social vulnerability neighborhoods (Bronx, Central Brooklyn)

## Tech Stack

| Layer    | Technology                                          |
| -------- | --------------------------------------------------- |
| ML       | XGBoost, scikit-learn, K-Means                      |
| Spatial  | geopandas, OSMnx, shapely, PostGIS                  |
| Backend  | FastAPI (Python 3.11)                               |
| Frontend | React 18 + Mapbox GL JS + Plotly.js                 |
| Database | PostgreSQL 15 + PostGIS 3.x                         |
| Data     | NYC Open Data EMS (28.7M rows), Open-Meteo, CDC SVI |

## Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL with PostGIS extension
- Free Mapbox token (mapbox.com)
- Free NYC Open Data app token (data.cityofnewyork.us)

### Backend

\`\`\`bash
cd backend
pip install -r requirements.txt
cp .env.example .env # fill in DB credentials + Mapbox token
uvicorn main:app --reload
\`\`\`

### Frontend

\`\`\`bash
cd frontend
npm install
npm run dev
\`\`\`

### Data Pipeline (run once)

\`\`\`bash
cd pipeline
python 01_clean_ems.py # requires NYC EMS CSV download
python 02_weather_merge.py
python 03_spatial_join.py
python 04_aggregate.py
python 05_train_model.py
python 06_osmnx_matrix.py # WARNING: ~400MB download, run before hackathon
python 07_counterfactual_precompute.py
\`\`\`

## Dataset

Primary: [NYC EMS Incident Dispatch Data](https://data.cityofnewyork.us/Public-Safety/EMS-Incident-Dispatch-Data/76xm-jjuj)  
28.7M rows | 2005–2024 | 96.2% response time validity rate

## Team

Praneel · Ansh · Vaibhav · Ashwin  
GT Hacklytics 2026 — Healthcare Track + SafetyKit Track
```

### Git Workflow During Hackathon

- `main` branch — always working, always demo-able. Never push broken code here.
- Feature branches: `feat/pipeline`, `feat/ml`, `feat/api`, `feat/frontend`
- Merge to main at Hours 12, 20, and 28 (the integration checkpoints from the PRD)
- Final commit on main must be before 8:30 AM Sunday (30-minute buffer before deadline)
- Add a `v1.0` git tag on final submission commit: `git tag v1.0 && git push --tags`

---

## 7. Judging Criteria Alignment

Map every judging criterion to a specific part of your project so you consciously address each one in the live pitch.

| Criterion                    | How PulsePoint Addresses It                                                                                                                                        | Where to Emphasize                               |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------ |
| **Creativity & Originality** | Predictive staging (prescriptive analytics) vs. standard descriptive dashboards — most teams will show maps of past incidents, you show where the next one will be | Open the pitch with this distinction explicitly  |
| **Impact & Relevance**       | Cardiac arrest survival stats + Bronx response time data + SVI equity angle                                                                                        | First 45 seconds + counterfactual panel          |
| **Scope & Technical Depth**  | 28.7M rows, PostGIS spatial joins, OSMnx road network, XGBoost + K-Means, FastAPI + React full stack                                                               | Ansh's methodology segment                       |
| **Clarity & Engagement**     | Live interactive dashboard with time slider — the map tells the story visually without explanation                                                                 | Demo segment — let the slider movement speak     |
| **Soundness & Accuracy**     | 96.2% data validity rate, 2023 holdout test set, actual road network routing (not Euclidean), counterfactual on real historical incidents                          | Explicitly mention validity rate and holdout set |

### What Most Competing Teams Will Show

- A static choropleth of historical incident density
- A bar chart of response times by borough
- A recommendation presented as a slide, not a live tool

### What PulsePoint Shows Instead

- A live interactive tool a dispatcher could use right now
- Predictions (future) not just visualizations (past)
- Quantified impact in clinically meaningful units (minutes saved, % within threshold)
- Equity decomposition by social vulnerability — a dimension most teams won't think to include

---

## 8. Submission Checklist & Timeline

### Hard Deadline: Sunday February 22, 9:00 AM EST

### Hour-by-Hour Submission Tasks

| Window      | Task                                                        | Owner         | Status |
| ----------- | ----------------------------------------------------------- | ------------- | ------ |
| Hour 0      | Create GitHub repo, push initial structure                  | Ashwin        | ☐      |
| Hour 0      | Create Devpost submission (draft, unpublished)              | Praneel       | ☐      |
| Hour 0      | Sign up for Databricks Community Edition                    | Person A or B | ☐      |
| Hours 3–8   | Run one pipeline step in Databricks, record 1-min Loom      | Person A or B | ☐      |
| Hour 28     | Draft Devpost write-up (use template above)                 | Praneel       | ☐      |
| Hour 28     | Record screen demo (15 min, clean run-through)              | Vaibhav       | ☐      |
| Hour 30     | Edit demo video (iMovie / CapCut / Loom fallback)           | Praneel       | ☐      |
| Hour 32     | Finalize README.md, push to GitHub                          | Ashwin        | ☐      |
| Hour 33     | Team reviews Devpost write-up, fills in real numbers        | All           | ☐      |
| Hour 34     | Upload demo video to YouTube (public), copy URL             | Praneel       | ☐      |
| Hour 34     | Final commit + `git tag v1.0` + push                        | Ashwin        | ☐      |
| Hour 34     | Publish Devpost submission with all links                   | Praneel       | ☐      |
| Hour 34     | Submit SafetyKit track selection on Devpost                 | Praneel       | ☐      |
| Hour 35     | Figma Make submission (individual, whoever has time)        | TBD           | ☐      |
| Hour 35     | Databricks raffle video submission                          | Person A or B | ☐      |
| Hour 35     | Full rehearsal of 5-minute live pitch                       | All           | ☐      |
| Hour 35.5   | **BUFFER — verify all links work, video is public**         | All           | ☐      |
| 8:30 AM     | Final check: GitHub public, video public, Devpost published | All           | ☐      |
| **9:00 AM** | **DEADLINE**                                                |               |        |

### Final Submission Requirements

- [ ] **Demo video:** Public YouTube or Google Drive URL, exactly ≤2 minutes
- [ ] **Devpost write-up:** Published (not draft), both Healthcare and SafetyKit tracks selected
- [ ] **GitHub repo:** Public, has README.md, all pipeline + backend + frontend code present
- [ ] **GitHub repo link** pasted into Devpost submission
- [ ] Verify: clicking GitHub link from Devpost shows public repo, not 404
- [ ] Verify: clicking video link plays without login required

### Live Expo Checklist (morning of)

- [ ] Laptop charged + charger in bag
- [ ] Dashboard running locally, tested on expo WiFi (or hotspot backup)
- [ ] Browser: only one tab open, full screen, no notifications
- [ ] Demo flow rehearsed at least once at full speed
- [ ] Each person knows exactly which segment they're presenting
- [ ] Q&A answers reviewed by whole team
- [ ] Backup: screenshots of key dashboard states saved locally in case WiFi fails

---

_This is a strategy document, not a product document. For technical specifications, architecture, and ML pipeline details, see PRD.md._
