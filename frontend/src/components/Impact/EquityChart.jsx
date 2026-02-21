import { useMemo } from 'react';
import createPlotlyComponent from 'react-plotly.js/factory';
import Plotly from 'plotly.js-basic-dist-min';

const Plot = createPlotlyComponent(Plotly);

export default function EquityChart({ data }) {
  if (!data || !data.by_svi_quartile) return null;

  const quartiles = data.by_svi_quartile;
  // Reversed order: Q4 at top, Q1 at bottom
  const labels = ['Q1 (Least)', 'Q2', 'Q3', 'Q4 (Most)'];
  const values = [quartiles.Q1?.median_saved_sec, quartiles.Q2?.median_saved_sec, quartiles.Q3?.median_saved_sec, quartiles.Q4?.median_saved_sec];
  // Colors: lightest at bottom (Q1) to darkest at top (Q4)
  const colors = ['#90CAF9', '#64B5F6', '#1976D2', '#1565C0'];

  const plotData = useMemo(() => [{
    y: labels,
    x: values.map(v => (v || 0) / 60),
    type: 'bar',
    orientation: 'h',
    marker: { color: colors },
    text: values.map(v => `${Math.round((v || 0) / 60 * 10) / 10} min`),
    textposition: 'outside',
    textfont: { color: '#aaa', size: 10, family: "'DM Mono', monospace" },
  }], [data]);

  const layout = useMemo(() => ({
    height: 160,
    margin: { l: 70, r: 50, t: 5, b: 25 },
    paper_bgcolor: 'transparent',
    plot_bgcolor: 'transparent',
    xaxis: {
      tickfont: { color: '#888', size: 9 },
      gridcolor: '#1a2a3a',
      ticksuffix: ' min',
    },
    yaxis: { tickfont: { color: '#aaa', size: 9 }, autorange: true },
  }), []);

  return (
    <div style={{ flex: '0 0 25%', padding: '0 8px' }}>
      <div style={{ fontSize: 11, color: '#aaa', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 6 }}>Equity Impact</div>
      <Plot data={plotData} layout={layout} config={{ displayModeBar: false, staticPlot: true }} style={{ width: '100%' }} />
    </div>
  );
}
