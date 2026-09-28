import { REPLAY_MIN_DATE, REPLAY_MAX_DATE } from '../constants';

// Parse YYYY-MM-DD as a local date (new Date('YYYY-MM-DD') would be UTC midnight).
function parseIsoDate(iso) {
  const [y, m, d] = iso.split('-').map(Number);
  return new Date(y, m - 1, d);
}

export function dowFromDate(iso) {
  return (parseIsoDate(iso).getDay() + 6) % 7; // 0 = Monday
}

export function monthFromDate(iso) {
  return Number(iso.split('-')[1]);
}

export function isReplayDate(iso) {
  return /^\d{4}-\d{2}-\d{2}$/.test(iso) && iso >= REPLAY_MIN_DATE && iso <= REPLAY_MAX_DATE;
}
