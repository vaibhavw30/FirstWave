import { useState, useCallback, useMemo } from 'react';
import { debounce } from 'lodash';
import Header from './components/Header';
import MapContainer from './components/Map/MapContainer';
import ZoneDetailPanel from './components/Map/ZoneDetailPanel';
import ControlPanel from './components/Controls/ControlPanel';
import ImpactPanel from './components/Impact/ImpactPanel';
import { useHeatmap } from './hooks/useHeatmap';
import { useStaging } from './hooks/useStaging';
import { useCounterfactual } from './hooks/useCounterfactual';
import { useZoneHistory } from './hooks/useZoneHistory';
import { DEMO_SCENARIOS } from './constants';
import { buildQueryParams } from './utils/queryParams';

const DEFAULT_CONTROLS = {
  date: '2025-10-10',
  hour: 20,
  weather: 'none',
  ambulances: 5,
};

export default function App() {
  const [controls, setControls] = useState(DEFAULT_CONTROLS);
  const [queryControls, setQueryControls] = useState(DEFAULT_CONTROLS);
  const [selectedZone, setSelectedZone] = useState(null);
  const [layerVisibility, setLayerVisibility] = useState({
    heatmap: true,
    staging: true,
    coverage: true,
  });

  const debouncedSetQuery = useMemo(
    () => debounce((c) => setQueryControls(c), 300),
    []
  );

  const handleControlChange = useCallback((key, value) => {
    setControls((prev) => {
      const next = { ...prev, [key]: value };
      debouncedSetQuery(next);
      return next;
    });
  }, [debouncedSetQuery]);

  const handleApplyScenario = useCallback((scenarioKey) => {
    const scenario = DEMO_SCENARIOS[scenarioKey];
    if (!scenario) return;
    const next = {
      date: scenario.date,
      hour: scenario.hour,
      weather: scenario.precipitation > 5 ? 'heavy' : scenario.precipitation > 0 ? 'light' : 'none',
      ambulances: scenario.ambulances,
    };
    setControls(next);
    setQueryControls(next);
  }, []);

  const handleLayerChange = useCallback((key, value) => {
    setLayerVisibility((prev) => ({ ...prev, [key]: value }));
  }, []);

  const handleZoneClick = useCallback((zone) => {
    setSelectedZone((prev) => (prev === zone ? null : zone));
  }, []);

  const params = buildQueryParams(queryControls);

  const { data: heatmapData } = useHeatmap(params);
  const { data: stagingData } = useStaging(params);
  const { data: counterfactualData, isLoading: cfLoading } = useCounterfactual({ hour: params.hour, dow: params.dow });
  const { data: zoneHistoryData } = useZoneHistory(selectedZone);

  const selectedProps = heatmapData?.features?.find((f) => f.properties.zone === selectedZone)?.properties;
  const replay = selectedProps
    ? {
        date: heatmapData.query_params?.date,
        hour: heatmapData.query_params?.hour,
        predicted: selectedProps.predicted_count,
        actual: selectedProps.actual_count ?? null,
      }
    : null;

  return (
    <>
      <Header />
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        <ControlPanel
          controls={controls}
          onControlChange={handleControlChange}
          layerVisibility={layerVisibility}
          onLayerChange={handleLayerChange}
          onApplyScenario={handleApplyScenario}
        />
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', position: 'relative' }}>
          <MapContainer
            heatmapData={heatmapData}
            stagingData={stagingData}
            layerVisibility={layerVisibility}
            selectedZone={selectedZone}
            onZoneClick={handleZoneClick}
            ambulanceCount={controls.ambulances}
          />
          {selectedZone && zoneHistoryData && (
            <ZoneDetailPanel
              data={zoneHistoryData}
              onClose={() => setSelectedZone(null)}
              replay={replay}
            />
          )}
        </div>
      </div>
      <ImpactPanel data={counterfactualData} isLoading={cfLoading} />
    </>
  );
}
