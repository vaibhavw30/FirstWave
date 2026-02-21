# DemandHeatmap — Integration Guide

# FirstWave | GT Hacklytics 2026

## What this file does

Replaces the rectangular zone boxes with two stacked Mapbox layers:

```
Layer order (bottom → top):
  1. ZIP fill layer   — real NYC ZIP polygon shapes, colored by zone demand
                        fades IN  at zoom > 10
  2. Heatmap layer    — smooth continuous gradient from zone centroids
                        fades OUT at zoom > 13

Result: smooth blur at city view, real neighborhood shapes when zoomed in.
```

No fake precision — ZIPs inside the same dispatch zone share the same color
value. The gain is geographic shape accuracy, not prediction resolution.

## Drop-in integration (MapContainer.jsx)

```jsx
// 1. Import
import { DemandHeatmap } from "./map/DemandHeatmap";

// 2. In your MapContainer component, wherever mapRef and predictions exist:
const [showZipOverlay, setShowZipOverlay] = useState(true);

// 3. After <Map ref={mapRef} ...> add:
<DemandHeatmap
  mapRef={mapRef}
  predictions={predictions}      // [{ zone: "B2", predicted: 8.4 }, ...]
  showZipOverlay={showZipOverlay}
/>

// 4. Optional toggle button in sidebar:
<button onClick={() => setShowZipOverlay(v => !v)}>
  {showZipOverlay ? "Hide ZIP borders" : "Show ZIP borders"}
</button>
```

The component returns null — it has no DOM output. It only manages map layers.
predictions can update freely (React Query refetch) and the component will
call setData() without re-adding layers, so there's no flicker.

## What predictions should look like

```js
// From /api/predict or your mock data
const predictions = [
  { zone: "B1", predicted: 6.2 },
  { zone: "B2", predicted: 8.4 },
  { zone: "B3", predicted: 7.1 },
  // ...all 31 zones
];
```

If a zone is missing from predictions, its ZIPs and centroid default to 0
(rendered as transparent). No crash.

## Removing the old rectangular boxes

In your existing MapContainer or wherever you currently add the zone fill layer:

```js
// DELETE or comment out anything like:
map.addLayer({
  id: "zone-fills",
  type: "fill",
  source: "zones",
  ...
});

// DemandHeatmap replaces this entirely.
```

## GeoJSON source fallback behavior

The ZIP GeoJSON (~500KB) is fetched once from NYC Open Data and module-cached.
If the fetch fails (bad hackathon wifi):

- ZIP layer silently doesn't render
- Heatmap layer still renders (no network dependency)
- No error thrown, no broken UI

Two fallback URLs are tried in order. If both fail, you just get the heatmap.

## Color ramp reference

| Weight | Color       | Meaning             |
| ------ | ----------- | ------------------- |
| 0.0    | transparent | No predicted demand |
| 0.1    | Deep blue   | Minimal demand      |
| 0.3    | Medium blue | Below average       |
| 0.5    | Cyan        | Average demand      |
| 0.7    | Yellow      | Above average       |
| 0.9    | Orange      | High demand         |
| 1.0    | Red         | Peak demand         |

Colors match FirstWave's blue → alert palette from the pitch deck.
The same ramp is applied to both the heatmap and ZIP fill layer for consistency.

## Zoom behavior

| Zoom level | What you see                          |
| ---------- | ------------------------------------- |
| 0–9        | Pure smooth heatmap, no ZIP borders   |
| 10–12      | Heatmap fading, ZIP shapes fading in  |
| 13+        | ZIP choropleth fully visible, no blur |

This gives the "wow" continuous look at the city overview the judges see first,
and real neighborhood precision when they zoom into the Bronx.

## Files touched

- frontend/src/components/map/DemandHeatmap.jsx ← NEW (this file)
- frontend/src/components/map/MapContainer.jsx ← ADD 4 lines (see above)
- No backend changes required
- No pipeline changes required

## Notes for Vaibhav

The ZONE_TO_ZIPS mapping is approximate — built from DOHMH UHF crosswalk + FDNY
zone shapefiles. Some ZIPs on zone boundaries may be assigned to the slightly
wrong zone. This is fine for a hackathon and visually undetectable. If a judge
asks, the honest answer is "we use dispatch zone predictions, ZIP shapes are
for visualization only."
