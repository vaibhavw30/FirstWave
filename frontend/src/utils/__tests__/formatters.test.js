import { describe, it, expect } from 'vitest';
import { formatSeconds, formatHour, formatPct } from '../formatters';

describe('formatSeconds', () => {
  it('formats 0 seconds', () => {
    expect(formatSeconds(0)).toBe('0 min 0 sec');
  });

  it('formats seconds under 60', () => {
    expect(formatSeconds(45)).toBe('0 min 45 sec');
  });

  it('formats exact minutes', () => {
    expect(formatSeconds(120)).toBe('2 min 0 sec');
  });

  it('formats minutes and seconds', () => {
    expect(formatSeconds(147)).toBe('2 min 27 sec');
  });

  it('formats large values (Bronx avg: 638 sec)', () => {
    expect(formatSeconds(638)).toBe('10 min 38 sec');
  });

  it('returns dash for null', () => {
    expect(formatSeconds(null)).toBe('—');
  });

  it('returns dash for undefined', () => {
    expect(formatSeconds(undefined)).toBe('—');
  });

  it('returns dash for NaN', () => {
    expect(formatSeconds(NaN)).toBe('—');
  });

  it('handles 480 seconds (8-min clinical threshold)', () => {
    expect(formatSeconds(480)).toBe('8 min 0 sec');
  });
});

describe('formatHour', () => {
  it('formats midnight (0) as 12:00 AM', () => {
    expect(formatHour(0)).toBe('12:00 AM');
  });

  it('formats noon (12) as 12:00 PM', () => {
    expect(formatHour(12)).toBe('12:00 PM');
  });

  it('formats morning hours', () => {
    expect(formatHour(1)).toBe('1:00 AM');
    expect(formatHour(6)).toBe('6:00 AM');
    expect(formatHour(11)).toBe('11:00 AM');
  });

  it('formats afternoon/evening hours', () => {
    expect(formatHour(13)).toBe('1:00 PM');
    expect(formatHour(18)).toBe('6:00 PM');
    expect(formatHour(20)).toBe('8:00 PM');
    expect(formatHour(23)).toBe('11:00 PM');
  });

  it('formats all 24 hours without error', () => {
    for (let h = 0; h < 24; h++) {
      expect(formatHour(h)).toMatch(/^\d{1,2}:00 [AP]M$/);
    }
  });
});

describe('formatPct', () => {
  it('formats a percentage with one decimal', () => {
    expect(formatPct(61.2)).toBe('61.2%');
  });

  it('formats 100%', () => {
    expect(formatPct(100)).toBe('100.0%');
  });

  it('formats 0%', () => {
    expect(formatPct(0)).toBe('0.0%');
  });

  it('returns dash for null', () => {
    expect(formatPct(null)).toBe('—');
  });

  it('returns dash for undefined', () => {
    expect(formatPct(undefined)).toBe('—');
  });

  it('returns dash for NaN', () => {
    expect(formatPct(NaN)).toBe('—');
  });

  it('rounds to one decimal place', () => {
    expect(formatPct(83.756)).toBe('83.8%');
  });
});
