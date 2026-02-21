export default function Header() {
  return (
    <header style={{
      height: 48,
      background: '#12122a',
      borderBottom: '1px solid #2a2a4a',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '0 20px',
      flexShrink: 0,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <span style={{ fontSize: 20, fontWeight: 700, color: '#42A5F5' }}>FirstWave</span>
        <span style={{ fontSize: 11, color: '#888', letterSpacing: 1, textTransform: 'uppercase' }}>Predictive EMS Staging</span>
      </div>
      <div style={{ fontSize: 12, color: '#666' }}>NYC Emergency Medical Services</div>
    </header>
  );
}
