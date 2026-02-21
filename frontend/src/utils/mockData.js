import mockResponses from '../../../data/mock_api_responses.json';

export function getMockHeatmap() {
  return mockResponses.heatmap;
}

export function getMockStaging() {
  return mockResponses.staging;
}

export function getMockCounterfactual() {
  return mockResponses.counterfactual;
}

export function getMockHistorical(zone) {
  // The JSON has a single historical_zone entry (B2 as reference)
  // For any zone, return that data with the zone code swapped
  const base = mockResponses.historical_zone;
  if (!zone) return base;

  // Try to find matching zone data from heatmap features for zone-specific props
  const feature = mockResponses.heatmap.features.find(f => f.properties.zone === zone);
  if (!feature) return base;

  const p = feature.properties;
  return {
    ...base,
    zone: p.zone,
    borough: p.borough,
    zone_name: p.zone_name,
    svi_score: p.svi_score,
    historical_avg_response_sec: undefined,
    avg_response_seconds: p.historical_avg_response_sec,
    avg_travel_seconds: Math.round(p.historical_avg_response_sec * 0.62),
    avg_dispatch_seconds: Math.round(p.historical_avg_response_sec * 0.38),
    high_acuity_ratio: p.high_acuity_ratio,
    held_ratio: parseFloat((0.04 + p.svi_score * 0.06).toFixed(2)),
    // Scale hourly_avg by zone's SVI relative to B2's (0.89)
    hourly_avg: base.hourly_avg.map(v => parseFloat((v * (p.svi_score / 0.89)).toFixed(1))),
  };
}

export function getMockBreakdown() {
  return mockResponses.breakdown;
}
