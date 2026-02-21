import TimeSlider from './TimeSlider';
import DayPicker from './DayPicker';
import WeatherSelector from './WeatherSelector';
import AmbulanceCount from './AmbulanceCount';
import LayerToggle from './LayerToggle';
import { DEMO_SCENARIOS } from '../../constants';

export default function ControlPanel({ controls, onControlChange, layerVisibility, onLayerChange, onApplyScenario }) {
  return (
    <div style={{
      width: 280,
      background: '#1a1a2e',
      borderRight: '1px solid #2a2a4a',
      padding: 16,
      overflowY: 'auto',
      flexShrink: 0,
    }}>
      <div style={{ marginBottom: 16 }}>
        <div style={{ fontSize: 11, color: '#aaa', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 8 }}>Demo Presets</div>
        <div style={{ display: 'flex', gap: 4 }}>
          <button
            onClick={() => onApplyScenario('friday_peak')}
            style={{
              flex: 1, padding: '6px 4px', fontSize: 10, fontWeight: 600,
              background: '#1565C0', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer',
            }}
          >Fri 8PM Peak</button>
          <button
            onClick={() => onApplyScenario('monday_quiet')}
            style={{
              flex: 1, padding: '6px 4px', fontSize: 10, fontWeight: 600,
              background: '#333', color: '#ccc', border: 'none', borderRadius: 4, cursor: 'pointer',
            }}
          >Mon 4AM Quiet</button>
          <button
            onClick={() => onApplyScenario('storm')}
            style={{
              flex: 1, padding: '6px 4px', fontSize: 10, fontWeight: 600,
              background: '#333', color: '#ccc', border: 'none', borderRadius: 4, cursor: 'pointer',
            }}
          >Storm</button>
        </div>
      </div>

      <TimeSlider value={controls.hour} onChange={(v) => onControlChange('hour', v)} />
      <DayPicker value={controls.dow} onChange={(v) => onControlChange('dow', v)} />
      <WeatherSelector value={controls.weather} onChange={(v) => onControlChange('weather', v)} />
      <AmbulanceCount value={controls.ambulances} onChange={(v) => onControlChange('ambulances', v)} />
      <LayerToggle visibility={layerVisibility} onChange={onLayerChange} />
    </div>
  );
}
