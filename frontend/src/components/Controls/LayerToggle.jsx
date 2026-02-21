const LAYERS = [
  { key: 'heatmap', label: 'Demand Heatmap' },
  { key: 'staging', label: 'Staging Pins' },
  { key: 'coverage', label: 'Coverage Circles' },
];

export default function LayerToggle({ visibility, onChange }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <label style={{ fontSize: 11, color: '#aaa', textTransform: 'uppercase', letterSpacing: 1, display: 'block', marginBottom: 6 }}>Layers</label>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        {LAYERS.map(({ key, label }) => (
          <label key={key} style={{
            display: 'flex', alignItems: 'center', gap: 8,
            fontSize: 12, cursor: 'pointer', padding: '4px 0',
          }}>
            <input
              type="checkbox"
              checked={visibility[key]}
              onChange={(e) => onChange(key, e.target.checked)}
              style={{ accentColor: '#42A5F5' }}
            />
            <span style={{ color: visibility[key] ? '#e0e0e0' : '#666' }}>{label}</span>
          </label>
        ))}
      </div>
    </div>
  );
}
