import { useMemo } from 'react';
import { Source, Layer } from 'react-map-gl';
import { ZONE_CENTROIDS } from '../../constants';
import { ZIP_TO_ZONE } from '../../constants/zoneToZips';
import { useNycZipGeoJSON } from '../../hooks/useNycZipGeoJSON';

// Heatmap blob layer — smooth gradient from zone centroids
const heatmapLayer = {
  id: 'demand-heatmap',
  type: 'heatmap',
  paint: {
    'heatmap-weight': ['get', 'weight'],
    'heatmap-intensity': 1.2,
    'heatmap-radius': [
      'interpolate', ['linear'], ['zoom'],
      9, 40,
      11, 60,
      13, 30,
    ],
    'heatmap-opacity': [
      'interpolate', ['linear'], ['zoom'],
      9, 0.85,
      12, 0.4,
      13, 0.0,
    ],
    'heatmap-color': [
      'interpolate', ['linear'], ['heatmap-density'],
      0.0, 'rgba(0,0,0,0)',
      0.1, '#1a237e',
      0.3, '#0277bd',
      0.5, '#00bcd4',
      0.7, '#fdd835',
      0.9, '#fb8c00',
      1.0, '#c62828',
    ],
  },
};

// ZIP polygon fill layer — fades in as heatmap fades out
const zipFillLayer = {
  id: 'zip-fill',
  type: 'fill',
  paint: {
    'fill-color': [
      'interpolate', ['linear'], ['get', 'normalized_intensity'],
      0.0, '#00897B',
      0.3, '#FDD835',
      0.6, '#FB8C00',
      1.0, '#C62828',
    ],
    'fill-opacity': [
      'interpolate', ['linear'], ['zoom'],
      9, 0.45,
      11, 0.55,
      13, 0.70,
    ],
  },
};

// ZIP outline layer — thin white borders
const zipOutlineLayer = {
  id: 'zip-outline',
  type: 'line',
  paint: {
    'line-color': '#ffffff',
    'line-width': 0.5,
    'line-opacity': [
      'interpolate', ['linear'], ['zoom'],
      9, 0.2,
      11, 0.3,
      13, 0.5,
    ],
  },
};

function buildZoneLookup(heatmapData) {
  const lookup = {};
  if (!heatmapData?.features) return lookup;
  for (const f of heatmapData.features) {
    const zone = f.properties?.zone;
    if (zone) {
      lookup[zone] = { ...f.properties };
    }
  }
  return lookup;
}

export default function DemandHeatmap({ heatmapData, visible }) {
  const { data: zipGeoJSON } = useNycZipGeoJSON();

  const zoneLookup = useMemo(() => buildZoneLookup(heatmapData), [heatmapData]);

  // Point features at zone centroids, weighted by demand
  const centroidSource = useMemo(() => {
    if (!heatmapData?.features) return null;
    return {
      type: 'FeatureCollection',
      features: Object.entries(ZONE_CENTROIDS).map(([zone, coords]) => ({
        type: 'Feature',
        geometry: { type: 'Point', coordinates: coords },
        properties: { zone, weight: zoneLookup[zone]?.normalized_intensity ?? 0 },
      })),
    };
  }, [heatmapData, zoneLookup]);

  // ZIP polygons enriched with demand from parent zone
  const enrichedZips = useMemo(() => {
    if (!zipGeoJSON?.features || Object.keys(zoneLookup).length === 0) return null;

    const features = [];
    for (const f of zipGeoJSON.features) {
      const props = f.properties || {};
      const zipCode = props.ZIPCODE || props.postalCode || props.ZCTA5CE10 || props.zipcode;
      if (!zipCode) continue;

      const zone = ZIP_TO_ZONE[zipCode];
      if (!zone) continue;

      const zoneProps = zoneLookup[zone];
      if (!zoneProps) continue;
      features.push({
        ...f,
        properties: {
          ...props,
          ...zoneProps,
        },
      });
    }

    if (features.length === 0) return null;
    return { type: 'FeatureCollection', features };
  }, [zipGeoJSON, zoneLookup]);

  if (!visible || !centroidSource) return null;

  return (
    <>
      <Source id="demand-centroids" type="geojson" data={centroidSource}>
        <Layer {...heatmapLayer} />
      </Source>
      {enrichedZips && (
        <Source id="zip-polygons" type="geojson" data={enrichedZips}>
          <Layer {...zipFillLayer} />
          <Layer {...zipOutlineLayer} />
        </Source>
      )}
    </>
  );
}
