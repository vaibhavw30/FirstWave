import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import Header from '../Header';

describe('Header', () => {
  it('renders the FirstWave brand name', () => {
    render(<Header />);
    expect(screen.getByText('FirstWave')).toBeInTheDocument();
  });

  it('renders the subtitle', () => {
    render(<Header />);
    expect(screen.getByText('Predictive EMS Staging')).toBeInTheDocument();
  });

  it('renders NYC EMS label', () => {
    render(<Header />);
    expect(screen.getByText('NYC Emergency Medical Services')).toBeInTheDocument();
  });

  it('renders as a header element', () => {
    const { container } = render(<Header />);
    expect(container.querySelector('header')).toBeInTheDocument();
  });
});
