import { describe, it, expect } from 'vitest';
import {
  VALID_ZONES, ZONE_NAMES, ZONE_CENTROIDS, ZONE_SVI,
  ZONE_BOROUGH, DEMO_SCENARIOS, WEATHER_PRESETS, DOW_LABELS,
} from '../constants';

describe('VALID_ZONES', () => {
  it('has exactly 31 zones', () => {
    expect(VALID_ZONES.length).toBe(31);
  });

  it('has correct borough zone counts', () => {
    const bronx = VALID_ZONES.filter(z => z.startsWith('B'));
    const brooklyn = VALID_ZONES.filter(z => z.startsWith('K'));
    const manhattan = VALID_ZONES.filter(z => z.startsWith('M'));
    const queens = VALID_ZONES.filter(z => z.startsWith('Q'));
    const statenIsland = VALID_ZONES.filter(z => z.startsWith('S'));
    expect(bronx.length).toBe(5);
    expect(brooklyn.length).toBe(7);
    expect(manhattan.length).toBe(9);
    expect(queens.length).toBe(7);
    expect(statenIsland.length).toBe(3);
  });

  it('contains no duplicates', () => {
    const unique = new Set(VALID_ZONES);
    expect(unique.size).toBe(VALID_ZONES.length);
  });
});

describe('ZONE_NAMES', () => {
  it('has an entry for every valid zone', () => {
    VALID_ZONES.forEach(z => {
      expect(ZONE_NAMES[z]).toBeDefined();
      expect(typeof ZONE_NAMES[z]).toBe('string');
    });
  });
});

describe('ZONE_CENTROIDS', () => {
  it('has an entry for every valid zone', () => {
    VALID_ZONES.forEach(z => {
      expect(ZONE_CENTROIDS[z]).toBeDefined();
      expect(ZONE_CENTROIDS[z].length).toBe(2);
    });
  });

  it('all coordinates are in NYC bounding box', () => {
    Object.entries(ZONE_CENTROIDS).forEach(([zone, [lng, lat]]) => {
      expect(lng).toBeGreaterThan(-74.3);
      expect(lng).toBeLessThan(-73.7);
      expect(lat).toBeGreaterThan(40.49);
      expect(lat).toBeLessThan(40.95);
    });
  });

  it('uses [longitude, latitude] order (GeoJSON convention)', () => {
    // All NYC longitudes are negative, latitudes are positive ~40
    Object.values(ZONE_CENTROIDS).forEach(([lng, lat]) => {
      expect(lng).toBeLessThan(0);
      expect(lat).toBeGreaterThan(0);
    });
  });
});

describe('ZONE_SVI', () => {
  it('has an entry for every valid zone', () => {
    VALID_ZONES.forEach(z => {
      expect(ZONE_SVI[z]).toBeDefined();
    });
  });

  it('all SVI scores are between 0 and 1', () => {
    Object.values(ZONE_SVI).forEach(v => {
      expect(v).toBeGreaterThanOrEqual(0);
      expect(v).toBeLessThanOrEqual(1);
    });
  });

  it('Bronx zones have higher SVI than Manhattan midtown', () => {
    expect(ZONE_SVI['B1']).toBeGreaterThan(ZONE_SVI['M3']);
  });
});

describe('ZONE_BOROUGH', () => {
  it('maps every valid zone to a borough', () => {
    VALID_ZONES.forEach(z => {
      expect(ZONE_BOROUGH[z]).toBeDefined();
    });
  });

  it('uses exact borough strings from API contract', () => {
    const boroughs = new Set(Object.values(ZONE_BOROUGH));
    expect(boroughs.has('BRONX')).toBe(true);
    expect(boroughs.has('BROOKLYN')).toBe(true);
    expect(boroughs.has('MANHATTAN')).toBe(true);
    expect(boroughs.has('QUEENS')).toBe(true);
    expect(boroughs.has('RICHMOND / STATEN ISLAND')).toBe(true);
  });

  it('S zones map to RICHMOND / STATEN ISLAND (with slash)', () => {
    expect(ZONE_BOROUGH['S1']).toBe('RICHMOND / STATEN ISLAND');
    expect(ZONE_BOROUGH['S2']).toBe('RICHMOND / STATEN ISLAND');
    expect(ZONE_BOROUGH['S3']).toBe('RICHMOND / STATEN ISLAND');
  });
});

describe('DEMO_SCENARIOS', () => {
  it('has friday_peak, monday_quiet, and storm', () => {
    expect(DEMO_SCENARIOS.friday_peak).toBeDefined();
    expect(DEMO_SCENARIOS.monday_quiet).toBeDefined();
    expect(DEMO_SCENARIOS.storm).toBeDefined();
  });

  it('friday_peak is hour 20 dow 4', () => {
    expect(DEMO_SCENARIOS.friday_peak.hour).toBe(20);
    expect(DEMO_SCENARIOS.friday_peak.dow).toBe(4);
  });

  it('monday_quiet is hour 4 dow 0', () => {
    expect(DEMO_SCENARIOS.monday_quiet.hour).toBe(4);
    expect(DEMO_SCENARIOS.monday_quiet.dow).toBe(0);
  });

  it('storm has high precipitation and windspeed', () => {
    expect(DEMO_SCENARIOS.storm.precipitation).toBeGreaterThan(5);
    expect(DEMO_SCENARIOS.storm.windspeed).toBeGreaterThan(20);
  });

  it('all scenarios have valid hour (0-23) and dow (0-6)', () => {
    Object.values(DEMO_SCENARIOS).forEach(s => {
      expect(s.hour).toBeGreaterThanOrEqual(0);
      expect(s.hour).toBeLessThanOrEqual(23);
      expect(s.dow).toBeGreaterThanOrEqual(0);
      expect(s.dow).toBeLessThanOrEqual(6);
    });
  });
});

describe('WEATHER_PRESETS', () => {
  it('has none, light, and heavy', () => {
    expect(WEATHER_PRESETS.none).toBeDefined();
    expect(WEATHER_PRESETS.light).toBeDefined();
    expect(WEATHER_PRESETS.heavy).toBeDefined();
  });

  it('none has zero precipitation', () => {
    expect(WEATHER_PRESETS.none.precipitation).toBe(0);
  });

  it('heavy has highest precipitation', () => {
    expect(WEATHER_PRESETS.heavy.precipitation).toBeGreaterThan(WEATHER_PRESETS.light.precipitation);
  });

  it('each preset has label, temperature, precipitation, windspeed', () => {
    Object.values(WEATHER_PRESETS).forEach(p => {
      expect(p.label).toBeDefined();
      expect(typeof p.temperature).toBe('number');
      expect(typeof p.precipitation).toBe('number');
      expect(typeof p.windspeed).toBe('number');
    });
  });
});

describe('DOW_LABELS', () => {
  it('has 7 labels', () => {
    expect(DOW_LABELS.length).toBe(7);
  });

  it('starts with Mon and ends with Sun', () => {
    expect(DOW_LABELS[0]).toBe('Mon');
    expect(DOW_LABELS[6]).toBe('Sun');
  });
});
