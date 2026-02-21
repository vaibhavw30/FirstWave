import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import DayPicker from '../DayPicker';

describe('DayPicker', () => {
  it('renders Day of Week label', () => {
    render(<DayPicker value={4} onChange={() => {}} />);
    expect(screen.getByText('Day of Week')).toBeInTheDocument();
  });

  it('renders 7 day buttons', () => {
    render(<DayPicker value={0} onChange={() => {}} />);
    const buttons = screen.getAllByRole('button');
    expect(buttons.length).toBe(7);
  });

  it('renders Mon through Sun labels', () => {
    render(<DayPicker value={0} onChange={() => {}} />);
    expect(screen.getByText('Mon')).toBeInTheDocument();
    expect(screen.getByText('Tue')).toBeInTheDocument();
    expect(screen.getByText('Wed')).toBeInTheDocument();
    expect(screen.getByText('Thu')).toBeInTheDocument();
    expect(screen.getByText('Fri')).toBeInTheDocument();
    expect(screen.getByText('Sat')).toBeInTheDocument();
    expect(screen.getByText('Sun')).toBeInTheDocument();
  });

  it('calls onChange with correct index when a day is clicked', () => {
    const handleChange = vi.fn();
    render(<DayPicker value={0} onChange={handleChange} />);
    fireEvent.click(screen.getByText('Fri'));
    expect(handleChange).toHaveBeenCalledWith(4);
  });

  it('highlights the selected day', () => {
    render(<DayPicker value={4} onChange={() => {}} />);
    const fri = screen.getByText('Fri');
    // Selected button has fontWeight 700
    expect(fri.style.fontWeight).toBe('700');
  });
});
