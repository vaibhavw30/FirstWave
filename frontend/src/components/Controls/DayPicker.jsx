import { DOW_LABELS } from '../../constants';

export default function DayPicker({ value, onChange }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <label style={{ fontSize: 11, color: '#aaa', textTransform: 'uppercase', letterSpacing: 1, display: 'block', marginBottom: 6 }}>Day of Week</label>
      <div style={{ display: 'flex', gap: 4 }}>
        {DOW_LABELS.map((label, i) => (
          <button
            key={i}
            onClick={() => onChange(i)}
            style={{
              flex: 1,
              padding: '6px 0',
              fontSize: 11,
              fontWeight: value === i ? 700 : 400,
              color: value === i ? '#fff' : '#888',
              background: value === i ? '#1565C0' : '#1a1a2e',
              border: '1px solid',
              borderColor: value === i ? '#42A5F5' : '#333',
              borderRadius: 4,
              cursor: 'pointer',
              transition: 'all 0.15s',
            }}
          >
            {label}
          </button>
        ))}
      </div>
    </div>
  );
}
