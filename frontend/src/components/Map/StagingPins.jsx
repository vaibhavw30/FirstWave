import { useState, useMemo } from 'react';
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
    'line-dasharray': [4, 3],
  },
};

function distributeAmbulances(features, total) {
  if (!features || features.length === 0) return [];
  const demands = features.map((f) => f.properties.predicted_demand_coverage || 1);
  const sumDemand = demands.reduce((a, b) => a + b, 0);
  const raw = demands.map((d) => (d / sumDemand) * total);
  const floors = raw.map((r) => Math.floor(r));
  const remainders = raw.map((r, i) => ({ i, r: r - floors[i] }));
  let distributed = floors.reduce((a, b) => a + b, 0);
  remainders.sort((a, b) => b.r - a.r);
  for (let k = 0; distributed < total && k < remainders.length; k++) {
    floors[remainders[k].i]++;
    distributed++;
  }
  return floors;
}

function seededRandom(seed) {
  let s = seed;
  return () => {
    s = (s * 16807 + 0) % 2147483647;
    return s / 2147483647;
  };
}

function generateDotPositions(lng, lat, radiusM, count, seed) {
  const rng = seededRandom(seed * 7919 + 1);
  const dots = [];
  const innerRadius = radiusM * 0.6;
  const kmInner = innerRadius / 1000;
  for (let i = 0; i < count; i++) {
    const angle = rng() * 2 * Math.PI;
    const dist = Math.sqrt(rng()) * kmInner;
    const dLat = (dist / 111.32) * Math.cos(angle);
    const dLng = (dist / (111.32 * Math.cos(lat * Math.PI / 180))) * Math.sin(angle);
    dots.push([lng + dLng, lat + dLat]);
  }
  return dots;
}

const popupStyle = {
  background: 'rgba(15, 15, 35, 0.95)',
  border: '1px solid #333',
  borderRadius: 8,
  padding: '10px 14px',
  minWidth: 190,
  fontSize: 12,
  color: '#e0e0e0',
};

export default function StagingPins({ data, showPins, showCoverage, ambulanceCount = 5 }) {
  const [selectedPin, setSelectedPin] = useState(null);

  const features = data?.features || [];

  const distribution = useMemo(
    () => distributeAmbulances(features, ambulanceCount),
    [features, ambulanceCount]
  );

  const circleCollection = useMemo(() => {
    const circleFeatures = features.map((f) => {
      const [lng, lat] = f.geometry.coordinates;
      const radius = f.properties.coverage_radius_m || 3500;
      return createCircleGeoJSON(lng, lat, radius);
    });
    return { type: 'FeatureCollection', features: circleFeatures };
  }, [features]);

  const allDots = useMemo(() => {
    const dots = [];
    features.forEach((f, i) => {
      const [lng, lat] = f.geometry.coordinates;
      const radius = f.properties.coverage_radius_m || 3500;
      const count = distribution[i] || 0;
      const positions = generateDotPositions(lng, lat, radius, count, i);
      positions.forEach((pos) => dots.push({ lng: pos[0], lat: pos[1], zoneIndex: i }));
    });
    return dots;
  }, [features, distribution]);

  if (features.length === 0) return null;

  const handlePinClick = (e, index) => {
    if (e.stopPropagation) e.stopPropagation();
    if (e.originalEvent?.stopPropagation) e.originalEvent.stopPropagation();
    setSelectedPin(selectedPin === index ? null : index);
  };

  const selectedFeature = selectedPin !== null ? features[selectedPin] : null;

  return (
    <>
      {showCoverage && (
        <Source id="coverage-circles" type="geojson" data={circleCollection}>
          <Layer {...coverageFill} />
          <Layer {...coverageStroke} />
        </Source>
      )}

      {/* Zone label pills */}
      {showPins && features.map((f, i) => {
        const [lng, lat] = f.geometry.coordinates;
        const count = distribution[i] || 0;
        const isSelected = selectedPin === i;
        return (
          <Marker key={`zone-${i}`} longitude={lng} latitude={lat} anchor="center">
            <div
              onClick={(e) => handlePinClick(e, i)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 4,
                padding: '3px 10px',
                borderRadius: 12,
                background: isSelected
                  ? 'rgba(66, 165, 245, 1)'
                  : 'rgba(66, 165, 245, 0.85)',
                border: isSelected ? '2px solid #90caf9' : '2px solid rgba(255,255,255,0.7)',
                cursor: 'pointer',
                boxShadow: isSelected
                  ? '0 0 12px rgba(66, 165, 245, 0.6)'
                  : '0 2px 8px rgba(0,0,0,0.4)',
                transition: 'box-shadow 0.2s, border 0.2s',
                whiteSpace: 'nowrap',
                fontFamily: "'DM Mono', monospace",
                fontSize: 11,
                fontWeight: 700,
                color: '#fff',
                letterSpacing: 0.5,
              }}
            >
              <span>Z{i + 1}</span>
              <span style={{
                background: 'rgba(239, 83, 80, 0.9)',
                borderRadius: 8,
                padding: '0 5px',
                fontSize: 10,
                fontWeight: 700,
                minWidth: 16,
                textAlign: 'center',
              }}>
                {count}
              </span>
            </div>
          </Marker>
        );
      })}

      {/* Individual ambulance dots */}
      {showPins && allDots.map((dot, i) => (
        <Marker key={`dot-${i}`} longitude={dot.lng} latitude={dot.lat} anchor="center">
          <div style={{
            width: 8,
            height: 8,
            borderRadius: '50%',
            background: '#EF5350',
            border: '1.5px solid #fff',
            boxShadow: '0 0 6px rgba(239, 83, 80, 0.5)',
            pointerEvents: 'none',
          }} />
        </Marker>
      ))}

      {/* Popup for selected zone */}
      {selectedFeature && (() => {
        const [lng, lat] = selectedFeature.geometry.coordinates;
        const p = selectedFeature.properties;
        const count = distribution[selectedPin] || 0;
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
                  Staging Zone {selectedPin + 1}
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
                Ambulances: <b style={{
                  color: '#EF5350',
                  fontFamily: "'DM Mono', monospace",
                }}>
                  {count}
                </b>
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
                  {'< ' + Math.max(3, 8 - count) + ' min'}
                </b>
              </div>
            </div>
          </Popup>
        );
      })()}
    </>
  );
}
