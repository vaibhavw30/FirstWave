import { formatSeconds, formatPct } from '../../utils/formatters';

export default function CoverageBars({ data }) {
  if (!data) return null;

  return (
    <div style={{ flex: '0 0 40%', padding: '0 12px' }}>
      <div style={{ fontSize: 11, color: '#aaa', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 10 }}>8-Minute Coverage</div>

      <div style={{ marginBottom: 10 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 3 }}>
          <span style={{ color: '#EF5350' }}>Static Stations</span>
          <span style={{ fontWeight: 600 }}>{formatPct(data.pct_within_8min_static)}</span>
        </div>
        <div style={{ height: 10, background: '#222', borderRadius: 5, overflow: 'hidden' }}>
          <div style={{
            height: '100%', background: '#EF5350', borderRadius: 5,
            width: `${data.pct_within_8min_static}%`,
            transition: 'width 600ms ease',
          }} />
        </div>
      </div>

      <div style={{ marginBottom: 14 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 3 }}>
          <span style={{ color: '#42A5F5' }}>FirstWave Staged</span>
          <span style={{ fontWeight: 600 }}>{formatPct(data.pct_within_8min_staged)}</span>
        </div>
        <div style={{ height: 10, background: '#222', borderRadius: 5, overflow: 'hidden' }}>
          <div style={{
            height: '100%', background: '#42A5F5', borderRadius: 5,
            width: `${data.pct_within_8min_staged}%`,
            transition: 'width 600ms ease',
          }} />
        </div>
      </div>

      <div style={{
        background: '#0d1a2e', borderRadius: 6, padding: '8px 12px',
        borderLeft: '3px solid #42A5F5',
      }}>
        <div style={{ fontSize: 10, color: '#aaa' }}>Median Response Time Saved</div>
        <div style={{ fontSize: 18, fontWeight: 700, color: '#42A5F5' }}>
          {formatSeconds(data.median_seconds_saved)}
        </div>
      </div>
    </div>
  );
}
