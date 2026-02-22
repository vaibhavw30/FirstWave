import { useState, useCallback } from 'react';

const DEFAULT_OVERLAYS = {
  equity: false,
};

export function useMapOverlays() {
  const [overlays, setOverlays] = useState(DEFAULT_OVERLAYS);

  const toggleOverlay = useCallback((key) => {
    setOverlays((prev) => {
      if (!(key in prev)) {
        console.warn(`useMapOverlays: unknown overlay key "${key}"`);
        return prev;
      }
      return { ...prev, [key]: !prev[key] };
    });
  }, []);

  const setOverlay = useCallback((key, value) => {
    setOverlays((prev) => {
      if (!(key in prev)) {
        console.warn(`useMapOverlays: unknown overlay key "${key}"`);
        return prev;
      }
      return { ...prev, [key]: value };
    });
  }, []);

  return { overlays, toggleOverlay, setOverlay };
}
