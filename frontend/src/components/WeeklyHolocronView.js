"use client";

import React, { useState, useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import { apiFetch } from '@/lib/desktopApi';
import ReadFreshness from './ReadFreshness';
import HolocronEvidence from './HolocronEvidence';

const measured = (value, suffix = '') => value == null ? 'Unavailable' : `${value}${suffix}`;

export default function WeeklyHolocronView({ activeWeekId, onOpenBestiary, onOpenJournal }) {
  const [data, setData] = useState(null);
  const [manifest, setManifest] = useState([]);
  const [selectedWeek, setSelectedWeek] = useState(activeWeekId || null);
  const [loading, setLoading] = useState(true);
  const [regenerating, setRegenerating] = useState(false);
  const [error, setError] = useState(null);
  const [exportNotice, setExportNotice] = useState(null);
  const [synthesizingAi, setSynthesizingAi] = useState(false);

  const [lastRead, setLastRead] = useState(null);
  const requestRevision = useRef(0);
  const selectedWeekRef = useRef(selectedWeek);
  selectedWeekRef.current = selectedWeek;
  const selectWeek = (week) => {
    requestRevision.current += 1;
    selectedWeekRef.current = week;
    setData(null);
    setLastRead(null);
    setError(null);
    setRegenerating(false);
    setSynthesizingAi(false);
    setSelectedWeek(week);
  };
  useEffect(() => () => { requestRevision.current += 1; }, []);

  // 1. Fetch manifest of available weeks
  useEffect(() => {
    let isCancelled = false;
    apiFetch('/api/holocron/weekly/manifest')
      .then(res => res.ok ? res.json() : [])
      .then(list => {
        if (!isCancelled && Array.isArray(list)) {
          if (list.length > 0) setManifest(list);
          if (!selectedWeekRef.current && list.length > 0) {
            selectWeek(list[0].week_id);
          }
        }
      })
      .catch(err => {
        if (!isCancelled) console.warn("Failed to load Holocron manifest", err);
      });

    return () => { isCancelled = true; };
  }, []);

  // Update selected week if prop changes
  useEffect(() => {
    if (activeWeekId && activeWeekId !== selectedWeek) {
      selectWeek(activeWeekId);
    }
  }, [activeWeekId]);

  // 2. Fetch specific or latest week data
  const fetchHolocron = (weekId) => {
    const revision = ++requestRevision.current;
    setLoading(true);
    setError(null);
    let endpoint = '/api/holocron/weekly/latest';
    if (weekId) {
      const manifestItem = manifest.find((m) => m.week_id === weekId);
      if (manifestItem?.is_in_flight) {
        endpoint = '/api/holocron/weekly/current';
      } else {
        endpoint = `/api/holocron/weekly/${weekId}`;
      }
    }

    apiFetch(endpoint, { signal: AbortSignal.timeout(10000) })
      .then(res => {
        if (!res.ok) throw new Error(`Holocron load failed (${res.status})`);
        return res.json();
      })
      .then(payload => {
        if (revision !== requestRevision.current) return;
        if (!payload?.week_id || (weekId && payload.week_id !== weekId)) throw new Error('Holocron identity mismatch');
        setData(payload);
        setLastRead(new Date().toISOString());
        if (!selectedWeek && payload?.week_id) {
          setSelectedWeek(payload.week_id);
        }
        setLoading(false);
      })
      .catch(err => {
        if (revision !== requestRevision.current) return;
        setError(err.message);
        setLoading(false);
      });
  };

  useEffect(() => {
    fetchHolocron(selectedWeek);
    return () => { requestRevision.current += 1; };
  }, [selectedWeek, manifest]);

  // 3. Handle manual regeneration
  const handleRegenerate = async () => {
    if (!selectedWeek) return;
    const week = selectedWeek;
    const revision = ++requestRevision.current;
    setRegenerating(true);
    try {
      const res = await apiFetch(`/api/holocron/weekly/${selectedWeek}/regenerate`, { method: 'POST' });
      if (!res.ok) throw new Error(`Regeneration failed (${res.status})`);
      const updated = await res.json();
      if (revision !== requestRevision.current) return;
      if (updated?.week_id !== week) throw new Error('Holocron identity mismatch');
      setData(updated);
      setLastRead(new Date().toISOString());
      setError(null);
    } catch (err) {
      if (revision === requestRevision.current) setError(err.message);
    } finally {
      if (revision === requestRevision.current) setRegenerating(false);
    }
  };

  // 4. Handle export
  const handleExportJson = () => {
    if (!data) return;
    const jsonStr = JSON.stringify(data, null, 2);
    const blob = new Blob([jsonStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `Holocron_${data.week_id}.json`;
    a.click();
    URL.revokeObjectURL(url);
    
    setExportNotice("Exported Holocron JSON payload!");
    setTimeout(() => setExportNotice(null), 3500);
  };

  const handleExportHtml = async () => {
    if (!data) return;
    try {
      const res = await apiFetch(`/api/holocron/weekly/${data.week_id}/html`);
      if (!res.ok) throw new Error(`HTML export failed (${res.status})`);
      let htmlText = await res.text();
      try {
        const parsed = JSON.parse(htmlText);
        if (parsed && typeof parsed.html === 'string') {
          htmlText = parsed.html;
        }
      } catch {
        // Already raw HTML text
      }
      const exported = new DOMParser().parseFromString(htmlText, 'text/html');
      const adjustment = exported.getElementById('decision-adjustment');
      if (adjustment && data.decision_review) {
        adjustment.textContent = data.decision_review.adjustment;
        if (data.decision_review.suggestion_source === 'user_edit') adjustment.append(' (User-edited proposal)');
      }
      htmlText = '<!DOCTYPE html>\n' + exported.documentElement.outerHTML;
      const blob = new Blob([htmlText], { type: 'text/html' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `Holocron_${data.week_id}.html`;
      a.click();
      URL.revokeObjectURL(url);

      setExportNotice("Exported standalone HTML dashboard!");
      setTimeout(() => setExportNotice(null), 3500);
    } catch (err) {
      alert("Export failed: " + err.message);
    }
  };

  // 5. Handle AI Debrief synthesis via local Ollama
  const handleSynthesizeAiDebrief = async () => {
    if (!selectedWeek && !data?.week_id) return;
    const targetWeek = selectedWeek || data.week_id;
    const revision = ++requestRevision.current;
    setSynthesizingAi(true);
    try {
      const res = await apiFetch(`/api/holocron/weekly/${targetWeek}/debrief/ai`, { method: 'POST' });
      if (!res.ok) throw new Error(`AI Debrief failed (${res.status})`);
      const result = await res.json();
      if (revision !== requestRevision.current) return;
      if (result.holocron?.week_id && result.holocron.week_id !== targetWeek) throw new Error('Holocron identity mismatch');
      setData(prev => ({
        ...prev,
        tactical_debrief: result.tactical_debrief,
        debrief_source: result.debrief_source,
        evidence: result.holocron?.evidence || prev.evidence
      }));
      setExportNotice(['ollama', 'openrouter'].includes(result.debrief_source) ? '✨ Tactical Sage debrief synthesized by the configured provider!' : '⚠️ Provider unavailable or disabled. Retained rule-based debrief.');
      setTimeout(() => setExportNotice(null), 4000);
    } catch (err) {
      if (revision === requestRevision.current) setError(err.message);
    } finally {
      if (revision === requestRevision.current) setSynthesizingAi(false);
    }
  };

  if (loading && !data) {
    return (
      <div role="status" className="min-h-[60vh] flex flex-col items-center justify-center space-y-4">
        <div className="w-12 h-12 rounded-full border-4 border-cyan-400 border-t-transparent animate-spin" />
        <div className="text-xs font-mono uppercase tracking-[0.3em] text-cyan-300">
          Decrypting Weekly Holocron Telemetry...
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div role="alert" className="p-8 bg-zinc-950/80 border border-red-500/30 rounded-xl space-y-4 text-center max-w-xl mx-auto my-12">
        <div className="text-3xl">💠</div>
        <h2 className="text-lg font-bold text-white uppercase tracking-wider">Holocron Telemetry Unavailable</h2>
        <p className="text-xs text-red-200/80 font-mono">{error || "No active telemetry found for this cycle."}</p>
        <button
          onClick={() => fetchHolocron(selectedWeek)}
          className="px-4 py-2 bg-cyan-500/20 border border-cyan-500/50 text-cyan-300 rounded text-xs font-bold uppercase tracking-wider hover:bg-cyan-500/30 transition-all"
        >
          Retry Transmission
        </button>
      </div>
    );
  }

  const { summary, tactical_debrief, daily_telemetry = [], sector_distribution = [], combat = {}, progression = {}, squad_mvp } = data;

  return (
    <motion.div
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      className="w-full max-w-6xl mx-auto space-y-6 pb-12"
    >
      <ReadFreshness label="Holocron" pending={loading || regenerating || synthesizingAi} lastRead={lastRead} error={!!error} sourceLabel="Generated" sourceTime={data.generated_at} onRetry={() => fetchHolocron(selectedWeek)} />
      {/* Top Cockpit Header */}
      <header className="flex flex-wrap items-center justify-between gap-4 p-5 rounded-xl border border-white/10 bg-zinc-950/70 backdrop-blur-xl shadow-2xl">
        <div className="flex items-center gap-3">
          <span className="px-2.5 py-1 rounded bg-cyan-950/60 border border-cyan-400/40 text-cyan-300 font-mono text-[11px] font-bold tracking-wider">
            NAVIS // HOLOCRON
          </span>
          <h1 className="text-xl font-extrabold uppercase tracking-wide text-white">
            Weekly Holocron Synthesis
          </h1>
          {data.is_in_flight ? (
            <span className="px-2.5 py-1 rounded-full bg-emerald-500/20 border border-emerald-400/40 text-emerald-300 font-mono text-[10px] font-bold tracking-wider animate-pulse flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
              ⚡ LIVE WTD
            </span>
          ) : (
            <span className="px-2.5 py-1 rounded-full bg-white/5 border border-white/10 text-zinc-400 font-mono text-[10px] font-medium tracking-wider flex items-center gap-1.5">
              <span>🔒</span> CONCLUDED
            </span>
          )}
        </div>

        <div className="flex items-center gap-3">
          {manifest.length > 0 && (
            <select
              aria-label="Select Operating Cycle"
              value={selectedWeek || data.week_id}
              onChange={(e) => selectWeek(e.target.value)}
              className="bg-zinc-900 border border-white/10 text-white text-xs font-mono px-3 py-1.5 rounded focus:outline-none focus:border-cyan-400 cursor-pointer"
            >
              {manifest.map((item) => (
                <option key={item.week_id} value={item.week_id}>
                  Cycle {item.week_id} {item.is_in_flight ? '[⚡ Live WTD]' : `(${item.start_date || 'Past'})`}
                </option>
              ))}
            </select>
          )}

          <button
            onClick={handleRegenerate}
            disabled={loading || regenerating || synthesizingAi}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-white/5 border border-white/10 text-xs font-bold text-white hover:bg-white/10 transition-all disabled:opacity-50"
            title="Re-aggregate from daily journals and XP ledger"
          >
            {regenerating ? '🔄 Calibrating...' : '🔄 Regenerate'}
          </button>

          <button
            onClick={handleExportHtml}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-cyan-500/20 border border-cyan-400/50 text-cyan-300 text-xs font-bold hover:bg-cyan-500/30 hover:shadow-[0_0_12px_rgba(0,212,255,0.25)] transition-all"
            title="Download standalone single-file HTML dashboard"
          >
            📥 Export HTML
          </button>

          <button
            onClick={handleExportJson}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-white/5 border border-white/10 text-zinc-300 text-xs font-bold hover:bg-white/10 transition-all"
            title="Download raw JSON telemetry"
          >
            📦 JSON
          </button>
        </div>
      </header>

      {exportNotice && (
        <div role="status" className="p-3 bg-emerald-950/60 border border-emerald-500/30 rounded-lg text-emerald-300 text-xs font-mono text-center">
          {exportNotice}
        </div>
      )}

      <section className="p-5 rounded-xl border border-white/10 bg-zinc-950/90 backdrop-blur-md space-y-3">
        <h2 className="text-sm font-bold text-cyan-300">Decision review</h2>
        <p className="text-xs text-zinc-400">Rule-based observations and proposal · {data.decision_review?.suggestion_source === 'user_edit' ? 'User-edited adjustment' : 'Not AI interpretation'}</p>
        <h3 className="text-sm text-cyan-200">What changed</h3>
        <p className="text-sm text-zinc-300">{data.decision_review?.changed || 'Unknown'}</p>
        <h3 className="text-sm text-cyan-200">Unresolved</h3>
        <p className="text-sm text-zinc-300">{data.decision_review?.unresolved || 'Unknown'}</p>
        <HolocronEvidence weekId={data.week_id} evidence={data.evidence} onOpenJournal={onOpenJournal} decisionOnly />
        <label className="block text-sm text-cyan-200">Suggested adjustment
          <textarea maxLength={2000} value={data.decision_review?.adjustment || ''} onChange={event => setData(previous => ({...previous, decision_review: {...previous.decision_review, adjustment: event.target.value, suggestion_source: 'user_edit'}}))} className="mt-2 w-full rounded border border-white/10 bg-zinc-900 p-2 text-white" />
        </label>
        <p className="text-xs text-zinc-400">{data.decision_review?.limits || 'Evidence unavailable. Review sources before choosing an adjustment.'}</p>
        <p className="text-xs text-zinc-500">Edits apply to this view and exports; reload resets them.</p>
      </section>

      {/* Tactical Debrief Banner */}
      <section className="p-5 rounded-xl border border-white/10 border-l-4 border-l-cyan-400 bg-zinc-950/60 backdrop-blur-xl shadow-lg space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/5 pb-2">
          <div className="flex items-center gap-2 text-cyan-300 text-xs font-mono font-bold uppercase tracking-widest">
            <span>💠</span>
            <span>Command Tactical Debrief // {data.week_id}</span>
            {['ollama', 'openrouter'].includes(data.debrief_source) ? (
              <span className="px-2 py-0.5 rounded bg-purple-950/80 border border-purple-400/50 text-purple-300 text-[10px] font-mono font-bold tracking-wider">
                ✨ AI INTERPRETATION
              </span>
            ) : (
              <span className="px-2 py-0.5 rounded bg-white/5 border border-white/10 text-zinc-400 text-[10px] font-mono tracking-wider">
                RULE-BASED
              </span>
            )}
          </div>
          <button
            onClick={handleSynthesizeAiDebrief}
            disabled={loading || regenerating || synthesizingAi}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-purple-500/20 border border-purple-400/50 text-purple-200 text-xs font-mono font-bold hover:bg-purple-500/30 hover:border-purple-300 transition-all disabled:opacity-50"
            title="Synthesize an inspiring tactical debrief using the configured provider"
          >
            {synthesizingAi ? '✨ Synthesizing...' : '✨ AI Tactical Debrief'}
          </button>
        </div>
        <p className="text-xs text-zinc-400">{['ollama', 'openrouter'].includes(data.debrief_source) ? 'AI interpretation; not verified conclusions.' : 'Deterministic summary of observed inputs.'}</p>
        <p className="text-sm leading-relaxed text-zinc-200">
          {tactical_debrief}
        </p>
      </section>

      <HolocronEvidence weekId={data.week_id} evidence={data.evidence} onOpenJournal={onOpenJournal} />

      {/* Headline Metric Cards */}
      <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-5 rounded-xl border border-white/10 bg-zinc-950/60 backdrop-blur-xl space-y-1 shadow-lg">
          <div className="text-[11px] font-mono uppercase tracking-wider text-zinc-400">Precision Clearance</div>
          <div className="text-3xl font-black text-cyan-400 tracking-tight">{measured(summary.precision_rate, '%')}</div>
          <div className="text-xs text-zinc-400 font-mono">{measured(summary.completed_tasks)} / {measured(summary.total_tasks)} Mandates Cleared</div>
        </div>

        <div className="p-5 rounded-xl border border-white/10 bg-zinc-950/60 backdrop-blur-xl space-y-1 shadow-lg">
          <div className="text-[11px] font-mono uppercase tracking-wider text-zinc-400">Progression Yield</div>
          <div className="text-3xl font-black text-purple-400 tracking-tight">{summary.total_xp_gained == null ? 'Unavailable' : summary.total_xp_gained.toLocaleString()} <span className="text-sm font-normal">XP</span></div>
          <div className="text-xs text-zinc-400 font-mono">Sovereign Level {measured(summary.current_level)}</div>
        </div>

        <div className="p-5 rounded-xl border border-white/10 bg-zinc-950/60 backdrop-blur-xl space-y-1 shadow-lg">
          <div className="text-[11px] font-mono uppercase tracking-wider text-zinc-400">Threat Neutralization</div>
          <div className="text-3xl font-black text-rose-400 tracking-tight">{measured(summary.threats_neutralized)} <span className="text-sm font-normal">Slayings</span></div>
          <div className="text-xs text-zinc-400 font-mono">{measured(summary.battles_fought)} Battles Fought</div>
        </div>

        <div className="p-5 rounded-xl border border-white/10 bg-zinc-950/60 backdrop-blur-xl space-y-1 shadow-lg">
          <div className="text-[11px] font-mono uppercase tracking-wider text-zinc-400">System Readiness</div>
          <div className="text-3xl font-black text-emerald-400 tracking-tight">{measured(summary.avg_readiness, '%')}</div>
          <div className="text-xs text-zinc-400 font-mono">{measured(summary.deep_work_hours)} measured focus hours</div>
        </div>
      </section>

      {/* Main 2-Column Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Left 2 Cols: 7-Day Rhythm Histogram & Manor Distribution */}
        <div className="lg:col-span-2 space-y-6">
          
          {/* 7-Day Precision Chart */}
          <section className="p-6 rounded-xl border border-white/10 bg-zinc-950/60 backdrop-blur-xl space-y-6 shadow-xl">
            <div className="flex justify-between items-center border-b border-white/10 pb-3">
              <h2 className="text-sm font-bold uppercase tracking-wider text-white flex items-center gap-2">
                <span>📊</span> 7-Day Precision & Task Rhythm
              </h2>
              <span className="text-xs font-mono text-cyan-400">
                {summary.is_in_flight
                  ? `In-Flight: Day ${summary.days_elapsed || 1} of 7 (${summary.days_remaining || 0}d remaining)`
                  : 'Baseline Target: 80%+'}
              </span>
            </div>

            <div className="flex items-end justify-between gap-3 h-44 pt-4 px-2">
              {daily_telemetry.map((day) => {
                const isUpcoming = day.day_status === 'upcoming';
                const isActive = day.day_status === 'active';
                const heightPct = isUpcoming ? 8 : Math.max(10, Math.min(100, day.precision || (day.total > 0 ? (day.completed / day.total * 100) : 0)));
                const barColor = isUpcoming ? 'rgba(255,255,255,0.08)' : (heightPct >= 95 ? '#10b981' : heightPct >= 80 ? '#00d4ff' : heightPct >= 60 ? '#f59e0b' : '#ff4d4d');
                return (
                  <div key={day.date} className={`flex-1 flex flex-col items-center justify-end h-full gap-2 ${isUpcoming ? 'opacity-40' : ''}`}>
                    <span className="text-[11px] font-mono text-zinc-300">
                      {isUpcoming ? '—' : measured(day.precision == null ? null : Math.round(day.precision), '%')}
                    </span>
                    <div className={`w-full max-w-[36px] bg-white/5 rounded-md h-full flex flex-col justify-end overflow-hidden border ${isActive ? 'border-cyan-400 shadow-[0_0_10px_rgba(0,212,255,0.35)]' : isUpcoming ? 'border-dashed border-white/10' : 'border-white/5'}`}>
                      <div
                        className="w-full rounded-sm transition-all duration-500"
                        style={{ height: `${heightPct}%`, backgroundColor: barColor }}
                        title={`${day.date} [${day.source_status || day.day_status || 'day'}]: ${measured(day.completed)}/${measured(day.total)} tasks (${measured(day.precision, '%')})`}
                      />
                    </div>
                    <span className={`text-xs font-mono font-bold flex items-center gap-1 ${isActive ? 'text-cyan-300' : isUpcoming ? 'text-zinc-500' : 'text-zinc-400'}`}>
                      {day.day_name}
                      {isActive && <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" title="Current Day" />}
                    </span>
                  </div>
                );
              })}
            </div>
          </section>

          {/* Manor Labor Balance */}
          <section className="p-6 rounded-xl border border-white/10 bg-zinc-950/60 backdrop-blur-xl space-y-4 shadow-xl">
            <div className="flex justify-between items-center border-b border-white/10 pb-3">
              <h2 className="text-sm font-bold uppercase tracking-wider text-white flex items-center gap-2">
                <span>🏰</span> Manor & Sector Labor Distribution
              </h2>
              <span className="text-xs font-mono text-zinc-400">{measured(summary.completed_tasks)} observed cleared mandates</span>
            </div>

            <div className="space-y-4 pt-1">
              {sector_distribution.map((sector) => (
                <div key={sector.sector_id} className="space-y-1.5">
                  <div className="flex justify-between text-xs">
                    <span className="font-semibold text-white flex items-center gap-1.5">
                      <span>{sector.icon}</span> {sector.name}
                    </span>
                    <span className="font-mono text-zinc-400">{measured(sector.completed)} tasks ({measured(sector.percentage, '%')})</span>
                  </div>
                  <div className="w-full h-2 rounded-full bg-white/5 overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all duration-500"
                      style={{ width: `${Math.min(100, sector.percentage)}%`, backgroundColor: sector.color }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </section>

        </div>

        {/* Right Col: Threat Neutralization, Honors & Squad Mentions */}
        <div className="space-y-6">

          {/* Threat Neutralization */}
          <section className="p-6 rounded-xl border border-white/10 bg-zinc-950/60 backdrop-blur-xl space-y-4 shadow-xl">
            <div className="flex justify-between items-center border-b border-white/10 pb-3">
              <h2 className="text-sm font-bold uppercase tracking-wider text-white flex items-center gap-2">
                <span>👾</span> Threat Neutralization
              </h2>
              <span className="text-xs font-mono text-rose-400">{measured(combat.victories)} verified victories</span>
            </div>

            <div className="space-y-2.5">
              {(combat.beasts_neutralized || []).map((beast, idx) => (
                <div
                  key={idx}
                  className="flex justify-between items-center p-3 rounded-lg border border-white/5 border-l-2 border-l-rose-500 bg-white/[0.02]"
                >
                  <div className="space-y-0.5">
                    <button type="button" onClick={() => onOpenBestiary?.(beast.bestiary_name || beast.name)} className="text-xs font-bold text-amber-400 hover:underline" aria-label={`Open ${beast.name} in Bestiary`}>{beast.name} ↗</button>
                    <div className="text-[10px] font-mono text-zinc-400">{beast.category || 'Threat'} {'//'} {beast.difficulty || 'Elite'}</div>
                  </div>
                  <span className="text-xs font-mono font-bold text-amber-400">{measured(beast.xp_awarded)} XP</span>
                </div>
              ))}

              {(!combat.beasts_neutralized || combat.beasts_neutralized.length === 0) && (
                <div className="text-center py-6 text-xs text-zinc-500 font-mono uppercase tracking-widest">
                  No verified victory records are aggregated.
                </div>
              )}
              {(combat.mentioned_beasts || []).map((beast, index) => <div key={`mention-${index}`} className="text-xs text-zinc-400">Journal mention: {beast.name} · outcome unverified</div>)}
            </div>
          </section>

          {/* Honors & Squad Mentions */}
          <section className="p-6 rounded-xl border border-white/10 bg-zinc-950/60 backdrop-blur-xl space-y-4 shadow-xl">
            <div className="flex justify-between items-center border-b border-white/10 pb-3">
              <h2 className="text-sm font-bold uppercase tracking-wider text-white flex items-center gap-2">
                <span>🏅</span> Honors & Squad Mentions
              </h2>
            </div>

            {/* Achievements */}
            <div className="space-y-2">
              {(progression.achievements_unlocked || []).map((ach) => (
                <div key={ach.code} className="flex items-center gap-3 p-3 rounded-lg bg-purple-950/20 border border-purple-500/30">
                  <span className="text-lg">{ach.icon || '🛡️'}</span>
                  <div className="space-y-0.5">
                    <div className="text-xs font-bold text-white">{ach.name}</div>
                    <div className="text-[10px] text-zinc-300">{ach.description}</div>
                  </div>
                </div>
              ))}
            </div>

            {/* Squad MVP */}
            {squad_mvp && (
              <div className="p-3.5 rounded-lg border border-cyan-400/30 bg-cyan-950/20 flex items-center justify-between">
                <div>
                  <div className="text-[10px] font-mono uppercase text-cyan-300 tracking-wider">Most journal mentions</div>
                  <div className="text-sm font-extrabold text-white">{squad_mvp.name} {'//'} {squad_mvp.role}</div>
                </div>
                <div className="text-xs font-mono font-bold text-cyan-400">{squad_mvp.deployments} Journal mentions</div>
              </div>
            )}
          </section>

        </div>

      </div>
    </motion.div>
  );
}
