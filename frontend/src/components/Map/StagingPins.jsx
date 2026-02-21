import { Marker, Source, Layer } from 'react-map-gl';

function createCircleGeoJSON(lng, lat, radiusM, steps = 64) {
  const coords = [];
  const km = radiusM / 1000;
  for (let i = 0; i <= steps; i++) {
    const angle = (i / steps) * 2 * Math.PI;
    const dLat = (km / 111.32) * Math.cos(angle);
    const dLng = (km / (111.32 * Math.cos(lat * Math.PI / 180))) * Math.sin(angle);
    coords.push([lng + dLng, lat + dLat]);
  }
  return {
    type: 'Feature',
    geometry: { type: 'Polygon', coordinates: [coords] },
  };
}

const coverageFill = {
  id: 'coverage-fill',
  type: 'fill',
  paint: {
    'fill-color': 'rgba(66, 165, 245, 0.15)',
  },
};

const coverageStroke = {
  id: 'coverage-stroke',
  type: 'line',
  paint: {
    'line-color': 'rgba(66, 165, 245, 0.6)',
    'line-width': 1.5,
  },
};

export default function StagingPins({ data, showPins, showCoverage }) {
  if (!data || !data.features) return null;

  const circleFeatures = data.features.map((f) => {
    const [lng, lat] = f.geometry.coordinates;
    const radius = f.properties.coverage_radius_m || 3500;
    return createCircleGeoJSON(lng, lat, radius);
  });

  const circleCollection = {
    type: 'FeatureCollection',
    features: circleFeatures,
  };

  return (
    <>
      {showCoverage && (
        <Source id="coverage-circles" type="geojson" data={circleCollection}>
          <Layer {...coverageFill} />
          <Layer {...coverageStroke} />
        </Source>
      )}
      {showPins && data.features.map((f, i) => {
        const [lng, lat] = f.geometry.coordinates;
        return (
          <Marker key={i} longitude={lng} latitude={lat} anchor="center">
            <div style={{
              width: 32,
              height: 32,
              borderRadius: '50%',
              background: 'rgba(66, 165, 245, 0.9)',
              border: '2px solid #fff',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 16,
              cursor: 'pointer',
              boxShadow: '0 2px 8px rgba(0,0,0,0.4)',
            }}>
              🚑
            </div>
          </Marker>
        );
      })}
    </>
  );
}
