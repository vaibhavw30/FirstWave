import { WEATHER_PRESETS } from '../constants';
import { dowFromDate, monthFromDate } from './replayDate';

export function buildQueryParams(controls) {
  const preset = WEATHER_PRESETS[controls.weather] || WEATHER_PRESETS.none;
  const params = {
    date: controls.date,
    hour: controls.hour,
    dow: dowFromDate(controls.date),
    month: monthFromDate(controls.date),
  };
  // 'actual' sends no weather, so the API replays the hour's real weather.
  if (!preset.actual) {
    params.temperature = preset.temperature;
    params.precipitation = preset.precipitation;
    params.windspeed = preset.windspeed;
  }
  params.ambulances = controls.ambulances;
  return params;
}
