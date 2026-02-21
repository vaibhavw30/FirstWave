# Ansh's Personal Guide — PulsePoint

## Role: Project Manager + Demo Owner

## Tools: Google Maps, FDNY website, Devpost, GitHub (approving PRs), CapCut/iMovie

---

## Your Job in One Sentence

You keep the team coordinated, produce the non-code deliverables that nobody else has time for, and deliver the demo pitch that wins the hackathon.

## What You Own

- `data/ems_stations.json` — 36 FDNY EMS station locations (you build this manually)
- Devpost write-up — full submission write-up
- 2-minute demo video — you coordinate with Vaibhav, record, and edit
- GitHub PR approvals — you are the required reviewer on all PRs to `main`
- Issue board — you track and report team progress every 4 hours
- The Hook segment (0:00–0:45) of the live 5-minute pitch

## What You Do NOT Do

- Edit any code files
- Edit `backend/`, `frontend/`, or `databricks_notebooks/`

---

## Why Your Work Matters

Without `ems_stations.json`, Praneel's counterfactual can't run — there's no baseline to compare against. Your job directly unblocks the most important ML output of the whole project.

Without the Devpost write-up, you can't submit. A brilliant demo with a missing Devpost is disqualified.

Without a polished demo video, judges watching asynchronously have nothing. The video is your backup pitch.

And in the live expo, the Hook is the most important 45 seconds of the presentation. Judges decide in the first minute whether they're interested. You own that minute.

---

## Pre-Hackathon Checklist

- [ ] Read PRD_v2.md sections 2 (Problem Statement) and 16 (Demo Narrative) — understand what PulsePoint does well enough to explain it to a non-technical judge
- [ ] Memorize the Hook (page 5 of this doc) — practice saying it out loud
- [ ] Download CapCut (mobile) or confirm iMovie is on your laptop
- [ ] Make a Devpost account: `devpost.com`
- [ ] Confirm you have a Google Maps account (for compiling EMS station locations)
- [ ] Install GitHub app on your phone so you can approve PRs from anywhere

---

## Task 1: ems_stations.json (Hours 0–4)

**This is your first and most time-sensitive task.** Praneel's counterfactual needs it. Start immediately.

You're building a JSON file listing the 36 NYC FDNY EMS stations. Each entry needs the station name, borough, address, and — most importantly — the latitude and longitude.

### Step 1 — Find All Stations

Open this URL: `https://www.nyc.gov/site/fdny/units/ems/ems-units.page`

You'll see a list of EMS battalions and stations. Note down every station you see. There should be approximately 36 total.

### Step 2 — Get Lat/Lon for Each Station

For each station:

1. Copy the station address
2. Go to Google Maps: `maps.google.com`
3. Search the address
4. Right-click on the pin → click the lat/lon numbers at the top
5. They're copied to clipboard as `lat,lon` (e.g., `40.7128,-74.0060`)
6. Note: lat comes first in Google Maps, but in the JSON file lon comes first for GeoJSON convention

### Step 3 — Build the JSON

Create the file `data/ems_stations.json`. Each station follows this format:

```json
[
  {
    "station_id": "EMS_M01",
    "name": "EMS Station 1",
    "borough": "MANHATTAN",
    "address": "100 Beekman Street, New York, NY",
    "lat": 40.7128,
    "lon": -74.006,
    "dispatch_zone": "M1"
  },
  {
    "station_id": "EMS_M02",
    "name": "EMS Station 2",
    "borough": "MANHATTAN",
    "address": "...",
    "lat": 40.7234,
    "lon": -73.9988,
    "dispatch_zone": "M2"
  }
]
```

**Dispatch zone assignment:** Use the zone map below to assign each station to its closest dispatch zone.

| Station borough prefix | Dispatch zones |
| ---------------------- | -------------- |
| Manhattan stations     | M1–M9          |
| Bronx stations         | B1–B5          |
| Brooklyn stations      | K1–K7          |
| Queens stations        | Q1–Q7          |
| Staten Island stations | S1–S3          |

For the dispatch zone, pick the zone whose centroid is closest to the station address (just eyeball it on Google Maps). It doesn't have to be perfect — just in the right borough.

### Step 4 — Commit the File

