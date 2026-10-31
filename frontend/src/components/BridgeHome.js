"use client";

import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { apiFetch, apiUrl, vaultAssetUrl, subscribeVaultStream } from '../lib/desktopApi';

import {
  READINESS_CATEGORIES,
  resolveMetric,
  resolveChronoMarker,
  resolveSpatialAnchor,
  resolveResolvedBars,
  resolveSystemIntegrity,
} from '../lib/commandTelemetry.mjs';

export default function BridgeHome({
  status: initialStatus,
  readiness: initialReadiness,
  onMissionClick,
  onRefreshStatus,
}) {
  const [status, setStatus] = useState(initialStatus);
  const [activeMissions, setActiveMissions] = useState(
    Array.isArray(initialStatus?.active_missions)
      ? initialStatus.active_missions
      : []
  );
  const [readiness, setReadiness] = useState(
    initialReadiness !== undefined
      ? initialReadiness
      : (initialStatus?.readiness !== undefined ? initialStatus.readiness : null)
  );
  const [availableMissions, setAvailableMissions] = useState([]);
  const [selectingSlot, setSelectingSlot] = useState(null);
  const [savingSlot, setSavingSlot] = useState(null);
  const [saveError, setSaveError] = useState(null);
  const [holocron, setHolocron] = useState(null);

  useEffect(() => {
    let isCancelled = false;
    apiFetch('/api/holocron/weekly/current')
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!isCancelled && data) {
          setHolocron(data);
        }
      })
      .catch(() => {});
    return () => {
      isCancelled = true;
    };
  }, []);

  // Synchronize when parent status prop changes without remounting
  useEffect(() => {
    setStatus(initialStatus);
    if (Array.isArray(initialStatus?.active_missions)) {
      setActiveMissions(initialStatus.active_missions);
    } else if (initialStatus && initialStatus.active_missions === undefined) {
      setActiveMissions([]);
    }
  }, [initialStatus]);

  // Synchronize readiness when prop or status.readiness changes
  useEffect(() => {
    if (initialReadiness !== undefined) {
      setReadiness(initialReadiness);
    } else if (initialStatus?.readiness !== undefined) {
      setReadiness(initialStatus.readiness);
    }
  }, [initialReadiness, initialStatus?.readiness]);

  // Fetch readiness telemetry from API if not provided via props
  useEffect(() => {
    if (initialReadiness !== undefined || initialStatus?.readiness !== undefined) {
      return;
    }
    let isCancelled = false;
    apiFetch('/api/readiness')
      .then((res) => {
        if (!res.ok) throw new Error(`Readiness fetch failed (${res.status})`);
        return res.json();
      })
      .then((data) => {
        if (!isCancelled && data) {
          setReadiness(data);
        }
      })
      .catch((err) => {
        if (!isCancelled) {
          console.warn("Failed to load readiness telemetry", err);
        }
      });

    return () => {
      isCancelled = true;
    };
  }, [initialReadiness, initialStatus?.readiness]);

  // Fetch available missions on mount
  useEffect(() => {
    let isCancelled = false;
    apiFetch('/api/missions/all')
      .then((res) => {
        if (!res.ok) throw new Error(`Missions fetch failed (${res.status})`);
        return res.json();
      })
      .then((data) => {
        if (!isCancelled && Array.isArray(data)) {
          setAvailableMissions(data);
        }
      })
      .catch((err) => {
        if (!isCancelled) {
          console.error("Failed to load missions", err);
        }
      });

    return () => {
      isCancelled = true;
    };
  }, []);

  // Subscribe to real-time vault changes for surgical telemetry refresh
  useEffect(() => {
    const unsubscribe = subscribeVaultStream((event) => {
      const path = (event?.path || '').replace(/\\/g, '/').toLowerCase();
      const type = (event?.type || '').toLowerCase();

      if (type === 'bridge' || path.includes('status.json')) {
        if (onRefreshStatus) onRefreshStatus();
      }

      if (path.includes('holocron') || path.includes('journal')) {
        apiFetch('/api/holocron/weekly/current')
          .then((res) => (res.ok ? res.json() : null))
          .then((data) => {
            if (data) setHolocron(data);
          })
          .catch(() => {});
      }

      if (path.includes('readiness') || path.includes('biometrics') || path.includes('vitals') || path.includes('status.json')) {
        apiFetch('/api/readiness')
          .then((res) => (res.ok ? res.json() : null))
          .then((data) => {
            if (data) setReadiness(data);
          })
          .catch(() => {});
      }

      if (path.includes('mission') || path.includes('sector_cache')) {
        apiFetch('/api/missions/all')
          .then((res) => (res.ok ? res.json() : null))
          .then((data) => {
            if (Array.isArray(data)) setAvailableMissions(data);
          })
          .catch(() => {});
      }
    });

    return () => {
      unsubscribe();
    };
  }, [onRefreshStatus]);

  const handleMissionSelect = async (missionName) => {
    if (selectingSlot === null) return;

    const targetSlot = selectingSlot;
    const previousMissions = [...activeMissions];

    // Optimistic update
    const nextMissions = [...activeMissions];
    nextMissions[targetSlot] = missionName;
    setActiveMissions(nextMissions);
    setSelectingSlot(null);
    setSaveError(null);
    setSavingSlot(targetSlot);

    try {
      const res = await apiFetch('/api/status/mission', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ slot_index: targetSlot, mission_name: missionName }),
      });

      if (!res.ok) {
        let errorDetail = `Save failed (${res.status})`;
        try {
          const errData = await res.json();
          if (errData?.detail) errorDetail = errData.detail;
        } catch (_) {}
        throw new Error(errorDetail);
      }

      const data = await res.json();
      if (Array.isArray(data?.active_missions)) {
        setActiveMissions(data.active_missions);
      }
      setSaveError(null);
      if (onRefreshStatus) {
        onRefreshStatus();
      }
    } catch (err) {
      console.error("Failed to save mission", err);
      // Visibly reconcile failure: revert optimistic update
      setActiveMissions(previousMissions);
      setSaveError(err.message || 'Failed to persist mission assignment');
    } finally {
      setSavingSlot(null);
    }
  };

  const chronoMarker = resolveChronoMarker(status);
  const isChronoAvailable = Boolean(chronoMarker);

  const currentRealm = resolveSpatialAnchor(status);
  const isRealmAvailable = Boolean(currentRealm);

  const resolvedBars = resolveResolvedBars(readiness);
  const systemIntegrity = resolveSystemIntegrity(status, resolvedBars);
  const isIntegrityAvailable = typeof systemIntegrity === 'number';

  const integrityColorClass = !isIntegrityAvailable
    ? 'text-white/40'
    : systemIntegrity < 30
    ? 'text-red-500'
    : systemIntegrity < 70
    ? 'text-yellow-500'
    : 'text-accent';

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.98 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 1.02 }}
      className="flex-1 overflow-hidden relative p-8"
      onClick={() => {
        if (selectingSlot !== null) setSelectingSlot(null);
      }}
    >
      <div className="max-w-6xl mx-auto h-full flex flex-col space-y-8 relative z-10">
        {/* Header Status */}
        <div className="flex justify-between items-start">
          <div className="space-y-1">
            <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.4em] text-accent font-bold">
              <span className="w-2 h-2 rounded-full bg-accent animate-pulse" />
              COMMAND <span className="text-white/20 ml-2">{'//'}</span>{' '}
              <span className="text-white/40">Operational Viewport</span>
            </div>
          </div>
        </div>

        {/* Grid of Tactical Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-black/20 p-8 rounded border border-white/10 space-y-4 group hover:border-accent/30 transition-all">
            <div className="text-[10px] uppercase tracking-[0.3em] text-white/30 font-bold">Chrono Marker</div>
            <div
              data-testid="chrono-marker"
              className={`text-3xl font-bold tracking-tighter group-hover:scale-105 transition-transform origin-left ${
                isChronoAvailable ? 'text-accent' : 'text-white/40'
              }`}
            >
              {isChronoAvailable ? chronoMarker : 'UNAVAILABLE'}
            </div>
          </div>
          <div className="bg-black/20 p-8 rounded border border-white/10 space-y-4 group hover:border-accent/30 transition-all">
            <div className="text-[10px] uppercase tracking-[0.3em] text-white/30 font-bold">Spatial Anchor</div>
            <div
              data-testid="spatial-anchor"
              className={`text-3xl font-bold tracking-tighter transition-colors ${
                isRealmAvailable ? 'text-white group-hover:text-accent' : 'text-white/40'
              }`}
            >
              {isRealmAvailable ? currentRealm : 'UNAVAILABLE'}
            </div>
          </div>
          <div className="bg-black/20 p-8 rounded border border-white/10 space-y-4 group hover:border-accent/30 transition-all">
            <div className="text-[10px] uppercase tracking-[0.3em] text-white/30 font-bold">System Integrity</div>
            <div
              data-testid="system-integrity"
              className={`text-3xl font-bold tracking-tighter ${integrityColorClass}`}
            >
              {isIntegrityAvailable ? `${systemIntegrity}%` : 'UNAVAILABLE'}
            </div>
          </div>
        </div>

        {/* Integrity Bars */}
        <div className="grid grid-cols-5 gap-4 py-4" data-testid="integrity-bars">
          {resolvedBars.map((bar) => (
            <div key={bar.key} className="space-y-2" data-testid={`readiness-metric-${bar.key}`}>
              <div className="flex justify-between items-center text-[8px] uppercase tracking-widest font-bold">
                <span className="text-white/30">{bar.label}</span>
                <span
                  data-testid={`bar-val-${bar.key}`}
                  className={bar.available ? 'text-accent font-mono' : 'text-white/30 font-mono'}
                >
                  {bar.available ? `${bar.value}%` : 'UNAVAILABLE'}
                </span>
              </div>
              <div className="h-1.5 w-full bg-white/5 rounded-full overflow-hidden border border-white/5">
                <div
                  className="h-full transition-all duration-500"
                  style={{
                    width: bar.available ? `${bar.value}%` : '0%',
                    backgroundColor: bar.available ? bar.barColor : 'transparent',
                  }}
                />
              </div>
            </div>
          ))}
        </div>

        {/* Holocron Executive Status Card */}
        {holocron && (
          <div className="bg-zinc-950/70 border border-white/10 border-l-4 border-l-cyan-400 p-6 rounded shadow-lg backdrop-blur space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/5 pb-2">
              <div className="flex items-center gap-2">
                <span className="text-cyan-400">💠</span>
                <span className="text-[10px] uppercase tracking-[0.3em] font-mono font-bold text-cyan-300">
                  Command Tactical Debrief // Weekly Holocron ({holocron.week_id})
                </span>
                {holocron.is_in_flight && (
                  <span className="px-2 py-0.5 rounded-full bg-emerald-500/20 border border-emerald-400/40 text-emerald-300 font-mono text-[9px] font-bold tracking-wider animate-pulse flex items-center gap-1">
                    <span className="w-1 h-1 rounded-full bg-emerald-400"></span>
                    LIVE WTD
                  </span>
                )}
                {['ollama', 'openrouter'].includes(holocron.debrief_source) && (
                  <span className="px-2 py-0.5 rounded bg-purple-950/80 border border-purple-400/50 text-purple-300 font-mono text-[9px] font-bold tracking-wider">
                    ✨ AI SAGE
                  </span>
                )}
              </div>
              <div className="flex items-center gap-4 text-xs font-mono">
                <span>
                  <strong className="text-cyan-400">{holocron.summary?.precision_rate == null ? 'Unavailable' : `${holocron.summary.precision_rate}%`}</strong> Precision
                </span>
                <span>
                  <strong className="text-purple-400">{holocron.summary?.total_xp_gained == null ? 'Unavailable' : holocron.summary.total_xp_gained.toLocaleString()}</strong> XP
                </span>
                <span>
                  <strong className="text-rose-400">{holocron.summary?.threats_neutralized ?? 'Unavailable'}</strong> Slayings
                </span>
                {holocron.summary?.is_in_flight && (
                  <span className="text-emerald-400 font-bold">
                    Day {holocron.summary?.days_elapsed || 1}/7
                  </span>
                )}
              </div>
            </div>
            <p className="text-xs text-zinc-300 leading-relaxed font-sans">
              {holocron.tactical_debrief}
            </p>
          </div>
        )}

        {/* Secondary Viewport: Active Missions */}
        <div className="flex-1 bg-black/35 rounded border border-white/10 p-10 relative overflow-visible group flex flex-col">
          <div className="absolute inset-0 bg-gradient-to-br from-accent/5 to-transparent pointer-events-none rounded" />
          <div className="flex items-center justify-between mb-8">
            <div className="flex items-center gap-3">
              <span className="w-2 h-2 rounded-full bg-accent animate-pulse" />
              <h2 className="text-xs font-bold uppercase tracking-[0.4em] text-accent/80">Active Missions</h2>
            </div>
            {savingSlot !== null && (
              <span className="text-[10px] text-accent/80 font-mono animate-pulse uppercase tracking-widest">
                Transmitting directive...
              </span>
            )}
          </div>

          {saveError && (
            <div
              data-testid="mission-save-error"
              role="alert"
              className="mb-6 p-4 bg-red-950/80 border border-red-500/50 rounded flex items-center justify-between text-red-200 text-xs shadow-lg relative z-30"
            >
              <div className="flex items-center gap-2">
                <span className="text-red-400 font-bold">⚠️ ASSIGNMENT ERROR:</span>
                <span>{saveError}</span>
              </div>
              <button
                onClick={() => setSaveError(null)}
                className="text-red-400 hover:text-white px-2 py-0.5 text-xs rounded border border-red-500/30 hover:border-red-500/60 transition-colors"
              >
                Dismiss
              </button>
            </div>
          )}

          <div className="grid grid-cols-3 gap-6 flex-1 relative z-20">
            {[0, 1, 2].map((idx) => {
              const missionName = activeMissions[idx] || null;
              const mission = missionName ? availableMissions.find((m) => m.name === missionName) : null;
              const imgUrl = mission
                ? vaultAssetUrl(`Operations/${mission.region}/Main/${mission.name}/Landscape.png`, {
                    cacheBust: false,
                  })
                : null;
              const isSlotSaving = savingSlot === idx;

              return (
                <div key={idx} className="relative" data-testid={`mission-slot-${idx}`}>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      setSelectingSlot(idx);
                    }}
                    className="absolute top-3 right-3 z-30 w-8 h-8 rounded-full bg-black/60 border border-white/10 flex items-center justify-center text-white/50 hover:text-white hover:border-accent/50 hover:bg-accent/10 transition-all backdrop-blur-sm shadow-lg"
                    title={missionName ? 'Switch mission' : 'Assign mission'}
                    disabled={savingSlot !== null}
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M8 7h12m0 0l-4-4m4 4l-4 4M4 17h12m0 0l-4 4m4-4l-4-4"
                      />
                    </svg>
                  </button>
                  <div
                    onClick={(e) => {
                      e.stopPropagation();
                      if (onMissionClick && missionName) {
                        onMissionClick(missionName, mission);
                      } else {
                        setSelectingSlot(idx);
                      }
                    }}
                    className="h-full p-6 bg-black/40 rounded border border-white/10 flex flex-col justify-center items-center gap-4 cursor-pointer hover:border-accent/50 hover:bg-white/5 transition-all overflow-hidden relative group/slot"
                  >
                    {(() => (
                      <>
                        <div className="absolute inset-0 transition-opacity opacity-60 group-hover/slot:opacity-100">
                          {imgUrl && (
                            <img
                              src={imgUrl}
                              alt={missionName || 'Mission preview'}
                              className="w-full h-full object-cover"
                              onError={(e) => {
                                e.target.style.display = 'none';
                              }}
                            />
                          )}
                        </div>
                        <div className="absolute inset-0 bg-gradient-to-t from-black/90 via-black/40 to-black/10 z-10" />

                        {!imgUrl && (
                          <div className="w-16 h-16 mx-auto rounded-full border border-white/20 flex items-center justify-center text-white/50 bg-black/50 text-2xl shadow-lg relative z-20 mb-4">
                            {isSlotSaving ? '⏳' : '🛡️'}
                          </div>
                        )}

                        <div className={`text-center relative z-20 w-full ${imgUrl ? 'mt-auto' : ''}`}>
                          <div
                            data-testid={`mission-name-${idx}`}
                            className="text-xs font-bold text-white uppercase tracking-widest mb-1 drop-shadow-lg"
                          >
                            {missionName || 'Empty Slot'}
                          </div>
                          <div className="text-[9px] text-accent/80 uppercase font-mono drop-shadow-lg">
                            {isSlotSaving
                              ? 'Synchronizing...'
                              : mission?.region || (missionName ? 'Active Operation' : 'Click to assign')}
                          </div>
                        </div>
                      </>
                    ))()}
                  </div>
                </div>
              );
            })}
          </div>

          <div className="absolute top-0 right-0 p-8 opacity-5 pointer-events-none">
            <svg className="w-48 h-48" fill="currentColor" viewBox="0 0 24 24">
              <path d="M12 2L1 21h22L12 2zm0 3.83L19.17 19H4.83L12 5.83zM11 16h2v2h-2v-2zm0-7h2v5h-2V9z" />
            </svg>
          </div>
        </div>
      </div>

      {/* Full-Screen Mission Selection Modal */}
      <AnimatePresence>
        {selectingSlot !== null && (
          <motion.div
            initial={{ opacity: 0, backdropFilter: 'blur(0px)' }}
            animate={{ opacity: 1, backdropFilter: 'blur(10px)' }}
            exit={{ opacity: 0, backdropFilter: 'blur(0px)' }}
            className="absolute inset-0 z-50 bg-black/80 p-8 md:p-12 flex flex-col overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
            data-testid="mission-selection-modal"
          >
            <div className="flex items-center justify-between mb-8 shrink-0">
              <div>
                <h3 className="text-3xl font-black text-white uppercase tracking-wider">Select Mission</h3>
                <div className="text-[10px] text-accent/60 tracking-[0.25em] uppercase font-bold font-mono mt-1">
                  Assign to Sector Slot {selectingSlot + 1}
                </div>
              </div>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setSelectingSlot(null);
                }}
                className="w-12 h-12 rounded border border-white/20 flex items-center justify-center text-white/50 hover:text-white hover:border-white/50 hover:bg-white/10 transition-colors"
              >
                ✕
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6 pb-12">
              {availableMissions.map((m) => {
                const imgUrl = vaultAssetUrl(`Operations/${m.region}/Main/${m.name}/Landscape.png`, {
                  cacheBust: false,
                });
                const isActive = activeMissions.includes(m.name);

                return (
                  <div
                    key={m.name}
                    data-testid={`mission-option-${m.name}`}
                    onClick={(e) => {
                      e.stopPropagation();
                      handleMissionSelect(m.name);
                    }}
                    className={`h-48 p-6 rounded border cursor-pointer flex flex-col justify-end relative overflow-hidden group transition-all ${
                      isActive
                        ? 'border-accent bg-accent/10 shadow-[0_0_20px_rgba(245,158,11,0.15)]'
                        : 'border-white/10 bg-zinc-900 hover:border-white/40 hover:shadow-2xl'
                    }`}
                  >
                    <div className="absolute inset-0 transition-opacity opacity-50 group-hover:opacity-80">
                      <img
                        src={imgUrl}
                        alt={m.name}
                        className="w-full h-full object-cover"
                        onError={(e) => {
                          e.target.style.display = 'none';
                        }}
                      />
                    </div>
                    <div className="absolute inset-0 bg-gradient-to-t from-black via-black/40 to-transparent z-10" />

                    <div className="relative z-20">
                      <div
                        className={`text-lg font-bold uppercase tracking-widest mb-1 drop-shadow-md transition-colors ${
                          isActive ? 'text-accent' : 'text-white group-hover:text-accent/80'
                        }`}
                      >
                        {m.name}
                      </div>
                      <div className="text-[10px] text-white/60 uppercase font-mono drop-shadow-md">{m.region}</div>
                    </div>

                    {isActive && (
                      <div className="absolute top-4 right-4 z-20 px-2 py-1 bg-accent/20 border border-accent/50 text-accent text-[9px] font-bold uppercase tracking-widest rounded-sm">
                        Active
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
