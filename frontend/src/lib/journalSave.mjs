import { apiFetch } from './desktopApi';

export function journalPath(day) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(day || '') ||
      Number(day.slice(0, 4)) < 1 || Number.isNaN(Date.parse(`${day}T00:00:00Z`)) ||
      new Date(`${day}T00:00:00Z`).toISOString().slice(0, 10) !== day) {
    throw new Error('Invalid journal date');
  }
  return `Journal/${day.slice(0, 4)}/${day.slice(5, 7)}/${day}.md`;
}

export function verifiedJournalReceipt(result, request) {
  return result?.saved === true && result.date === request.date && result.path === journalPath(request.date) &&
    typeof result.content === 'string' && typeof result.sha256 === 'string' && /^[0-9a-f]{64}$/.test(result.sha256) &&
    typeof result.request_id === 'string' && /^[A-Za-z0-9_-]{16,80}$/.test(result.request_id) &&
    ((result.status === 'success' && result.xp_status === 'complete') ||
     (result.status === 'saved_xp_pending' && result.xp_status === 'pending'));
}

export async function saveJournalEntry(request) {
  journalPath(request.date); // Reject an invalid target before any mutation request.
  // Reuse the exact date/section/entry. The canonical service derives the same
  // durable request identity, even after a lost response or component unmount.
  let response;
  try {
    response = await apiFetch('/api/journal/entry', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(request),
    });
  } catch {
    throw Object.assign(new Error('Save not verified. Review the journal before retrying the same entry.'), { unverified: true });
  }
  if (!response || typeof response.ok !== 'boolean') {
    throw Object.assign(new Error('Save not verified. Review the journal before retrying the same entry.'), { unverified: true });
  }
  if (!response.ok) {
    let code;
    try { code = (await response.json()).detail; } catch { /* Outcome may be committed. */ }
    if ([400, 404, 422].includes(response.status) &&
        ['invalid_argument', 'source_missing', 'section_missing_or_ambiguous', 'source_too_large'].includes(code)) {
      throw new Error('Entry was not saved. Check the journal date, section and entry.');
    }
    throw Object.assign(new Error('Save not verified. Review the journal before retrying the same entry.'), { unverified: true });
  }
  let result;
  try { result = await response.json(); } catch { /* A successful transport is not saved-state proof. */ }
  if (!verifiedJournalReceipt(result, request)) {
    throw Object.assign(new Error('Saved-state verification unavailable. Review the journal before retrying the same entry.'), { unverified: true });
  }
  return result;
}
