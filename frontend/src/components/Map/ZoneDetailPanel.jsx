import { useMemo } from 'react';
import createPlotlyComponent from 'react-plotly.js/factory';
import Plotly from 'plotly.js-basic-dist-min';
import { formatSeconds } from '../../utils/formatters';

const Plot = createPlotlyComponent(Plotly);

export default function ZoneDetailPanel({ data, onClose }) {
  const sparkData = useMemo(() => [{
    x: Array.from({ length: 24 }, (_, i) => i),
    y: data?.hourly_avg || [],
    type: 'scatter',
    mode: 'lines',
    fill: 'tozeroy',
    fillcolor: 'rgba(66,165,245,0.15)',
    line: { color: '#42A5F5', width: 2 },
  }], [data?.hourly_avg]);

  const sparkLayout = useMemo(() => ({
    height: 120,
    margin: { l: 30, r: 10, t: 5, b: 25 },
    paper_bgcolor: 'transparent',
    plot_bgcolor: 'transparent',
    xaxis: { tickfont: { color: '#888', size: 9 }, gridcolor: '#222', dtick: 6 },
    yaxis: { tickfont: { color: '#888', size: 9 }, gridcolor: '#222' },
  }), []);

  if (!data) return null;

  const sviLabel = data.svi_score >= 0.75 ? 'Very High' : data.svi_score >= 0.5 ? 'High' : data.svi_score >= 0.25 ? 'Moderate' : 'Low';
  const sviColor = data.svi_score >= 0.75 ? '#EF5350' : data.svi_score >= 0.5 ? '#FB8C00' : data.svi_score >= 0.25 ? '#FDD835' : '#00897B';

  const dispatchPct = data.avg_response_seconds > 0 ? (data.avg_dispatch_seconds / data.avg_response_seconds) * 100 : 50;
  const travelPct = 100 - dispatchPct;

  return (
    <div style={{
      position: 'absolute',
      top: 0,
      left: 0,
      width: 300,
      height: '100%',
      background: '#12122a',
      borderRight: '1px solid #2a2a4a',
      padding: 16,
      overflowY: 'auto',
      zIndex: 20,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <div>
          <div style={{ fontWeight: 700, fontSize: 18 }}>{data.zone} — {data.zone_name}</div>
          <div style={{ color: '#aaa', fontSize: 12 }}>{data.borough}</div>
        </div>
        <button onClick={onClose} style={{
          background: 'none', border: 'none', color: '#888', fontSize: 20, cursor: 'pointer',
        }}>&#x2715;</button>
      </div>

      <div style={{ marginBottom: 12 }}>
        <div style={{ fontSize: 12, color: '#aaa', marginBottom: 2 }}>Social Vulnerability</div>
        <span style={{ color: sviColor, fontWeight: 600 }}>{sviLabel}</span>
        <span style={{ color: '#888', marginLeft: 8, fontFamily: "'DM Mono', monospace" }}>({data.svi_score?.toFixed(2)})</span>
      </div>

      <div style={{ marginBottom: 12 }}>
        <div style={{ fontSize: 12, color: '#aaa', marginBottom: 2 }}>Avg Response Time</div>
        <div style={{ fontSize: 16, fontWeight: 600, fontFamily: "'DM Mono', monospace" }}>{formatSeconds(data.avg_response_seconds)}</div>
      </div>

      <div style={{ marginBottom: 12 }}>
        <div style={{ fontSize: 12, color: '#aaa', marginBottom: 6 }}>Response Breakdown</div>
        <div style={{ display: 'flex', height: 12, borderRadius: 6, overflow: 'hidden' }}>
          <div style={{ width: `${dispatchPct}%`, background: '#FB8C00' }} title={`Dispatch: ${formatSeconds(data.avg_dispatch_seconds)}`} />
          <div style={{ width: `${travelPct}%`, background: '#42A5F5' }} title={`Travel: ${formatSeconds(data.avg_travel_seconds)}`} />
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: '#888', marginTop: 2 }}>
          <span>Dispatch <span style={{ fontFamily: "'DM Mono', monospace" }}>{formatSeconds(data.avg_dispatch_seconds)}</span></span>
          <span>Travel <span style={{ fontFamily: "'DM Mono', monospace" }}>{formatSeconds(data.avg_travel_seconds)}</span></span>
        </div>
      </div>

      <div style={{ marginBottom: 8 }}>
        <div style={{ fontSize: 12, color: '#aaa', marginBottom: 4 }}>Hourly Demand Pattern</div>
        <Plot data={sparkData} layout={sparkLayout} config={{ displayModeBar: false, staticPlot: true }} style={{ width: '100%' }} />
      </div>

      <div style={{ fontSize: 11, color: '#666' }}>
        High-acuity: {((data.high_acuity_ratio || 0) * 100).toFixed(0)}% &middot; Held: {((data.held_ratio || 0) * 100).toFixed(0)}%
      </div>
    </div>
  );
}
