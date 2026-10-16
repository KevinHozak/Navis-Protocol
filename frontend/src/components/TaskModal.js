"use client";

import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { journalDay } from '@/lib/journalDay';
import { apiFetch } from '@/lib/desktopApi';

const MANOR_OPTIONS = [
  { id: 'Sanctum', label: 'The Sanctum', icon: '🏰' },
  { id: 'Domestic', label: 'The Domestic Breach', icon: '🏠' },
  { id: 'Front', label: 'The High-Velocity Front', icon: '⚔️' },
  { id: 'Gauntlet', label: 'The Bureaucratic Gauntlet', icon: '⚖️' },
  { id: 'Outland', label: 'The Kinetic Outland', icon: '🧭' },
];

const RECURRENCE_PRESETS = [
  { id: 'daily', label: 'Daily' },
  { id: 'weekly', label: 'Weekly' },
  { id: 'every 2 weeks', label: 'Bi-Weekly (2 weeks)' },
  { id: 'monthly', label: 'Monthly' },
  { id: 'yearly', label: 'Yearly' },
];

const SUGGESTED_LABELS = ['@comm', '@tech', '@dev', '@ops', '@admin', '@health', '@finance'];

function addDaysToDateStr(dateStr, days) {
  const [y, m, d] = dateStr.split('-').map(Number);
  const date = new Date(y, m - 1, d);
  date.setDate(date.getDate() + days);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

export default function TaskModal({
  isOpen,
  onClose,
  initialTask = null,
  onTaskSaved,
  defaultArea = 'Sanctum',
  defaultDueDate = '',
}) {
  const isEditing = Boolean(initialTask?.id);
  const [text, setText] = useState('');
  const [description, setDescription] = useState('');
  const [priority, setPriority] = useState(4);
  const [dueDate, setDueDate] = useState('');
  const [area, setArea] = useState('Sanctum');
  const [isRecurring, setIsRecurring] = useState(false);
  const [frequency, setFrequency] = useState('daily');
  const [labels, setLabels] = useState([]);
  const [labelInput, setLabelInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Sync state when modal opens or initialTask changes
  useEffect(() => {
    if (isOpen) {
      if (initialTask) {
        setText(initialTask.text || '');
        setDescription(initialTask.description || '');
        setPriority(initialTask.priority ? Number(initialTask.priority) : 4);
        setDueDate(initialTask.due_date || initialTask.next_due || '');
        setArea(initialTask.area || defaultArea);
        const recurring = Boolean(initialTask.frequency);
        setIsRecurring(recurring);
        setFrequency(initialTask.frequency || 'daily');
        setLabels(Array.isArray(initialTask.labels) ? [...initialTask.labels] : []);
      } else {
        setText('');
        setDescription('');
        setPriority(4);
        setDueDate(defaultDueDate || journalDay());
        setArea(defaultArea);
        setIsRecurring(false);
        setFrequency('daily');
        setLabels([]);
      }
      setLabelInput('');
      setError('');
      setLoading(false);
    }
  }, [isOpen, initialTask, defaultArea, defaultDueDate]);

  // Handle ESC key to close modal
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && isOpen && !loading) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, loading, onClose]);

  if (!isOpen) return null;

  const handleAddLabel = (rawTag) => {
    const tag = (rawTag || labelInput).trim();
    if (!tag) return;
    const formatted = tag.startsWith('@') ? tag.toLowerCase() : `@${tag.toLowerCase()}`;
    if (!labels.includes(formatted)) {
      setLabels([...labels, formatted]);
    }
    setLabelInput('');
  };

  const handleRemoveLabel = (tagToRemove) => {
    setLabels(labels.filter((t) => t !== tagToRemove));
  };

  const handleLabelKeyDown = (e) => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault();
      handleAddLabel();
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!text.trim()) {
      setError('Directive text is required');
      return;
    }
    setError('');
    setLoading(true);

    try {
      const todayStr = journalDay();
      const payloadDate = dueDate ? dueDate : isRecurring ? todayStr : null;

      if (isRecurring) {
        if (isEditing) {
          const res = await apiFetch(`/api/recurring/${encodeURIComponent(initialTask.id)}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              text: text.trim(),
              area,
              frequency,
              due_date: payloadDate,
              priority: Number(priority),
              labels,
              description,
            }),
          });
          if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            throw new Error(errData.detail || 'Failed to update recurring mandate');
          }
          const data = await res.json();
          onTaskSaved?.(data.task || data);
        } else {
          const res = await apiFetch('/api/recurring', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              text: text.trim(),
              area,
              frequency,
              due_date: payloadDate,
              next_due: payloadDate,
              priority: Number(priority),
              labels,
              description,
            }),
          });
          if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            throw new Error(errData.detail || 'Failed to create recurring mandate');
          }
          const data = await res.json();
          onTaskSaved?.(data.task || data);
        }
      } else {
        // Active task
        if (isEditing) {
          const res = await apiFetch(`/api/active_tasks/${encodeURIComponent(initialTask.id)}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              text: text.trim(),
              area,
              priority: Number(priority),
              due_date: payloadDate,
              labels,
              description,
            }),
          });
          if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            throw new Error(errData.detail || 'Failed to update active directive');
          }
          const data = await res.json();
          onTaskSaved?.(data.task || data);
        } else {
          const res = await apiFetch('/api/active_tasks', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              text: text.trim(),
              area,
              priority: Number(priority),
              due_date: payloadDate,
              labels,
              description,
            }),
          });
          if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            throw new Error(errData.detail || 'Failed to create active directive');
          }
          const data = await res.json();
          onTaskSaved?.(data.task || data);
        }
      }

      onClose();
    } catch (err) {
      console.error('Error submitting directive:', err);
      setError(err.message || 'Operation failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const todayStr = journalDay();

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="task-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md"
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 10 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 10 }}
        transition={{ duration: 0.15 }}
        className="w-full max-w-2xl bg-zinc-950 border border-white/10 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/10 bg-zinc-900/60">
          <div className="flex items-center gap-3">
            <span className="text-xl">📋</span>
            <div>
              <h2 id="task-modal-title" className="text-sm font-bold uppercase tracking-wider text-white">
                {isEditing ? 'Edit Directive' : 'Deploy New Directive'}
              </h2>
              <p className="text-[10px] font-mono uppercase tracking-widest text-cyan-400/70">
                {isRecurring ? 'Recurring Operational Mandate' : 'Active Tactical Directive'}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={loading}
            className="w-8 h-8 rounded-lg flex items-center justify-center text-white/50 hover:text-white hover:bg-white/10 transition-colors"
            title="Close (Esc)"
          >
            ✕
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto p-6 space-y-5 custom-scrollbar">
          {error && (
            <div role="alert" className="p-3 bg-red-950/40 border border-red-500/40 rounded-xl text-xs text-red-300">
              ⚠️ {error}
            </div>
          )}

          {/* Title */}
          <div className="space-y-1.5">
            <label className="text-[10px] font-bold uppercase tracking-widest text-cyan-400">
              Directive Title <span className="text-red-400">*</span>
            </label>
            <input
              type="text"
              required
              disabled={loading}
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="e.g. Calibrate optical link array in Friðr Hall"
              className="w-full bg-black/60 border border-white/15 rounded-xl px-4 py-2.5 text-sm text-white focus:border-cyan-400 focus:outline-none transition-colors"
            />
          </div>

          {/* Priority & Manor Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Priority Selector */}
            <div className="space-y-1.5">
              <label className="text-[10px] font-bold uppercase tracking-widest text-cyan-400">
                Priority Tier
              </label>
              <div className="grid grid-cols-4 gap-2">
                {[
                  { tier: 1, label: 'P1', name: 'Urgent', border: 'border-red-500', active: 'bg-red-500/20 text-red-300 border-red-500' },
                  { tier: 2, label: 'P2', name: 'High', border: 'border-amber-500', active: 'bg-amber-500/20 text-amber-300 border-amber-500' },
                  { tier: 3, label: 'P3', name: 'Medium', border: 'border-sky-500', active: 'bg-sky-500/20 text-sky-300 border-sky-500' },
                  { tier: 4, label: 'P4', name: 'Normal', border: 'border-zinc-500', active: 'bg-zinc-700/40 text-zinc-300 border-zinc-400' },
                ].map((item) => (
                  <button
                    key={item.tier}
                    type="button"
                    disabled={loading}
                    onClick={() => setPriority(item.tier)}
                    className={`py-2 px-1 text-center rounded-xl border text-xs font-bold transition-all ${
                      priority === item.tier
                        ? item.active
                        : 'border-white/10 bg-black/40 text-white/50 hover:border-white/30 hover:text-white'
                    }`}
                  >
                    <div>{item.label}</div>
                    <div className="text-[9px] font-normal opacity-75">{item.name}</div>
                  </button>
                ))}
              </div>
            </div>

            {/* Manor Selector */}
            <div className="space-y-1.5">
              <label className="text-[10px] font-bold uppercase tracking-widest text-cyan-400">
                Operational Manor
              </label>
              <select
                disabled={loading}
                value={area}
                onChange={(e) => setArea(e.target.value)}
                className="w-full bg-black/60 border border-white/15 rounded-xl px-3 py-2.5 text-sm text-white focus:border-cyan-400 focus:outline-none transition-colors"
              >
                {MANOR_OPTIONS.map((opt) => (
                  <option key={opt.id} value={opt.id} className="bg-zinc-900 text-white">
                    {opt.icon} {opt.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Due Date & Presets */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <label className="text-[10px] font-bold uppercase tracking-widest text-cyan-400">
                Target Due Date
              </label>
              <div className="flex items-center gap-1.5 text-[10px]">
                <button
                  type="button"
                  disabled={loading}
                  onClick={() => setDueDate(todayStr)}
                  className="px-2 py-0.5 rounded bg-amber-500/10 border border-amber-500/30 text-amber-300 hover:bg-amber-500/20"
                >
                  Today
                </button>
                <button
                  type="button"
                  disabled={loading}
                  onClick={() => setDueDate(addDaysToDateStr(todayStr, 1))}
                  className="px-2 py-0.5 rounded bg-cyan-500/10 border border-cyan-500/30 text-cyan-300 hover:bg-cyan-500/20"
                >
                  Tomorrow
                </button>
                <button
                  type="button"
                  disabled={loading}
                  onClick={() => setDueDate(addDaysToDateStr(todayStr, 7))}
                  className="px-2 py-0.5 rounded bg-zinc-800 border border-white/10 text-white/70 hover:bg-zinc-700"
                >
                  +1 Week
                </button>
                {dueDate && (
                  <button
                    type="button"
                    disabled={loading}
                    onClick={() => setDueDate('')}
                    className="px-2 py-0.5 rounded bg-red-950/40 border border-red-500/20 text-red-400 hover:bg-red-900/30"
                  >
                    Clear
                  </button>
                )}
              </div>
            </div>
            <input
              type="date"
              disabled={loading}
              value={dueDate}
              onChange={(e) => setDueDate(e.target.value)}
              className="w-full bg-black/60 border border-white/15 rounded-xl px-4 py-2 text-sm text-white focus:border-cyan-400 focus:outline-none transition-colors"
            />
          </div>

          {/* Recurrence Selector */}
          <div className="p-3.5 bg-black/40 border border-white/10 rounded-xl space-y-3">
            <label className="flex items-center gap-2.5 cursor-pointer">
              <input
                type="checkbox"
                disabled={loading}
                checked={isRecurring}
                onChange={(e) => setIsRecurring(e.target.checked)}
                className="w-4 h-4 rounded border-white/20 bg-zinc-900 text-cyan-400 focus:ring-0 focus:ring-offset-0"
              />
              <span className="text-xs font-bold uppercase tracking-wider text-white">
                🔄 Recurring Protocol Mandate
              </span>
            </label>

            {isRecurring && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className="pt-2 border-t border-white/5 space-y-2"
              >
                <label className="text-[10px] font-bold uppercase tracking-widest text-cyan-400/80">
                  Cadence / Interval
                </label>
                <div className="flex flex-wrap gap-2">
                  {RECURRENCE_PRESETS.map((preset) => (
                    <button
                      key={preset.id}
                      type="button"
                      disabled={loading}
                      onClick={() => setFrequency(preset.id)}
                      className={`px-3 py-1.5 rounded-lg border text-xs font-mono transition-all ${
                        frequency === preset.id
                          ? 'border-cyan-400 bg-cyan-400/20 text-cyan-300 font-bold'
                          : 'border-white/10 bg-zinc-900 text-white/50 hover:border-white/30 hover:text-white'
                      }`}
                    >
                      {preset.label}
                    </button>
                  ))}
                </div>
              </motion.div>
            )}
          </div>

          {/* Labels & Chips */}
          <div className="space-y-2">
            <label className="text-[10px] font-bold uppercase tracking-widest text-cyan-400">
              Directive Labels
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                disabled={loading}
                value={labelInput}
                onChange={(e) => setLabelInput(e.target.value)}
                onKeyDown={handleLabelKeyDown}
                placeholder="Type label and press Enter (e.g. @comm, @tech)"
                className="flex-1 bg-black/60 border border-white/15 rounded-xl px-4 py-2 text-sm text-white focus:border-cyan-400 focus:outline-none transition-colors"
              />
              <button
                type="button"
                disabled={loading || !labelInput.trim()}
                onClick={() => handleAddLabel()}
                className="px-4 py-2 bg-zinc-800 border border-white/15 text-white/80 hover:text-white hover:bg-zinc-700 rounded-xl text-xs font-bold uppercase tracking-wider disabled:opacity-40"
              >
                + Add Tag
              </button>
            </div>

            {/* Active Label Badges */}
            {labels.length > 0 && (
              <div className="flex flex-wrap gap-1.5 pt-1">
                {labels.map((tag) => (
                  <span
                    key={tag}
                    className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-mono border border-cyan-400/30 bg-cyan-950/40 text-cyan-300"
                  >
                    <span>{tag}</span>
                    <button
                      type="button"
                      disabled={loading}
                      onClick={() => handleRemoveLabel(tag)}
                      className="hover:text-red-400 ml-0.5"
                    >
                      ✕
                    </button>
                  </span>
                ))}
              </div>
            )}

            {/* Quick Suggestions */}
            <div className="flex flex-wrap items-center gap-1.5 pt-1">
              <span className="text-[10px] text-white/40 uppercase tracking-widest">Suggestions:</span>
              {SUGGESTED_LABELS.map((tag) => (
                <button
                  key={tag}
                  type="button"
                  disabled={loading || labels.includes(tag)}
                  onClick={() => handleAddLabel(tag)}
                  className="text-[10px] font-mono text-white/50 hover:text-cyan-300 px-1.5 py-0.5 rounded border border-white/5 bg-zinc-900/60 disabled:opacity-20"
                >
                  {tag}
                </button>
              ))}
            </div>
          </div>

          {/* Description (Markdown notes) */}
          <div className="space-y-1.5">
            <label className="text-[10px] font-bold uppercase tracking-widest text-cyan-400">
              Dossier Notes & Markdown Details
            </label>
            <textarea
              rows={4}
              disabled={loading}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Add tactical markdown notes, references, checklist items, or external telemetry URLs..."
              className="w-full bg-black/60 border border-white/15 rounded-xl p-3 text-sm text-white focus:border-cyan-400 focus:outline-none font-mono text-xs transition-colors"
            />
          </div>

          {/* Modal Footer */}
          <div className="flex items-center justify-end gap-3 pt-4 border-t border-white/10">
            <button
              type="button"
              disabled={loading}
              onClick={onClose}
              className="px-4 py-2.5 rounded-xl border border-white/15 text-white/70 hover:text-white hover:bg-white/5 text-xs font-bold uppercase tracking-wider transition-all"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading || !text.trim()}
              className="px-6 py-2.5 rounded-xl bg-cyan-400 text-black hover:bg-white text-xs font-black uppercase tracking-wider transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-[0_0_15px_rgba(0,212,255,0.25)] flex items-center gap-2"
            >
              {loading ? (
                <>
                  <span className="w-3.5 h-3.5 border-2 border-black border-t-transparent rounded-full animate-spin" />
                  <span>Transmitting...</span>
                </>
              ) : (
                <span>{isEditing ? 'Commit Changes' : 'Deploy Directive'}</span>
              )}
            </button>
          </div>
        </form>
      </motion.div>
    </div>
  );
}
