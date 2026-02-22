import { useRef, useState, useEffect } from 'react';
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

export default function ControlPanel({ controls, onControlChange, layerVisibility, onLayerChange, onApplyScenario, isPlaying, onTogglePlay }) {
  const activePreset = getActivePreset(controls);

  const presetButton = (key, label) => {
    const isActive = activePreset === key;
    return (
      <button
        onClick={() => onApplyScenario(key)}
        style={{
          flex: 1, padding: '8px 6px', fontSize: 11, fontWeight: 500,
          fontFamily: "'DM Mono', monospace", letterSpacing: '0.03em',
          background: isActive ? '#1565C0' : '#333',
          color: isActive ? '#fff' : '#ccc',
          border: 'none', borderRadius: 4, cursor: 'pointer',
          borderLeft: isActive ? '3px solid #42A5F5' : '3px solid transparent',
          boxShadow: isActive ? '0 0 8px rgba(21,101,192,0.4)' : 'none',
        }}
      >{label}</button>
    );
  };

  const scrollRef = useRef(null);
  const [showScrollFade, setShowScrollFade] = useState(false);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const check = () => {
      setShowScrollFade(el.scrollHeight - el.scrollTop - el.clientHeight > 20);
    };
    check();
    el.addEventListener('scroll', check);
    window.addEventListener('resize', check);
    return () => {
      el.removeEventListener('scroll', check);
      window.removeEventListener('resize', check);
    };
  }, []);

  return (
    <div style={{
      width: 280,
      flexShrink: 0,
      position: 'relative',
      display: 'flex',
      flexDirection: 'column',
    }}>
      <div
        ref={scrollRef}
        style={{
          flex: 1,
          background: '#1a1a2e',
          borderRight: '1px solid #2a2a4a',
          padding: 16,
          overflowY: 'auto',
        }}
      >
        <div>
          <div style={{ fontSize: 11, color: '#aaa', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 8 }}>Demo Presets</div>
          <div style={{ display: 'flex', gap: 4 }}>
            {presetButton('friday_peak', 'Fri 8PM Peak')}
            {presetButton('monday_quiet', 'Mon 4AM Quiet')}
            {presetButton('storm', 'Storm')}
          </div>
        </div>

        <Divider />
        <TimeSlider value={controls.hour} onChange={(v) => onControlChange('hour', v)} isPlaying={isPlaying} onTogglePlay={onTogglePlay} />
        <Divider />
        <DayPicker value={controls.dow} onChange={(v) => onControlChange('dow', v)} />
        <Divider />
        <WeatherSelector value={controls.weather} onChange={(v) => onControlChange('weather', v)} />
        <Divider />
        <AmbulanceCount value={controls.ambulances} onChange={(v) => onControlChange('ambulances', v)} />
        <Divider />
        <LayerToggle visibility={layerVisibility} onChange={onLayerChange} />
      </div>

      {showScrollFade && (
        <div style={{
          position: 'absolute', bottom: 0, left: 0,
          width: 279, height: 48,
          background: 'linear-gradient(to bottom, rgba(26,26,46,0) 0%, rgba(26,26,46,0.95) 100%)',
          pointerEvents: 'none', zIndex: 2,
          display: 'flex', alignItems: 'flex-end', justifyContent: 'center',
          paddingBottom: 6,
        }}>
          <svg width="10" height="6" viewBox="0 0 10 6" fill="none">
            <path d="M1 1l4 4 4-4" stroke="rgba(255,255,255,0.4)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </div>
      )}
    </div>
  );
}
