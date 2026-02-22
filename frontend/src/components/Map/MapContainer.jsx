import { useState, useCallback } from 'react';
import Map from 'react-map-gl';
import 'mapbox-gl/dist/mapbox-gl.css';
import { MAPBOX_TOKEN } from '../../constants';
import DemandHeatmap from './DemandHeatmap';
import ZoneChoropleth from './ZoneChoropleth';
import StagingPins from './StagingPins';
import ZoneTooltip from './ZoneTooltip';

const INITIAL_VIEW = {
  longitude: -73.97,
  latitude: 40.73,
  zoom: 10.5,
  pitch: 0,
  bearing: 0,
};

export default function MapContainer({ heatmapData, stagingData, layerVisibility, selectedZone, onZoneClick, ambulanceCount, counterfactualByZone }) {
  const [hoverInfo, setHoverInfo] = useState(null);

  const onMouseMove = useCallback((e) => {
    const feature = e.features && e.features[0];
    if (feature) {
      setHoverInfo({
        x: e.point.x,
        y: e.point.y,
        properties: feature.properties,
      });
    } else {
      setHoverInfo(null);
    }
  }, []);

  const onMouseLeave = useCallback(() => setHoverInfo(null), []);

  const onClick = useCallback((e) => {
    const feature = e.features && e.features[0];
    if (feature && feature.properties?.zone) {
      onZoneClick(feature.properties.zone);
    }
  }, [onZoneClick]);

  return (
    <div style={{ flex: 1, position: 'relative' }}>
      <Map
        initialViewState={INITIAL_VIEW}
        mapboxAccessToken={MAPBOX_TOKEN}
        mapStyle="mapbox://styles/mapbox/dark-v11"
        interactiveLayerIds={layerVisibility.heatmap ? ['zone-fill', 'zip-fill'] : []}
        onMouseMove={onMouseMove}
        onMouseLeave={onMouseLeave}
        onClick={onClick}
        style={{ width: '100%', height: '100%' }}
      >
        <DemandHeatmap heatmapData={heatmapData} visible={layerVisibility.heatmap} />
        {layerVisibility.heatmap && <ZoneChoropleth data={heatmapData} />}
        <StagingPins
          data={stagingData}
          showPins={layerVisibility.staging}
          showCoverage={layerVisibility.coverage}
          ambulanceCount={ambulanceCount}
          counterfactualByZone={counterfactualByZone}
        />
      </Map>
      {hoverInfo && <ZoneTooltip info={hoverInfo} />}
    </div>
  );
}
