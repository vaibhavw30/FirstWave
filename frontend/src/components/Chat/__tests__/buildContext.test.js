import { describe, it, expect } from 'vitest';
import { buildContext } from '../AiPanel';

describe('buildContext', () => {
  it('derives the day of week from the replay date', () => {
    const ctx = buildContext(null, null, { date: '2025-10-10', hour: 20, weather: 'actual', ambulances: 5 });
    expect(ctx).toMatchObject({ hour: 20, dow: 4, date: '2025-10-10', weather: 'actual', ambulances: 5 });
  });
});
