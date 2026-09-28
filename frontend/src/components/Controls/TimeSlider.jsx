import { formatHour } from '../../utils/formatters';

export default function TimeSlider({ value, onChange, isPlaying, onTogglePlay }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <label style={{ fontSize: 11, color: '#aaa', textTransform: 'uppercase', letterSpacing: 1 }}>Hour</label>
          <button
            onClick={onTogglePlay}
            title={isPlaying ? 'Pause animation' : 'Watch the wave (animate 24h)'}
            style={{
              background: 'none', border: 'none', cursor: 'pointer',
              fontSize: 14, padding: '0 2px', lineHeight: 1,
              color: isPlaying ? '#FDD835' : '#42A5F5',
            }}
          >
            {isPlaying ? '⏸' : '▶'}
          </button>
        </div>
        <span style={{ fontSize: 18, fontWeight: 600, color: '#42A5F5', fontFamily: "'DM Mono', monospace" }}>{formatHour(value)}</span>
      </div>
      <input
        type="range"
        min={0}
        max={23}
        value={value}
        onChange={(e) => onChange(parseInt(e.target.value))}
        style={{ width: '100%', accentColor: '#42A5F5' }}
      />
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 9, color: '#555' }}>
        <span>12 AM</span>
        <span>6 AM</span>
        <span>12 PM</span>
        <span>6 PM</span>
        <span>11 PM</span>
      </div>
    </div>
  );
}
