"use client";

import React, { useEffect, useRef, useState } from 'react';
import { apiFetch } from '@/lib/desktopApi';

export default function HolocronEvidence({ weekId, evidence, onOpenJournal }) {
  const [inspection, setInspection] = useState(null);
  const revision = useRef(0);
  useEffect(() => { revision.current += 1; setInspection(null); return () => { revision.current += 1; }; }, [weekId, evidence]);
  const inspect = async (source) => {
    const request = ++revision.current;
    setInspection({ status: 'loading' });
    try {
      const response = await apiFetch(`/api/holocron/weekly/${encodeURIComponent(weekId)}/evidence/${encodeURIComponent(source.id)}`);
      if (!response.ok) throw new Error('unavailable');
      const value = await response.json();
      if (request !== revision.current) return;
      const changed = source.fingerprint && value.fingerprint !== source.fingerprint && value.status === 'available';
      setInspection({ ...value, status: changed ? 'changed; regenerate this cycle' : value.status });
    } catch {
      if (request === revision.current) setInspection({ status: 'unavailable' });
    }
  };
  return (
    <section className="p-5 rounded-xl border border-white/10 bg-zinc-950/90 backdrop-blur-md space-y-3">
      <h2 className="text-sm font-bold text-cyan-300">Evidence &amp; rules</h2>
      <p className="text-xs text-zinc-400">{evidence?.start_date} – {evidence?.end_date} · {evidence?.logged_days ?? 0}/7 readable journal days</p>
      {!evidence && <p>Evidence unavailable. Regenerate this cycle.</p>}
      {Object.entries(evidence?.metrics || {}).map(([key, metric]) => (
        <details key={key} className="text-xs text-zinc-300">
          <summary className="cursor-pointer">{key.replaceAll('_', ' ')} · {metric.status}</summary>
          <p className="py-2">{metric.rule}</p>
          <div className="flex flex-wrap gap-2">{metric.source_ids.map(id => {
            const source = evidence.sources.find(item => item.id === id);
            return source && <button type="button" key={id} onClick={() => inspect(source)} className="text-cyan-300 underline">Inspect {source.date || source.label || id}</button>;
          })}</div>
        </details>
      ))}
      <details className="text-xs text-zinc-400"><summary>Source coverage</summary>
        {evidence?.sources?.map(source => <div key={source.id}>{source.date || source.label}: {source.status}</div>)}
      </details>
      {inspection && <div role="status" className="text-xs text-amber-200">
        Source: {inspection.date || inspection.id || ''} · {inspection.status}
        {inspection.counts && <span> · {inspection.counts.completed}/{inspection.counts.total} checked items</span>}
        {inspection.total_xp != null && <span> · {inspection.total_xp} signed Keeper XP</span>}
        {inspection.status === 'available' && /^Journal\/(?:\d{4}\/\d{2}\/)?\d{4}-\d{2}-\d{2}\.md$/.test(inspection.path || '') && onOpenJournal && (
          <button type="button" className="block text-cyan-300 underline" onClick={() => onOpenJournal(inspection.path, inspection.date)}>Open source journal</button>
        )}
      </div>}
      <p className="text-xs text-zinc-500">References support metric inputs, not AI interpretations. Exports retain a source-status snapshot.</p>
    </section>
  );
}
