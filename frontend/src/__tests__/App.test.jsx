import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import App from '../App';

// Mock all hooks to return mock data immediately
vi.mock('../hooks/useHeatmap', () => ({
  useHeatmap: () => ({
    data: {
      type: 'FeatureCollection',
      features: [{
        type: 'Feature',
        properties: { zone: 'B1', normalized_intensity: 0.94, zone_name: 'South Bronx', borough: 'BRONX', predicted_count: 19.2, svi_score: 0.94, historical_avg_response_sec: 641, high_acuity_ratio: 0.29 },
        geometry: { type: 'MultiPolygon', coordinates: [[[[-73.93, 40.80], [-73.89, 40.80], [-73.89, 40.82], [-73.93, 40.82], [-73.93, 40.80]]]] },
      }],
    },
    isLoading: false,
  }),
}));

vi.mock('../hooks/useStaging', () => ({
  useStaging: () => ({
    data: {
      type: 'FeatureCollection',
      features: [{
        type: 'Feature',
        properties: { staging_index: 0, coverage_radius_m: 3500, predicted_demand_coverage: 31.2, cluster_zones: ['B1', 'B2'] },
        geometry: { type: 'Point', coordinates: [-73.9196, 40.8448] },
      }],
    },
    isLoading: false,
  }),
}));

vi.mock('../hooks/useCounterfactual', () => ({
  useCounterfactual: () => ({
    data: {
      median_seconds_saved: 147,
      pct_within_8min_static: 61.2,
      pct_within_8min_staged: 83.7,
      by_svi_quartile: { Q1: { median_saved_sec: 89 }, Q2: { median_saved_sec: 118 }, Q3: { median_saved_sec: 159 }, Q4: { median_saved_sec: 213 } },
      histogram_baseline_seconds: [320, 480, 520],
      histogram_staged_seconds: [210, 310, 380],
      by_borough: {},
    },
    isLoading: false,
  }),
}));

vi.mock('../hooks/useStations', () => ({
  useStations: () => ({ data: { type: 'FeatureCollection', features: [] }, isLoading: false }),
}));

vi.mock('../hooks/useZoneHistory', () => ({
  useZoneHistory: () => ({
    data: null,
    isLoading: false,
  }),
}));

function renderApp() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 0 } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  );
}

const ambulanceControl = () => within(screen.getByText('Ambulances').parentElement);
const layersSection = () => within(screen.getByText('Layers').parentElement);

describe('App', () => {
  it('renders the header', () => {
    renderApp();
    expect(screen.getByText('FirstWave')).toBeInTheDocument();
  });

  it('renders the control panel with all controls', () => {
    renderApp();
    expect(screen.getByText('Hour')).toBeInTheDocument();
    expect(screen.getByText('Replay Date')).toBeInTheDocument();
    expect(screen.getByText('Weather')).toBeInTheDocument();
    expect(screen.getByText('Ambulances')).toBeInTheDocument();
    expect(screen.getByText('Layers')).toBeInTheDocument();
  });

  it('renders the map', () => {
    renderApp();
    expect(screen.getByTestId('map')).toBeInTheDocument();
  });

  it('renders the impact panel', () => {
    renderApp();
    expect(screen.getByText('8-Minute Coverage')).toBeInTheDocument();
    expect(screen.getByText('2 min 27 sec')).toBeInTheDocument();
  });

  it('renders demo preset buttons', () => {
    renderApp();
    expect(screen.getByText('Fri 8PM Peak')).toBeInTheDocument();
    expect(screen.getByText('Mon 4AM Quiet')).toBeInTheDocument();
    expect(screen.getByText('Storm')).toBeInTheDocument();
  });

  it('defaults to hour 20 (8:00 PM)', () => {
    renderApp();
    expect(screen.getByText('8:00 PM')).toBeInTheDocument();
  });

  it('defaults to replaying Friday 2025-10-10', () => {
    renderApp();
    expect(screen.getByLabelText('Replay Date').value).toBe('2025-10-10');
    expect(screen.getByText('Fri')).toBeInTheDocument();
  });

  it('defaults to 5 ambulances', () => {
    renderApp();
    expect(ambulanceControl().getByText('5')).toBeInTheDocument();
  });

  it('updates ambulance count on plus button click', () => {
    renderApp();
    fireEvent.click(ambulanceControl().getByText('+'));
    expect(ambulanceControl().getByText('6')).toBeInTheDocument();
  });

  it('applies Friday Peak demo scenario', () => {
    renderApp();
    fireEvent.click(screen.getByText('Fri 8PM Peak'));
    expect(screen.getByText('8:00 PM')).toBeInTheDocument();
    expect(ambulanceControl().getByText('5')).toBeInTheDocument();
  });

  it('applies Monday Quiet demo scenario', () => {
    renderApp();
    fireEvent.click(screen.getByText('Mon 4AM Quiet'));
    expect(screen.getByText('4:00 AM')).toBeInTheDocument();
    expect(screen.getByLabelText('Replay Date').value).toBe('2025-10-20');
  });

  it('applies Storm demo scenario', () => {
    renderApp();
    fireEvent.click(screen.getByText('Storm'));
    expect(screen.getByText('6:00 PM')).toBeInTheDocument();
    expect(ambulanceControl().getByText('7')).toBeInTheDocument();
  });

  it('toggles layer visibility', () => {
    renderApp();
    const checkboxes = layersSection().getAllByRole('checkbox');
    // heatmap, staging, coverage on by default; EMS stations off
    expect(checkboxes.map(cb => cb.checked)).toEqual([true, true, true, false]);
    // Uncheck heatmap
    fireEvent.click(checkboxes[0]);
    expect(checkboxes[0]).not.toBeChecked();
  });

  it('updates the replay date', () => {
    renderApp();
    fireEvent.change(screen.getByLabelText('Replay Date'), { target: { value: '2025-10-13' } });
    expect(screen.getByLabelText('Replay Date').value).toBe('2025-10-13');
    expect(screen.getByText('Mon')).toBeInTheDocument();
  });

  it('changes weather selection', () => {
    renderApp();
    const radios = screen.getAllByRole('radio');
    fireEvent.click(screen.getByText('Heavy Storm'));
    expect(radios[2]).toBeChecked();
  });
});
