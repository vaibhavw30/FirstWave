import { Source, Layer } from 'react-map-gl';

const fillLayer = {
  id: 'zone-fill',
  type: 'fill',
  paint: {
    'fill-color': [
      'interpolate', ['linear'], ['get', 'predicted_count'],
      0,  '#00897B',
      5,  '#FDD835',
      10, '#FB8C00',
      18, '#C62828'
    ],
    'fill-opacity': 0,
  },
};

const outlineLayer = {
  id: 'zone-outline',
  type: 'line',
  paint: {
    'line-color': '#ffffff',
    'line-width': 0.8,
    'line-opacity': 0,
    'line-blur': 0.5,
  },
};

export default function ZoneChoropleth({ data }) {
  if (!data || !data.features || data.features.length === 0) return null;

  return (
    <Source id="zones" type="geojson" data={data}>
      <Layer {...fillLayer} />
      <Layer {...outlineLayer} />
    </Source>
  );
}
