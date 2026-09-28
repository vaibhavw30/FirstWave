import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import ControlPanel from '../ControlPanel';

const defaultControls = { date: '2025-10-10', hour: 20, weather: 'none', ambulances: 5 };

const defaultVisibility = { heatmap: true, staging: true, coverage: true };

describe('ControlPanel', () => {
  it('renders demo preset buttons', () => {
    render(
      <ControlPanel
        controls={defaultControls}
        onControlChange={() => {}}
        layerVisibility={defaultVisibility}
        onLayerChange={() => {}}
        onApplyScenario={() => {}}
      />
    );
    expect(screen.getByText('Fri 8PM Peak')).toBeInTheDocument();
    expect(screen.getByText('Mon 4AM Quiet')).toBeInTheDocument();
    expect(screen.getByText('Storm')).toBeInTheDocument();
  });

  it('calls onApplyScenario when Friday Peak preset is clicked', () => {
    const handleScenario = vi.fn();
    render(
      <ControlPanel
        controls={defaultControls}
        onControlChange={() => {}}
        layerVisibility={defaultVisibility}
        onLayerChange={() => {}}
        onApplyScenario={handleScenario}
      />
    );
    fireEvent.click(screen.getByText('Fri 8PM Peak'));
    expect(handleScenario).toHaveBeenCalledWith('friday_peak');
  });

  it('calls onApplyScenario with monday_quiet', () => {
    const handleScenario = vi.fn();
    render(
      <ControlPanel
        controls={defaultControls}
        onControlChange={() => {}}
        layerVisibility={defaultVisibility}
        onLayerChange={() => {}}
        onApplyScenario={handleScenario}
      />
    );
    fireEvent.click(screen.getByText('Mon 4AM Quiet'));
    expect(handleScenario).toHaveBeenCalledWith('monday_quiet');
  });

  it('calls onApplyScenario with storm', () => {
    const handleScenario = vi.fn();
    render(
      <ControlPanel
        controls={defaultControls}
        onControlChange={() => {}}
        layerVisibility={defaultVisibility}
        onLayerChange={() => {}}
        onApplyScenario={handleScenario}
      />
    );
    fireEvent.click(screen.getByText('Storm'));
    expect(handleScenario).toHaveBeenCalledWith('storm');
  });

  it('renders all child control components', () => {
    render(
      <ControlPanel
        controls={defaultControls}
        onControlChange={() => {}}
        layerVisibility={defaultVisibility}
        onLayerChange={() => {}}
        onApplyScenario={() => {}}
      />
    );
    // TimeSlider
    expect(screen.getByText('Hour')).toBeInTheDocument();
    // DatePicker
    expect(screen.getByText('Replay Date')).toBeInTheDocument();
    // WeatherSelector
    expect(screen.getByText('Weather')).toBeInTheDocument();
    // AmbulanceCount
    expect(screen.getByText('Ambulances')).toBeInTheDocument();
    // LayerToggle
    expect(screen.getByText('Layers')).toBeInTheDocument();
  });

  it('highlights the preset matching the current controls', () => {
    render(
      <ControlPanel
        controls={defaultControls}
        onControlChange={() => {}}
        layerVisibility={defaultVisibility}
        onLayerChange={() => {}}
        onApplyScenario={() => {}}
      />
    );
    expect(screen.getByText('Fri 8PM Peak')).toHaveStyle({ backgroundColor: '#1565C0' });
    expect(screen.getByText('Storm')).toHaveStyle({ backgroundColor: '#333' });
  });
});
