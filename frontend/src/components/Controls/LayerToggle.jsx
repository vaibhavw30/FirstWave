const LAYERS = [
  { key: 'heatmap', label: 'Demand Heatmap', color: null },
  { key: 'staging', label: 'Staging Pins', color: null },
  { key: 'coverage', label: 'Coverage Circles', color: null },
  { key: 'stations', label: 'EMS Stations', color: '#78909C' },
];

export default function LayerToggle({ visibility, onChange }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <label style={{ fontSize: 11, color: '#aaa', textTransform: 'uppercase', letterSpacing: 1, display: 'block', marginBottom: 6 }}>Layers</label>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        {LAYERS.map(({ key, label, color }) => (
          <label key={key} style={{
            display: 'flex', alignItems: 'center', gap: 8,
            fontSize: 12, cursor: 'pointer', padding: '4px 0',
          }}>
            <input
              type="checkbox"
              checked={visibility[key] ?? false}
              onChange={(e) => onChange(key, e.target.checked)}
              style={{ accentColor: '#42A5F5' }}
            />
            {color && (
              <span style={{
                width: 10, height: 10, borderRadius: '50%',
                background: color, flexShrink: 0,
              }} />
            )}
            <span style={{ color: (visibility[key] ?? false) ? '#e0e0e0' : '#666' }}>{label}</span>
          </label>
        ))}
      </div>
    </div>
  );
}
