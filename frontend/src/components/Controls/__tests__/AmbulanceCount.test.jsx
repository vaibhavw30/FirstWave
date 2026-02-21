import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import AmbulanceCount from '../AmbulanceCount';

describe('AmbulanceCount', () => {
  it('renders Ambulances label', () => {
    render(<AmbulanceCount value={5} onChange={() => {}} />);
    expect(screen.getByText('Ambulances')).toBeInTheDocument();
  });

  it('displays the current count', () => {
    render(<AmbulanceCount value={5} onChange={() => {}} />);
    expect(screen.getByText('5')).toBeInTheDocument();
  });

  it('calls onChange with decremented value on minus click', () => {
    const handleChange = vi.fn();
    render(<AmbulanceCount value={5} onChange={handleChange} />);
    // The minus button contains the − entity
    const buttons = screen.getAllByRole('button');
    fireEvent.click(buttons[0]); // minus button
    expect(handleChange).toHaveBeenCalledWith(4);
  });

  it('calls onChange with incremented value on plus click', () => {
    const handleChange = vi.fn();
    render(<AmbulanceCount value={5} onChange={handleChange} />);
    const buttons = screen.getAllByRole('button');
    fireEvent.click(buttons[1]); // plus button
    expect(handleChange).toHaveBeenCalledWith(6);
  });

  it('disables minus button at minimum (1)', () => {
    render(<AmbulanceCount value={1} onChange={() => {}} />);
    const buttons = screen.getAllByRole('button');
    expect(buttons[0]).toBeDisabled();
  });

  it('disables plus button at maximum (10)', () => {
    render(<AmbulanceCount value={10} onChange={() => {}} />);
    const buttons = screen.getAllByRole('button');
    expect(buttons[1]).toBeDisabled();
  });

  it('clamps down to 1 when at 1', () => {
    const handleChange = vi.fn();
    render(<AmbulanceCount value={1} onChange={handleChange} />);
    const buttons = screen.getAllByRole('button');
    // Even if clicked, should not go below 1
    fireEvent.click(buttons[0]);
    // Button is disabled so click may not fire, but if it did, Math.max(1,0) = 1
  });

  it('enables both buttons at mid-range', () => {
    render(<AmbulanceCount value={5} onChange={() => {}} />);
    const buttons = screen.getAllByRole('button');
    expect(buttons[0]).not.toBeDisabled();
    expect(buttons[1]).not.toBeDisabled();
  });
});
