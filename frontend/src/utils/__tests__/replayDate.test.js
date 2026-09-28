import { describe, it, expect } from 'vitest';
import { dowFromDate, monthFromDate, isReplayDate, dateWithDow, applyAiControls } from '../replayDate';
import { DEMO_SCENARIOS } from '../../constants';

describe('replayDate', () => {
  it('maps dates to Mon=0 weekdays without timezone drift', () => {
    expect(dowFromDate('2025-10-10')).toBe(4);
    expect(dowFromDate('2025-10-20')).toBe(0);
    expect(dowFromDate('2025-10-12')).toBe(6);
    expect(dowFromDate('2025-01-01')).toBe(2);
  });

  it('extracts the month', () => {
    expect(monthFromDate('2025-07-30')).toBe(7);
  });

  it('accepts only in-range ISO dates', () => {
    expect(isReplayDate('2025-01-01')).toBe(true);
    expect(isReplayDate('2026-06-30')).toBe(true);
    expect(isReplayDate('2024-12-31')).toBe(false);
    expect(isReplayDate('2026-07-01')).toBe(false);
    expect(isReplayDate('')).toBe(false);
  });

  it('demo presets fall on the weekdays their names promise', () => {
    expect(dowFromDate(DEMO_SCENARIOS.friday_peak.date)).toBe(4);
    expect(dowFromDate(DEMO_SCENARIOS.monday_quiet.date)).toBe(0);
    expect(dowFromDate(DEMO_SCENARIOS.storm.date)).toBe(2);
  });
});

describe('dateWithDow', () => {
  it('moves the date to the requested weekday in the same Mon–Sun week', () => {
    expect(dateWithDow('2025-10-10', 0)).toBe('2025-10-06');
    expect(dateWithDow('2025-10-10', 4)).toBe('2025-10-10');
    expect(dateWithDow('2025-10-10', 6)).toBe('2025-10-12');
  });

  it('stays inside the replay window at its edges', () => {
    expect(dateWithDow('2025-01-01', 0)).toBe('2025-01-06');
    expect(dateWithDow('2026-06-30', 6)).toBe('2026-06-28');
  });
});

describe('applyAiControls', () => {
  const prev = { date: '2025-10-10', hour: 20, weather: 'actual', ambulances: 5 };

  it('turns an AI day-of-week into a replay date and drops dow', () => {
    expect(applyAiControls(prev, { hour: 4, dow: 0 })).toEqual({
      date: '2025-10-06', hour: 4, weather: 'actual', ambulances: 5,
    });
  });

  it('keeps the date when the AI only changes the hour', () => {
    expect(applyAiControls(prev, { hour: 8 })).toEqual({ ...prev, hour: 8 });
  });

  it('restores a full controls snapshot unchanged (undo)', () => {
    const snap = { date: '2025-07-30', hour: 18, weather: 'actual', ambulances: 7 };
    expect(applyAiControls(prev, snap)).toEqual(snap);
  });
});
