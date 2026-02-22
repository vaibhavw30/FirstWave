import { useMemo } from 'react';
import createPlotlyComponent from 'react-plotly.js/factory';
import Plotly from 'plotly.js-basic-dist-min';

const Plot = createPlotlyComponent(Plotly);

export default function ResponseHistogram({ data }) {
  const plotData = useMemo(() => [
    {
      x: (data?.histogram_baseline_seconds || []).map(s => s / 60),
      type: 'histogram',
      name: 'Static',
      marker: { color: 'rgba(239,83,80,0.65)' },
      nbinsx: 15,
    },
    {
      x: (data?.histogram_staged_seconds || []).map(s => s / 60),
      type: 'histogram',
      name: 'FirstWave',
      marker: { color: 'rgba(66,165,245,0.65)' },
      nbinsx: 15,
    },
  ], [data]);

  const layout = useMemo(() => ({
    height: 210,
    margin: { l: 35, r: 10, t: 5, b: 30 },
    paper_bgcolor: 'transparent',
    plot_bgcolor: 'transparent',
    barmode: 'overlay',
    xaxis: {
      title: { text: 'Minutes', font: { size: 10, color: '#888' } },
      tickfont: { color: '#888', size: 9 },
      gridcolor: '#1a2a3a',
      range: [0, 20],
    },
    yaxis: {
      tickfont: { color: '#888', size: 9 },
      gridcolor: '#1a2a3a',
    },
    legend: { font: { color: '#aaa', size: 9 }, x: 0.6, y: 0.95, bgcolor: 'transparent' },
    shapes: [{
      type: 'line',
      x0: 8, x1: 8, y0: 0, y1: 1,
      yref: 'paper',
      line: { color: '#FDD835', width: 2, dash: 'dash' },
    }],
    annotations: [{
      x: 8.3, y: 0.95, yref: 'paper',
      text: '8 min target',
      showarrow: false,
      font: { color: '#FDD835', size: 9 },
    }],
  }), []);

  if (!data) return null;

  return (
    <div style={{ flex: '1 1 0', padding: '0 8px' }}>
      <div style={{ fontSize: 11, color: '#aaa', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 6 }}>Response Time Distribution</div>
      <Plot data={plotData} layout={layout} config={{ displayModeBar: false, staticPlot: true }} style={{ width: '100%' }} />
    </div>
  );
}
