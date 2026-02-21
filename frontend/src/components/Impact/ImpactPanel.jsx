import CoverageBars from './CoverageBars';
import ResponseHistogram from './ResponseHistogram';
import EquityChart from './EquityChart';

export default function ImpactPanel({ data, isLoading }) {
  if (isLoading) {
    return (
      <div style={{
        height: 220, background: '#0d0d1a', borderTop: '1px solid #2a2a4a',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        color: '#555', flexShrink: 0,
      }}>
        Loading impact analysis...
      </div>
    );
  }

  return (
    <div style={{
      height: 220,
      background: '#0d0d1a',
      borderTop: '1px solid #2a2a4a',
      display: 'flex',
      alignItems: 'stretch',
      padding: 12,
      flexShrink: 0,
    }}>
      <CoverageBars data={data} />
      <ResponseHistogram data={data} />
      <EquityChart data={data} />
    </div>
  );
}
