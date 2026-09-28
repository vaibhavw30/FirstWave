import { describe, it, expect } from 'vitest';
import { dowFromDate, monthFromDate, isReplayDate } from '../replayDate';
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
