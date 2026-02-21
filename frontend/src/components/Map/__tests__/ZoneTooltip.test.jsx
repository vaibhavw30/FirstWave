import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import ZoneTooltip from '../ZoneTooltip';

describe('ZoneTooltip', () => {
  it('returns null when info is null', () => {
    const { container } = render(<ZoneTooltip info={null} />);
    expect(container.innerHTML).toBe('');
  });

  it('returns null when info has no properties', () => {
    const { container } = render(<ZoneTooltip info={{ x: 0, y: 0 }} />);
    expect(container.innerHTML).toBe('');
  });

  it('renders zone name and code', () => {
    const info = {
      x: 100,
      y: 200,
      properties: {
        zone: 'B2',
        zone_name: 'West/Central Bronx',
        borough: 'BRONX',
        normalized_intensity: 0.91,
        predicted_count: 18.4,
        svi_score: 0.89,
        historical_avg_response_sec: 638,
      },
    };
    render(<ZoneTooltip info={info} />);
    expect(screen.getByText(/B2/)).toBeInTheDocument();
    expect(screen.getByText(/West\/Central Bronx/)).toBeInTheDocument();
    expect(screen.getByText('BRONX')).toBeInTheDocument();
  });

  it('displays SVI score', () => {
    const info = {
      x: 0, y: 0,
      properties: {
        zone: 'B1', zone_name: 'South Bronx', borough: 'BRONX',
        normalized_intensity: 0.94, predicted_count: 19.2,
        svi_score: 0.94, historical_avg_response_sec: 641,
      },
    };
    render(<ZoneTooltip info={info} />);
    expect(screen.getByText(/0.94/)).toBeInTheDocument();
  });

  it('displays formatted avg response time', () => {
    const info = {
      x: 0, y: 0,
      properties: {
        zone: 'B1', zone_name: 'South Bronx', borough: 'BRONX',
        normalized_intensity: 0.94, predicted_count: 19.2,
        svi_score: 0.94, historical_avg_response_sec: 641,
      },
    };
    render(<ZoneTooltip info={info} />);
    expect(screen.getByText(/10 min 41 sec/)).toBeInTheDocument();
  });

  it('handles string numeric properties (GeoJSON serialization)', () => {
    const info = {
      x: 0, y: 0,
      properties: {
        zone: 'M1', zone_name: 'Lower Manhattan', borough: 'MANHATTAN',
        normalized_intensity: '0.45', predicted_count: '8.3',
        svi_score: '0.31', historical_avg_response_sec: '630',
      },
    };
    render(<ZoneTooltip info={info} />);
    // Should handle string-to-number parsing
    expect(screen.getByText(/8.3/)).toBeInTheDocument();
    expect(screen.getByText(/10 min 30 sec/)).toBeInTheDocument();
  });
});
