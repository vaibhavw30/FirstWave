import { useEffect, useRef, useMemo } from 'react';
import { useMap } from 'react-map-gl';
import { ZONE_SVI } from '../../constants';
import { ZIP_TO_ZONE } from '../../constants/zoneToZips';
import { useNycZipGeoJSON } from '../../hooks/useNycZipGeoJSON';

const SOURCE_ID = 'fw-equity-source';
const FILL_ID = 'fw-equity-fill';
const LINE_ID = 'fw-equity-line';

const getZip = (props) =>
  props?.postalCode || props?.ZIPCODE || props?.ZCTA5CE10 || props?.zipcode || props?.zip || props?.ZIP || '';

function removeLayers(map) {
  try { if (map.getLayer(LINE_ID)) map.removeLayer(LINE_ID); } catch { /* */ }
  try { if (map.getLayer(FILL_ID)) map.removeLayer(FILL_ID); } catch { /* */ }
  try { if (map.getSource(SOURCE_ID)) map.removeSource(SOURCE_ID); } catch { /* */ }
}

export default function EquityLayer({ visible }) {
  const { current: mapRef } = useMap();
  const { data: zipGeoJSON } = useNycZipGeoJSON();
  const layersAdded = useRef(false);

  const enrichedGeoJSON = useMemo(() => {
    if (!zipGeoJSON?.features) return null;

    const features = [];
    for (const f of zipGeoJSON.features) {
      const zip = getZip(f.properties);
      if (!zip) continue;
      const zone = ZIP_TO_ZONE[zip];
      if (!zone) continue;
      const svi = ZONE_SVI[zone];
      if (svi == null) continue;
      features.push({
        ...f,
        properties: { ...f.properties, svi_score: svi, zone },
      });
    }

    if (features.length === 0) return null;
    return { type: 'FeatureCollection', features };
  }, [zipGeoJSON]);

  useEffect(() => {
    const map = mapRef?.getMap?.();
    if (!map || !enrichedGeoJSON) return;

    function addLayers() {
      // Always clean up first to ensure fresh paint properties
      removeLayers(map);

      map.addSource(SOURCE_ID, {
        type: 'geojson',
        data: enrichedGeoJSON,
      });

      map.addLayer({
        id: FILL_ID,
        type: 'fill',
        source: SOURCE_ID,
        paint: {
          'fill-color': [
            'interpolate', ['linear'], ['get', 'svi_score'],
            0.0, '#a855f7',
            0.3, '#9333ea',
            0.5, '#7e22ce',
            0.7, '#6b21a8',
            1.0, '#581c87',
          ],
          'fill-opacity': [
            'interpolate', ['linear'], ['get', 'svi_score'],
            0.0, 0.55,
            0.3, 0.65,
            0.6, 0.75,
            1.0, 0.85,
          ],
        },
        layout: {
          visibility: 'visible',
        },
      });

      map.addLayer({
        id: LINE_ID,
        type: 'line',
        source: SOURCE_ID,
        paint: {
          'line-color': '#a855f7',
          'line-opacity': 0.6,
          'line-width': [
            'interpolate', ['linear'], ['zoom'],
            8, 0.5,
            12, 1.0,
            15, 1.5,
          ],
        },
        layout: {
          visibility: 'visible',
        },
      });

      layersAdded.current = true;
    }

    if (visible) {
      // Recreate layers fresh every time we toggle on
      if (map.isStyleLoaded()) {
        addLayers();
      } else {
        map.once('style.load', addLayers);
      }
    } else if (layersAdded.current) {
      removeLayers(map);
      layersAdded.current = false;
    }

    return () => {
      // Cleanup on unmount only
    };
  }, [mapRef, enrichedGeoJSON, visible]);

  // Full cleanup on unmount
  useEffect(() => {
    return () => {
      const map = mapRef?.getMap?.();
      if (!map) return;
      removeLayers(map);
      layersAdded.current = false;
    };
  }, [mapRef]);

  return null;
}
