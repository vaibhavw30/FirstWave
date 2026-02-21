import { useState } from 'react';
import { Marker, Popup, Source, Layer } from 'react-map-gl';

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

const DUMMY_UNITS = [
  { unit: 'EMS-47X', crew: 'Rivera, Chen', status: 'Staged — Idle', eta: '< 4 min' },
  { unit: 'EMS-23K', crew: 'Okafor, Singh', status: 'Staged — Idle', eta: '< 5 min' },
  { unit: 'EMS-61A', crew: 'Gutierrez, Park', status: 'Staged — Idle', eta: '< 3 min' },
  { unit: 'EMS-15R', crew: 'Johnson, Lee', status: 'Staged — Idle', eta: '< 6 min' },
  { unit: 'EMS-38M', crew: 'Nguyen, Brown', status: 'Staged — Idle', eta: '< 4 min' },
  { unit: 'EMS-52D', crew: 'Garcia, Kim', status: 'Staged — Idle', eta: '< 5 min' },
  { unit: 'EMS-09F', crew: 'Patel, Williams', status: 'Staged — Idle', eta: '< 3 min' },
  { unit: 'EMS-74B', crew: 'Thomas, Zhang', status: 'Staged — Idle', eta: '< 6 min' },
  { unit: 'EMS-20W', crew: 'Davis, Tanaka', status: 'Staged — Idle', eta: '< 4 min' },
  { unit: 'EMS-85L', crew: 'Martinez, Ali', status: 'Staged — Idle', eta: '< 5 min' },
];

const popupStyle = {
  background: 'rgba(15, 15, 35, 0.95)',
  border: '1px solid #333',
  borderRadius: 8,
  padding: '10px 14px',
  minWidth: 190,
  fontSize: 12,
  color: '#e0e0e0',
};

export default function StagingPins({ data, showPins, showCoverage }) {
  const [selectedPin, setSelectedPin] = useState(null);

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

  const handlePinClick = (e, index) => {
    e.originalEvent?.stopPropagation?.();
    e.stopPropagation?.();
    setSelectedPin(selectedPin === index ? null : index);
  };

  const selectedFeature = selectedPin !== null ? data.features[selectedPin] : null;
  const unitInfo = selectedPin !== null ? DUMMY_UNITS[selectedPin % DUMMY_UNITS.length] : null;

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
            <div
              onClick={(e) => handlePinClick({ originalEvent: e, stopPropagation: () => {} }, i)}
              style={{
                width: 32,
                height: 32,
                borderRadius: '50%',
                background: selectedPin === i
                  ? 'rgba(66, 165, 245, 1)'
                  : 'rgba(66, 165, 245, 0.9)',
                border: selectedPin === i ? '2px solid #90caf9' : '2px solid #fff',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 16,
                cursor: 'pointer',
                boxShadow: selectedPin === i
                  ? '0 0 12px rgba(66, 165, 245, 0.6)'
                  : '0 2px 8px rgba(0,0,0,0.4)',
                transition: 'box-shadow 0.2s, border 0.2s',
              }}>
              🚑
            </div>
          </Marker>
        );
      })}

      {selectedFeature && unitInfo && (() => {
        const [lng, lat] = selectedFeature.geometry.coordinates;
        const p = selectedFeature.properties;
        return (
          <Popup
            longitude={lng}
            latitude={lat}
            anchor="bottom"
            offset={[0, -20]}
            closeOnClick={false}
            closeButton={false}
            className="staging-popup"
          >
            <div style={popupStyle}>
              <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: 6,
              }}>
                <span style={{
                  fontWeight: 700,
                  fontSize: 14,
                  color: '#fff',
                  fontFamily: "'DM Mono', monospace",
                }}>
                  {unitInfo.unit}
                </span>
                <span
                  onClick={() => setSelectedPin(null)}
                  style={{
                    cursor: 'pointer',
                    color: '#666',
                    fontSize: 16,
                    lineHeight: 1,
                    padding: '0 2px',
                  }}
                >
                  ×
                </span>
              </div>

              <div style={{ marginBottom: 4 }}>
                Crew: <b style={{ color: '#fff' }}>{unitInfo.crew}</b>
              </div>

              <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                marginBottom: 4,
              }}>
                <div style={{
                  width: 7,
                  height: 7,
                  borderRadius: '50%',
                  background: '#4caf50',
                  boxShadow: '0 0 4px rgba(76, 175, 80, 0.6)',
                }} />
                <span>{unitInfo.status}</span>
              </div>

              <div style={{ marginBottom: 4 }}>
                Coverage: <b style={{
                  color: '#42a5f5',
                  fontFamily: "'DM Mono', monospace",
                }}>
                  {p.predicted_demand_coverage?.toFixed?.(1) ?? p.predicted_demand_coverage}%
                </b>
              </div>

              <div style={{ marginBottom: 4 }}>
                Zones: <span style={{
                  color: '#aaa',
                  fontFamily: "'DM Mono', monospace",
                }}>
                  {Array.isArray(p.cluster_zones) ? p.cluster_zones.join(', ') : p.cluster_zones}
                </span>
              </div>

              <div>
                Est. response: <b style={{
                  color: '#4caf50',
                  fontFamily: "'DM Mono', monospace",
                }}>
                  {unitInfo.eta}
                </b>
              </div>
            </div>
          </Popup>
        );
      })()}
    </>
  );
}
