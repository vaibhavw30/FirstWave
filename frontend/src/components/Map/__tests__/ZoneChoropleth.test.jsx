import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import ZoneChoropleth from '../ZoneChoropleth';

describe('ZoneChoropleth', () => {
  it('returns null when data is null', () => {
    const { container } = render(<ZoneChoropleth data={null} />);
    expect(container.innerHTML).toBe('');
  });

  it('returns null when features is empty', () => {
    const { container } = render(<ZoneChoropleth data={{ type: 'FeatureCollection', features: [] }} />);
    expect(container.innerHTML).toBe('');
  });

  it('renders Source and Layers when data has features', () => {
    const data = {
      type: 'FeatureCollection',
      features: [{
        type: 'Feature',
        properties: { zone: 'B1', normalized_intensity: 0.9 },
        geometry: { type: 'MultiPolygon', coordinates: [[[[-73.9, 40.8], [-73.8, 40.8], [-73.8, 40.9], [-73.9, 40.9], [-73.9, 40.8]]]] },
      }],
    };
    render(<ZoneChoropleth data={data} />);
    expect(screen.getByTestId('source-zones')).toBeInTheDocument();
    expect(screen.getByTestId('layer-zone-fill')).toBeInTheDocument();
    expect(screen.getByTestId('layer-zone-outline')).toBeInTheDocument();
  });
});
