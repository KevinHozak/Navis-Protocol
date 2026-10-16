export const MAP_WIDTH = 1024;
export const MAP_HEIGHT = 576;
export const MAX_POSITION_AGE_MS = 5 * 60 * 1000;
export const MARKER_STYLES = {
  player: { label: 'Player', color: '#00d4ff' },
  antagonist: { label: 'Antagonist', color: '#ff4d4d' },
  beast: { label: 'Beast', color: '#f59e0b' },
  squad: { label: 'Squad', color: '#a78bfa' }
};

/** Coordinates are explicit canvas pixels, never inferred from realm nodes. */
export function resolveMapTelemetry(status, realm, now = Date.now()) {
  const source = status?.map_telemetry;
  const markers = [];
  const details = [];
  for (const [kind, style] of Object.entries(MARKER_STYLES)) {
    const target = kind === 'antagonist' ? status?.current_antagonist
      : kind === 'beast' ? status?.current_beast : null;
    const active = typeof target === 'string' && target.trim() && target !== 'None';
    const position = source?.[kind];
    let reason;
    if ((kind === 'antagonist' || kind === 'beast') && !active) reason = 'No active target';
    else if (kind === 'squad' && (!Array.isArray(status?.squad) || !status.squad.length)) reason = 'No deployed squad';
    else if (!realm || status?.current_realm !== realm) reason = 'Current realm unavailable or mismatched';
    else if (!position || typeof position !== 'object') reason = 'Position unavailable';
    else if (source?.version !== 1 || source?.coordinate_space !== 'canvas-1024x576') reason = 'Unsupported coordinate contract';
    else if (position.realm !== realm) reason = 'Position belongs to another realm';
    else if (active && position.target !== target) reason = 'Position belongs to another target';
    else if (kind === 'squad' && (!Array.isArray(position.members) ||
      position.members.length !== status.squad.length ||
      !position.members.every((name, i) => typeof name === 'string' && name === status.squad[i]))) reason = 'Position belongs to another squad';
    else if (!Number.isFinite(position.x) || !Number.isFinite(position.y)) reason = 'Malformed coordinates';
    else if (position.x < 0 || position.x > MAP_WIDTH || position.y < 0 || position.y > MAP_HEIGHT) reason = 'Position outside map bounds';
    else {
      const observed = typeof position.observed_at === 'string' && /(?:Z|[+-]\d{2}:\d{2})$/.test(position.observed_at)
        ? Date.parse(position.observed_at) : NaN;
      if (!Number.isFinite(observed)) reason = 'Observation time unavailable';
      else if (observed > now) reason = 'Observation time is in the future';
      else if (now - observed > MAX_POSITION_AGE_MS) reason = 'Position is stale';
    }
    const label = active ? `${style.label}: ${target}` : style.label;
    if (!reason) markers.push({ kind, label, color: style.color, x: position.x, y: position.y });
    details.push({ kind, label, color: style.color, text: reason || `(${position.x}, ${position.y})`, placed: !reason });
  }
  return { markers, details };
}
