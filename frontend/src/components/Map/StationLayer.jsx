import { Source, Layer } from 'react-map-gl';
import { useStations } from '../../hooks/useStations';

const circleLayer = {
  id: 'ems-stations-circle',
  type: 'circle',
  paint: {
    'circle-radius': 7,
    'circle-color': '#78909C',
    'circle-stroke-width': 1.5,
    'circle-stroke-color': '#ECEFF1',
  },
};

export function StationTooltip({ info }) {
  if (!info) return null;
  const p = info.properties;
  return (
    <div style={{
      position: 'absolute',
      left: info.x + 12,
      top: info.y + 12,
      background: 'rgba(15, 15, 35, 0.95)',
      border: '1px solid #78909C',
      borderRadius: 8,
      padding: '8px 12px',
      pointerEvents: 'none',
      zIndex: 20,
      fontSize: 12,
      minWidth: 160,
    }}>
      <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 2, color: '#ECEFF1' }}>
        {p.name}
      </div>
      <div style={{ color: '#90A4AE' }}>{p.borough}</div>
      {p.address && (
        <div style={{ color: '#666', fontSize: 11, marginTop: 2 }}>{p.address}</div>
      )}
    </div>
  );
}

export default function StationLayer({ visible }) {
  const { data } = useStations();

  if (!visible || !data || !data.features || data.features.length === 0) return null;

  return (
    <Source id="ems-stations" type="geojson" data={data}>
      <Layer {...circleLayer} />
    </Source>
  );
}
