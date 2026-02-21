import { describe, it, expect } from 'vitest';
import { getMockHeatmap, getMockStaging, getMockCounterfactual, getMockHistorical, getMockBreakdown } from '../mockData';

describe('getMockHeatmap', () => {
  it('returns a GeoJSON FeatureCollection', () => {
    const data = getMockHeatmap();
    expect(data.type).toBe('FeatureCollection');
    expect(data.features).toBeDefined();
    expect(Array.isArray(data.features)).toBe(true);
  });

  it('has features with required properties', () => {
    const data = getMockHeatmap();
    const feature = data.features[0];
    expect(feature.type).toBe('Feature');
    expect(feature.properties.zone).toBeDefined();
    expect(feature.properties.borough).toBeDefined();
    expect(feature.properties.zone_name).toBeDefined();
    expect(feature.properties.predicted_count).toBeDefined();
    expect(feature.properties.normalized_intensity).toBeDefined();
    expect(feature.properties.svi_score).toBeDefined();
    expect(feature.properties.historical_avg_response_sec).toBeDefined();
    expect(feature.properties.high_acuity_ratio).toBeDefined();
  });

  it('has MultiPolygon geometries', () => {
    const data = getMockHeatmap();
    data.features.forEach((f) => {
      expect(f.geometry.type).toBe('MultiPolygon');
      expect(f.geometry.coordinates).toBeDefined();
    });
  });

  it('contains all 31 zones', () => {
    const data = getMockHeatmap();
    expect(data.features.length).toBe(31);
  });

  it('has normalized_intensity between 0 and 1', () => {
    const data = getMockHeatmap();
    data.features.forEach((f) => {
      expect(f.properties.normalized_intensity).toBeGreaterThanOrEqual(0);
      expect(f.properties.normalized_intensity).toBeLessThanOrEqual(1);
    });
  });
});

describe('getMockStaging', () => {
  it('returns a GeoJSON FeatureCollection', () => {
    const data = getMockStaging();
    expect(data.type).toBe('FeatureCollection');
    expect(Array.isArray(data.features)).toBe(true);
  });

  it('has Point geometries with [lng, lat]', () => {
    const data = getMockStaging();
    data.features.forEach((f) => {
      expect(f.geometry.type).toBe('Point');
      const [lng, lat] = f.geometry.coordinates;
      // NYC bounding box check
      expect(lng).toBeGreaterThan(-74.3);
      expect(lng).toBeLessThan(-73.7);
      expect(lat).toBeGreaterThan(40.4);
      expect(lat).toBeLessThan(40.95);
    });
  });

  it('has staging properties', () => {
    const data = getMockStaging();
    data.features.forEach((f) => {
      expect(f.properties.staging_index).toBeDefined();
      expect(f.properties.coverage_radius_m).toBeDefined();
      expect(f.properties.predicted_demand_coverage).toBeDefined();
      expect(f.properties.cluster_zones).toBeDefined();
    });
  });
});

describe('getMockCounterfactual', () => {
  it('returns counterfactual data with required fields', () => {
    const data = getMockCounterfactual();
    expect(data.median_seconds_saved).toBeDefined();
    expect(data.pct_within_8min_static).toBeDefined();
    expect(data.pct_within_8min_staged).toBeDefined();
    expect(data.by_borough).toBeDefined();
    expect(data.by_svi_quartile).toBeDefined();
    expect(data.histogram_baseline_seconds).toBeDefined();
    expect(data.histogram_staged_seconds).toBeDefined();
  });

  it('has all 5 boroughs in by_borough', () => {
    const data = getMockCounterfactual();
    expect(data.by_borough.BRONX).toBeDefined();
    expect(data.by_borough.BROOKLYN).toBeDefined();
    expect(data.by_borough.MANHATTAN).toBeDefined();
    expect(data.by_borough.QUEENS).toBeDefined();
    expect(data.by_borough['RICHMOND / STATEN ISLAND']).toBeDefined();
  });

  it('has 4 SVI quartiles', () => {
    const data = getMockCounterfactual();
    expect(data.by_svi_quartile.Q1).toBeDefined();
    expect(data.by_svi_quartile.Q2).toBeDefined();
    expect(data.by_svi_quartile.Q3).toBeDefined();
    expect(data.by_svi_quartile.Q4).toBeDefined();
  });

  it('staged coverage > static coverage', () => {
    const data = getMockCounterfactual();
    expect(data.pct_within_8min_staged).toBeGreaterThan(data.pct_within_8min_static);
  });
});

describe('getMockHistorical', () => {
  it('returns base historical data when no zone', () => {
    const data = getMockHistorical();
    expect(data.zone).toBeDefined();
    expect(data.hourly_avg).toBeDefined();
    expect(data.hourly_avg.length).toBe(24);
  });

  it('adapts data for a specific zone', () => {
    const data = getMockHistorical('B1');
    expect(data.zone).toBe('B1');
    expect(data.borough).toBe('BRONX');
    expect(data.zone_name).toBe('South Bronx');
  });

  it('returns base data for unknown zone', () => {
    const data = getMockHistorical('XX');
    // Falls back to base since XX not in heatmap features
    expect(data.hourly_avg.length).toBe(24);
  });

  it('has exactly 24 hourly_avg values', () => {
    const data = getMockHistorical('M3');
    expect(data.hourly_avg.length).toBe(24);
  });
});

describe('getMockBreakdown', () => {
  it('returns an array of borough objects', () => {
    const data = getMockBreakdown();
    expect(Array.isArray(data)).toBe(true);
    expect(data.length).toBe(5);
  });

  it('has required fields for each borough', () => {
    const data = getMockBreakdown();
    data.forEach((b) => {
      expect(b.name).toBeDefined();
      expect(b.avg_dispatch_seconds).toBeDefined();
      expect(b.avg_travel_seconds).toBeDefined();
      expect(b.avg_total_seconds).toBeDefined();
      expect(b.pct_held).toBeDefined();
      expect(b.high_acuity_ratio).toBeDefined();
      expect(b.zones).toBeDefined();
    });
  });
});
