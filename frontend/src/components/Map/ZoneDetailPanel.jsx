import { useMemo } from 'react';
import createPlotlyComponent from 'react-plotly.js/factory';
import Plotly from 'plotly.js-basic-dist-min';
import { formatSeconds } from '../../utils/formatters';

const Plot = createPlotlyComponent(Plotly);

export default function ZoneDetailPanel({ data, onClose, counterfactualData }) {
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

      {(() => {
        const bd = counterfactualData?.by_borough?.[data.borough];
        if (!bd) return null;
        const zoneCounterfactual = counterfactualData?.by_zone?.[data.zone];
        const saved = bd.median_saved_sec;
        const staticPct = bd.static;
        const stagedPct = bd.staged;
        const beforeTime = zoneCounterfactual?.static_time ?? data.avg_response_seconds;
        const afterTime = zoneCounterfactual ? (zoneCounterfactual.staged_time) : Math.max(0, beforeTime - saved);
        const afterColor = afterTime <= 480 ? '#4caf50' : afterTime <= 600 ? '#FB8C00' : '#EF5350';
        const stagedPctColor = stagedPct >= 80 ? '#4caf50' : stagedPct >= 60 ? '#FB8C00' : '#EF5350';
        return (
          <div style={{ marginBottom: 12, background: 'rgba(255,255,255,0.03)', borderRadius: 8, padding: 10 }}>
            <div style={{ fontSize: 12, color: '#aaa', marginBottom: 6 }}>Staging Impact — {data.borough}</div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 4 }}>
              <span style={{ fontSize: 11, color: '#999' }}>Before</span>
              <span style={{ fontWeight: 600, fontFamily: "'DM Mono', monospace", color: '#EF5350' }}>{formatSeconds(beforeTime)}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 4 }}>
              <span style={{ fontSize: 11, color: '#999' }}>After</span>
              <span style={{ fontWeight: 600, fontFamily: "'DM Mono', monospace", color: afterColor }}>{formatSeconds(afterTime)}</span>
            </div>
            {(zoneCounterfactual?.seconds_saved ?? saved) > 0 && (
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 6 }}>
                <span style={{ fontSize: 11, color: '#999' }}>Time saved</span>
                <span style={{ fontWeight: 600, fontFamily: "'DM Mono', monospace", color: '#42a5f5' }}>{formatSeconds(zoneCounterfactual?.seconds_saved ?? saved)}</span>
              </div>
            )}
            <div style={{ borderTop: '1px solid #2a2a4a', paddingTop: 6, marginTop: 2 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 2 }}>
                <span style={{ fontSize: 11, color: '#999' }}>Without FirstWave</span>
                <span style={{ fontWeight: 600, fontFamily: "'DM Mono', monospace", color: '#EF5350', fontSize: 12 }}>{staticPct}%</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 2 }}>
                <span style={{ fontSize: 11, color: '#999' }}>With FirstWave</span>
                <span style={{ fontWeight: 600, fontFamily: "'DM Mono', monospace", color: stagedPctColor, fontSize: 12 }}>{stagedPct}%</span>
              </div>
              <div style={{ fontSize: 9, color: '#888', textAlign: 'right' }}>calls within 8-min target</div>
            </div>
            <div style={{
              marginTop: 6, fontSize: 10, textAlign: 'right',
              color: afterTime <= 480 ? '#4caf50' : '#FB8C00',
              fontWeight: 600,
            }}>
              {afterTime <= 480 ? '● Under 8-min clinical threshold' : '● Above 8-min clinical threshold'}
            </div>
          </div>
        );
      })()}

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
