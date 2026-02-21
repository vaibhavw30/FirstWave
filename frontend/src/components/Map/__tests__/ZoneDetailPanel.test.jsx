import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import ZoneDetailPanel from '../ZoneDetailPanel';

const mockZoneData = {
  zone: 'B2',
  borough: 'BRONX',
  zone_name: 'West/Central Bronx',
  svi_score: 0.89,
  avg_response_seconds: 638,
  avg_travel_seconds: 395,
  avg_dispatch_seconds: 243,
  high_acuity_ratio: 0.28,
  held_ratio: 0.09,
  hourly_avg: [
    3.1, 2.4, 1.9, 1.6, 1.8, 2.3, 3.8, 6.1, 8.4, 9.2, 9.8, 10.1,
    10.4, 10.7, 11.2, 11.8, 12.4, 13.1, 14.8, 16.2, 15.9, 14.3, 11.8, 7.4,
  ],
};

describe('ZoneDetailPanel', () => {
  it('returns null when data is null', () => {
    const { container } = render(<ZoneDetailPanel data={null} onClose={() => {}} />);
    expect(container.innerHTML).toBe('');
  });

  it('renders zone code and name', () => {
    render(<ZoneDetailPanel data={mockZoneData} onClose={() => {}} />);
    expect(screen.getByText(/B2/)).toBeInTheDocument();
    expect(screen.getByText(/West\/Central Bronx/)).toBeInTheDocument();
  });

  it('renders borough name', () => {
    render(<ZoneDetailPanel data={mockZoneData} onClose={() => {}} />);
    expect(screen.getByText('BRONX')).toBeInTheDocument();
  });

  it('renders SVI label "Very High" for score >= 0.75', () => {
    render(<ZoneDetailPanel data={mockZoneData} onClose={() => {}} />);
    expect(screen.getByText('Very High')).toBeInTheDocument();
  });

  it('renders SVI label "High" for score 0.5-0.74', () => {
    const data = { ...mockZoneData, svi_score: 0.6 };
    render(<ZoneDetailPanel data={data} onClose={() => {}} />);
    expect(screen.getByText('High')).toBeInTheDocument();
  });

  it('renders SVI label "Moderate" for score 0.25-0.49', () => {
    const data = { ...mockZoneData, svi_score: 0.35 };
    render(<ZoneDetailPanel data={data} onClose={() => {}} />);
    expect(screen.getByText('Moderate')).toBeInTheDocument();
  });

  it('renders SVI label "Low" for score < 0.25', () => {
    const data = { ...mockZoneData, svi_score: 0.12 };
    render(<ZoneDetailPanel data={data} onClose={() => {}} />);
    expect(screen.getByText('Low')).toBeInTheDocument();
  });

  it('displays formatted avg response time', () => {
    render(<ZoneDetailPanel data={mockZoneData} onClose={() => {}} />);
    expect(screen.getByText('10 min 38 sec')).toBeInTheDocument();
  });

  it('renders response breakdown dispatch and travel labels', () => {
    render(<ZoneDetailPanel data={mockZoneData} onClose={() => {}} />);
    expect(screen.getByText(/Dispatch/)).toBeInTheDocument();
    expect(screen.getByText(/Travel/)).toBeInTheDocument();
  });

  it('shows high-acuity and held percentages', () => {
    render(<ZoneDetailPanel data={mockZoneData} onClose={() => {}} />);
    expect(screen.getByText(/28%/)).toBeInTheDocument();
    expect(screen.getByText(/9%/)).toBeInTheDocument();
  });

  it('calls onClose when close button is clicked', () => {
    const handleClose = vi.fn();
    render(<ZoneDetailPanel data={mockZoneData} onClose={handleClose} />);
    const closeButton = screen.getByRole('button');
    fireEvent.click(closeButton);
    expect(handleClose).toHaveBeenCalledTimes(1);
  });

  it('renders Plotly chart for hourly demand', () => {
    render(<ZoneDetailPanel data={mockZoneData} onClose={() => {}} />);
    expect(screen.getByText('Hourly Demand Pattern')).toBeInTheDocument();
    expect(screen.getByTestId('plotly-chart')).toBeInTheDocument();
  });
});
