"use client";

import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import dynamic from 'next/dynamic';
import { journalDay } from '@/lib/journalDay';
import { apiFetch, subscribeVaultStream } from '@/lib/desktopApi';
import TaskModal from './TaskModal';
import TaskStatusPicker from './TaskStatusPicker';

const MarkdownRenderer = dynamic(() => import('./MarkdownRenderer'), { ssr: false });

const MANORS = [
  { id: 'ALL', label: 'All Manors', icon: '🌐', area: null },
  { id: 'Sanctum', label: 'Sanctum', icon: '🏰', area: 'sanctum' },
  { id: 'Domestic', label: 'Domestic', icon: '🏠', area: 'domestic' },
  { id: 'Front', label: 'Front', icon: '⚔️', area: 'front' },
  { id: 'Gauntlet', label: 'Gauntlet', icon: '⚖️', area: 'bureaucratic' },
  { id: 'Outland', label: 'Outland', icon: '🧭', area: 'world' },
];

const AREA_DISPLAY = {
  sanctum: { label: 'Sanctum', icon: '🏰', badge: 'text-cyan-400 border-cyan-500/30 bg-cyan-950/30' },
  domestic: { label: 'Domestic', icon: '🏠', badge: 'text-emerald-400 border-emerald-500/30 bg-emerald-950/30' },
  front: { label: 'Front', icon: '⚔️', badge: 'text-rose-400 border-rose-500/30 bg-rose-950/30' },
  bureaucratic: { label: 'Gauntlet', icon: '⚖️', badge: 'text-amber-400 border-amber-500/30 bg-amber-950/30' },
  world: { label: 'Outland', icon: '🧭', badge: 'text-purple-400 border-purple-500/30 bg-purple-950/30' },
};

function normalizeArea(area) {
  if (!area) return 'sanctum';
  const val = String(area).trim().toLowerCase();
  if (['sanctum', 'the sanctum', 'command'].includes(val)) return 'sanctum';
  if (['domestic', 'the domestic breach', 'home'].includes(val)) return 'domestic';
  if (['front', 'the high-velocity front', 'work'].includes(val)) return 'front';
  if (['gauntlet', 'bureaucratic', 'the bureaucratic gauntlet', 'finances'].includes(val)) return 'bureaucratic';
  if (['outland', 'world', 'the kinetic outland', 'kinetic outland'].includes(val)) return 'world';
  return val;
}

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
  if (!dateStr) return null;
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

