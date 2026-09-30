import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import EquityChart from '../EquityChart';

vi.mock('react-plotly.js/factory', () => ({
  default: () => (props) => <div data-testid="plotly-chart">{JSON.stringify(props.data[0].x)}</div>,
}));

const minutes = (secs) => JSON.stringify(secs.map(s => s / 60));

describe('EquityChart', () => {
  it('returns null without quartile data', () => {
    const { container } = render(<EquityChart data={{}} />);
    expect(container.innerHTML).toBe('');
  });

  it('plots the mean seconds saved per quartile when present', () => {
    const data = {
      by_svi_quartile: {
        Q1: { median_saved_sec: 0, mean_saved_sec: 60 },
        Q2: { median_saved_sec: 0, mean_saved_sec: 120 },
        Q3: { median_saved_sec: 0, mean_saved_sec: 30 },
        Q4: { median_saved_sec: 0, mean_saved_sec: 90 },
      },
    };
    render(<EquityChart data={data} />);
    expect(screen.getByTestId('plotly-chart').textContent).toBe(minutes([60, 120, 30, 90]));
    expect(screen.getByText('Mean Time Saved by SVI Quartile')).toBeInTheDocument();
  });

  it('falls back to the median when the mean is missing (mock data)', () => {
    const data = {
      by_svi_quartile: {
        Q1: { median_saved_sec: 89 }, Q2: { median_saved_sec: 118 },
        Q3: { median_saved_sec: 159 }, Q4: { median_saved_sec: 213 },
      },
    };
    render(<EquityChart data={data} />);
    expect(screen.getByTestId('plotly-chart').textContent).toBe(minutes([89, 118, 159, 213]));
    expect(screen.getByText('Median Time Saved by SVI Quartile')).toBeInTheDocument();
  });
});