```bash
# You don't need to use git from the command line.
# Go to github.com/yourteam/pulsepoint
# Navigate to data/
# Click "Add file" → "Create new file"
# Name it: ems_stations.json
# Paste your JSON
# Commit directly to feat/pipeline branch (NOT main)
# Write commit message: "data: ems_stations.json — 36 FDNY EMS stations, closes #27"
```

**Tell Praneel in group chat:** `ems_stations.json committed to feat/pipeline. 36 stations. Please copy to DBFS.`

Praneel then runs in Databricks:

```python
dbutils.fs.cp("file:/path/to/ems_stations.json", "dbfs:/pulsepoint/data/ems_stations.json")
```

### If You Can't Find All 36 Stations

Use this starter list and fill in the rest:

- Station 1 — 100 Beekman St, Manhattan → M1
- Station 2 — 4 Gouverneur Slip, Manhattan → M1
- Station 4 — 429 East 26th St, Manhattan → M4
- Station 7 — 340 East 125th St, Manhattan → M7
- Station 17 — 1718 2nd Ave, Manhattan → M6
- Station 18 — 84 Thayer St, Manhattan → M9
- Station 26 — 159 Lenox Ave, Manhattan → M7
- Station 26B — 35 W 132nd St, Manhattan → M7
- Station 35 — 1855 Westchester Ave, Bronx → B3
- Station 41 — 5308 Broadway, Bronx → B5
- Station 43 — 1901 Mapes Ave, Bronx → B2
- Station 47 — 801 Intervale Ave, Bronx → B1
- Station 49 — 4424 White Plains Rd, Bronx → B4
- Station 50 — 344 E 149th St, Bronx → B1
- Station 53 — 456 Vanderbilt Ave, Brooklyn → K7
- Station 57 — 85 Snyder Ave, Brooklyn → K2
- Station 58 — 1369 Atlantic Ave, Brooklyn → K5
- Station 63 — 770 E 98th St, Brooklyn → K4
- Station 70 — 1399 Flatbush Ave, Brooklyn → K6
- Station 75 — 406 Hendrix St, Brooklyn → K4
- Station 44 — 46-01 Queenboro Bridge, Queens → Q6
- Station 45 — 87-91 Francis Lewis Blvd, Queens → Q5
- Station 46 — 148-01 Hillside Ave, Queens → Q1
- Station 49Q — 182-24 Horace Harding Exp, Queens → Q2
- Station 52 — 68-00 136th St, Queens → Q3
- Station 54 — 58-02 101st St, Queens → Q4
- Station 55 — 4238 Main St, Queens → Q2
- Station 61 — 45 Bay St, Staten Island → S1
- Station 62 — 1725 Richmond Ave, Staten Island → S2
- Station 67 — 2475 Richmond Ave, Staten Island → S2

Fill in the missing ones from the FDNY website. Get as close to 36 as you can — 28+ is sufficient for the model to work.

---

## Task 2: GitHub PR Approvals (Ongoing)

You are set as a required reviewer for all PRs to `main`. You'll get email/phone notifications when a PR is opened.

**Your job:** Review that the PR description is filled out (not blank), it has the right label, and it closes an issue. Then approve it.

You do not need to read the code. You're the process gate, not the code reviewer.

**How to approve a PR:**

1. Open GitHub on your phone or laptop
2. Go to Pull Requests tab
3. Click the PR
4. Click "Review changes" → "Approve" → "Submit review"
5. If the PR description is empty or missing the issue number, comment: "Please add which issue this closes" before approving

**Response time target:** Approve PRs within 10 minutes of them being opened. Delays in PR approval delay the merge which delays the integration.

---

## Task 3: Issue Board Tracking (Every 4 Hours)

Every 4 hours, open GitHub Issues and do a board check. Post this update in the group chat:

```
BOARD UPDATE (Hour 12):
✓ Closed: #19 (Notebook 01), #20 (weather merge), #11 (mock endpoints)
⏳ In progress: #21 (SVI join), #13 (artifact loading), #3 (choropleth)
⚠️  Blocked: #14 (waiting on demand_model.pkl from Praneel)
📋 Not started: #22, #23, #24...

Next milestone: demand_model.pkl expected at Hour ~10
```

This replaces the need for team standup meetings — everyone reads the update and moves on.

