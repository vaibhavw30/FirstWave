import { intensityColor } from '../../utils/colorScale';
import { formatSeconds } from '../../utils/formatters';

export default function ZoneTooltip({ info }) {
  if (!info || !info.properties) return null;
  const p = info.properties;
  const intensity = typeof p.normalized_intensity === 'string' ? parseFloat(p.normalized_intensity) : p.normalized_intensity;

  return (
    <div style={{
      position: 'absolute',
      left: info.x + 12,
      top: info.y + 12,
      background: 'rgba(15, 15, 35, 0.95)',
      border: '1px solid #333',
      borderRadius: 8,
      padding: '10px 14px',
      pointerEvents: 'none',
      zIndex: 10,
      minWidth: 180,
      fontSize: 12,
    }}>
      <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 4 }}>
        {p.zone} — {p.zone_name}
      </div>
      <div style={{ color: '#aaa', marginBottom: 6 }}>{p.borough}</div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
        <div style={{
          width: 12, height: 12, borderRadius: 2,
          background: intensityColor(intensity || 0),
        }} />
        <span>Predicted: <b style={{ fontFamily: "'DM Mono', monospace" }}>{typeof p.predicted_count === 'string' ? parseFloat(p.predicted_count).toFixed(1) : p.predicted_count?.toFixed?.(1) ?? '—'}</b> calls/hr</span>
      </div>
      <div>SVI: <b style={{ fontFamily: "'DM Mono', monospace" }}>{p.svi_score}</b></div>
      <div>Avg Response: <b style={{ fontFamily: "'DM Mono', monospace" }}>{formatSeconds(typeof p.historical_avg_response_sec === 'string' ? parseFloat(p.historical_avg_response_sec) : p.historical_avg_response_sec)}</b></div>
    </div>
  );
}
