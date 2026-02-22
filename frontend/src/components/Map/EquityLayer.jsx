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
      if (layersAdded.current) return;

      if (map.getSource(SOURCE_ID)) {
        map.removeLayer(LINE_ID).catch(() => {});
        map.removeLayer(FILL_ID).catch(() => {});
        map.removeSource(SOURCE_ID);
      }

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
            0.0, 'rgba(255,253,245,0)',
            0.2, 'rgba(233,213,255,0.55)',
            0.4, 'rgba(192,132,252,0.70)',
            0.6, 'rgba(147,51,234,0.82)',
            0.8, 'rgba(107,33,168,0.90)',
            1.0, 'rgba(76,5,149,0.95)',
          ],
          'fill-opacity': 1,
        },
        layout: {
          visibility: visible ? 'visible' : 'none',
        },
      });

      map.addLayer({
        id: LINE_ID,
        type: 'line',
        source: SOURCE_ID,
        paint: {
          'line-color': 'rgba(216,180,254,0.3)',
          'line-width': [
            'interpolate', ['linear'], ['zoom'],
            8, 0.5,
            12, 1.0,
            15, 1.5,
          ],
        },
        layout: {
          visibility: visible ? 'visible' : 'none',
        },
      });

      layersAdded.current = true;
    }

    if (visible && !layersAdded.current) {
      if (map.isStyleLoaded()) {
        addLayers();
      } else {
        map.once('style.load', addLayers);
      }
    }

    if (layersAdded.current) {
      const vis = visible ? 'visible' : 'none';
      try {
        if (map.getLayer(FILL_ID)) map.setLayoutProperty(FILL_ID, 'visibility', vis);
        if (map.getLayer(LINE_ID)) map.setLayoutProperty(LINE_ID, 'visibility', vis);
      } catch {
        // layer not ready yet
      }
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
      try {
        if (map.getLayer(FILL_ID)) map.removeLayer(FILL_ID);
        if (map.getLayer(LINE_ID)) map.removeLayer(LINE_ID);
        if (map.getSource(SOURCE_ID)) map.removeSource(SOURCE_ID);
      } catch {
        // map may already be destroyed
      }
      layersAdded.current = false;
    };
  }, [mapRef]);

  return null;
}