---

## Task 4: Devpost Write-Up (Hours 3–12, finalize Hours 26–30)

### When to Work on This

- Start drafting during Hours 3–12 when the coders are heads-down and don't need you
- Fill in real numbers when Praneel posts counterfactual results at Hour ~20
- Final polish and publish at Hour 28–30

### Where to Create It

Go to `devpost.com` → your account → "Start a project"

Fill in:

- Project name: **PulsePoint**
- Tagline: **We predict where the next 911 call will happen — before it happens.**
- Cover image: a screenshot of the dashboard (get from Vaibhav around Hour 24)
- Team members: add Vaibhav, Ashwin, Praneel
- Tracks: select **Healthcare** AND **SafetyKit: Best AI for Human Safety**
- GitHub URL: your repo URL
- Demo video: YouTube URL (add when ready)

### Full Write-Up Template

Copy this into the Devpost text editor. Replace all `[BRACKETS]` with real values.

---

**Inspiration**

In New York City, roughly 1 in 3 Priority 1 and 2 EMS calls doesn't meet the 8-minute response standard that doctors link to cardiac arrest survival. The Bronx — the most socially vulnerable borough by CDC Social Vulnerability Index — averages 638 seconds of response time, already 33% above that threshold on average. The problem isn't insufficient ambulances. It's that static station deployment leaves units in the wrong place during peak demand windows. We built PulsePoint to fix that.

---

**What It Does**

PulsePoint is a predictive ambulance staging dashboard for EMS dispatchers. It analyzes 28.7 million validated NYC EMS incidents alongside weather data and time-of-day demand patterns to forecast where emergency calls will concentrate — then recommends optimal staging locations for idle ambulances before those calls arrive.

The dispatcher-facing dashboard features:

- A real-time demand heatmap by NYC EMS dispatch zone, color-coded from teal (low demand) to red (critical)
- A time-of-day slider that updates staging recommendations dynamically for any hour of the week
- [K] ambulance staging pins with 8-minute drive coverage circles using real NYC road network routing
- A counterfactual impact panel showing the improvement from static stations to PulsePoint staging
- Borough and social vulnerability breakdown showing where the biggest gains occur

---

**How We Built It**

_Data:_ 28.7 million validated NYC EMS incidents (2005–2024) from NYC Open Data, filtered to [X] million rows for our training window. We confirmed a 96.2% response time validity rate — unusually high for a public dataset. We joined these with Open-Meteo historical hourly weather and CDC Social Vulnerability Index scores at the dispatch zone level. Our entire pipeline ran on Databricks with MLflow experiment tracking.

_Machine Learning:_ XGBoost demand forecaster trained on temporal features (hour, day of week, month — all cyclically encoded to prevent discontinuities), weather features (temperature, precipitation, windspeed, severe weather flag), and zone-level structural features (SVI score, historical high-acuity ratio, rolling incident baseline). Test RMSE on our 2023 holdout: **[X] incidents per zone per hour**.

_Optimization:_ Weighted K-Means spatial clustering where each NYC dispatch zone is weighted by its predicted demand, with cluster centroids snapped to real OpenStreetMap road network nodes.

_Counterfactual:_ We simulated [X] historical Priority 1 and 2 incidents from our 2023 holdout, comparing drive times from the nearest fixed FDNY station vs. the nearest PulsePoint staging location using actual NYC road network shortest-path distances.

_Stack:_ Python, FastAPI, XGBoost, scikit-learn, OSMnx, geopandas, PostGIS, React 18, Mapbox GL JS, Plotly.js, Databricks, Delta Lake, MLflow.

---

**Challenges We Ran Into**

The NYC EMS dataset contains 28.7 million rows spanning 20 years — data cleaning and pre-computation of the road network drive-time matrix had to be done before the hackathon to stay within the 36-hour window. Dispatch zone codes occasionally appear with mismatched boroughs due to CAD system entry errors; we built a validation step to isolate the 31 clean zones. The year 2020 showed a ~100k drop in volume from COVID-19 lockdown suppressing non-emergency calls, which we excluded from training to prevent the model learning a false seasonal dip.

---

**Accomplishments We're Proud Of**

