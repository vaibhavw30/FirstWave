import { formatSeconds, formatPct } from '../../utils/formatters';

export default function CoverageBars({ data, selectedBorough, selectedZone }) {
  if (!data) return null;

  const boroughData = selectedBorough && data.by_borough?.[selectedBorough];
  const zoneData = selectedZone && data.by_zone?.[selectedZone];
  const staticPct = boroughData ? boroughData.static : data.pct_within_8min_static;
  const stagedPct = boroughData ? boroughData.staged : data.pct_within_8min_staged;
  // Prefer the mean: the median is 0 for most slots because most calls are in zones no staged unit improves.
  // Mock data has no mean fields, so fall back to the median.
  const scopeMean = boroughData ? boroughData.mean_saved_sec : data.mean_seconds_saved;
  const useMean = !zoneData && scopeMean != null;
  const savedSec = zoneData ? zoneData.seconds_saved
    : useMean ? scopeMean
    : (boroughData ? boroughData.median_saved_sec : data.median_seconds_saved);
  const scopeLabel = zoneData ? selectedZone : (boroughData ? selectedBorough : 'CITYWIDE');

  return (
    <div style={{ flex: '0 0 40%', padding: '0 12px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 10 }}>
        <span style={{ fontSize: 11, color: '#aaa', textTransform: 'uppercase', letterSpacing: 1 }}>8-Minute Coverage</span>
        <span style={{ fontSize: 9, color: boroughData ? '#42A5F5' : '#666', textTransform: 'uppercase', letterSpacing: 1, transition: 'color 300ms ease' }}>{scopeLabel}</span>
      </div>

      <div style={{ marginBottom: 8 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 3 }}>
          <span style={{ fontSize: 10, color: '#EF5350', textTransform: 'uppercase', letterSpacing: 1 }}>Without FirstWave</span>
          <span style={{ fontSize: 28, fontWeight: 700, color: '#EF5350', fontFamily: "'DM Mono', monospace" }}>{formatPct(staticPct)}</span>
        </div>
        <div style={{ height: 6, background: '#222', borderRadius: 3, overflow: 'hidden' }}>
          <div style={{
            height: '100%', background: '#EF5350', borderRadius: 3,
            width: `${staticPct}%`,
            transition: 'width 600ms ease',
          }} />
        </div>
      </div>

      <div style={{ marginBottom: 14 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 3 }}>
          <span style={{ fontSize: 10, color: '#42A5F5', textTransform: 'uppercase', letterSpacing: 1 }}>With FirstWave</span>
          <span style={{ fontSize: 28, fontWeight: 700, color: '#42A5F5', fontFamily: "'DM Mono', monospace" }}>{formatPct(stagedPct)}</span>
        </div>
        <div style={{ height: 6, background: '#222', borderRadius: 3, overflow: 'hidden' }}>
          <div style={{
            height: '100%', background: '#42A5F5', borderRadius: 3,
            width: `${stagedPct}%`,
            transition: 'width 600ms ease',
          }} />
        </div>
      </div>

      <div style={{
        background: '#1a2a3a', borderRadius: 8, padding: '12px 16px',
        textAlign: 'center',
      }}>
        <div style={{ fontSize: 10, color: '#8899aa', textTransform: 'uppercase', letterSpacing: 2, marginBottom: 4 }}>{zoneData ? 'Response Time Saved' : useMean ? 'Mean Response Time Saved' : 'Median Response Time Saved'}</div>
        <div style={{ fontSize: 48, fontWeight: 800, color: '#42A5F5', fontFamily: "'DM Mono', monospace", lineHeight: 1.1 }}>
          {formatSeconds(savedSec)}
        </div>
      </div>
    </div>
  );
}
