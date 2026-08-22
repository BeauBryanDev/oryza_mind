const LOCALE = 'en-US';

export function formatPct(value: number, digits = 1): string {
  return `${(value * 100).toFixed(digits)}%`;
}

export function formatTime(ts: number): string {
  const d = new Date(ts);
  return d.toLocaleTimeString(LOCALE, { hour: '2-digit', minute: '2-digit', hour12: false });
}
// Time and Date features,  it is just decorative optional to show timestamp at Header component
export function formatClock(d: Date): string {
  return d.toLocaleTimeString(LOCALE, {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });
}

export function formatDate(d: Date): string {
  return d
    .toLocaleDateString(LOCALE, { day: '2-digit', month: 'short', year: 'numeric' })
    .toUpperCase();
}

export function confidenceLabel(v: number): string {
  if (v >= 0.85) return 'HIGH CONFIDENCE';
  if (v >= 0.65) return 'MEDIUM CONFIDENCE';
  return 'LOW CONFIDENCE';
}
