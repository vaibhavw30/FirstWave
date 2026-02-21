import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import TimeSlider from '../TimeSlider';

describe('TimeSlider', () => {
  it('renders the Hour label', () => {
    render(<TimeSlider value={20} onChange={() => {}} />);
    expect(screen.getByText('Hour')).toBeInTheDocument();
  });

  it('displays formatted hour value', () => {
    render(<TimeSlider value={20} onChange={() => {}} />);
    expect(screen.getByText('8:00 PM')).toBeInTheDocument();
  });

  it('displays midnight for hour 0', () => {
    render(<TimeSlider value={0} onChange={() => {}} />);
    expect(screen.getByText('12:00 AM')).toBeInTheDocument();
  });

  it('renders a range input with min 0 and max 23', () => {
    render(<TimeSlider value={10} onChange={() => {}} />);
    const slider = screen.getByRole('slider');
    expect(slider).toHaveAttribute('min', '0');
    expect(slider).toHaveAttribute('max', '23');
  });

  it('calls onChange with parsed integer on change', () => {
    const handleChange = vi.fn();
    render(<TimeSlider value={10} onChange={handleChange} />);
    const slider = screen.getByRole('slider');
    fireEvent.change(slider, { target: { value: '15' } });
    expect(handleChange).toHaveBeenCalledWith(15);
  });

  it('renders tick labels (12 AM, 6 AM, etc.)', () => {
    render(<TimeSlider value={10} onChange={() => {}} />);
    expect(screen.getByText('12 AM')).toBeInTheDocument();
    expect(screen.getByText('6 AM')).toBeInTheDocument();
    expect(screen.getByText('12 PM')).toBeInTheDocument();
    expect(screen.getByText('6 PM')).toBeInTheDocument();
    expect(screen.getByText('11 PM')).toBeInTheDocument();
  });
});
