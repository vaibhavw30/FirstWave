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

function toIsoDate(d) {
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function addDays(iso, days) {
  const d = parseIsoDate(iso);
  d.setDate(d.getDate() + days);
  return toIsoDate(d);
}

// Same Mon–Sun week as `iso`, on weekday `dow` (0 = Monday); a week later or
// earlier if that falls outside the replay window.
export function dateWithDow(iso, dow) {
  let out = addDays(iso, dow - dowFromDate(iso));
  if (out < REPLAY_MIN_DATE) out = addDays(out, 7);
  if (out > REPLAY_MAX_DATE) out = addDays(out, -7);
  return out;
}

// The AI dispatcher speaks in day-of-week; controls hold a replay date.
export function applyAiControls(prev, partial) {
  const { dow, month, ...rest } = partial;
  const next = { ...prev, ...rest };
  if (dow !== undefined && dow !== null) next.date = dateWithDow(next.date, Number(dow));
  return next;
}
