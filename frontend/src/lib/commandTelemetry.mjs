export const READINESS_CATEGORIES = [
  { key: 'The Sanctum', label: 'Sanctum Integrity' },
  { key: 'The Domestic Breach', label: 'Domestic Readiness' },
  { key: 'The High-Velocity Front', label: 'Frontline Status' },
  { key: 'The Bureaucratic Gauntlet', label: 'Gauntlet Flow' },
  { key: 'The Kinetic Outland', label: 'Outland Mastery' },
];

export function resolveMetric(readinessSource, key, label) {
  if (!readinessSource || typeof readinessSource !== 'object') {
    return null;
  }
  const source =
    readinessSource.readiness && typeof readinessSource.readiness === 'object' && !Array.isArray(readinessSource.readiness)
      ? readinessSource.readiness
      : readinessSource;

  if (Array.isArray(source)) {
    const item = source.find(
      (x) => x?.key === key || x?.manor === key || x?.label === label || x?.name === key || x?.name === label
    );
    if (!item) return null;
    const num = typeof item.value === 'number' ? item.value : (typeof item === 'number' ? item : null);
    if (num !== null && !isNaN(num)) {
      return { value: Math.round(num), color: item.color };
    }
    return null;
  }

  const entry = source[key] ?? source[label] ?? source[key.toLowerCase()] ?? source[label.toLowerCase()];
  if (entry === undefined || entry === null) {
    return null;
  }
  if (typeof entry === 'number' && !isNaN(entry)) {
    return { value: Math.round(entry), color: undefined };
  }
  if (typeof entry === 'object' && typeof entry.value === 'number' && !isNaN(entry.value)) {
    return { value: Math.round(entry.value), color: entry.color };
  }
  return null;
}

export function resolveChronoMarker(status) {
  const date = status?.last_updated || status?.date || status?.chrono_marker || null;
  if (!date || typeof date !== 'string' || !date.trim()) {
    return null;
  }
  return date.trim();
}

export function resolveSpatialAnchor(status) {
  const realm = status?.current_realm || null;
  if (!realm || typeof realm !== 'string' || !realm.trim()) {
    return null;
  }
  return realm.trim();
}

export function resolveResolvedBars(readiness) {
  return READINESS_CATEGORIES.map((cat) => {
    const metric = resolveMetric(readiness, cat.key, cat.label);
    if (!metric) {
      return {
        ...cat,
        available: false,
        value: null,
        barColor: '#71717a',
      };
    }
    const val = Math.max(0, Math.min(100, metric.value));
    let color = metric.color;
    if (!color) {
      if (val < 30) color = '#ef4444';
      else if (val < 70) color = '#eab308';
      else color = '#00d4ff';
    }
    return {
      ...cat,
      available: true,
      value: val,
      barColor: color,
    };
  });
}

export function resolveSystemIntegrity(status, resolvedBars) {
  if (typeof status?.system_integrity === 'number' && !isNaN(status.system_integrity)) {
    return Math.max(0, Math.min(100, Math.round(status.system_integrity)));
  }
  const availableBars = (resolvedBars || []).filter((b) => b.available && typeof b.value === 'number');
  if (availableBars.length > 0) {
    const sum = availableBars.reduce((acc, curr) => acc + curr.value, 0);
    return Math.round(sum / availableBars.length);
  }
  return null;
}
