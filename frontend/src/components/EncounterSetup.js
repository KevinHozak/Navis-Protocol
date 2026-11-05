"use client";
import React, { useEffect, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import { apiFetch } from '../lib/desktopApi';

export default function EncounterSetup({ battle }) {
  const [catalog, setCatalog] = useState(null);
  const [enemyId, setEnemyId] = useState('');
  const [review, setReview] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const inFlight = useRef(false);
  useEffect(() => {
    let ignore = false;
    apiFetch('/api/battle/encounters').then(async response => {
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Could not load encounter choices.');
      if (!ignore) setCatalog(data);
    }).catch(error => { if (!ignore) setError(error.message); });
    return () => { ignore = true; };
  }, [battle]);

  async function request(confirm) {
    if (inFlight.current) return;
    inFlight.current = true;
    setBusy(true); setError(''); setMessage('');
    try {
      const response = await apiFetch(confirm ? '/api/battle/encounter' : '/api/battle/encounter/preview', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enemy_id: enemyId, ...(confirm ? { preview_token: review.preview_token } : {}) }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || 'Encounter setup failed. Review again before retrying.');
      if (confirm) {
        setReview(null);
        setMessage(`Encounter with ${enemyId} started.`);
      } else setReview(data);
    } catch (error) { setError(error.message); }
    finally { inFlight.current = false; setBusy(false); }
  }

  const enemy = review?.encounter.enemies[0];
  return <motion.section initial={{ opacity: 0 }} animate={{ opacity: 1 }} aria-labelledby="encounter-setup-title"
    className="mb-6 p-5 bg-zinc-950/90 backdrop-blur-md border border-white/10 rounded-xl text-sm">
    <h3 id="encounter-setup-title" className="font-bold text-red-400 mb-3">Set up an encounter</h3>
    {!catalog && !error && <p role="status">Loading encounter choices…</p>}
    {catalog?.blocked && <p role="status" className="text-amber-400 mb-3">{catalog.blocked}</p>}
    <label htmlFor="encounter-enemy" className="block text-zinc-300 mb-2">Enemy</label>
    <select id="encounter-enemy" value={enemyId} disabled={!catalog || !!catalog.blocked || busy}
      onChange={event => { setEnemyId(event.target.value); setReview(null); setError(''); setMessage(''); }}
      className="w-full sm:w-auto max-w-full bg-zinc-900 border border-white/20 rounded p-2 text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan-400">
      <option value="">Choose an existing enemy</option>
      {catalog?.candidates.map(row => <option key={row.enemy_id} value={row.enemy_id} disabled={!!row.unavailable}>{row.name}{row.unavailable ? ' — unavailable' : ''}</option>)}
    </select>
    <button type="button" disabled={!enemyId || !!catalog?.blocked || busy} onClick={() => request(false)}
      className="sm:ml-3 mt-3 sm:mt-0 px-4 py-2 rounded border border-cyan-400/40 text-cyan-300 disabled:opacity-40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan-400">Preview encounter</button>
    {catalog?.candidates.length === 0 && <p className="mt-3 text-zinc-400">No enemies found. Add a combat profile before starting an encounter.</p>}
    {catalog?.candidates.some(row => row.unavailable) && <details className="mt-3 text-zinc-400"><summary>Unavailable enemies</summary>
      <ul>{catalog.candidates.filter(row => row.unavailable).map(row => <li key={row.enemy_id}>{row.name}: {row.unavailable}</li>)}</ul>
    </details>}
    {enemy && <div className="mt-4 border-t border-white/10 pt-4" aria-label="Encounter preview">
      <h4 className="font-bold text-white">Review: {enemy.id}</h4>
      <p className="text-zinc-300">Enemy HP {enemy.hp} · Attack {enemy.attack} · {enemy.affinity}</p>
      <p className="text-zinc-300">Intent sequence: {enemy.intent_pattern.join(' → ')}</p>
      <p className="text-zinc-300">Keeper HP 100 · Base AP per turn 2 · Turn 1</p>
      {Object.entries(enemy.vulnerabilities).map(([element, multiplier]) => <p key={element} className="text-amber-400">Weakness: {element} · XP ×{multiplier}</p>)}
      <p className="mt-2 text-zinc-400">Confirmation starts this encounter. Cards, tasks and XP stay as they are. Active encounters must finish before another can start.</p>
      <div className="flex flex-wrap gap-3 mt-3">
        <button type="button" disabled={busy || !!catalog?.blocked} onClick={() => request(true)} className="px-4 py-2 rounded border border-red-400/50 text-red-300 disabled:opacity-40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan-400">Confirm and start encounter</button>
        <button type="button" disabled={busy} onClick={() => setReview(null)} className="px-4 py-2 rounded border border-white/20 text-zinc-300">Dismiss preview</button>
      </div>
    </div>}
    {busy && <p role="status" className="mt-3 text-cyan-300">Checking encounter…</p>}
    {error && <p role="alert" className="mt-3 text-red-300">{error}</p>}
    {message && <p role="status" className="mt-3 text-cyan-300">{message}</p>}
  </motion.section>;
}