export default function TasksCockpit() {
  const [todayStr, setTodayStr] = useState(() => journalDay());
  const [activeTasks, setActiveTasks] = useState([]);
  const [recurringTasks, setRecurringTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [completingIds, setCompletingIds] = useState(new Set());

  // Filter States
  const [viewTab, setViewTab] = useState('today'); // 'today' | 'upcoming' | 'all'
  const [selectedManor, setSelectedManor] = useState('ALL');
  const [selectedPriority, setSelectedPriority] = useState('ALL'); // 'ALL' | 1 | 2 | 3 | 4
  const [selectedLabel, setSelectedLabel] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedNotesIds, setExpandedNotesIds] = useState(new Set());

  // Modal State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingTask, setEditingTask] = useState(null);
  const [modalDefaultDueDate, setModalDefaultDueDate] = useState('');

  // Keep todayStr fresh
  useEffect(() => {
    const timer = setInterval(() => {
      setTodayStr(journalDay());
    }, 60000);
    return () => clearInterval(timer);
  }, []);

  const [statusMessage, setStatusMessage] = useState('');
  const [includeCompleted, setIncludeCompleted] = useState(false);
  const statusPending = React.useRef(false);
  const statusFocus = React.useRef(null);
  useEffect(() => {
    if (!loading && !statusPending.current && statusFocus.current) {
      if (typeof document !== 'undefined') document.getElementById(statusFocus.current)?.focus();
      statusFocus.current = null;
    }
  }, [loading, completingIds]);
  const changeTaskStatus = async (task, desired) => {
    if (statusPending.current) return;
    statusPending.current = true;
    statusFocus.current = `cockpit-status-${task.isRecurring ? 'recurring' : 'active'}-${task.id}`;
    setStatusMessage('Saving task…');
    setCompletingIds(previous => new Set(previous).add(task.id));
    try {
      const snapshot = (task.isRecurring ? recurringTasks : activeTasks).find(item => item.id === task.id);
      if (!snapshot) throw new Error('Task unavailable. Reload before retrying.');
      const endpoint = task.isRecurring ? '/api/recurring' : '/api/active_tasks';
      const response = await apiFetch(`${endpoint}/${encodeURIComponent(task.id)}/complete`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({task_status: desired, expected_task: snapshot}),
      });
      if (!response.ok) throw new Error('Status save not confirmed. Reload before retrying.');
      const readback = await apiFetch(task.isRecurring ? endpoint : `${endpoint}?include_completed=true`);
      if (!readback.ok) throw new Error('Status readback unavailable. Reload before retrying.');
      const saved = (await readback.json()).find(item => item.id === task.id);
      const actual = task.isRecurring ? saved?.occurrence_status?.status : (saved?.status === 'completed' ? 'done' : saved?.status || 'pending');
      if (!saved || actual !== desired) throw new Error('Persisted status changed. Reload before retrying.');
      if (desired === 'done') setIncludeCompleted(true);
      await fetchAllTasks();
      setStatusMessage('Task saved');
    } catch (error) {
      setStatusMessage(error.message || 'Save not confirmed. Reload before retrying.');
      await fetchAllTasks();
    } finally {
      statusPending.current = false;
      setCompletingIds(previous => { const next = new Set(previous); next.delete(task.id); return next; });
    }
  };

  // Fetch all tasks from backend
  const fetchAllTasks = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const [activeRes, recRes] = await Promise.all([
        apiFetch('/api/active_tasks?include_completed=true'),
        apiFetch('/api/recurring'),
      ]);

      if (!activeRes.ok) throw new Error('Failed to load active directives');
      if (!recRes.ok) throw new Error('Failed to load recurring protocols');

      const activeData = await activeRes.json();
      const recData = await recRes.json();

      setActiveTasks(Array.isArray(activeData) ? activeData : []);
      setRecurringTasks(Array.isArray(recData) ? recData : []);
    } catch (err) {
      console.error('Error fetching directives:', err);
      setError(err.message || 'Error connecting to directives manifold');
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial fetch and reactive event subscriptions
  useEffect(() => {
    fetchAllTasks();

    const handleProgressionChange = () => {
      fetchAllTasks();
    };
    window.addEventListener('navis:progression-changed', handleProgressionChange);

    const unsubscribe = subscribeVaultStream({
      onEvent: (event) => {
        if (!event) return;
        const path = (event.path || '').toLowerCase();
        if (path.includes('ops_state.json') || path.includes('bridge') || path.includes('journal')) {
          fetchAllTasks();
        }
      },
    });

    return () => {
      window.removeEventListener('navis:progression-changed', handleProgressionChange);
      if (typeof unsubscribe === 'function') unsubscribe();
    };
  }, [fetchAllTasks]);

  // Combine and normalize all tasks
  const allTasks = useMemo(() => {
    const active = activeTasks.filter(task => includeCompleted || task.status !== 'completed').map((t) => ({
      ...t,
      isRecurring: false,
      normalizedArea: normalizeArea(t.area),
      effectivePriority: Number(t.priority) || 4,
      effectiveDueDate: t.due_date || null,
      labels: Array.isArray(t.labels) ? t.labels : [],
    }));

    const recurring = recurringTasks.map((t) => ({
      ...t,
      isRecurring: true,
      normalizedArea: normalizeArea(t.area),
      effectivePriority: Number(t.priority) || 4,
      effectiveDueDate: t.next_due || t.due_date || null,
      labels: Array.isArray(t.labels) ? t.labels : [],
    }));

    return [...active, ...recurring];
  }, [activeTasks, recurringTasks, includeCompleted]);

  // Extract all active labels across loaded tasks
  const availableLabels = useMemo(() => {
    const labelSet = new Set();
    allTasks.forEach((t) => {
      (t.labels || []).forEach((l) => {
        if (l && typeof l === 'string') labelSet.add(l.toLowerCase());
      });
    });
    return Array.from(labelSet).sort();
  }, [allTasks]);

  // Filter tasks based on Manor, Priority, Label, Search
  const filteredTasks = useMemo(() => {
    return allTasks.filter((task) => {
      // Manor filter
      if (selectedManor !== 'ALL') {
        const manorObj = MANORS.find((m) => m.id === selectedManor);
        if (manorObj && task.normalizedArea !== manorObj.area) return false;
      }

      // Priority filter
      if (selectedPriority !== 'ALL') {
        if (task.effectivePriority !== Number(selectedPriority)) return false;
      }

      // Label filter
      if (selectedLabel) {
        const hasLabel = (task.labels || []).some(
          (l) => l.toLowerCase() === selectedLabel.toLowerCase()
        );
        if (!hasLabel) return false;
      }

      // Search query
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const textMatch = (task.text || '').toLowerCase().includes(q);
        const descMatch = (task.description || '').toLowerCase().includes(q);
        const labelMatch = (task.labels || []).some((l) => l.toLowerCase().includes(q));
        if (!textMatch && !descMatch && !labelMatch) return false;
      }

      return true;
    });
  }, [allTasks, selectedManor, selectedPriority, selectedLabel, searchQuery]);

  // Toggle notes expansion
  const toggleExpandNotes = (id) => {
    setExpandedNotesIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  // Complete Directive handler
  const handleCompleteTask = async (task) => {
    if (completingIds.has(task.id)) return;
    setCompletingIds((prev) => new Set(prev).add(task.id));

    try {
      const endpoint = task.isRecurring
        ? `/api/recurring/${encodeURIComponent(task.id)}/complete`
        : `/api/active_tasks/${encodeURIComponent(task.id)}/complete`;

      const res = await apiFetch(endpoint, { method: 'POST' });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || 'Directive completion rejected');
      }

      // Refresh list
      await fetchAllTasks();
    } catch (err) {
      console.error('Error completing directive:', err);
      alert(`Directive completion failed: ${err.message || err}`);
    } finally {
      setCompletingIds((prev) => {
        const next = new Set(prev);
        next.delete(task.id);
        return next;
      });
    }
  };

  // Delete Directive handler
  const handleDeleteTask = async (task) => {
    if (!window.confirm(`Are you sure you want to terminate directive "${task.text}"?`)) return;

    try {
      const endpoint = task.isRecurring
        ? `/api/recurring/${encodeURIComponent(task.id)}`
        : `/api/active_tasks/${encodeURIComponent(task.id)}`;

      const res = await apiFetch(endpoint, { method: 'DELETE' });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || 'Delete failed');
      }

      await fetchAllTasks();
    } catch (err) {
      console.error('Error deleting directive:', err);
      alert(`Delete failed: ${err.message || err}`);
    }
  };

  // Open modal for editing
  const handleEditTask = (task) => {
    setEditingTask(task);
    setModalDefaultDueDate(task.effectiveDueDate || '');
    setIsModalOpen(true);
  };

  // Open modal for new task
  const handleNewTask = (targetDate = '') => {
    setEditingTask(null);
    setModalDefaultDueDate(targetDate || todayStr);
    setIsModalOpen(true);
  };

  // Stats calculation
  const stats = useMemo(() => {
    const total = allTasks.length;
    const overdue = allTasks.filter((t) => t.effectiveDueDate && t.effectiveDueDate < todayStr).length;
    const todayCount = allTasks.filter((t) => t.effectiveDueDate && t.effectiveDueDate === todayStr).length;
    const urgentCount = allTasks.filter((t) => t.effectivePriority === 1 || t.effectivePriority === 2).length;
    return { total, overdue, todayCount, urgentCount };
  }, [allTasks, todayStr]);

  // Agenda Days calculation for Upcoming view (7 days)
  const agendaDays = useMemo(() => {
    const days = [];
    for (let i = 0; i < 7; i++) {
      const dStr = addDaysToDateStr(todayStr, i);
      const [y, m, d] = dStr.split('-').map(Number);
      const dt = new Date(y, m - 1, d);
      const weekday = dt.toLocaleDateString('en-US', { weekday: 'short' });
      const month = dt.toLocaleDateString('en-US', { month: 'short' });
      const label =
        i === 0
          ? `Today · ${weekday}, ${month} ${d}`
          : i === 1
          ? `Tomorrow · ${weekday}, ${month} ${d}`
          : `${weekday}, ${month} ${d}`;
      days.push({
        dateStr: dStr,
        label,
        isToday: i === 0,
        isTomorrow: i === 1,
      });
    }
    return days;
  }, [todayStr]);

  // Render a Single Task Row
  const renderTaskRow = (task) => {
    const pTheme = PRIORITY_THEMES[task.effectivePriority] || PRIORITY_THEMES[4];
    const areaMeta = AREA_DISPLAY[task.normalizedArea] || AREA_DISPLAY.sanctum;
    const dateBadge = formatDateBadge(task.effectiveDueDate, todayStr);
    const isExpanded = expandedNotesIds.has(task.id);
    const isCompleting = completingIds.has(task.id);

    return (
      <motion.div
        key={task.id}
        layout
        initial={{ opacity: 0, y: 4 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -4 }}
        className="group bg-zinc-950/80 hover:bg-zinc-900/90 border border-white/10 hover:border-cyan-400/30 rounded-xl p-3.5 transition-all shadow-md backdrop-blur-sm space-y-2.5"
      >
        <div className="flex items-start gap-3.5">
          <TaskStatusPicker completedAt={task.completed_at || task.completion?.completed_at} id={`cockpit-status-${task.isRecurring ? 'recurring' : 'active'}-${task.id}`} label={task.text} disabled={isCompleting || statusPending.current}
            value={task.isRecurring ? (task.occurrence_status?.date === todayStr ? task.occurrence_status.status : task.last_done === todayStr ? 'done' : 'pending') : task.status || 'pending'}
            onChange={status => changeTaskStatus(task, status)} />
          {/* Priority-Colored Check Ring */}
          <button
            type="button"
            disabled={isCompleting || statusPending.current}
            onClick={() => handleCompleteTask(task)}
            title={`Complete directive (${pTheme.label} ${pTheme.name})`}
            className={`w-5 h-5 mt-0.5 rounded-full border-2 flex items-center justify-center transition-all shrink-0 ${pTheme.ringBorder} ${pTheme.ringHover} ${
              isCompleting ? 'animate-spin border-t-transparent' : ''
            }`}
          >
            <span className="opacity-0 group-hover:opacity-100 text-[10px] font-black transition-opacity">
              ✓
            </span>
          </button>

          {/* Task Info & Title */}
          <div className="flex-1 min-w-0">
            <div className="flex flex-wrap items-center gap-2 mb-1">
              <span className={`text-sm font-semibold tracking-wide text-white ${isCompleting ? 'line-through opacity-50' : ''}`}>
                {task.text}
              </span>

              {/* Priority Pill */}
              <span className={`text-[9px] font-bold font-mono px-1.5 py-0.5 rounded border ${pTheme.badge}`}>
                {pTheme.label}
              </span>

              {/* Recurring Badge */}
              {task.isRecurring && (
                <span className="text-[9px] font-mono px-1.5 py-0.5 rounded border border-cyan-500/30 bg-cyan-950/30 text-cyan-300 flex items-center gap-1">
                  <span>🔄</span> {task.frequency || 'recurring'}
                </span>
              )}
            </div>

            {/* Badges Bar: Manor, Due Date, Labels */}
            <div className="flex flex-wrap items-center gap-2 text-xs">
              {/* Manor Badge */}
              <span className={`text-[10px] font-mono px-2 py-0.5 rounded-md border flex items-center gap-1 ${areaMeta.badge}`}>
                <span>{areaMeta.icon}</span>
                <span>{areaMeta.label}</span>
              </span>

              {/* Due Date Status Badge */}
              {dateBadge && (
                <span className={`text-[10px] font-mono px-2 py-0.5 rounded-md border ${dateBadge.classes}`}>
                  {dateBadge.text}
                </span>
              )}

              {/* Label Chips */}
              {(task.labels || []).map((label) => (
                <button
                  key={label}
                  type="button"
                  onClick={() => setSelectedLabel(selectedLabel === label ? null : label)}
                  className={`text-[10px] font-mono px-2 py-0.5 rounded-md border transition-all ${
                    selectedLabel === label
                      ? 'border-cyan-400 bg-cyan-400/20 text-cyan-200'
                      : 'border-white/10 bg-zinc-900/60 text-zinc-400 hover:border-cyan-400/30 hover:text-cyan-300'
                  }`}
                >
                  {label}
                </button>
              ))}

              {/* Notes Indicator */}
              {task.description && (
                <button
                  type="button"
                  onClick={() => toggleExpandNotes(task.id)}
                  className="text-[10px] font-mono text-cyan-400 hover:text-white px-2 py-0.5 rounded border border-cyan-400/20 bg-cyan-950/20 flex items-center gap-1 transition-colors"
                >
                  <span>📝 Notes</span>
                  <span>{isExpanded ? '▲' : '▼'}</span>
                </button>
              )}
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
            <button
              type="button"
              onClick={() => handleEditTask(task)}
              className="w-7 h-7 rounded-lg flex items-center justify-center text-zinc-400 hover:text-white hover:bg-white/10 transition-colors"
              title="Edit directive"
            >
              ✏️
            </button>
            <button
              type="button"
              onClick={() => handleDeleteTask(task)}
              className="w-7 h-7 rounded-lg flex items-center justify-center text-zinc-400 hover:text-red-400 hover:bg-red-950/30 transition-colors"
              title="Terminate directive"
            >
              🗑️
            </button>
          </div>
        </div>

        {/* Expandable Markdown Notes */}
        {task.description && isExpanded && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="mt-2.5 pt-2.5 border-t border-white/5 pl-8"
          >
            <div className="bg-black/50 border border-white/10 rounded-xl p-4 text-xs text-zinc-300 leading-relaxed shadow-inner">
              <MarkdownRenderer content={task.description} />
            </div>
          </motion.div>
        )}
      </motion.div>
    );
  };

  // Section Grouping for Today View
  const todayTasks = useMemo(() => {
    const overdue = filteredTasks.filter((t) => t.effectiveDueDate && t.effectiveDueDate < todayStr);
    const today = filteredTasks.filter((t) => t.effectiveDueDate && t.effectiveDueDate === todayStr);
    const unscheduled = filteredTasks.filter((t) => !t.effectiveDueDate);
    const future = filteredTasks.filter((t) => t.effectiveDueDate && t.effectiveDueDate > todayStr);
    return { overdue, today, unscheduled, future };
  }, [filteredTasks, todayStr]);

  // Section Grouping for Upcoming (7-day agenda)
  const upcomingGrouped = useMemo(() => {
    const dayMap = {};
    agendaDays.forEach((d) => {
      dayMap[d.dateStr] = [];
    });

    const overdue = [];
    const later = [];
    const unscheduled = [];

    const lastAgendaDay = agendaDays[agendaDays.length - 1]?.dateStr;

    filteredTasks.forEach((task) => {
      const d = task.effectiveDueDate;
      if (!d) {
        unscheduled.push(task);
      } else if (d < todayStr) {
        overdue.push(task);
      } else if (dayMap[d]) {
        dayMap[d].push(task);
      } else if (d > lastAgendaDay) {
        later.push(task);
      }
    });

    return { dayMap, overdue, later, unscheduled };
  }, [filteredTasks, agendaDays, todayStr]);

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden bg-zinc-950/60 backdrop-blur-md">
      {/* Top Banner & Stats Cockpit */}
      <div className="p-6 border-b border-white/10 bg-zinc-950/80 shrink-0 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-cyan-500/10 border border-cyan-400/40 flex items-center justify-center text-xl text-cyan-400 shadow-[0_0_15px_rgba(0,212,255,0.15)]">
              📋
            </div>
            <div>
              <h1 className="text-xl font-black uppercase tracking-wider text-white">Directives Cockpit</h1>
              <p className="text-[10px] font-mono uppercase tracking-widest text-cyan-400/70">
                Central Tactical Agenda & Operational Directives
              </p>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="flex items-center gap-2.5">
            <button
              type="button"
              onClick={fetchAllTasks}
              disabled={loading}
              className="px-3.5 py-2 rounded-xl border border-white/10 hover:border-white/20 bg-zinc-900/60 text-white/70 hover:text-white text-xs font-bold uppercase tracking-wider transition-all flex items-center gap-1.5"
              title="Refresh directives"
            >
              <span className={loading ? 'animate-spin' : ''}>🔄</span>
              <span>Sync</span>
            </button>
            <button
              type="button"
              onClick={() => handleNewTask()}
              className="px-5 py-2 rounded-xl bg-cyan-400 text-black hover:bg-white text-xs font-black uppercase tracking-wider transition-all shadow-[0_0_15px_rgba(0,212,255,0.25)] flex items-center gap-2"
            >
              <span>+</span>
              <span>New Directive</span>
            </button>
          </div>
        </div>

        {/* Telemetry Stats Bar */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-1">
          <div className="p-2.5 bg-black/40 border border-white/5 rounded-xl flex items-center justify-between">
            <span className="text-[10px] font-mono uppercase tracking-widest text-white/50">Total Directives</span>
            <span className="text-sm font-mono font-bold text-cyan-400">{stats.total}</span>
          </div>
          <div className="p-2.5 bg-black/40 border border-white/5 rounded-xl flex items-center justify-between">
            <span className="text-[10px] font-mono uppercase tracking-widest text-white/50">Today Agenda</span>
            <span className="text-sm font-mono font-bold text-amber-400">{stats.todayCount}</span>
          </div>
          <div className="p-2.5 bg-black/40 border border-white/5 rounded-xl flex items-center justify-between">
            <span className="text-[10px] font-mono uppercase tracking-widest text-white/50">Overdue</span>
            <span className={`text-sm font-mono font-bold ${stats.overdue > 0 ? 'text-rose-400 animate-pulse' : 'text-zinc-500'}`}>
              {stats.overdue}
            </span>
          </div>
          <div className="p-2.5 bg-black/40 border border-white/5 rounded-xl flex items-center justify-between">
            <span className="text-[10px] font-mono uppercase tracking-widest text-white/50">Urgent (P1/P2)</span>
            <span className="text-sm font-mono font-bold text-red-400">{stats.urgentCount}</span>
          </div>
        </div>

        {/* Navigation View Tabs (Today, Upcoming, All) */}
        <div className="flex items-center gap-2 border-b border-white/5 pb-1">
          {[
            { id: 'today', label: 'Today', icon: '☀️', count: todayTasks.today.length + todayTasks.overdue.length },
            { id: 'upcoming', label: 'Upcoming (7-Day Agenda)', icon: '📅', count: filteredTasks.length },
            { id: 'all', label: 'All Directives', icon: '📁', count: filteredTasks.length },
          ].map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setViewTab(tab.id)}
              className={`px-4 py-2 rounded-xl font-bold text-xs uppercase tracking-wider flex items-center gap-2 transition-all ${
                viewTab === tab.id
                  ? 'bg-cyan-400/20 text-cyan-300 border border-cyan-400/40 shadow-[0_0_10px_rgba(0,212,255,0.1)]'
                  : 'text-white/50 hover:text-white hover:bg-white/5 border border-transparent'
              }`}
            >
              <span>{tab.icon}</span>
              <span>{tab.label}</span>
              <span className="text-[10px] font-mono px-1.5 py-0.2 rounded-full bg-black/40 text-white/60">
                {tab.count}
              </span>
            </button>
          ))}
        </div>

        {/* Filters Bar: Manor, Priority, Labels, Search */}
        <div className="space-y-2.5 pt-1">
          {/* Manor Filter Pills */}
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-[10px] font-mono uppercase tracking-widest text-white/40 mr-1">Manor:</span>
            {MANORS.map((m) => (
              <button
                key={m.id}
                type="button"
                onClick={() => setSelectedManor(m.id)}
                className={`px-2.5 py-1 rounded-lg text-xs font-mono transition-all border ${
                  selectedManor === m.id
                    ? 'border-cyan-400 bg-cyan-400/20 text-cyan-300 font-bold'
                    : 'border-white/5 bg-black/40 text-white/50 hover:border-white/20 hover:text-white'
                }`}
              >
                <span>{m.icon}</span> <span className="ml-1">{m.label}</span>
              </button>
            ))}

            {/* Priority Filter */}
            <div className="h-4 w-px bg-white/10 mx-2 hidden sm:block" />
            <span className="text-[10px] font-mono uppercase tracking-widest text-white/40 mr-1 hidden sm:inline">Priority:</span>
            {['ALL', 1, 2, 3, 4].map((p) => {
              const pTheme = typeof p === 'number' ? PRIORITY_THEMES[p] : null;
              return (
                <button
                  key={String(p)}
                  type="button"
                  onClick={() => setSelectedPriority(p)}
                  className={`px-2 py-0.5 rounded-lg text-[11px] font-mono transition-all border ${
                    selectedPriority === p
                      ? 'border-cyan-400 bg-cyan-400/20 text-cyan-300 font-bold'
                      : 'border-white/5 bg-black/40 text-white/50 hover:border-white/20 hover:text-white'
                  }`}
                >
                  {pTheme ? pTheme.label : 'All'}
                </button>
              );
            })}
          </div>

          {/* Active Labels Filter & Search */}
          <div className="flex flex-wrap items-center justify-between gap-3">
            {availableLabels.length > 0 && (
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="text-[10px] font-mono uppercase tracking-widest text-white/40 mr-1">Labels:</span>
                {availableLabels.map((tag) => (
                  <button
                    key={tag}
                    type="button"
                    onClick={() => setSelectedLabel(selectedLabel === tag ? null : tag)}
                    className={`px-2 py-0.5 rounded-md text-[10px] font-mono transition-all border ${
                      selectedLabel === tag
                        ? 'border-cyan-400 bg-cyan-400/20 text-cyan-300 font-bold'
                        : 'border-white/5 bg-zinc-900/40 text-zinc-400 hover:border-white/20 hover:text-white'
                    }`}
                  >
                    {tag}
                  </button>
                ))}
                {selectedLabel && (
                  <button
                    type="button"
                    onClick={() => setSelectedLabel(null)}
                    className="text-[10px] font-mono text-rose-400 hover:underline ml-1"
                  >
                    ✕ Clear Tag
                  </button>
                )}
              </div>
            )}

            {/* Quick Search */}
            <div className="relative min-w-[200px] max-w-xs ml-auto">
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Filter directives..."
                className="w-full bg-black/60 border border-white/10 rounded-xl px-3 py-1.5 text-xs text-white placeholder-white/30 focus:border-cyan-400 focus:outline-none"
              />
              {searchQuery && (
                <button
                  type="button"
                  onClick={() => setSearchQuery('')}
                  className="absolute right-2.5 top-1.5 text-xs text-white/40 hover:text-white"
                >
                  ✕
                </button>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Main Task List Viewport */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6 custom-scrollbar">
        <div className="flex items-center gap-3 text-xs text-cyan-400">
          <button type="button" aria-pressed={includeCompleted} onClick={() => setIncludeCompleted(value => !value)} className="rounded border border-white/10 bg-zinc-950/90 px-2 py-1 focus-visible:outline focus-visible:outline-2">
            {includeCompleted ? 'Hide completed' : 'Show completed'}
          </button>
          <span role="status" aria-live="polite">{statusMessage}</span>
        </div>
        {error && (
          <div role="alert" className="p-4 bg-red-950/40 border border-red-500/40 rounded-xl text-sm text-red-300 flex items-center justify-between">
            <span>⚠️ {error}</span>
            <button
              type="button"
              onClick={fetchAllTasks}
              className="px-3 py-1 bg-red-900/60 hover:bg-red-800 rounded-lg text-xs font-bold uppercase tracking-wider"
            >
              Retry
            </button>
          </div>
        )}

        {loading && (
          <div className="py-12 text-center space-y-3 font-mono text-cyan-400 animate-pulse">
            <div className="w-8 h-8 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin mx-auto" />
            <p className="text-xs uppercase tracking-widest">Synchronizing directives telemetry...</p>
          </div>
        )}

        {!loading && filteredTasks.length === 0 && (
          <div className="py-16 text-center border border-white/5 border-dashed rounded-2xl bg-zinc-950/40 space-y-3">
            <div className="text-3xl">🛡️</div>
            <h3 className="text-sm font-bold uppercase tracking-wider text-white">No active directives found</h3>
            <p className="text-xs text-white/40 max-w-sm mx-auto">
              All tactical directives for this filter are satisfied or none have been assigned.
            </p>
            <button
              type="button"
              onClick={() => handleNewTask()}
              className="px-4 py-2 bg-cyan-400/20 border border-cyan-400/40 text-cyan-300 rounded-xl text-xs font-bold uppercase tracking-wider hover:bg-cyan-400 hover:text-black transition-all"
            >
              + Deploy Directive
            </button>
          </div>
        )}

        {/* View 1: TODAY VIEW */}
        {!loading && viewTab === 'today' && filteredTasks.length > 0 && (
          <div className="space-y-6 max-w-4xl mx-auto">
            {/* Overdue Section */}
            {todayTasks.overdue.length > 0 && (
              <div className="space-y-3">
                <div className="flex items-center justify-between border-b border-rose-500/20 pb-2">
                  <h3 className="text-xs font-bold uppercase tracking-widest text-rose-400 flex items-center gap-2">
                    <span>⚠️</span>
                    <span>Overdue Directives ({todayTasks.overdue.length})</span>
                  </h3>
                </div>
                <div className="space-y-2">
                  {todayTasks.overdue.map(renderTaskRow)}
                </div>
              </div>
            )}

            {/* Today Section */}
            <div className="space-y-3">
              <div className="flex items-center justify-between border-b border-amber-500/20 pb-2">
                <h3 className="text-xs font-bold uppercase tracking-widest text-amber-300 flex items-center gap-2">
                  <span>⚡</span>
                  <span>Due Today · {todayStr} ({todayTasks.today.length})</span>
                </h3>
                <button
                  type="button"
                  onClick={() => handleNewTask(todayStr)}
                  className="text-[11px] font-mono text-cyan-400 hover:text-white"
                >
                  + Add for Today
                </button>
              </div>
              {todayTasks.today.length === 0 ? (
                <p className="text-xs font-mono text-white/30 italic py-2">No directives due today.</p>
              ) : (
                <div className="space-y-2">
                  {todayTasks.today.map(renderTaskRow)}
                </div>
              )}
            </div>

            {/* Unscheduled / Inbox Section */}
            {todayTasks.unscheduled.length > 0 && (
              <div className="space-y-3 pt-4">
                <div className="flex items-center justify-between border-b border-white/5 pb-2">
                  <h3 className="text-xs font-bold uppercase tracking-widest text-white/50 flex items-center gap-2">
                    <span>📥</span>
                    <span>Unscheduled Directives ({todayTasks.unscheduled.length})</span>
                  </h3>
                </div>
                <div className="space-y-2">
                  {todayTasks.unscheduled.map(renderTaskRow)}
                </div>
              </div>
            )}
          </div>
        )}

        {/* View 2: UPCOMING 7-DAY AGENDA VIEW */}
        {!loading && viewTab === 'upcoming' && filteredTasks.length > 0 && (
          <div className="space-y-8 max-w-4xl mx-auto">
            {/* Overdue alert if any */}
            {upcomingGrouped.overdue.length > 0 && (
              <div className="space-y-3">
                <div className="flex items-center justify-between border-b border-rose-500/20 pb-2">
                  <h3 className="text-xs font-bold uppercase tracking-widest text-rose-400 flex items-center gap-2">
                    <span>⚠️</span>
                    <span>Overdue Directives ({upcomingGrouped.overdue.length})</span>
                  </h3>
                </div>
                <div className="space-y-2">
                  {upcomingGrouped.overdue.map(renderTaskRow)}
                </div>
              </div>
            )}

            {/* 7 Daily Agenda Buckets */}
            {agendaDays.map((day) => {
              const tasksForDay = upcomingGrouped.dayMap[day.dateStr] || [];
              return (
                <div key={day.dateStr} className="space-y-3">
                  <div className="flex items-center justify-between border-b border-white/10 pb-2">
                    <div className="flex items-center gap-2">
                      <span className="text-xs">{day.isToday ? '☀️' : day.isTomorrow ? '🌅' : '📅'}</span>
                      <h3
                        className={`text-xs font-bold uppercase tracking-wider ${
                          day.isToday ? 'text-amber-300' : day.isTomorrow ? 'text-cyan-300' : 'text-white/80'
                        }`}
                      >
                        {day.label}
                      </h3>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-white/5 text-white/40">
                        {tasksForDay.length}
                      </span>
                    </div>
                    <button
                      type="button"
                      onClick={() => handleNewTask(day.dateStr)}
                      className="text-[11px] font-mono text-cyan-400 hover:text-white"
                    >
                      + Add
                    </button>
                  </div>

                  {tasksForDay.length === 0 ? (
                    <div className="py-2.5 px-3 rounded-lg border border-white/5 bg-black/20 text-[11px] font-mono text-white/20 italic">
                      No directives scheduled
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {tasksForDay.map(renderTaskRow)}
                    </div>
                  )}
                </div>
              );
            })}

            {/* Later (> 7 Days) */}
            {upcomingGrouped.later.length > 0 && (
              <div className="space-y-3 pt-4">
                <div className="flex items-center justify-between border-b border-white/10 pb-2">
                  <h3 className="text-xs font-bold uppercase tracking-widest text-white/50 flex items-center gap-2">
                    <span>🔮</span>
                    <span>Later (Beyond 7 Days) ({upcomingGrouped.later.length})</span>
                  </h3>
                </div>
                <div className="space-y-2">
                  {upcomingGrouped.later.map(renderTaskRow)}
                </div>
              </div>
            )}

            {/* Unscheduled */}
            {upcomingGrouped.unscheduled.length > 0 && (
              <div className="space-y-3 pt-4">
                <div className="flex items-center justify-between border-b border-white/5 pb-2">
                  <h3 className="text-xs font-bold uppercase tracking-widest text-white/50 flex items-center gap-2">
                    <span>📥</span>
                    <span>Unscheduled Directives ({upcomingGrouped.unscheduled.length})</span>
                  </h3>
                </div>
                <div className="space-y-2">
                  {upcomingGrouped.unscheduled.map(renderTaskRow)}
                </div>
              </div>
            )}
          </div>
        )}

        {/* View 3: ALL DIRECTIVES VIEW */}
        {!loading && viewTab === 'all' && filteredTasks.length > 0 && (
          <div className="space-y-3 max-w-4xl mx-auto">
            <div className="flex items-center justify-between border-b border-white/10 pb-2">
              <h3 className="text-xs font-bold uppercase tracking-widest text-white/70">
                All Active Directives ({filteredTasks.length})
              </h3>
            </div>
            <div className="space-y-2">
              {filteredTasks.map(renderTaskRow)}
            </div>
          </div>
        )}
      </div>

      {/* Task Creation & Edit Modal */}
      <AnimatePresence>
        {isModalOpen && (
          <TaskModal
            isOpen={isModalOpen}
            onClose={() => setIsModalOpen(false)}
            initialTask={editingTask}
            defaultDueDate={modalDefaultDueDate}
            defaultArea={selectedManor !== 'ALL' ? selectedManor : 'Sanctum'}
            onTaskSaved={fetchAllTasks}
          />
        )}
      </AnimatePresence>
    </div>
  );
}
