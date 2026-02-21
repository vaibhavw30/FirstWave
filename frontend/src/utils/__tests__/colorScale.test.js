import { describe, it, expect } from 'vitest';
import { intensityColor } from '../colorScale';

describe('intensityColor', () => {
  it('returns teal at 0.0', () => {
    expect(intensityColor(0)).toBe('rgb(0,137,123)');
  });

  it('returns yellow at 0.3', () => {
    expect(intensityColor(0.3)).toBe('rgb(253,216,53)');
  });

  it('returns orange at 0.6', () => {
    expect(intensityColor(0.6)).toBe('rgb(251,140,0)');
  });

  it('returns red at 1.0', () => {
    expect(intensityColor(1.0)).toBe('rgb(198,40,40)');
  });

  it('interpolates between teal and yellow at 0.15', () => {
    const color = intensityColor(0.15);
    // Midpoint between teal and yellow
    expect(color).toMatch(/^rgb\(\d+,\d+,\d+\)$/);
    // Should have increasing red, green stays high
    const [, r, g, b] = color.match(/rgb\((\d+),(\d+),(\d+)\)/);
    expect(Number(r)).toBeGreaterThan(0);
    expect(Number(r)).toBeLessThan(253);
    expect(Number(g)).toBeGreaterThan(137);
  });

  it('clamps values below 0', () => {
    expect(intensityColor(-0.5)).toBe(intensityColor(0));
  });

  it('clamps values above 1', () => {
    expect(intensityColor(1.5)).toBe(intensityColor(1));
  });

  it('handles 0.5 (between yellow and orange)', () => {
    const color = intensityColor(0.5);
    expect(color).toMatch(/^rgb\(\d+,\d+,\d+\)$/);
    const [, r, g, b] = color.match(/rgb\((\d+),(\d+),(\d+)\)/);
    // Should be between yellow (253,216,53) and orange (251,140,0)
    expect(Number(r)).toBeGreaterThanOrEqual(251);
    expect(Number(g)).toBeGreaterThan(0);
    expect(Number(g)).toBeLessThan(216);
  });

  it('returns valid rgb format for all values', () => {
    for (let v = 0; v <= 1; v += 0.1) {
      expect(intensityColor(v)).toMatch(/^rgb\(\d+,\d+,\d+\)$/);
    }
  });
});
