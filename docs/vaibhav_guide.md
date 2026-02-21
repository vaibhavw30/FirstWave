# Vaibhav's Personal Guide — PulsePoint

## Role: Frontend Lead + Integration Owner

## Tool: Claude Max (`cd ~/pulsepoint-frontend && claude`)

---

## Your Job in One Sentence

You build everything the judges see and touch. The map, the slider, the charts, the staging pins — all of it is yours. You also own the final integration when Ashwin's API and your frontend need to talk to each other.

## What You Own

- `frontend/` directory — entirely yours, nobody else touches it
- The 2-minute demo video (you drive the screen, Ansh records/edits)
- The integration debugging sprint at Hour 22

## What You Do NOT Touch

- `backend/` — that's Ashwin's
- `databricks_notebooks/` — that's Praneel's
- `data/ems_stations.json` — that's Ansh's

---

## Pre-Hackathon Checklist

Do these before you arrive:

- [ ] Get a free Mapbox token: sign up at `mapbox.com` → Account → Tokens → Create token
- [ ] Have Node.js 18+ installed: `node --version`
- [ ] Have Claude Code installed: `npm install -g @anthropic-ai/claude-code`
- [ ] Create the GitHub repo (you're the repo owner), make it public
- [ ] Push initial file structure — empty dirs for `frontend/`, `backend/`, `databricks_notebooks/`, `data/`
- [ ] Push `CLAUDE.md`, `PRD_v2.md`, `HACKATHON_STRATEGY.md`
- [ ] Create branches: `feat/frontend`, `feat/backend`, `feat/pipeline`
- [ ] Enable branch protection on `main`: Settings → Branches → require 1 PR approval
- [ ] Set Ansh as a collaborator with write access so he can approve PRs
- [ ] Create 30 GitHub issues (list at bottom of this doc)
- [ ] Create worktrees:

```bash
git worktree add ../pulsepoint-frontend feat/frontend
git worktree add ../pulsepoint-backend  feat/backend
git worktree add ../pulsepoint-pipeline feat/pipeline
```

- [ ] Confirm `mock_api_responses.json` is committed by Ashwin before you start coding

---

## Hour 0 — Setup (60 minutes, all 4 together)

Your specific tasks this hour:

1. Create GitHub repo, push initial structure, create branches, set up worktrees (15 min)
2. Enable branch protection, add Ansh as collaborator (5 min)
3. Create all 30 GitHub issues with labels (10 min — use the list at the bottom)
4. Create Devpost draft: `devpost.com` → Start a project, fill title and teammates, save as draft. Don't publish yet (5 min)
5. Start your Claude Code session:

```bash
cd ~/pulsepoint-frontend
claude
```

First thing you say to Claude Code:

```
/init
Read CLAUDE.md. I'm building the React frontend for this project.
My module is the frontend/ directory only. Set up a new Vite + React 18
project here with Tailwind CSS. Install: react-map-gl@7, mapbox-gl@3,
react-plotly.js, plotly.js, axios, lodash, @tanstack/react-query.
Create the folder structure from the CLAUDE.md context.
```

---

## Your Full Build Plan

### Phase 1: Foundation (Hours 0–6)

**Goal: Mapbox map renders, all 4 controls work, API calls go to mock data**

#### Step 1 — Vite Setup (Hour 0–1)

```bash
cd ~/pulsepoint-frontend
npm create vite@latest . -- --template react
npm install
npm install react-map-gl mapbox-gl react-plotly.js plotly.js axios lodash @tanstack/react-query tailwindcss postcss autoprefixer
npx tailwindcss init -p
```

Create `.env`:

```
VITE_MAPBOX_TOKEN=pk.eyJ1IjoiLi4uIn0...   ← your token here
VITE_API_BASE_URL=http://localhost:8000
```

Create `src/constants.js`:

```javascript
export const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN;
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;
export const USE_MOCK_DATA = true; // flip to false at Hour 22

export const VALID_ZONES = [
  "B1",
  "B2",
  "B3",
  "B4",
  "B5",
  "K1",
  "K2",
  "K3",
  "K4",
  "K5",
  "K6",
  "K7",
  "M1",
  "M2",
  "M3",
  "M4",
  "M5",
  "M6",
  "M7",
  "M8",
  "M9",
  "Q1",
  "Q2",
  "Q3",
  "Q4",
  "Q5",
  "Q6",
  "Q7",
  "S1",
  "S2",
  "S3",
];

export const ZONE_NAMES = {
  B1: "South Bronx",
  B2: "West/Central Bronx",
  B3: "East Bronx",
  B4: "North Bronx",
  B5: "Riverdale",
  K1: "Southern Brooklyn",
  K2: "Park Slope",
  K3: "Bushwick",
  K4: "East New York",
  K5: "Bed-Stuy",
  K6: "Borough Park",
  K7: "Williamsburg",
  M1: "Lower Manhattan",
  M2: "Midtown South",
  M3: "Midtown",
  M4: "Murray Hill",
  M5: "Upper East Side S",
  M6: "Upper East Side N",
  M7: "Harlem",
  M8: "Washington Heights S",
  M9: "Washington Heights N",
  Q1: "Far Rockaway",
  Q2: "Flushing",
  Q3: "Forest Hills",
  Q4: "Ridgewood",
  Q5: "Jamaica",
  Q6: "Astoria",
  Q7: "Whitestone",
  S1: "North Shore SI",
  S2: "Mid-Island SI",
  S3: "South Shore SI",
};
```

#### Step 2 — App Shell + Map (Hour 1–3)

Ask Claude Code:

```
Build the App.jsx with this layout:
- Header: dark bar, "🚑 PulsePoint" title left, "NYC Predictive EMS Staging" subtitle right
- Left sidebar: 300px wide, dark background #1a1a2e, contains ControlPanel
- Main area: fills remaining width, contains MapContainer
- Bottom panel: 220px tall, dark background, contains ImpactPanel
- Use Tailwind for layout. Dark color scheme throughout.

For MapContainer: use react-map-gl Map component. Style: mapbox://styles/mapbox/dark-v11.
Initial viewport: longitude -73.97, latitude 40.73, zoom 10.5.
Pass MAPBOX_TOKEN from constants.js.
```

#### Step 3 — Controls (Hour 3–6)

Ask Claude Code:

```
Build all 4 control components in frontend/src/components/Controls/:

1. TimeSlider.jsx
   - Input type range, min=0 max=23 step=1
   - Default value: 20 (8 PM)
   - Debounce onChange with lodash at 300ms
   - Display formatted time: 0="12:00 AM", 12="12:00 PM", 20="8:00 PM" etc.
   - Show tick marks for 12AM, 6AM, 12PM, 6PM, 11PM

2. DayPicker.jsx
   - 7 buttons: Mon Tue Wed Thu Fri Sat Sun
   - Default: Friday (index 4)
   - Single select, active button highlighted blue

3. WeatherSelector.jsx
   - Three radio buttons: None (temp=15°C, precip=0, wind=10)
   - Light Rain (temp=12°C, precip=2, wind=15)
   - Heavy Rain/Storm (temp=8°C, precip=8, wind=30, is_severe=1)
   - Returns {temperature_2m, precipitation, windspeed_10m, is_severe_weather}

4. AmbulanceCount.jsx
   - Minus button, number display, plus button
   - Range 1–10, default 5
   - Label: "Ambulances to Stage"

5. LayerToggle.jsx
   - Three checkboxes: Demand Heatmap (default on), Staging Pins (on), Coverage Circles (on)

Wrap all in ControlPanel.jsx that holds all state and passes onChange callbacks up to App.jsx.
```

#### Step 4 — Mock Data Hooks (Hour 5–6)

Ask Claude Code:

```
Build data hooks in frontend/src/hooks/:

1. useHeatmap.js
   - Takes params: {hour, dow, month, temperature_2m, precipitation, windspeed_10m, ambulances}
   - If USE_MOCK_DATA=true: return mockData.heatmap from data/mock_api_responses.json
   - If false: GET ${API_BASE_URL}/api/heatmap with params
   - Use @tanstack/react-query for caching
   - Debounce: only fire when params stabilize for 300ms

2. useStaging.js — same pattern, hits /api/staging

3. useCounterfactual.js — takes {hour, dow}, hits /api/counterfactual, no debounce needed

4. useZoneHistory.js — takes zone string, hits /api/historical/{zone}

Wire all hooks to ControlPanel state in App.jsx.
```

---

### Phase 2: Map Layers (Hours 6–16)

**Goal: All map layers working, zone click works, tooltips work**

#### Step 5 — Zone Choropleth (Hour 6–9)

The choropleth needs zone boundary GeoJSON from Ashwin's `/api/heatmap`. Until that's ready you'll use 5 hardcoded zones.

Ask Claude Code:

```
Build ZoneChoropleth.jsx in frontend/src/components/Map/.
Props: geojsonData (GeoJSON FeatureCollection), visible (bool).

Use react-map-gl Source and Layer.
Source id: "zones", type: "geojson"

Fill layer (id: "zone-fill"):
  fill-color interpolate linear on normalized_intensity:
    0.0 → #00897B (teal, low demand)
    0.3 → #FDD835 (yellow)
    0.6 → #FB8C00 (orange)
    1.0 → #C62828 (red, critical)
  fill-opacity: 0.70

Outline layer (id: "zone-outline"):
  line-color: #ffffff
  line-width: 0.8
  line-opacity: 0.4

If geojsonData is null or visible=false, render null.
Add onMouseEnter and onMouseLeave handlers that fire with feature properties.
Add onClick handler that fires with feature properties.
```

For testing before Ashwin's API is ready, create `frontend/src/utils/mockGeoJSON.js` with 5 polygon features covering parts of the Bronx and Brooklyn with fake normalized_intensity values.

#### Step 6 — Staging Pins + Coverage Circles (Hour 9–11)

Ask Claude Code:

```
Build StagingPins.jsx in frontend/src/components/Map/.
Props: stagingData (GeoJSON FeatureCollection from /api/staging), visible (bool).

For each feature in stagingData.features:
1. Render a Marker at feature.geometry.coordinates [lon, lat]
   - Custom HTML div: ambulance emoji 🚑 in a blue circle, 32x32px
   - Show on hover: tooltip with cluster_zones list and predicted_demand_coverage

2. Render a coverage circle using a Source + Layer:
   - Use shapely-like approach in JS: create a circle GeoJSON polygon
   - Radius: feature.properties.coverage_radius_m meters
   - Color: rgba(66, 165, 245, 0.15) fill, rgba(66, 165, 245, 0.6) stroke

Helper function createCircleGeoJSON(lon, lat, radiusMeters, steps=64):
  Use the haversine approximation to create a polygon feature.
```

#### Step 7 — Tooltip + Zone Detail (Hour 11–14)

Ask Claude Code:

```
Build ZoneTooltip.jsx:
- Shows on hover over a dispatch zone
- Positions at mouse cursor
- Displays: zone code, zone name, borough, predicted_count,
  normalized_intensity as a colored bar, svi_score, historical_avg_response_sec

Build ZoneDetailPanel.jsx (appears in left sidebar when a zone is clicked):
- Shows: zone name, borough, SVI score with vulnerability label
- Avg response time: avg_response_seconds formatted as "X min Y sec"
- Response decomposition bar: dispatch time vs travel time (two colored segments)
- Mini sparkline chart (Plotly) of hourly_avg[0..23], x-axis 12AM→11PM
- Close button (X) in top right

Wire onMouseEnter → show tooltip, onClick → show ZoneDetailPanel,
onMouseLeave → hide tooltip in MapContainer.jsx.
```

#### Step 8 — Layer Toggle Wire-Up (Hour 14–16)

All three layers (ZoneChoropleth, StagingPins, coverage circles) should respond to the LayerToggle checkboxes. Pass `visible` prop from App state to each component.

---

### Phase 3: Impact Panel (Hours 16–22)

**Goal: Bottom panel shows before/after stats, histogram, equity chart**

#### Step 9 — Coverage Bars (Hour 16–18)

Ask Claude Code:

```
Build CoverageBars.jsx in frontend/src/components/Impact/.
Props: pct_within_8min_static (float), pct_within_8min_staged (float), median_seconds_saved (int).

Layout:
Row 1: Label "Static Stations" | Progress bar (red fill) | "61.2% within 8 min"
Row 2: Label "PulsePoint Staged" | Progress bar (blue fill) | "83.7% within 8 min"
Row 3: Centered stat card: "Median Response Time Saved: 2 min 27 sec"

Animate the bars: use CSS transition width 600ms ease when data updates.
Format median_seconds_saved as "X min Y sec" (e.g. 147 → "2 min 27 sec").
```

#### Step 10 — Response Histogram (Hour 18–20)

Ask Claude Code:

```
Build ResponseHistogram.jsx using react-plotly.js.
Props: histogram_baseline_seconds (array), histogram_staged_seconds (array).

Two overlapping histogram traces:
- Baseline: name="Static Stations", color="#EF5350", opacity 0.65
- Staged: name="PulsePoint Staged", color="#42A5F5", opacity 0.65
- barmode: "overlay"

X-axis: convert seconds to minutes (divide by 60), title "Response Time (min)", range [0,25]
Y-axis: title "Incidents"

Add a vertical dashed yellow line at x=8 (the 8-minute target):
  shapes: [{type:'line', x0:8, x1:8, y0:0, y1:1, yref:'paper',
            line:{color:'#FFD600', width:2, dash:'dash'}}]
Add annotation: "8-min target" near the line.

Dark theme: paper_bgcolor and plot_bgcolor both "transparent",
font color #e0e0e0. height: 160px, no toolbar.
```

#### Step 11 — Equity Chart (Hour 20–21)

Ask Claude Code:

```
Build EquityChart.jsx using react-plotly.js.
Props: by_svi_quartile ({Q1:{median_saved_sec}, Q2, Q3, Q4}).

Horizontal bar chart:
- Y-axis: ["Q1 (Low Risk)", "Q2", "Q3", "Q4 (High Risk)"]
- X-axis: median seconds saved, title "Median Seconds Saved"
- Bar color gradient: Q1=#42A5F5 (light blue) → Q4=#1565C0 (deep blue)
- Add value labels on each bar

Title: "Biggest Gains in Most Vulnerable Neighborhoods"
Dark theme, height 130px, no toolbar.
```

#### Step 12 — ImpactPanel Assembly (Hour 21–22)

Ask Claude Code:

```
Assemble ImpactPanel.jsx:
- Left section (40%): CoverageBars component
- Center section (35%): ResponseHistogram component
- Right section (25%): EquityChart component
- Dark background #0d0d1a, padding 12px
- If counterfactual data is loading: show skeleton placeholders
- If counterfactual shows USE_MOCK_DATA values: show subtle "preview data" badge
Wire to useCounterfactual hook from App.jsx state (hour + dow).
```

---

### Phase 4: Integration Sprint (Hours 22–26)

This is the most important phase. Ashwin's API is now fully live.

#### Step 13 — Flip the Flag

```javascript
// frontend/src/constants.js
export const USE_MOCK_DATA = false;
```

Run the app. You will likely see errors. Work through them one by one.

**Most common issues and fixes:**

**CORS error:**

```
Access to XMLHttpRequest blocked by CORS policy
```

→ Tell Ashwin in chat: "CORS error from localhost:3000, add it to allow_origins." His fix takes 30 seconds.

**Field name mismatch:**

```
normalized_intensity is undefined, map shows no color
```

→ Check `data/mock_api_responses.json` for the exact field name. Check what Ashwin's endpoint is actually returning with:

```bash
curl "http://localhost:8000/api/heatmap?hour=20&dow=4&month=10&temperature=15&precipitation=0&windspeed=10&ambulances=5" | python3 -m json.tool | head -40
```

→ If his field name differs, ask Ashwin to update his serializer — don't rename on the frontend side.

**Map not updating on slider move:**
Tell Claude Code: "The map choropleth is not re-rendering when the slider moves. Paste App.jsx, MapContainer.jsx, useHeatmap.js, ZoneChoropleth.jsx and find why."

**Coverage circles not showing:**
Check that staging GeoJSON Point coordinates are [lon, lat] not [lat, lon].

#### Step 14 — Demo Scenarios (Hour 24–25)

Add two preset buttons at the top of ControlPanel:

```javascript
const DEMO_SCENARIOS = {
  friday_peak: { hour: 20, dow: 4, month: 10, weather: "none", ambulances: 5 },
  monday_quiet: { hour: 4, dow: 0, month: 10, weather: "none", ambulances: 5 },
};
```

Clicking "Fri 8PM" instantly sets all sliders/pickers to those values. This is for the live demo — you don't want to be fumbling with controls while presenting.

#### Step 15 — Polish (Hour 25–26)

- Smooth color transition on choropleth update: add `transition: {duration: 300}` to Mapbox layer paint properties
- Loading states: when API call is in-flight, show a subtle spinner on the map
- Error state: if API returns non-200, show "Using preview data" banner and fall back to mock
- Check layout doesn't break at 1280×800 (common laptop resolution for demos)

---

### Phase 5: Demo Video (Hours 26–30)

**You drive the screen. Ansh records and edits.**

#### Recording Setup

1. Close all browser tabs except the dashboard
2. Turn off all notifications: Mac → Focus Mode → Do Not Disturb
3. Set browser to full screen (F11)
4. Open QuickTime → File → New Screen Recording
5. Set to record at 1080p
6. Default to the Friday 8PM scenario

#### Recording Script (2 minutes exactly)

```
0:00–0:15 — TITLE CARD (Ansh adds in editing)
Text: "Bronx EMS average response time: 10.6 min | Clinical target: 8 min"

0:15–0:25 — ONE LINE PITCH (voiceover while showing Monday 4AM)
"PulsePoint uses 28 million EMS incidents to predict where the next
emergency will happen — before the 911 call comes in."

0:25–1:30 — DASHBOARD WALKTHROUGH (live screen recording, you narrate)
- Show Monday 4AM: calm map, light colors
- Drag slider to Friday 8PM: "Watch the Bronx and Brooklyn"
- Map goes orange/red: "Five million Fridays telling us where the next wave hits"
- Click staging (K=5): pins appear with coverage circles
- "These circles are 8-minute drive radii using real NYC road networks"
- Point to impact panel: coverage stat jump

1:30–1:50 — IMPACT NUMBERS (Ansh adds text overlays in editing)
Text overlay: "[X]% → [Y]% of calls within 8 minutes"
Text overlay: "[Z] min [W] sec median response time saved"
Text overlay: "Largest gains in highest-vulnerability neighborhoods"

1:50–2:00 — CLOSE (Ansh adds in editing)
"PulsePoint | GT Hacklytics 2026 | Healthcare Track + SafetyKit"
```

Record the walkthrough segment (0:25–1:30) at least 3 times. Use the cleanest take. Ansh assembles the full 2-minute video.

---

## Your Commits + PRs Workflow

After completing each major step, commit and push:

```bash
# Ask Claude Code to do this:
"Commit all changes with message 'feat: [description] — closes #[issue number]'.
Push to feat/frontend. Open a PR to main titled '[description]'
with the frontend label."
```

**PR schedule:**

- Hour 6: PR closing issues #1, #2, #3 (setup + controls + mock hooks)
- Hour 12 (Checkpoint 1): PR closing issues #4, #5 (choropleth + staging pins)
- Hour 18: PR closing issues #6, #7, #8 (impact panel components)
- Hour 22 (Checkpoint 2): PR closing #9 (real API wired)
- Hour 26: Final PR closing #10 (polish + demo ready)

---

## Group Chat Communication Rules

Post these exact messages at these times:

| When              | Message                                                          |
| ----------------- | ---------------------------------------------------------------- |
| Hour 0            | `READY: GitHub repo live, worktrees set up, all issues created`  |
| Map renders       | `frontend: Mapbox basemap renders on localhost:3000`             |
| Mock data working | `frontend: choropleth + staging pins working on mock data`       |
| Hour 22           | `frontend: USE_MOCK_DATA flipped to false, testing real API now` |
| Integration bug   | `BLOCKED: [Ashwin/Praneel] — [specific thing I need]`            |
| Demo ready        | `frontend: demo video recorded, ready for editing`               |

Only tag someone by name when you need something from them specifically.

---

## If Things Go Wrong

**Map is blank:**

1. Open browser console (F12)
2. Look for Mapbox token error → check `.env` has `VITE_MAPBOX_TOKEN`
3. Look for CORS error → tell Ashwin
4. Look for undefined properties → field name mismatch with mock data

**Slider is laggy/crashing the browser:**
Debounce is missing or not working. Ask Claude Code: "The TimeSlider is calling useHeatmap on every pixel of movement. Show me useHeatmap.js and TimeSlider.jsx and fix the debounce."

**API times out:**
Ashwin's model inference is slow. Switch `USE_MOCK_DATA = true` temporarily, keep building, flag Ashwin in chat.

**Can't finish impact panel by Hour 22:**
Ship without the EquityChart. CoverageBars + ResponseHistogram are the two most important. EquityChart can be added during polish if time allows.

**Video editing takes too long:**
Use Loom as fallback. Record directly in Loom, share the URL. It's a 2-minute setup. Acceptable for submission.

---

## GitHub Issues to Create (Your Task in Hour 0)

Create all of these. Assign the frontend ones to yourself, backend to Ashwin, pipeline to Praneel, deliverables to Ansh.

**Frontend (assign to Vaibhav):**

- #1 `frontend` — Base map + Mapbox setup
- #2 `frontend` — ControlPanel: TimeSlider, DayPicker, WeatherSelector, AmbulanceCount
- #3 `frontend` — ZoneChoropleth layer (mock data)
- #4 `frontend` — StagingPins + coverage circles
- #5 `frontend` — ZoneTooltip + ZoneDetailPanel
- #6 `frontend` — ImpactPanel: CoverageBars
- #7 `frontend` — ResponseHistogram (Plotly)
- #8 `frontend` — EquityChart (SVI quartile)
- #9 `integration` — Wire real API (USE_MOCK_DATA=false)
- #10 `frontend` — Final polish + demo scenarios

**Backend (assign to Ashwin):**

- #11 `backend` — FastAPI skeleton + mock endpoints + CORS
- #12 `backend` — PostGIS zone boundaries
- #13 `backend` — Startup artifact loading
- #14 `backend` — /api/heatmap real inference
- #15 `backend` — /api/staging K-Means
- #16 `backend` — /api/counterfactual Parquet cache
- #17 `backend` — /api/historical + /api/breakdown
- #18 `backend` — Error handling + perf validation

**Pipeline (assign to Praneel):**

- #19 `pipeline` — Notebook 01: ingest + clean
- #20 `pipeline` — Notebook 02: weather merge
- #21 `pipeline` — Notebook 03: SVI join
- #22 `pipeline` — Notebook 04: aggregation
- #23 `pipeline` — Notebook 05: XGBoost training
- #24 `pipeline` — Notebook 06: OSMnx matrix (PRE-HACKATHON)
- #25 `pipeline` — Notebooks 07–08: staging + counterfactual
- #26 `pipeline` — Artifact export to backend/artifacts/

**Deliverables (assign to Ansh):**

- #27 `deliverable` — ems_stations.json (36 FDNY stations)
- #28 `deliverable` — Devpost write-up
- #29 `deliverable` — 2-minute demo video
- #30 `deliverable` — README final pass + submission

---

## Your Hour-by-Hour Summary

| Hour  | Task                                           | Closes |
| ----- | ---------------------------------------------- | ------ |
| 0–1   | GitHub setup, worktrees, issues, Vite scaffold | Setup  |
| 1–3   | App shell, Mapbox basemap renders              | #1     |
| 3–6   | All 4 controls + Layer Toggle                  | #2     |
| 6–9   | ZoneChoropleth (mock GeoJSON)                  | #3     |
| 9–11  | StagingPins + coverage circles                 | #4     |
| 11–14 | ZoneTooltip + ZoneDetailPanel                  | #5     |
| 14–16 | Layer toggles + mock API hooks wired           |        |
| 16–18 | CoverageBars                                   | #6     |
| 18–20 | ResponseHistogram                              | #7     |
| 20–22 | EquityChart + ImpactPanel assembly             | #8     |
| 22–24 | Flip real API, debug integration issues        | #9     |
| 24–26 | Demo presets, polish, animations               | #10    |
| 26–29 | Record demo video (3 takes minimum)            | #29    |
| 29–32 | Pitch rehearsal, expo prep                     |        |
| 32–34 | Buffer: fix anything that breaks on hotspot    |        |
