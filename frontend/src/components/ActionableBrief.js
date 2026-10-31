"use client";
import { useState } from 'react';
import { apiFetch } from '@/lib/desktopApi';

const fields = ['Goal', 'Known facts', 'Uncertainties', 'One suggested next action'];
export default function ActionableBrief({ entry, date, section, disabled, available }) {
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [savedPath, setSavedPath] = useState('');
  async function request(operation, body) {
    const response = await apiFetch(`/api/journal/brief/${operation}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || 'Brief request failed.');
    return result;
  }
  async function generate() {
    if (busy || disabled) return;
    setBusy(true); setError(''); setSavedPath('');
    const snapshot = { original: entry, date, section };
    try {
      const result = await request('generate', snapshot);
      if (!result.brief || fields.some(field => typeof result.brief[field] !== 'string')) throw new Error('Invalid brief returned. Original unchanged.');
      setPreview({ ...snapshot, brief: result.brief });
    } catch (error) { setError(error.message || 'Brief generation failed. Original unchanged.'); }
    finally { setBusy(false); }
  }
  async function save() {
    if (busy || !preview) return;
    setBusy(true); setError('');
    try {
      const result = await request('save', preview);
      if (!result.saved || !result.path) throw new Error('Save could not be verified; retry the same brief.');
      setSavedPath(result.path); setPreview(null);
    } catch (error) { setError(error.message || 'Save could not be verified; retry the same brief.'); }
    finally { setBusy(false); }
  }
  return <div className="space-y-3 rounded border border-white/10 bg-zinc-950/90 p-3 backdrop-blur-md">
    <button type="button" onClick={generate} disabled={busy || disabled || !available || !entry.trim() || Boolean(preview)} className="rounded border border-accent/30 px-3 py-2 text-xs font-bold text-accent disabled:opacity-40">{busy ? 'Working…' : 'Create actionable brief'}</button>
    <p className="text-xs text-white/50">For complex or tangled notes. When enabled, sends this draft to the configured provider. Review before saving.</p>
    {preview && <div className="space-y-3">
      <details open><summary className="text-sm text-white/70">Original · {preview.date}</summary><pre className="max-h-64 overflow-auto whitespace-pre-wrap text-sm text-white/70">{preview.original}</pre></details>
      {fields.map(field => <label key={field} className="block text-xs text-white/70">{field}<textarea value={preview.brief[field]} disabled={busy} maxLength={5000} rows={3} onChange={event => setPreview(previous => ({ ...previous, brief: { ...previous.brief, [field]: event.target.value } }))} className="mt-1 w-full rounded border border-white/10 bg-zinc-900 p-2 text-sm text-white" /></label>)}
      <p className="text-xs text-white/50">Save retains the original and brief together in Library. Suggestions do not create tasks.</p>
      <div className="flex gap-2"><button type="button" disabled={busy || fields.some(field => !preview.brief[field].trim())} onClick={save} className="rounded bg-accent px-3 py-2 text-xs font-bold text-zinc-950 disabled:opacity-40">Save brief</button><button type="button" disabled={busy} onClick={() => { setPreview(null); setError(''); }} className="px-3 py-2 text-xs text-white/70">Discard brief</button></div>
    </div>}
    {savedPath && <p role="status" className="text-sm text-accent">Saved: {savedPath}</p>}
    {error && <p role="alert" className="text-sm text-red-300">{error}</p>}
  </div>;
}
