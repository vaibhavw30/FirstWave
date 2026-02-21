export default function AmbulanceCount({ value, onChange }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <label style={{ fontSize: 11, color: '#aaa', textTransform: 'uppercase', letterSpacing: 1, display: 'block', marginBottom: 6 }}>Ambulances</label>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <button
          onClick={() => onChange(Math.max(1, value - 1))}
          disabled={value <= 1}
          style={{
            width: 32, height: 32, borderRadius: '50%',
            background: '#1a1a2e', border: '1px solid #333',
            color: value <= 1 ? '#333' : '#42A5F5', fontSize: 18,
            cursor: value <= 1 ? 'not-allowed' : 'pointer',
          }}
        >&minus;</button>
        <span style={{ fontSize: 24, fontWeight: 800, color: '#42A5F5', minWidth: 30, textAlign: 'center', fontFamily: "'DM Mono', monospace" }}>{value}</span>
        <button
          onClick={() => onChange(Math.min(10, value + 1))}
          disabled={value >= 10}
          style={{
            width: 32, height: 32, borderRadius: '50%',
            background: '#1a1a2e', border: '1px solid #333',
            color: value >= 10 ? '#333' : '#42A5F5', fontSize: 18,
            cursor: value >= 10 ? 'not-allowed' : 'pointer',
          }}
        >+</button>
      </div>
    </div>
  );
}