Using the full 28.7M row dataset rather than a sample — the scale is what makes temporal predictions credible. The response time decomposition: NYC's dataset uniquely provides dispatch delay vs. travel time separately, letting us prove we target the right component (travel time, the piece addressable by staging). The equity finding: highest-SVI neighborhoods see the largest absolute improvement, meaning PulsePoint closes the coverage gap in the communities that need it most.

---

**What We Learned**

[Fill this in during the last 2 hours — be honest. Judges value authentic reflection. Examples: what surprised you about the data, what was harder than expected, what you'd do differently.]

---

**What's Next**

Integration with real-time CAD feeds for live deployment. Traffic API data for more accurate peak-hour drive times. A formal clinical validation study. Generalizing the pipeline to other cities (Austin, Chicago, Los Angeles all have comparable open EMS datasets).

---

**Human Safety Impact** _(SafetyKit Track)_

PulsePoint addresses a concrete, data-validated human safety gap: emergency medical response time inequity. Using 28.7 million validated NYC EMS incidents, we confirmed that the Bronx experiences average EMS response times of 638 seconds — 33% above the clinical 8-minute threshold linked to cardiac arrest survival. Every minute of delay beyond 4 minutes reduces cardiac arrest survival probability by approximately 10%. Our predictive staging system reduces median response time by [X] minutes [Y] seconds in high-need neighborhoods. The AI gives dispatchers a tool that anticipates where crises will occur before the 911 call arrives, enabling faster and more equitable emergency response for the people who need it most.

---

**Built With:**
`python` `fastapi` `xgboost` `scikit-learn` `osmnx` `geopandas` `postgis` `react` `mapbox-gl` `plotly` `databricks` `mlflow` `delta-lake` `nyc-open-data` `open-meteo`

---

### Numbers to Fill In (get from Praneel at Hour ~20)

| Placeholder                                  | Where to get it                  | Example      |
| -------------------------------------------- | -------------------------------- | ------------ |
| `[X] million rows` for training              | Praneel's Notebook 01 output     | 5.6 million  |
| RMSE `[X] incidents per zone per hour`       | Praneel's Notebook 05 output     | 3.8          |
| `[X] historical incidents` in counterfactual | Praneel's Notebook 08 output     | 4,200        |
| `[X]% → [Y]%` within 8 min                   | Praneel's counterfactual results | 61% → 84%    |
| `[X] min [Y] sec` median saved               | Praneel's counterfactual results | 2 min 27 sec |

---

## Task 5: 2-Minute Demo Video (Hours 26–30)

### Your Role

Vaibhav drives the screen and narrates. You record and edit.

### Recording (Hour 26–27)

- Use QuickTime on Mac: File → New Screen Recording → record Vaibhav's screen
- Or use your phone camera pointing at his laptop screen (works fine at 1080p)
- Record at least 3 takes of the 2:25–1:30 dashboard walkthrough segment
- Keep the best take

### Editing (Hours 27–29)

Use CapCut (free, mobile or desktop) or iMovie.

**Video structure:**

```
0:00–0:15  TITLE CARD
  Text: "The Bronx | Avg EMS Response: 10.6 min | Clinical Target: 8 min"
  Background: dark, simple
  Music: low ambient (CapCut has built-in free tracks)

0:15–0:25  ONE-LINE PITCH (text overlay while showing Monday 4AM map)
  Text: "PulsePoint uses 28 million EMS incidents to predict where
         the next emergency will happen — before the 911 call comes in."

0:25–1:30  DASHBOARD WALKTHROUGH (Vaibhav's screen recording)
  Keep his narration audio
  Add a subtle zoom-in when he shows the impact panel numbers

1:30–1:50  IMPACT CARD
  Text: "[X]% → [Y]% of calls within 8 minutes"
  Text: "[Z] min [W] sec median response time saved"
  Text: "Largest gains in highest-risk neighborhoods"
  Fade these in one by one

1:50–2:00  CLOSE
  Text: "PulsePoint"
  Text: "GT Hacklytics 2026 | Healthcare Track | SafetyKit Track"
  Team names optional
```

### Upload + Submit

1. Export from CapCut/iMovie as MP4 at 1080p
2. Upload to YouTube: `studio.youtube.com` → Upload → set to **Public**
3. Wait for YouTube to finish processing (5–10 min)
4. Copy the URL and paste into Devpost

---

## Task 6: The Live Pitch — Your Segment (Hours 30–34)

You present the Hook (first 45 seconds). This is the most important part of the 5-minute pitch.

### Your Script (memorize this word for word)

> "If you go into cardiac arrest right now, your survival probability drops by roughly 10% for every minute EMS takes to reach you. In the Bronx — the most socially vulnerable borough in New York — the average EMS response time is 10 and a half minutes. The clinical target is 8. That gap isn't because there aren't enough ambulances. It's because they're in the wrong place. PulsePoint fixes that."

### Delivery Notes

- Speak slowly. You will naturally want to rush. Don't.
- Make eye contact with judges, not your teammates
- "10 and a half minutes" should land heavily — pause after it
- "PulsePoint fixes that" is your handoff to Ansh — say it, then step back

### Practice Schedule

- Hour 30: First full run-through with the whole team, timer running
- Hour 32: Second run-through, fix anything that felt awkward
- Hour 33: Final run-through — this time don't stop even if someone messes up

### Q&A Role

You don't answer technical questions — that's Vaibhav, Ashwin, or Praneel. Your job during Q&A is to watch for judges who look confused and redirect the question to the right teammate.

---

## Task 7: Final Submission Checklist

Own this list. Nothing gets submitted until you personally verify each item.

**Due by 8:30 AM Sunday (30 min buffer before 9 AM deadline):**

- [ ] GitHub repo is **public** — go to repo → Settings → verify "Public" status
- [ ] GitHub repo has a README — Vaibhav writes it, you verify it's there
- [ ] Devpost is **Published** (not draft) — the Publish button has been clicked
- [ ] Devpost has Healthcare track selected
- [ ] Devpost has SafetyKit track selected
- [ ] Demo video URL is pasted into Devpost
- [ ] GitHub repo URL is pasted into Devpost
- [ ] Demo video is **public** on YouTube — click the link from an incognito window and verify it plays without login
- [ ] Demo video is ≤ 2 minutes — check the video length
- [ ] All `[BRACKET]` placeholders have been replaced in the write-up
- [ ] Databricks raffle: Praneel's Loom link submitted to raffle form
- [ ] `git tag v1.0` has been pushed on main (ask Vaibhav to confirm)

Post in group chat when done: `SUBMISSION COMPLETE. All links verified. GitHub public. Video public. Devpost published.`

---

## Group Chat Rules

**Post these messages at these times:**

| When                             | Message                                                                                     |
| -------------------------------- | ------------------------------------------------------------------------------------------- |
| ems_stations.json committed      | `ems_stations.json committed (36 stations). Praneel: copy to DBFS.`                         |
| Every 4 hours                    | Board update with open/closed/blocked issues                                                |
| PR opened (you get notification) | Approve within 10 minutes, post `PR #XX approved and merged`                                |
| Counterfactual numbers in        | `Real numbers from Praneel: [X]%→[Y]% within 8min, [Z]sec saved. Filling into Devpost now.` |
| Video uploaded                   | `Demo video uploaded: [YouTube URL]. Vaibhav: check it looks right.`                        |
| Final submission                 | `SUBMITTED. All links live. Go sleep.`                                                      |

---

## Your Hour-by-Hour Summary

| Hour    | Task                                                       |
| ------- | ---------------------------------------------------------- |
| 0–1     | GitHub setup help (Vaibhav leads, you assist)              |
| 0–4     | ems_stations.json: 36 FDNY stations with lat/lon           |
| 3–8     | Devpost draft: all sections written with placeholders      |
| 4–30    | GitHub PR approvals: approve within 10 min of notification |
| 4–30    | Issue board updates every 4 hours in group chat            |
| ~20     | Get real numbers from Praneel, fill into Devpost           |
| 24–26   | Get dashboard screenshot from Vaibhav, add to Devpost      |
| 26–27   | Record demo video (3 takes of walkthrough)                 |
| 27–29   | Edit demo video in CapCut/iMovie                           |
| 29–30   | Upload to YouTube (public), paste URL into Devpost         |
| 30–34   | Pitch rehearsal (3 runs), submission checklist             |
| 8:30 AM | Verify all submission links are public and working         |
