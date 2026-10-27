"use client";

import React, { useState, useEffect } from 'react';
import dynamic from 'next/dynamic';
import { journalDay } from '@/lib/journalDay';
import { useTaskBoard } from '@/lib/useTaskBoard';
import { motion, AnimatePresence } from 'framer-motion';
import TaskStatusPicker from './TaskStatusPicker';
import TaskModal from '@/components/TaskModal';

const MarkdownRenderer = dynamic(() => import('./MarkdownRenderer'), { ssr: false });

const PRIORITY_THEMES = {
  1: {
    label: 'P1',
    name: 'Urgent',
    ringBorder: 'border-red-500',
    ringHover: 'hover:border-red-400 hover:bg-red-500/20 text-red-400',
    badge: 'border-red-500/40 bg-red-950/40 text-red-300',
  },
  2: {
    label: 'P2',
    name: 'High',
    ringBorder: 'border-amber-500',
    ringHover: 'hover:border-amber-400 hover:bg-amber-500/20 text-amber-400',
    badge: 'border-amber-500/40 bg-amber-950/40 text-amber-300',
  },
  3: {
    label: 'P3',
    name: 'Medium',
    ringBorder: 'border-sky-500',
    ringHover: 'hover:border-sky-400 hover:bg-sky-500/20 text-sky-400',
    badge: 'border-sky-500/40 bg-sky-950/40 text-sky-300',
  },
  4: {
    label: 'P4',
    name: 'Normal',
    ringBorder: 'border-zinc-500',
    ringHover: 'hover:border-zinc-400 hover:bg-zinc-500/20 text-zinc-400',
    badge: 'border-zinc-700/50 bg-zinc-900/60 text-zinc-400',
  },
};

