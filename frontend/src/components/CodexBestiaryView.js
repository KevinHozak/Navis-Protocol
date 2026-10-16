"use client";
import React, { useEffect, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import { apiFetch } from '@/lib/desktopApi';

export default function CodexBestiaryView({ selectedBeast, children }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [attempt, setAttempt] = useState(0);
  const selected = useRef(null);
  useEffect(() => {
    const controller = new AbortController();
    setData(null); setError(null);
    apiFetch('/api/battle/bestiary', { signal: controller.signal })
      .then(res => { if (!res.ok) throw new Error(`Bestiary unavailable (${res.status})`); return res.json(); })
      .then(value => { if (!controller.signal.aborted) setData(value); })
      .catch(err => { if (!controller.signal.aborted) setError(err.message); });
    return () => controller.abort();
  }, [attempt]);
  useEffect(() => { selected.current?.scrollIntoView({ block: 'center', behavior: 'smooth' }); }, [data, selectedBeast]);
  return <div className="h-full overflow-y-auto bg-zinc-950 p-6 space-y-6">
    <h2 className="text-2xl font-black text-amber-400">👾 Beast Bestiary</h2>
    {!data && !error && <p role="status">Loading combat history…</p>}
    {error && <div role="alert">{error} <button onClick={() => setAttempt(n => n + 1)} className="text-amber-400 underline">Retry</button></div>}
    {data && <>
      <p className="text-sm text-zinc-400">{data.history_note}</p>
      {selectedBeast && !data.beasts.some(b => b.name === selectedBeast) && <p role="status" className="text-amber-400">No catalog or recorded history for {selectedBeast}.</p>}
      {!data.beasts.length && <p>No beasts cataloged yet.</p>}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {data.beasts.map(beast => <motion.article key={beast.name} ref={beast.name === selectedBeast ? selected : null}
          initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
          className={`p-5 rounded-xl bg-zinc-950/90 backdrop-blur-md border ${beast.name === selectedBeast ? 'border-amber-400' : 'border-white/10'} space-y-3`}>
          <h3 className="text-lg font-bold text-amber-400">{beast.name}</h3>
          <p className="text-sm text-zinc-300">Affinity / strength: {beast.affinity || 'Unknown'}</p>
          <p className="text-sm text-zinc-300">Weaknesses: {Object.entries(beast.vulnerabilities).map(([element, multiplier]) => `${element} ×${multiplier}`).join(', ') || 'None documented'}</p>
          {beast.profile_error && <p className="text-amber-300 text-xs">Elemental profile unavailable</p>}
          <dl className="grid grid-cols-2 gap-2 text-sm text-zinc-300">
            <dt>Encounters</dt><dd>{beast.encounters}</dd>
            <dt>Wins / defeats</dt><dd>{beast.wins} / {beast.defeats}</dd>
            <dt>Win / defeat rate</dt><dd>{beast.win_rate == null ? '—' : `${beast.win_rate}% / ${beast.defeat_rate}%`}</dd>
            <dt>Unresolved</dt><dd>{beast.active}</dd>
            <dt>Total slayings</dt><dd>{beast.slayings}</dd>
            <dt>Best turn damage</dt><dd>{beast.highest_turn_damage}</dd>
          </dl>
          <p className="text-xs text-amber-300">🏆 {beast.trophies.join(' · ') || 'No trophies unlocked'}</p>
        </motion.article>)}
      </div>
    </>}
    {children}
  </div>;
}
