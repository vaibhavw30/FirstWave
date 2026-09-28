import { WEATHER_PRESETS } from '../constants';
import { dowFromDate, monthFromDate } from './replayDate';

export function buildQueryParams(controls) {
  const preset = WEATHER_PRESETS[controls.weather] || WEATHER_PRESETS.none;
  return {
    date: controls.date,
    hour: controls.hour,
    dow: dowFromDate(controls.date),
    month: monthFromDate(controls.date),
    temperature: preset.temperature,
    precipitation: preset.precipitation,
    windspeed: preset.windspeed,
    ambulances: controls.ambulances,
  };
}
