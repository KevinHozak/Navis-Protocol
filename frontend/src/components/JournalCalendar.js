"use client";

import { journalDay } from "@/lib/journalDay";

import React, { useState, useEffect, useCallback, useRef } from 'react';
import AsyncJobModal from './AsyncJobModal';
import { apiFetch } from '@/lib/desktopApi';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

const DAYS = ['S', 'M', 'T', 'W', 'T', 'F', 'S'];
const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

function getDaysInMonth(year, month) {
  return new Date(year, month, 0).getDate();
}

function getFirstDayOfWeek(year, month) {
  // 0 = Sunday
  return new Date(year, month - 1, 1).getDay();
}

function buildCalendarGrid(year, month) {
  const totalDays = getDaysInMonth(year, month);
  const firstDow = getFirstDayOfWeek(year, month);
  const grid = [];
  let week = Array(7).fill(null);
  let dayCounter = 1;

  for (let col = firstDow; col < 7; col++) {
    week[col] = dayCounter++;
  }
  grid.push(week);

  while (dayCounter <= totalDays) {
    week = Array(7).fill(null);
    for (let col = 0; col < 7 && dayCounter <= totalDays; col++) {
      week[col] = dayCounter++;
    }
    grid.push(week);
  }

  // Pad to always show 6 rows (like the Python version)
  while (grid.length < 6) {
    grid.push(Array(7).fill(null));
  }

  return grid;
}

const getLocalDateStr = journalDay;

