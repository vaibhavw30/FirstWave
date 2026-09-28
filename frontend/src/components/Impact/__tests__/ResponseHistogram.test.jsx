import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import ResponseHistogram from '../ResponseHistogram';

const mockData = {
  histogram_baseline_seconds: [320, 480, 520, 610, 390, 720, 445, 510],
  histogram_staged_seconds: [210, 310, 380, 440, 290, 510, 335, 390],
};

describe('ResponseHistogram', () => {
  it('returns null when data is null', () => {
    const { container } = render(<ResponseHistogram data={null} />);
    expect(container.innerHTML).toBe('');
  });

  it('returns null when data is undefined', () => {
    const { container } = render(<ResponseHistogram data={undefined} />);
    expect(container.innerHTML).toBe('');
  });

  it('renders "Response Time Distribution" heading with valid data', () => {
    render(<ResponseHistogram data={mockData} />);
    expect(screen.getByText('Response Time Distribution')).toBeInTheDocument();
  });

  it('renders Plotly chart', () => {
    render(<ResponseHistogram data={mockData} />);
    expect(screen.getByTestId('plotly-chart')).toBeInTheDocument();
  });

  it('handles missing histogram arrays gracefully', () => {
    const { container } = render(<ResponseHistogram data={{}} />);
    expect(container.innerHTML).not.toBe('');
    expect(screen.getByTestId('plotly-chart')).toBeInTheDocument();
  });

  it('re-renders without crash when data transitions null → valid', () => {
    const { rerender, container } = render(<ResponseHistogram data={null} />);
    expect(container.innerHTML).toBe('');

    rerender(<ResponseHistogram data={mockData} />);
    expect(screen.getByText('Response Time Distribution')).toBeInTheDocument();
    expect(screen.getByTestId('plotly-chart')).toBeInTheDocument();
  });

  it('re-renders without crash when data transitions valid → null → valid', () => {
    const { rerender, container } = render(<ResponseHistogram data={mockData} />);
    expect(screen.getByTestId('plotly-chart')).toBeInTheDocument();

    rerender(<ResponseHistogram data={null} />);
    expect(container.innerHTML).toBe('');

    rerender(<ResponseHistogram data={mockData} />);
    expect(screen.getByText('Response Time Distribution')).toBeInTheDocument();
  });
});
