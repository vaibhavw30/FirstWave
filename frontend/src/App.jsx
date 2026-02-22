import { useState, useCallback, useMemo, useEffect } from 'react';
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
import { DEMO_SCENARIOS, WEATHER_PRESETS } from './constants';
import AiPanel from './components/Chat/AiPanel';
import { useMapOverlays } from './hooks/useMapOverlays';

const DEFAULT_CONTROLS = {
  hour: 20,
  dow: 4,
  month: 10,
  weather: 'none',
  ambulances: 5,
};

function resolveWeather(controls) {
  const preset = WEATHER_PRESETS[controls.weather] || WEATHER_PRESETS.none;
  return {
    hour: controls.hour,
    dow: controls.dow,
    month: controls.month,
    temperature: preset.temperature,
    precipitation: preset.precipitation,
    windspeed: preset.windspeed,
    ambulances: controls.ambulances,
  };
}

export default function App() {
  const [controls, setControls] = useState(DEFAULT_CONTROLS);
  const [queryControls, setQueryControls] = useState(DEFAULT_CONTROLS);
  const [selectedZone, setSelectedZone] = useState(null);
  const [layerVisibility, setLayerVisibility] = useState({
    heatmap: true,
    staging: true,
    coverage: true,
    stations: false,
  });
  const [isPlaying, setIsPlaying] = useState(false);
  const { overlays, toggleOverlay } = useMapOverlays();

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
      hour: scenario.hour,
      dow: scenario.dow,
      month: scenario.month,
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

  // "Watch the Wave" — advance hour every 1.5s, stop when reaching hour 23
  useEffect(() => {
    if (!isPlaying) return;
    const id = setInterval(() => {
      setControls((prev) => {
        const nextHour = prev.hour >= 23 ? 23 : prev.hour + 1;
        const next = { ...prev, hour: nextHour };
        setQueryControls(next);
        return next;
      });
      // Check if we've reached 23 to stop (read outside updater to avoid nesting)
    }, 1500);
    return () => clearInterval(id);
  }, [isPlaying]);

  // Stop animation when hour reaches 23
  useEffect(() => {
    if (isPlaying && controls.hour >= 23) {
      setIsPlaying(false);
    }
  }, [controls.hour, isPlaying]);

  const handleTogglePlay = useCallback(() => setIsPlaying((p) => !p), []);

  const handleAiControlsUpdate = useCallback((partial) => {
    setControls((prev) => {
      const resolved = { ...prev, ...partial };
      setQueryControls(resolved);
      return resolved;
    });
  }, []);

  const params = resolveWeather(queryControls);

  const { data: heatmapData } = useHeatmap(params);
  const { data: stagingData } = useStaging(params);
  const { data: counterfactualData, isLoading: cfLoading } = useCounterfactual(params);
  const { data: zoneHistoryData } = useZoneHistory(selectedZone);

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
          isPlaying={isPlaying}
          onTogglePlay={handleTogglePlay}
        />
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', position: 'relative' }}>
          <MapContainer
            heatmapData={heatmapData}
            stagingData={stagingData}
            layerVisibility={layerVisibility}
            selectedZone={selectedZone}
            onZoneClick={handleZoneClick}
            ambulanceCount={controls.ambulances}
            counterfactualByZone={counterfactualData?.by_zone}
            overlays={overlays}
          />
          {selectedZone && zoneHistoryData && (
            <ZoneDetailPanel
              data={zoneHistoryData}
              onClose={() => setSelectedZone(null)}
              counterfactualData={counterfactualData}
            />
          )}
          <AiPanel
            heatmapData={heatmapData}
            counterfactualData={counterfactualData}
            controls={controls}
            onControlsUpdate={handleAiControlsUpdate}
          />
        </div>
      </div>
      <ImpactPanel data={counterfactualData} isLoading={cfLoading} selectedBorough={zoneHistoryData?.borough || null} overlays={overlays} toggleOverlay={toggleOverlay} />
    </>
  );
}
