import TimeSlider from './TimeSlider';
import DayPicker from './DayPicker';
import WeatherSelector from './WeatherSelector';
import AmbulanceCount from './AmbulanceCount';
import LayerToggle from './LayerToggle';
import { DEMO_SCENARIOS } from '../../constants';

const Divider = () => (
  <div style={{ height: 1, background: '#2a2a4a', margin: '16px 0' }} />
);

function getActivePreset(controls) {
  for (const [key, scenario] of Object.entries(DEMO_SCENARIOS)) {
    if (
      controls.hour === scenario.hour &&
      controls.dow === scenario.dow &&
      controls.ambulances === scenario.ambulances
    ) {
      return key;
    }
  }
  return null;
}

export default function ControlPanel({ controls, onControlChange, layerVisibility, onLayerChange, onApplyScenario }) {
  const activePreset = getActivePreset(controls);

  const presetButton = (key, label) => {
    const isActive = activePreset === key;
    return (
      <button
        onClick={() => onApplyScenario(key)}
        style={{
          flex: 1, padding: '6px 4px', fontSize: 10, fontWeight: 600,
          background: isActive ? '#1565C0' : '#333',
          color: isActive ? '#fff' : '#ccc',
          border: 'none', borderRadius: 4, cursor: 'pointer',
          borderLeft: isActive ? '3px solid #42A5F5' : '3px solid transparent',
        }}
      >{label}</button>
    );
  };

  return (
    <div style={{
      width: 280,
      background: '#1a1a2e',
      borderRight: '1px solid #2a2a4a',
      padding: 16,
      overflowY: 'auto',
      flexShrink: 0,
    }}>
      <div>
        <div style={{ fontSize: 11, color: '#aaa', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 8 }}>Demo Presets</div>
        <div style={{ display: 'flex', gap: 4 }}>
          {presetButton('friday_peak', 'Fri 8PM Peak')}
          {presetButton('monday_quiet', 'Mon 4AM Quiet')}
          {presetButton('storm', 'Storm')}
        </div>
      </div>

      <Divider />
      <TimeSlider value={controls.hour} onChange={(v) => onControlChange('hour', v)} />
      <Divider />
      <DayPicker value={controls.dow} onChange={(v) => onControlChange('dow', v)} />
      <Divider />
      <WeatherSelector value={controls.weather} onChange={(v) => onControlChange('weather', v)} />
      <Divider />
      <AmbulanceCount value={controls.ambulances} onChange={(v) => onControlChange('ambulances', v)} />
      <Divider />
      <LayerToggle visibility={layerVisibility} onChange={onLayerChange} />
    </div>
  );
}
