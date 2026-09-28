import { describe, it, expect } from 'vitest';
import { buildQueryParams } from '../queryParams';

describe('buildQueryParams', () => {
  it('derives dow and month from the date and expands weather', () => {
    expect(buildQueryParams({ date: '2025-10-10', hour: 20, weather: 'heavy', ambulances: 7 })).toEqual({
      date: '2025-10-10', hour: 20, dow: 4, month: 10,
      temperature: 8, precipitation: 8, windspeed: 30, ambulances: 7,
    });
  });

  it('omits weather for the actual preset so the API replays the real hour', () => {
    expect(buildQueryParams({ date: '2025-07-30', hour: 18, weather: 'actual', ambulances: 7 })).toEqual({
      date: '2025-07-30', hour: 18, dow: 2, month: 7, ambulances: 7,
    });
  });

  it('falls back to clear weather for unknown presets', () => {
    expect(buildQueryParams({ date: '2025-10-20', hour: 4, weather: 'bogus', ambulances: 5 }).precipitation).toBe(0);
  });
});
