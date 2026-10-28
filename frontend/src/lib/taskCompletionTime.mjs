export const DEFAULT_TIMEZONE = 'America/Chicago';
export function navisTimezone(value) {
  if (typeof value !== 'string') return DEFAULT_TIMEZONE;
  try { new Intl.DateTimeFormat('en-US', {timeZone: value || DEFAULT_TIMEZONE}); return value || DEFAULT_TIMEZONE; }
  catch { return DEFAULT_TIMEZONE; }
}
export function completionInstant(value) {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(value) || !Number.isFinite(Date.parse(value))) return null;
  const calendar = new Date(`${value.slice(0, 10)}T00:00:00Z`);
  return calendar.toISOString().slice(0, 10) === value.slice(0, 10) ? value : null;
}
export function completionMetadata(line) {
  const markers = [...line.matchAll(/<!-- navis-completion:(\{[^\r\n]*?\}) -->/g)];
  if (markers.length !== 1) return null;
  try { return completionInstant(JSON.parse(markers[0][1]).completed_at); } catch { return null; }
}
export function formatCompletionTime(value, timezone) {
  const instant = completionInstant(value);
  if (!instant) return 'Completion time unknown';
  return `Completed ${new Intl.DateTimeFormat('en-US', {timeZone: navisTimezone(timezone), year: 'numeric', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', second: '2-digit', timeZoneName: 'short'}).format(new Date(instant))}`;
}
