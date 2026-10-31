"use client";

import { useState, useRef, useEffect } from 'react';
import { apiFetch, supportsLocalOllama } from '@/lib/desktopApi';
import ActionableBrief from './ActionableBrief';
import { saveJournalEntry } from '@/lib/journalSave.mjs';

const JOURNAL_SECTIONS = [
  { value: 'sanctum', label: '🏰 The Sanctum' },
  { value: 'domestic', label: '🏠 The Domestic Breach' },
  { value: 'front', label: '⚔️ The High-Velocity Front' },
  { value: 'gauntlet', label: '⚖️ The Bureaucratic Gauntlet' },
  { value: 'outland', label: '🥾 The Kinetic Outland' },
];

export default function JournalEntryComposer({ date, onSaved, onUnverified, initialDraft, savedReceipt }) {
  const [isOpen, setIsOpen] = useState(Boolean(initialDraft?.entry));
  const [section, setSection] = useState(initialDraft?.section || 'sanctum');
  const [entry, setEntry] = useState(initialDraft?.entry || '');
  const [saving, setSaving] = useState(false);
  const savePending = useRef(false);
  const [polishing, setPolishing] = useState(false);
  const [originalEntry, setOriginalEntry] = useState(null);
  const [error, setError] = useState('');
  const canSuggestLocally = supportsLocalOllama();
  const draftRef = useRef(null);
  draftRef.current = { entry, section };
  useEffect(() => {
    if (!savedReceipt?.verified || savedReceipt.xp_status !== 'complete' || savedReceipt.date !== date) return;
    setError(previous => previous.startsWith('Entry saved. XP sync is pending') ? '' : previous);
    if (savedReceipt.request?.entry === draftRef.current.entry && savedReceipt.request?.section === draftRef.current.section) {
      setEntry('');
      setOriginalEntry(null);
      setIsOpen(false);
    }
  }, [savedReceipt, date]);

  const polishEntry = async () => {
    if (savePending.current || saving || polishing || !entry.trim()) return;
    setOriginalEntry((original) => original ?? entry);
    setPolishing(true);
    setError('');
    try {
      const response = await apiFetch('/api/journal/entry/polish', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ entry, section }),
      });
      if (!response.ok) {
        let message = await response.text();
        try {
          message = JSON.parse(message).detail || message;
        } catch {
          // Keep the raw response text for non-JSON errors.
        }
        throw new Error(message || 'Journal entry could not be polished.');
      }
      const result = await response.json();
      if (!result.suggestion?.trim()) throw new Error('Configured provider returned an empty suggestion.');
      setEntry(result.suggestion);
    } catch (polishError) {
      setError(polishError instanceof TypeError
        ? 'Could not reach the local journal polishing service. Your draft is unchanged.'
        : (polishError.message || 'Journal entry could not be polished. Your draft is unchanged.'));
    } finally {
      setPolishing(false);
    }
  };

  const saveEntry = async (event) => {
    event.preventDefault();
    if (savePending.current || saving || polishing || !entry.trim()) return;

    savePending.current = true;
    setSaving(true);
    setError('');
    const request = { date, section, entry };
    try {
      const result = await saveJournalEntry(request);
      onSaved?.(result, request);
      if (result.xp_status === 'pending') {
        setError('Entry saved. XP sync is pending; save this same entry again to retry without adding a duplicate.');
        return;
      }
      setEntry('');
      setOriginalEntry(null);
      setIsOpen(false);
    } catch (saveError) {
      if (saveError.unverified) onUnverified?.(request);
      setError(saveError.message || 'Journal entry could not be saved.');
    } finally {
      savePending.current = false;
      setSaving(false);
    }
  };

  return (
    <section className="mb-6 rounded border border-accent/20 bg-zinc-950/70 backdrop-blur-md">
      <div className="flex items-center justify-between gap-4 p-4">
        <div>
          <h2 className="text-sm font-bold uppercase tracking-wider text-white">Journal Entry</h2>
          <p className="mt-1 text-xs text-white/45">Add an entry to {date || 'the selected journal date'}.</p>
        </div>
        <button
          type="button"
          onClick={() => { setIsOpen((open) => !open); setError(''); }}
          className="rounded border border-accent/30 bg-accent/10 px-3 py-2 text-xs font-bold text-accent transition hover:bg-accent/20"
          aria-expanded={isOpen}
        >
          {isOpen ? 'Close' : '+ Add Entry'}
        </button>
      </div>

      {isOpen && (
        <form onSubmit={saveEntry} className="space-y-3 border-t border-white/10 p-4">
          <label className="block text-xs font-semibold text-white/70">
            Journal section
            <select
              value={section}
              onChange={(event) => setSection(event.target.value)}
              disabled={saving || polishing}
              className="mt-1.5 w-full rounded border border-white/10 bg-zinc-900 px-3 py-2 text-sm text-white outline-none focus:border-accent/50"
            >
              {JOURNAL_SECTIONS.map((item) => (
                <option key={item.value} value={item.value}>{item.label}</option>
              ))}
            </select>
          </label>

          <label className="block text-xs font-semibold text-white/70">
            Entry
            <textarea
              value={entry}
              onChange={(event) => setEntry(event.target.value)}
              disabled={saving || polishing}
              required
              rows={4}
              maxLength={10000}
              placeholder="Write an entry; it will be saved as a checked list item."
              className="mt-1.5 w-full resize-y rounded border border-white/10 bg-zinc-900 px-3 py-2 text-sm leading-relaxed text-white placeholder:text-white/25 outline-none focus:border-accent/50"
            />
          </label>

          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={polishEntry}
              disabled={saving || polishing || !entry.trim()}
              className="rounded border border-accent/30 bg-accent/10 px-3 py-2 text-xs font-bold text-accent transition hover:bg-accent/20 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {polishing ? 'Polishing with configured AI...' : canSuggestLocally ? 'Polish with AI' : 'Suggestions unavailable'}
            </button>
            {originalEntry !== null && (
              <button
                type="button"
                onClick={() => {
                  setEntry(originalEntry);
                  setOriginalEntry(null);
                  setError('');
                }}
                disabled={saving || polishing}
                className="rounded border border-white/15 px-3 py-2 text-xs font-semibold text-white/70 transition hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-40"
              >
                Restore original draft
              </button>
            )}
            <span className="text-xs text-white/40">{canSuggestLocally ? 'When enabled, sends this draft to the configured provider. Suggestions are not saved automatically.' : 'Configured text suggestions require the desktop app or a local Navis server.'}</span>
          </div>

          <ActionableBrief entry={entry} date={date} section={section} disabled={saving || polishing} available={canSuggestLocally} />

          {error && <p role="alert" className="text-sm text-red-300">{error}</p>}

          <div className="flex justify-end">
            <button
              type="submit"
              disabled={saving || polishing || !entry.trim()}
              className="rounded bg-accent px-4 py-2 text-xs font-black uppercase tracking-wider text-zinc-950 transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {saving ? 'Saving…' : 'Save Entry'}
            </button>
          </div>
        </form>
      )}
    </section>
  );
}
