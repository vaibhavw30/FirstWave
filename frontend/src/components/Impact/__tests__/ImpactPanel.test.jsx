import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import ImpactPanel from '../ImpactPanel';

const mockData = {
  median_seconds_saved: 147,
  pct_within_8min_static: 61.2,
  pct_within_8min_staged: 83.7,
  by_borough: {
    BRONX: { static: 48.2, staged: 74.6, median_saved_sec: 213 },
    BROOKLYN: { static: 58.4, staged: 81.2, median_saved_sec: 159 },
  },
  by_svi_quartile: {
    Q1: { median_saved_sec: 89 },
    Q2: { median_saved_sec: 118 },
    Q3: { median_saved_sec: 159 },
    Q4: { median_saved_sec: 213 },
  },
  histogram_baseline_seconds: [320, 480, 520, 610, 390, 720, 445, 510],
  histogram_staged_seconds: [210, 310, 380, 440, 290, 510, 335, 390],
};

const overlayProps = { overlays: { equity: false }, toggleOverlay: () => {} };

describe('ImpactPanel', () => {
  it('shows loading state', () => {
    render(<ImpactPanel data={null} isLoading={true} />);
    expect(screen.getByText('Loading impact analysis...')).toBeInTheDocument();
  });

  it('renders child components when data is provided', () => {
    render(<ImpactPanel data={mockData} isLoading={false} {...overlayProps} />);
    // CoverageBars renders "8-Minute Coverage"
    expect(screen.getByText('8-Minute Coverage')).toBeInTheDocument();
  });

  it('renders response time distribution', () => {
    render(<ImpactPanel data={mockData} isLoading={false} {...overlayProps} />);
    expect(screen.getByText('Response Time Distribution')).toBeInTheDocument();
  });

  it('renders the map overlays panel with the equity toggle', () => {
    const toggleOverlay = vi.fn();
    render(<ImpactPanel data={mockData} isLoading={false} overlays={{ equity: false }} toggleOverlay={toggleOverlay} />);
    expect(screen.getByText('Map Overlays')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('checkbox', { name: 'Toggle Equity (SVI) overlay' }));
    expect(toggleOverlay).toHaveBeenCalledWith('equity');
  });

  it('shows the SVI legend when the equity overlay is on', () => {
    render(<ImpactPanel data={mockData} isLoading={false} overlays={{ equity: true }} toggleOverlay={() => {}} />);
    expect(screen.getByText('Vulnerability')).toBeInTheDocument();
  });
});
