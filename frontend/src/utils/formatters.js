export function formatSeconds(sec) {
  if (sec == null || isNaN(sec)) return '—';
  const m = Math.floor(sec / 60);
  const s = Math.round(sec % 60);
  return `${m} min ${s} sec`;
}

export function formatHour(h) {
  if (h === 0) return '12:00 AM';
  if (h === 12) return '12:00 PM';
  if (h < 12) return `${h}:00 AM`;
  return `${h - 12}:00 PM`;
}

export function formatPct(val) {
  if (val == null || isNaN(val)) return '—';
  return `${val.toFixed(1)}%`;
}
