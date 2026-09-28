import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import DatePicker from '../DatePicker';

describe('DatePicker', () => {
  it('renders a labelled date input bounded to the replay range', () => {
    render(<DatePicker value="2025-10-10" onChange={() => {}} />);
    const input = screen.getByLabelText('Replay Date');
    expect(input).toHaveAttribute('type', 'date');
    expect(input).toHaveAttribute('min', '2025-01-01');
    expect(input).toHaveAttribute('max', '2026-06-30');
    expect(input.value).toBe('2025-10-10');
  });

  it('shows the weekday of the selected date', () => {
    render(<DatePicker value="2025-10-10" onChange={() => {}} />);
    expect(screen.getByText('Fri')).toBeInTheDocument();
  });

  it('calls onChange with a valid date', () => {
    const onChange = vi.fn();
    render(<DatePicker value="2025-10-10" onChange={onChange} />);
    fireEvent.change(screen.getByLabelText('Replay Date'), { target: { value: '2025-10-20' } });
    expect(onChange).toHaveBeenCalledWith('2025-10-20');
  });

  it('ignores out-of-range dates', () => {
    const onChange = vi.fn();
    render(<DatePicker value="2025-10-10" onChange={onChange} />);
    fireEvent.change(screen.getByLabelText('Replay Date'), { target: { value: '2024-05-01' } });
    expect(onChange).not.toHaveBeenCalled();
  });
});
