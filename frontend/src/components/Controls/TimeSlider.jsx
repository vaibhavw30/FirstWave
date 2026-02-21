import { formatHour } from '../../utils/formatters';

export default function TimeSlider({ value, onChange }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
        <label style={{ fontSize: 11, color: '#aaa', textTransform: 'uppercase', letterSpacing: 1 }}>Hour</label>
        <span style={{ fontSize: 13, fontWeight: 600, color: '#42A5F5' }}>{formatHour(value)}</span>
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