export default function JournalCalendar({ onDateSelect, selectedDate, onRolloverComplete }) {
  const requestId = useRef(null);
  const today = new Date();
  const [year, setYear] = useState(today.getFullYear());
  const [month, setMonth] = useState(today.getMonth() + 1); // 1-indexed
  const [activeDates, setActiveDates] = useState(new Set());
  const [loadingDates, setLoadingDates] = useState(false);
  const [isRollingOver, setIsRollingOver] = useState(false);
  const [activeJob, setActiveJob] = useState(null);

  const completeRollover = async () => {
    try {
      const statusRes = await apiFetch(`/api/status`);
      if (statusRes.ok) {
        const statusData = await statusRes.json();
        const new_date = statusData.last_updated;
        if (new_date) {
          const [newY, newM, newD] = new_date.split('-');
          const parsedYear = parseInt(newY);
          const parsedMonth = parseInt(newM);
          
          setYear(parsedYear);
          setMonth(parsedMonth);
          await fetchActiveDates(parsedYear, parsedMonth);
          
          if (onRolloverComplete) {
            onRolloverComplete(new_date);
          }
        }
      }
    } catch (e) {
      console.error("Failed to fetch new status after rollover:", e);
    } finally {
      setActiveJob(null);
      requestId.current = null;
    }
  };

  const fetchActiveDates = useCallback(async (y, m) => {
    setLoadingDates(true);
    try {
      const res = await apiFetch(`/api/journal/month?year=${y}&month=${m}`);
      const data = await res.json();
      setActiveDates(new Set(data.dates || []));
    } catch (e) {
      setActiveDates(new Set());
    } finally {
      setLoadingDates(false);
    }
  }, []);

  useEffect(() => {
    fetchActiveDates(year, month);
  }, [year, month, fetchActiveDates]);

  useEffect(() => {
    if (selectedDate) {
      const [y, m, d] = selectedDate.split('-');
      if (y && m) {
        setYear(parseInt(y, 10));
        setMonth(parseInt(m, 10));
      }
    }
  }, [selectedDate]);

  const changeMonth = (delta) => {
    let m = month + delta;
    let y = year;
    if (m > 12) { m = 1; y += 1; }
    if (m < 1)  { m = 12; y -= 1; }
    setMonth(m);
    setYear(y);
  };

  const goToToday = () => {
    const t = new Date();
    setYear(t.getFullYear());
    setMonth(t.getMonth() + 1);
    const todayStr = getLocalDateStr(t);
    onDateSelect(todayStr);
  };

  const handleNewDay = async () => {
    const confirmMsg = "Initiate Daily Rollover?\n\nThis will run the backup protocol, archive today's tasks, process XP accrual, and anchor the new day's journal.";
    if (!window.confirm(confirmMsg)) return;

    setIsRollingOver(true);
    try {
      requestId.current ??= crypto.randomUUID();
      const res = await apiFetch(`/api/journal/rollover?run_async=true&request_id=${requestId.current}`, {
        method: 'POST',
      });
      if (!res.ok) {
        throw new Error(await res.text());
      }
      const data = await res.json();
      if (data.status === 'accepted' && data.job_id) {
        setActiveJob({ id: data.job_id, title: "Daily Rollover Sequence" });
      } else {
        alert("Daily rollover finished but did not return an accepted job.");
      }
    } catch (err) {
      console.error("DEBUG: Rollover failed:", err);
      alert(`Daily Rollover failed: ${err.message || err}`);
    } finally {
      setIsRollingOver(false);
    }
  };

  const handleDayClick = (day) => {
    const dateStr = `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
    onDateSelect(dateStr);
  };

  const grid = buildCalendarGrid(year, month);

  const todayStr = getLocalDateStr(today);

  return (
    <div className="bg-zinc-900 border border-white/10 rounded m-2 pb-3 mb-2 select-none">
      {/* Month/Year Header */}
      <div className="flex items-center justify-between px-3 pt-3 pb-2 gap-1">
        <button
          onClick={() => setYear(y => y - 1)}
          className="w-6 h-6 flex items-center justify-center rounded text-white/30 hover:text-accent hover:bg-accent/10 transition-all text-[10px] font-bold"
          title="Previous year"
        >«</button>
        <button
          onClick={() => changeMonth(-1)}
          className="w-6 h-6 flex items-center justify-center rounded text-white/30 hover:text-accent hover:bg-accent/10 transition-all text-[10px] font-bold"
          title="Previous month"
        >‹</button>

        <div className="flex-1 text-center">
          <span className="text-[11px] font-black uppercase tracking-[0.2em] text-accent">
            {MONTHS[month - 1]} {year}
          </span>
          {loadingDates && (
            <span className="ml-1.5 inline-block w-1.5 h-1.5 rounded-full bg-accent/50 animate-pulse" />
          )}
        </div>

        <button
          onClick={() => changeMonth(1)}
          className="w-6 h-6 flex items-center justify-center rounded text-white/30 hover:text-accent hover:bg-accent/10 transition-all text-[10px] font-bold"
          title="Next month"
        >›</button>
        <button
          onClick={() => setYear(y => y + 1)}
          className="w-6 h-6 flex items-center justify-center rounded text-white/30 hover:text-accent hover:bg-accent/10 transition-all text-[10px] font-bold"
          title="Next year"
        >»</button>
      </div>

      {/* Day-of-week headers */}
      <div className="grid grid-cols-7 px-2 mb-1">
        {DAYS.map((d, i) => (
          <div
            key={i}
            className="text-center text-[9px] font-bold uppercase tracking-wider text-white/25"
          >
            {d}
          </div>
        ))}
      </div>

      {/* Calendar grid */}
      <div className="px-2 space-y-0.5">
        {grid.map((week, wi) => (
          <div key={wi} className="grid grid-cols-7">
            {week.map((day, di) => {
              if (!day) {
                return <div key={di} className="h-7" />;
              }
              const dateStr = `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
              const hasEntry = activeDates.has(dateStr);
              const isSelected = selectedDate === dateStr;
              const isToday = dateStr === todayStr;

              return (
                <button
                  key={di}
                  onClick={() => handleDayClick(day)}
                  disabled={!hasEntry}
                  title={hasEntry ? `Load ${dateStr}` : dateStr}
                  className={`
                    h-7 w-full flex items-center justify-center rounded text-[10px] font-bold transition-all
                    ${isSelected
                      ? 'bg-accent text-zinc-950 shadow-[0_0_10px_rgba(0,212,255,0.3)]'
                      : hasEntry
                        ? 'text-white hover:bg-accent/20 hover:text-accent cursor-pointer'
                        : 'text-white/15 cursor-default'
                    }
                    ${isToday && !isSelected ? 'ring-1 ring-accent/40 ring-inset' : ''}
                  `}
                >
                  {hasEntry && !isSelected && (
                    <span className="relative">
                      {day}
                      <span className="absolute -bottom-0.5 left-1/2 -translate-x-1/2 w-1 h-1 rounded-full bg-accent/70" />
                    </span>
                  )}
                  {(!hasEntry || isSelected) && day}
                </button>
              );
            })}
          </div>
        ))}
      </div>

      {/* Today button */}
      <div className="px-2 mt-2 flex flex-col gap-1.5">
        <button
          onClick={goToToday}
          className="w-full py-1.5 rounded border transition-all text-[9px] font-bold uppercase tracking-[0.2em] bg-zinc-900 border-white/10 text-white/60 hover:bg-zinc-800 hover:text-white hover:border-white/20"
        >
          📅 Today
        </button>
        <button
          onClick={handleNewDay}
          disabled={isRollingOver}
          className={`w-full py-1.5 rounded border transition-all text-[9px] font-bold uppercase tracking-[0.2em] ${
            isRollingOver 
              ? 'border-yellow-500/20 bg-yellow-500/5 text-yellow-500/60 cursor-not-allowed animate-pulse shadow-[0_0_10px_rgba(234,179,8,0.15)]'
              : 'bg-zinc-900 border-white/10 text-white/60 hover:bg-zinc-800 hover:text-white hover:border-white/20'
          }`}
        >
          {isRollingOver ? '🌅 Rolling...' : '🌅 New Day'}
        </button>
      </div>
      {activeJob && (
        <AsyncJobModal 
          jobId={activeJob.id} 
          title={activeJob.title} 
          operation="rollover"
          onClose={() => { setActiveJob(null); requestId.current = null; }}
          onComplete={completeRollover}
        />
      )}
    </div>
  );
}
