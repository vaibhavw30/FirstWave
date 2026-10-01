import { useMemo } from 'react';
import createPlotlyComponent from 'react-plotly.js/factory';
import Plotly from 'plotly.js-basic-dist-min';

const Plot = createPlotlyComponent(Plotly);

const QUARTILES = ['Q1', 'Q2', 'Q3', 'Q4'];
// Reversed order: Q4 at top, Q1 at bottom
const LABELS = ['Q1 (Least)', 'Q2', 'Q3', 'Q4 (Most)'];
// Colors: lightest at bottom (Q1) to darkest at top (Q4)
const COLORS = ['#90CAF9', '#64B5F6', '#1976D2', '#1565C0'];

const LAYOUT = {
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
};

export default function EquityChart({ data }) {
  const quartiles = data?.by_svi_quartile;

  const { plotData, useMean } = useMemo(() => {
    if (!quartiles) return { plotData: null, useMean: false };
    // Prefer the mean (the median is 0 for most slots); mock data only has the median.
    const useMean = QUARTILES.some(q => quartiles[q]?.mean_saved_sec != null);
    const values = QUARTILES.map(q => useMean ? quartiles[q]?.mean_saved_sec : quartiles[q]?.median_saved_sec);
    return {
      useMean,
      plotData: [{
        y: LABELS,
        x: values.map(v => (v || 0) / 60),
        type: 'bar',
        orientation: 'h',
        marker: { color: COLORS },
        text: values.map(v => `${Math.round((v || 0) / 60 * 10) / 10} min`),
        textposition: 'outside',
        cliponaxis: false, // the longest bar's label sits in the right margin
        textfont: { color: '#aaa', size: 10, family: "'DM Mono', monospace" },
      }],
    };
  }, [quartiles]);

  if (!plotData) return null;

  return (
    <div style={{ flex: '0 0 25%', padding: '0 8px' }}>
      <div style={{ fontSize: 11, color: '#aaa', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 2 }}>Equity Impact</div>
      <div style={{ fontSize: 9, color: '#666', marginBottom: 4 }}>{useMean ? 'Mean' : 'Median'} Time Saved by SVI Quartile</div>
      <Plot data={plotData} layout={LAYOUT} config={{ displayModeBar: false, staticPlot: true }} style={{ width: '100%' }} />
    </div>
  );
}
