"use client";
import { useState } from 'react';
import { motion } from 'framer-motion';
import { apiFetch } from '@/lib/desktopApi';

const empty = { question: '', findings: '', uncertainty: '', application: '' };
const labels = { question: 'Question', findings: 'Findings (cite source numbers)', uncertainty: 'Uncertainty and disagreements', application: 'One practical application' };
function suggestedFilename(question) {
  const value = question.normalize('NFKD').replace(/[\u0300-\u036f]/g, '').replace(/[^A-Za-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 80).replace(/-$/g, '');
  return !value || /^(con|prn|aux|nul|com[1-9]|lpt[1-9])$/i.test(value) || /^(secrets?|credentials?|tokens?|oauth\d*|client-secrets?|service-accounts?|private-keys?|configs?|settings)(-|$)/i.test(value) ? 'knowledge-note' : value;
}
export default function KnowledgeNoteComposer({ candidates = [] }) {
  const [open, setOpen] = useState(false);
  const [paths, setPaths] = useState('');
  const [sources, setSources] = useState(null);
  const [fields, setFields] = useState(empty);
  const [destination, setDestination] = useState('Library/Notes');
  const [filename, setFilename] = useState('');
  const [filenameEdited, setFilenameEdited] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [receipt, setReceipt] = useState('');
  async function request(operation, body) {
    const response = await apiFetch(`/api/knowledge-notes/${operation}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || 'Knowledge note request failed.');
    return result;
  }
  function changePaths(value) { setPaths(value); setSources(null); setReceipt(''); }
  async function load() {
    if (busy) return;
    setBusy(true); setError(''); setReceipt(''); setSources(null);
    try {
      const result = await request('sources', { paths: paths.split('\n').map(path => path.trim()).filter(Boolean) });
      if (!Array.isArray(result.sources) || !result.sources.length) throw new Error('No selected sources were returned.');
      setSources(result.sources);
    } catch (error) { setError(error.message || 'Sources unavailable.'); }
    finally { setBusy(false); }
  }
  async function save() {
    if (busy || !sources) return;
    setBusy(true); setError('');
    try {
      const result = await request('save', { ...fields, destination, filename, sources: sources.map(({path, sha256}) => ({path, sha256})) });
      if (!result.saved || !result.path) throw new Error('Save could not be verified. Retry the same note.');
      setReceipt(result.path);
    } catch (error) { setError(error.message || 'Save could not be verified. Retry the same note.'); }
    finally { setBusy(false); }
  }
  const choices = candidates.filter(doc => typeof doc.id === 'string' && /\.md$/i.test(doc.id)).slice(0, 10);
  return <section className="rounded border border-white/10 bg-zinc-950/90 p-4 backdrop-blur-md">
    <button type="button" onClick={() => setOpen(value => !value)} aria-expanded={open} className="rounded border border-cyan-400/30 px-3 py-2 text-sm text-cyan-300">{open ? 'Close knowledge note' : 'Create knowledge note'}</button>
    {open && <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mt-4 space-y-3">
      <label className="block text-sm text-white/70">Source Markdown paths (one per line, up to five)<textarea value={paths} onChange={e => changePaths(e.target.value)} disabled={busy} rows={3} maxLength={5120} className="mt-1 w-full rounded border border-white/10 bg-zinc-900 p-2 text-white" /></label>
      {choices.length > 0 && <div className="flex flex-wrap gap-2">{choices.map(doc => <button type="button" key={doc.id} disabled={busy} onClick={() => changePaths([...new Set([...paths.split('\n').filter(Boolean), doc.id])].join('\n'))} className="rounded border border-white/15 px-2 py-1 text-xs text-cyan-200">Add source: {doc.name}</button>)}</div>}
      <button type="button" onClick={load} disabled={busy || !paths.trim()} className="rounded border border-cyan-400/30 px-3 py-2 text-sm text-cyan-300 disabled:opacity-40">{busy ? 'Working…' : 'Load selected sources'}</button>
      {sources && <>
        {sources.map((source, i) => <details open key={source.path} className="text-sm text-white/70"><summary>[{i + 1}] {source.path}</summary><pre className="max-h-64 overflow-auto whitespace-pre-wrap p-2">{source.content}</pre></details>)}
        {Object.entries(labels).map(([key,label]) => <label key={key} className="block text-sm text-white/70">{label}<textarea value={fields[key]} onChange={e => { setFields(previous => ({...previous, [key]: e.target.value})); if (key === 'question' && !filenameEdited) setFilename(suggestedFilename(e.target.value)); setReceipt(''); }} disabled={busy} rows={key === 'findings' ? 5 : 2} maxLength={10000} className="mt-1 w-full rounded border border-white/10 bg-zinc-900 p-2 text-white" /></label>)}
        <label className="block text-sm text-white/70">Destination<select value={destination} onChange={e => { setDestination(e.target.value); setReceipt(''); }} disabled={busy} className="ml-2 rounded bg-zinc-900 p-2"><option>Library/Notes</option><option>Library/Knowledge Notes</option></select></label>
        <label className="block text-sm text-white/70">Filename (letters, numbers, hyphens or underscores)<input value={filename} onChange={e => { setFilename(e.target.value); setFilenameEdited(true); setReceipt(''); }} disabled={busy} maxLength={80} className="mt-1 w-full rounded border border-white/10 bg-zinc-900 p-2" /></label>
        <p className="text-xs text-white/50">References are retained with source digests. Sources are rechecked before saving; existing notes are never overwritten.</p>
        <div className="flex gap-2"><button type="button" onClick={save} disabled={busy || !filename.trim() || Object.values(fields).some(value => !value.trim())} className="rounded bg-cyan-400 px-3 py-2 text-sm font-bold text-zinc-950 disabled:opacity-40">Save knowledge note</button><button type="button" disabled={busy} onClick={() => { setSources(null); setFields(empty); setFilename(''); setFilenameEdited(false); setError(''); setReceipt(''); }} className="px-3 py-2 text-sm text-white/70">Discard note</button></div>
      </>}
      {error && <p role="alert" className="text-sm text-red-300">{error}</p>}
      {receipt && <p role="status" className="text-sm text-cyan-300">Saved: {receipt}</p>}
    </motion.div>}
  </section>;
}
