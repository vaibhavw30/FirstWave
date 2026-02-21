const STOPS = [
  { t: 0.0, r: 0, g: 137, b: 123 },   // #00897B teal
  { t: 0.3, r: 253, g: 216, b: 53 },   // #FDD835 yellow
  { t: 0.6, r: 251, g: 140, b: 0 },    // #FB8C00 orange
  { t: 1.0, r: 198, g: 40, b: 40 },    // #C62828 red
];

function lerp(a, b, t) {
  return Math.round(a + (b - a) * t);
}

export function intensityColor(value) {
  const v = Math.max(0, Math.min(1, value));
  for (let i = 0; i < STOPS.length - 1; i++) {
    const s0 = STOPS[i], s1 = STOPS[i + 1];
    if (v >= s0.t && v <= s1.t) {
      const t = (v - s0.t) / (s1.t - s0.t);
      const r = lerp(s0.r, s1.r, t);
      const g = lerp(s0.g, s1.g, t);
      const b = lerp(s0.b, s1.b, t);
      return `rgb(${r},${g},${b})`;
    }
  }
  const last = STOPS[STOPS.length - 1];
  return `rgb(${last.r},${last.g},${last.b})`;
}
