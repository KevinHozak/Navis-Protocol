"use client";
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import { apiFetch, subscribeVaultStream } from '@/lib/desktopApi';
import { completionInstant, formatCompletionTime, navisTimezone } from '../lib/taskCompletionTime.mjs';

const AREAS = [['sanctum', 'Sanctum'], ['domestic', 'Domestic'], ['front', 'Front'], ['bureaucratic', 'Gauntlet'], ['world', 'Outland'], ['unassigned', 'Unassigned']];

export default function CompletedToday({ onBack, onOpenJournal }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [area, setArea] = useState('all');
  const [search, setSearch] = useState('');
  const revision = useRef(0);
  const refresh = useCallback(async () => {
    const request = ++revision.current;
    setLoading(true); setError(''); setData(null);
    try {
      const response = await apiFetch('/api/tasks/completed-today', {signal: AbortSignal.timeout(30000)});
      if (!response.ok) throw new Error('Completion evidence unavailable. Retry.');
      const value = await response.json();
      const validEntry = item => item && typeof item.id === 'string' && typeof item.text === 'string'
        && AREAS.some(([id]) => id === item.area) && typeof item.source?.path === 'string'
        && item.source.path.startsWith('Journal/') && !item.source.path.split('/').some(part => part === '..' || part === '.')
        && Number.isInteger(item.source.line_number) && item.source.line_number > 0;
      if (!['complete', 'empty', 'partial', 'unavailable'].includes(value.status)
          || typeof value.timezone !== 'string' || navisTimezone(value.timezone) !== value.timezone
          || !Array.isArray(value.completed) || !Array.isArray(value.journal_evidence) || !Array.isArray(value.issues)
          || value.completed.some(item => !validEntry(item) || !completionInstant(item.completed_at))
          || value.journal_evidence.some(item => !validEntry(item))
          || value.issues.some(item => typeof item.path !== 'string' || typeof item.reason !== 'string')) {
        throw new Error('Completion evidence returned an invalid response. Retry.');
      }
      if (request === revision.current) setData(value);
    } catch (failure) {
      if (request === revision.current) setError(failure.message || 'Completion evidence unavailable. Retry.');
    } finally {
      if (request === revision.current) setLoading(false);
    }
  }, []);
  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, 60000);
    let pending;
    const unsubscribe = subscribeVaultStream(() => {
      clearTimeout(pending); pending = setTimeout(refresh, 250);
    });
    return () => { ++revision.current; clearInterval(timer); clearTimeout(pending); unsubscribe(); };
  }, [refresh]);
  const filtered = items => items.filter(item => (area === 'all' || item.area === area)
    && item.text.toLowerCase().includes(search.toLowerCase()));
  const renderGroups = (items, unknown = false) => AREAS.map(([identity, label]) => {
    const rows = filtered(items).filter(item => item.area === identity);
    return rows.length ? <section key={identity} aria-label={`${label}${unknown ? ' journal evidence' : ' completions'}`} className="space-y-2">
      <h3 className="text-sm font-bold text-cyan-300">{label} <span className="text-white/40">({rows.length})</span></h3>
      {rows.map(item => <article key={item.id} className="rounded-xl border border-white/10 bg-zinc-950/90 p-4 backdrop-blur-md">
        <p className="text-sm text-white/90">{item.text}</p>
        {unknown ? <p className="mt-1 text-xs text-amber-200/70">Completion time unknown · journal {item.source.journal_date}</p>
          : <time dateTime={item.completed_at} className="mt-1 block text-xs text-white/50">{formatCompletionTime(item.completed_at, data.timezone)}</time>}
        <button type="button" disabled={!onOpenJournal} onClick={() => onOpenJournal?.(item.source.path, item.source.journal_date)}
          className="mt-2 text-xs text-cyan-400 underline underline-offset-4 focus-visible:outline focus-visible:outline-2" aria-label={`Open source ${item.source.path} line ${item.source.line_number}`}>
          Open source · {item.source.journal_date || item.source.path} · line {item.source.line_number}
        </button>
      </article>)}
    </section> : null;
  });
  return <motion.div initial={{opacity:0}} animate={{opacity:1}} className="flex h-full flex-col overflow-hidden rounded-xl border border-white/10 bg-zinc-950/90 backdrop-blur-md">
    <header className="shrink-0 space-y-3 border-b border-white/10 p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div><h1 className="text-xl font-bold text-white">Completed today</h1>
          {data?.date && <p className="text-xs text-cyan-400">{data.date} · {data.timezone} · calendar day</p>}</div>
        <div className="flex gap-2"><button type="button" onClick={refresh} disabled={loading} className="rounded border border-cyan-400/30 px-3 py-2 text-xs text-cyan-300">Refresh</button>
          <button type="button" onClick={onBack} className="rounded border border-white/10 px-3 py-2 text-xs text-white/60">Back to directives</button></div>
      </div>
      <div className="flex flex-wrap gap-3">
        <select aria-label="Operation area" value={area} onChange={event => setArea(event.target.value)} className="rounded border border-white/10 bg-zinc-950 px-2 py-1 text-sm text-white">
          <option value="all">All areas</option>{AREAS.map(([id, label]) => <option key={id} value={id}>{label}</option>)}
        </select>
        <input aria-label="Filter completed entries" placeholder="Filter entries" value={search} onChange={event => setSearch(event.target.value)} className="rounded border border-white/10 bg-zinc-950 px-3 py-1 text-sm text-white" />
      </div>
    </header>
    <div className="flex-1 space-y-5 overflow-y-auto p-5">
      {loading && <p role="status" className="text-cyan-300">Loading completion evidence…</p>}
      {error && <p role="alert" className="text-red-300">{error}</p>}
      {data?.status === 'unavailable' && <p role="alert" className="text-red-300">Completion evidence unavailable. Check the source and retry.</p>}
      {data?.status === 'partial' && <p role="alert" className="text-amber-200">Partial results. Some sources could not be included.</p>}
      {data?.issues?.length > 0 && <details className="text-xs text-amber-200/70"><summary>Coverage details</summary><ul>{data.issues.map((issue, index) => <li key={index}>{issue.path}: {issue.reason.replaceAll('_', ' ')}</li>)}</ul></details>}
      {data && data.status !== 'unavailable' && <>
        <section aria-label="Timestamped task completions" className="space-y-4">
          <h2 className="text-sm font-bold text-white">Timestamped completions ({filtered(data.completed).length})</h2>
          {!filtered(data.completed).length && <p className="text-sm text-white/50">{data.status === 'partial' ? 'No matching completions in the available sources.' : 'No matching completions today.'}</p>}
          {renderGroups(data.completed)}
        </section>
        <section aria-label="Unknown-time journal evidence" className="space-y-4 border-t border-white/10 pt-4">
          <h2 className="text-sm font-bold text-amber-100">Journal-day evidence ({filtered(data.journal_evidence).length})</h2>
          <p className="text-xs text-white/50">Checked items with unknown completion time may include activity logs. They are not counted as completed today.</p>
          {renderGroups(data.journal_evidence, true)}
        </section>
      </>}
    </div>
  </motion.div>;
}
