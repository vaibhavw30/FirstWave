import CoverageBars from './CoverageBars';
import ResponseHistogram from './ResponseHistogram';
import OverlayPanel from './OverlayPanel';

export default function ImpactPanel({ data, isLoading, selectedBorough, overlays, toggleOverlay }) {
  if (isLoading) {
    return (
      <div style={{
        height: 280, background: '#0d0d1a', borderTop: '1px solid #2a2a4a',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        color: '#555', flexShrink: 0,
      }}>
        Loading impact analysis...
      </div>
    );
  }

  return (
    <div style={{
      height: 280,
      background: '#0d0d1a',
      borderTop: '1px solid #2a2a4a',
      display: 'flex',
      alignItems: 'stretch',
      padding: 12,
      flexShrink: 0,
    }}>
      <CoverageBars data={data} selectedBorough={selectedBorough} />
      <ResponseHistogram data={data} selectedBorough={selectedBorough} />
      <OverlayPanel overlays={overlays} toggleOverlay={toggleOverlay} />
    </div>
  );
}
