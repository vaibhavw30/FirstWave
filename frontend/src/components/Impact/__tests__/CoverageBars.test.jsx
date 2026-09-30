import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import CoverageBars from '../CoverageBars';

const mockData = {
  median_seconds_saved: 147,
  pct_within_8min_static: 61.2,
  pct_within_8min_staged: 83.7,
};

describe('CoverageBars', () => {
  it('returns null when data is null', () => {
    const { container } = render(<CoverageBars data={null} />);
    expect(container.innerHTML).toBe('');
  });

  it('renders 8-Minute Coverage heading', () => {
    render(<CoverageBars data={mockData} />);
    expect(screen.getByText('8-Minute Coverage')).toBeInTheDocument();
  });

  it('renders Without FirstWave label', () => {
    render(<CoverageBars data={mockData} />);
    expect(screen.getByText('Without FirstWave')).toBeInTheDocument();
  });

  it('renders With FirstWave label', () => {
    render(<CoverageBars data={mockData} />);
    expect(screen.getByText('With FirstWave')).toBeInTheDocument();
  });

  it('displays static percentage', () => {
    render(<CoverageBars data={mockData} />);
    expect(screen.getByText('61.2%')).toBeInTheDocument();
  });

  it('displays staged percentage', () => {
    render(<CoverageBars data={mockData} />);
    expect(screen.getByText('83.7%')).toBeInTheDocument();
  });

  it('renders Median Response Time Saved label', () => {
    render(<CoverageBars data={mockData} />);
    expect(screen.getByText('Median Response Time Saved')).toBeInTheDocument();
  });

  it('displays formatted seconds saved (2 min 27 sec)', () => {
    render(<CoverageBars data={mockData} />);
    expect(screen.getByText('2 min 27 sec')).toBeInTheDocument();
  });
});

describe('CoverageBars mean seconds saved', () => {
  const withMean = { ...mockData, median_seconds_saved: 0, mean_seconds_saved: 98 };

  it('shows the citywide mean when the API provides it', () => {
    render(<CoverageBars data={withMean} />);
    expect(screen.getByText('Mean Response Time Saved')).toBeInTheDocument();
    expect(screen.getByText('1 min 38 sec')).toBeInTheDocument();
  });

  it('shows the borough mean when a borough is selected', () => {
    const data = {
      ...withMean,
      by_borough: { BRONX: { static: 48.9, staged: 61.3, median_saved_sec: 0, mean_saved_sec: 125 } },
    };
    render(<CoverageBars data={data} selectedBorough="BRONX" />);
    expect(screen.getByText('Mean Response Time Saved')).toBeInTheDocument();
    expect(screen.getByText('2 min 5 sec')).toBeInTheDocument();
  });

  it('falls back to the borough median when the borough has no mean', () => {
    const data = {
      ...mockData,
      by_borough: { BRONX: { static: 48.2, staged: 74.6, median_saved_sec: 213 } },
    };
    render(<CoverageBars data={data} selectedBorough="BRONX" />);
    expect(screen.getByText('Median Response Time Saved')).toBeInTheDocument();
    expect(screen.getByText('3 min 33 sec')).toBeInTheDocument();
  });
});
