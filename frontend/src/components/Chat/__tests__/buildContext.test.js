import { describe, it, expect } from 'vitest';
import { buildContext } from '../AiPanel';

describe('buildContext', () => {
  it('derives the day of week from the replay date', () => {
    const ctx = buildContext(null, null, { date: '2025-10-10', hour: 20, weather: 'actual', ambulances: 5 });
    expect(ctx).toMatchObject({ hour: 20, dow: 4, date: '2025-10-10', weather: 'actual', ambulances: 5 });
  });
});

describe('buildContext coverage', () => {
  const controls = { date: '2025-10-10', hour: 20, weather: 'actual', ambulances: 5 };

  it('passes the mean seconds saved alongside the median', () => {
    const cf = { pct_within_8min_static: 56.7, pct_within_8min_staged: 66.8, median_seconds_saved: 0, mean_seconds_saved: 98.1 };
    expect(buildContext(null, cf, controls).coverage).toEqual({
      pct_static: 56.7, pct_staged: 66.8, median_saved_sec: 0, mean_saved_sec: 98.1,
    });
  });

  it('omits the mean when the API does not provide it (mock data)', () => {
    const cf = { pct_within_8min_static: 61.2, pct_within_8min_staged: 83.7, median_seconds_saved: 147 };
    expect(buildContext(null, cf, controls).coverage).not.toHaveProperty('mean_saved_sec');
  });
});