function addDaysToDateStr(dateStr, days) {
  const [y, m, d] = dateStr.split('-').map(Number);
  const date = new Date(y, m - 1, d);
  date.setDate(date.getDate() + days);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

function formatDateBadge(dateStr, todayStr) {
  if (!dateStr || typeof dateStr !== 'string' || !dateStr.includes('-')) return null;
  if (dateStr < todayStr) {
    return {
      type: 'overdue',
      text: `⚠️ Overdue · ${dateStr}`,
      classes: 'text-rose-300 bg-rose-950/50 border-rose-500/40 font-bold',
    };
  }
  if (dateStr === todayStr) {
    return {
      type: 'today',
      text: '⚡ Today',
      classes: 'text-amber-300 bg-amber-950/50 border-amber-500/40 font-bold',
    };
  }
  const tomorrowStr = addDaysToDateStr(todayStr, 1);
  if (dateStr === tomorrowStr) {
    return {
      type: 'tomorrow',
      text: '🌅 Tomorrow',
      classes: 'text-cyan-300 bg-cyan-950/50 border-cyan-500/40',
    };
  }
  const [y, m, d] = dateStr.split('-').map(Number);
  const dt = new Date(y, m - 1, d);
  const dayName = dt.toLocaleDateString('en-US', { weekday: 'short' });
  const monthName = dt.toLocaleDateString('en-US', { month: 'short' });
  return {
    type: 'future',
    text: `📅 ${dayName}, ${monthName} ${d}`,
    classes: 'text-zinc-400 bg-zinc-900/60 border-white/10',
  };
}

const freqColors = {
  daily: 'text-sky-400 border-sky-400/30 bg-sky-400/5',
  weekly: 'text-emerald-400 border-emerald-400/30 bg-emerald-400/5',
  'bi-weekly': 'text-teal-400 border-teal-400/30 bg-teal-400/5',
  'every 2 weeks': 'text-emerald-400 border-emerald-400/30 bg-emerald-400/5',
  'every 3 weeks': 'text-cyan-400 border-cyan-400/30 bg-cyan-400/5',
  monthly: 'text-amber-400 border-amber-400/30 bg-amber-400/5',
  bimonthly: 'text-orange-400 border-orange-400/30 bg-orange-400/5',
  'every 2 months': 'text-orange-400 border-orange-400/30 bg-orange-400/5',
  quarterly: 'text-orange-400 border-orange-400/30 bg-orange-400/5',
  seasonal: 'text-purple-400 border-purple-400/30 bg-purple-400/5',
};

export default function RecurringBoard({ area }) {
  return <RecurringBoardArea key={area} area={area} />;
}

function RecurringBoardArea({ area }) {
  const { tasks, loading, listError, mutationError, pending, loaded, refresh: fetchTasks, mutate } = useTaskBoard('/api/recurring', area);
  const [statusMessage, setStatusMessage] = useState('');
  const changeStatus = async (task, task_status) => {
    setStatusMessage('Saving task…');
    const saved = await mutate(`/api/recurring/${encodeURIComponent(task.id)}/complete`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ task_status, expected_task: task }),
    }, 'Change task status', null, items => items.some(item => item.id === task.id && item.occurrence_status?.status === task_status));
    setStatusMessage(saved ? 'Task saved' : 'Save not confirmed. Review the refreshed task before retrying.');
  };
  const [todayStr, setTodayStr] = useState(() => journalDay());
  useEffect(() => {
    const timer = setInterval(() => setTodayStr(journalDay()), 30000);
    return () => clearInterval(timer);
  }, []);

  const [showAddForm, setShowAddForm] = useState(false);
  const [newTask, setNewTask] = useState({ text: '', frequency: 'daily', priority: 4, description: '' });
  const [expandedNotesIds, setExpandedNotesIds] = useState(new Set());
  const [completingIds, setCompletingIds] = useState(new Set());
  const [editingTask, setEditingTask] = useState(null);

  const toggleExpandNotes = (id) => {
    setExpandedNotesIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleAddTask = async (e) => {
    e.preventDefault();
    if (!newTask.text.trim()) return;
    const payload = {
      text: newTask.text.trim(),
      frequency: newTask.frequency,
      area,
      next_due: journalDay(),
      priority: Number(newTask.priority) || 4,
      description: newTask.description || '',
    };
    const saved = await mutate('/api/recurring', {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    }, 'Create task', newTask);
    if (saved) {
      setNewTask({ text: '', frequency: 'daily', priority: 4, description: '' });
      setShowAddForm(false);
    }
  };

  const handleDelete = async (id) => {
    if (pending || (typeof window !== 'undefined' && window.confirm && !window.confirm("Are you sure you want to delete this recurring mandate?"))) return;
    await mutate(`/api/recurring/${encodeURIComponent(id)}`, { method: "DELETE" }, 'Delete task');
  };

  const handleMarkDone = async (id) => {
    if (typeof setCompletingIds === 'function') {
      setCompletingIds((prev) => new Set(prev).add(id));
    }
    try {
      await mutate(`/api/recurring/${encodeURIComponent(id)}/complete`, { method: "POST" }, 'Complete task');
    } finally {
      if (typeof setCompletingIds === 'function') {
        setCompletingIds((prev) => {
          const next = new Set(prev);
          next.delete(id);
          return next;
        });
      }
    }
  };

  return (
    <div aria-busy={loading || pending} className="max-w-4xl mx-auto space-y-6">
      <div className="flex justify-between items-center bg-zinc-900/60 p-4 rounded-xl border border-white/10 shadow-lg backdrop-blur-sm">
        <div>
          <h2 className="text-lg font-bold text-white uppercase tracking-widest flex items-center gap-2">
            <span className="text-2xl">🔄</span> Recurring Mandates
          </h2>
          <p className="text-[10px] font-mono text-white/50 uppercase tracking-widest">Area: {String(area || '').toUpperCase()}</p>
        </div>
        <button 
          disabled={pending}
          onClick={() => setShowAddForm(!showAddForm)}
          className="disabled:opacity-50 disabled:cursor-not-allowed px-4 py-2 bg-accent/10 border border-accent/40 text-accent font-bold text-[10px] uppercase tracking-widest rounded-lg hover:bg-accent hover:text-black transition-all"
        >
          {showAddForm ? 'Cancel' : '+ New Mandate'}
        </button>
      </div>

      <AnimatePresence>
        {showAddForm && (
          <motion.form 
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            onSubmit={handleAddTask}
            className="bg-zinc-950 p-4 border border-accent/30 rounded-xl overflow-hidden shadow-[0_0_15px_rgba(0,212,255,0.1)] space-y-4"
          >
            <div className="space-y-3">
              <div className="flex flex-col sm:flex-row gap-3">
                <div className="flex-1 space-y-1">
                  <label className="text-[10px] font-bold text-accent uppercase tracking-widest">Mandate Description</label>
                  <input 
                    disabled={pending}
                    type="text" 
                    value={newTask.text}
                    onChange={(e) => setNewTask({ ...newTask, text: e.target.value })}
                    placeholder="e.g., 🧹 Kitchen Deep Clean"
                    className="w-full bg-black border border-white/20 rounded p-2 text-sm text-white focus:border-accent outline-none"
                    required
                  />
                </div>
                <div className="w-full sm:w-44 space-y-1">
                  <label className="text-[10px] font-bold text-accent uppercase tracking-widest">Frequency</label>
                  <select 
                    disabled={pending}
                    value={newTask.frequency}
                    onChange={(e) => setNewTask({ ...newTask, frequency: e.target.value })}
                    className="w-full bg-black border border-white/20 rounded p-2 text-sm text-white focus:border-accent outline-none"
                  >
                    <option value="daily">Daily</option>
                    <option value="weekly">Weekly</option>
                    <option value="bi-weekly">Bi-Weekly</option>
                    <option value="every 2 weeks">Every 2 Weeks</option>
                    <option value="every 3 weeks">Every 3 Weeks</option>
                    <option value="monthly">Monthly</option>
                    <option value="bimonthly">Every 2 Months</option>
                    <option value="quarterly">Quarterly</option>
                    <option value="seasonal">Seasonal</option>
                  </select>
                </div>
                <div className="w-full sm:w-36 space-y-1">
                  <label className="text-[10px] font-bold text-accent uppercase tracking-widest">Priority</label>
                  <select
                    disabled={pending}
                    value={newTask.priority}
                    onChange={(e) => setNewTask({ ...newTask, priority: Number(e.target.value) })}
                    className="w-full bg-black border border-white/20 rounded p-2 text-sm text-white focus:border-accent outline-none"
                  >
                    <option value={1}>P1 - Urgent</option>
                    <option value={2}>P2 - High</option>
                    <option value={3}>P3 - Medium</option>
                    <option value={4}>P4 - Normal</option>
                  </select>
                </div>
              </div>

              <div className="space-y-1">
                <label className="text-[10px] font-bold text-accent uppercase tracking-widest">Description / Markdown Notes (Optional)</label>
                <textarea
                  disabled={pending}
                  rows={2}
                  value={newTask.description}
                  onChange={(e) => setNewTask({ ...newTask, description: e.target.value })}
                  placeholder="Mandate details, checklist, or instructions..."
                  className="w-full bg-black border border-white/20 rounded p-2 text-xs text-white focus:border-accent outline-none resize-y"
                />
              </div>
            </div>

            <div className="flex justify-end gap-3 pt-1">
              <button
                type="button"
                disabled={pending}
                onClick={() => setShowAddForm(false)}
                className="px-4 py-2 border border-white/10 text-white/60 hover:text-white rounded text-xs font-bold uppercase tracking-wider"
              >
                Cancel
              </button>
              <button 
                disabled={pending || !loaded || loading || !!listError} 
                type="submit" 
                className="disabled:opacity-50 disabled:cursor-not-allowed px-6 py-2 bg-accent text-black font-bold uppercase tracking-widest text-xs rounded hover:bg-white transition-colors h-[38px]"
              >
                Deploy
              </button>
            </div>
          </motion.form>
        )}
      </AnimatePresence>

      <div className="space-y-4">
        {loading && <p role="status" className="text-accent animate-pulse font-mono text-sm">Loading tasks...</p>}
        {listError && (
          <div role="alert" className="bg-zinc-950/90 backdrop-blur-md border border-white/10 p-4 rounded-xl text-red-400">
            <p>{listError}{loaded ? ' Showing last confirmed tasks.' : ''}</p>
            <button type="button" onClick={fetchTasks} disabled={loading || pending} className="mt-2 text-accent underline disabled:opacity-50">Retry loading</button>
          </div>
        )}
        {mutationError && <p role="alert" className="text-red-400">{mutationError} Use the same action to retry.</p>}
        <p role="status" aria-live="polite" className="text-xs text-accent">{statusMessage}</p>
        {pending && <p role="status" className="text-accent font-mono text-sm">Saving task...</p>}
        {tasks.length === 0 ? (loaded && !loading && !listError ? (
          <div className="text-center py-12 text-white/30 font-mono text-xs uppercase tracking-widest border border-white/5 border-dashed rounded-xl bg-zinc-900/30">
            No recurring mandates established for this sector.
          </div>
        ) : null) : (
          [...tasks].sort((a, b) => (a.next_due || todayStr).localeCompare(b.next_due || todayStr)).map(task => {
            const priorityNum = Number(task.priority) || 4;
            const pTheme = PRIORITY_THEMES[priorityNum] || PRIORITY_THEMES[4];
            const isOverdue = task.next_due && task.next_due < todayStr;
            const isDueToday = task.next_due && task.next_due === todayStr;
            const freqStyle = freqColors[task.frequency] || 'text-cyan-400 border-cyan-400/30 bg-cyan-400/5';
            const dateBadge = formatDateBadge(task.next_due, todayStr);
            const isExpanded = expandedNotesIds.has(task.id);
            const isCompleting = completingIds.has(task.id);

            return (
              <motion.div 
                layout
                initial={{ opacity: 0, y: 5 }}
                animate={{ opacity: 1, y: 0 }}
                key={task.id} 
                className={`p-4 rounded-xl border flex flex-col gap-3 transition-all group backdrop-blur-sm shadow-md ${
                  isOverdue ? 'bg-red-950/20 border-red-500/40 shadow-[0_0_10px_rgba(239,68,68,0.1)]' :
                  isDueToday ? 'bg-amber-950/20 border-amber-500/40' :
                  'bg-zinc-900/60 border-white/10 hover:border-white/20'
                }`}
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-start gap-3 flex-1 min-w-0">
                    <TaskStatusPicker label={task.text} value={task.occurrence_status?.date === todayStr ? task.occurrence_status.status : (task.last_done === todayStr ? 'done' : 'pending')} disabled={pending || loading || !!listError} onChange={status => changeStatus(task, status)} />
                    <button 
                      disabled={pending || loading || !!listError || isCompleting}
                      onClick={() => handleMarkDone(task.id)}
                      className={`disabled:opacity-50 disabled:cursor-not-allowed w-7 h-7 mt-0.5 rounded-full border-2 flex items-center justify-center transition-colors shrink-0 ${pTheme.ringBorder} ${pTheme.ringHover} ${isCompleting ? 'animate-spin border-t-transparent' : ''}`}
                      title="Mark Done Today"
                    >
                      <span className={`text-xs font-black transition-opacity ${isCompleting ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'}`}>✓</span>
                    </button>

                    <div className="flex-1 min-w-0">
                      <div className="flex flex-wrap items-center gap-2 mb-1">
                        <span className={`text-sm font-bold text-white break-words ${isCompleting ? 'line-through opacity-50' : ''}`}>
                          {task.text}
                        </span>
                        <span className={`text-[9px] font-bold font-mono px-1.5 py-0.5 rounded border ${pTheme.badge}`}>
                          {pTheme.label}
                        </span>
                        <span className={`text-[9px] px-1.5 py-0.5 rounded font-mono uppercase tracking-wider border ${freqStyle}`}>
                          {task.frequency || 'recurring'}
                        </span>
                      </div>

                      <div className="flex flex-wrap items-center gap-2 text-xs">
                        {dateBadge && (
                          <span className={`text-[10px] font-mono px-2 py-0.5 rounded-md border ${dateBadge.classes}`}>
                            {dateBadge.text}
                          </span>
                        )}
                        <span className="text-[10px] font-mono uppercase tracking-widest text-white/40">
                          Last: {task.last_done || 'Never'}
                        </span>
                        <span className={`text-[10px] font-mono uppercase tracking-widest ${isOverdue ? 'text-red-400 font-bold' : isDueToday ? 'text-amber-400 font-bold' : 'text-white/40'}`}>
                          Next: {task.next_due || 'Unscheduled'}
                        </span>
                        {(Array.isArray(task.labels) ? task.labels : []).map(label => (
                          <span key={label} className="text-[10px] font-mono px-2 py-0.5 rounded-md border border-white/10 bg-zinc-950/60 text-zinc-400">
                            {label}
                          </span>
                        ))}
                        {task.description && (
                          <button
                            type="button"
                            onClick={() => toggleExpandNotes(task.id)}
                            className="text-[10px] font-mono text-cyan-400 hover:text-white px-2 py-0.5 rounded border border-cyan-400/20 bg-cyan-950/20 flex items-center gap-1 transition-colors"
                            title="Toggle notes"
                          >
                            <span>📝 Notes</span>
                            <span>{isExpanded ? '▲' : '▼'}</span>
                          </button>
                        )}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-1.5 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
                    <button
                      type="button"
                      disabled={pending || loading}
                      onClick={() => setEditingTask(task)}
                      className="w-7 h-7 rounded-lg border border-white/10 bg-zinc-800/40 text-white/70 hover:text-white hover:bg-white/10 flex items-center justify-center transition-colors text-xs"
                      title="Edit Mandate"
                    >
                      ✏️
                    </button>
                    <button 
                      disabled={pending || loading || !!listError}
                      onClick={() => handleDelete(task.id)}
                      className="w-7 h-7 rounded-lg border border-red-500/20 bg-red-950/20 text-red-400 hover:text-red-300 hover:bg-red-900/40 flex items-center justify-center transition-colors text-xs"
                      title="Delete Mandate"
                    >
                      ✕
                    </button>
                  </div>
                </div>

                {task.description && isExpanded && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                    className="mt-1 pt-2 border-t border-white/5 pl-10"
                  >
                    <div className="bg-black/50 border border-white/10 rounded-xl p-3.5 text-xs text-zinc-300 leading-relaxed shadow-inner">
                      <MarkdownRenderer content={task.description} />
                    </div>
                  </motion.div>
                )}
              </motion.div>
            );
          })
        )}
      </div>

      {editingTask && (
        <TaskModal
          isOpen={Boolean(editingTask)}
          onClose={() => setEditingTask(null)}
          initialTask={editingTask}
          defaultArea={area}
          onTaskSaved={() => {
            setEditingTask(null);
            fetchTasks();
          }}
        />
      )}
    </div>
  );
}
