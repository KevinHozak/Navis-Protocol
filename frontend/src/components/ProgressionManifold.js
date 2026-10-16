"use client";
import React, { useState, useEffect, useRef, useCallback } from "react";
import { motion } from "framer-motion";
import { apiFetch } from "../lib/desktopApi";
import ConstellationTalentTree from "./ConstellationTalentTree";

const localDate = (date = new Date()) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;

export default function ProgressionManifold({ status }) {
  const [xpData, setXpData] = useState(null);
  const [talentState, setTalentState] = useState(null);
  const [allocatingNodeId, setAllocatingNodeId] = useState(null);
  const [talentError, setTalentError] = useState(null);
  const [selectedBranch, setSelectedBranch] = useState(null);
  const [saving, setSaving] = useState(false);
  const submitting = useRef(false);
  const [writeError, setWriteError] = useState(null);
  const loadId = useRef(0);
  const [achievements, setAchievements] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [formDate, setFormDate] = useState(() => {
    return localDate();
  });
  const [formAmount, setFormAmount] = useState(10);
  const [formDetails, setFormDetails] = useState("Daily Standard");
  const pendingAward = useRef(null);


  const fetchProgression = useCallback(async () => {
    const id = ++loadId.current;
    setLoading(true);
    setError(null);
    try {
      const [xpRes, achRes, talentRes] = await Promise.all([
        apiFetch("/api/v1/progression/xp"),
        apiFetch("/api/v1/progression/achievements"),
        apiFetch("/api/v1/progression/talents?entity_id=keeper"),
      ]);
      if (!xpRes.ok || !achRes.ok) throw new Error("Failed to load progression data");
      const data = await xpRes.json();
      const milestones = await achRes.json();
      let talents = null;
      if (talentRes.ok) {
        talents = await talentRes.json();
      }
      if (id !== loadId.current) return;
      setXpData(data);
      setAchievements(milestones);
      if (talents) setTalentState(talents);
    } catch (error) {
      if (id === loadId.current) setError(error.message);
      console.error("Failed to fetch progression data", error);
    } finally {
      if (id === loadId.current) setLoading(false);
    }
  }, []);

  const handleAllocateTalent = async (nodeId, rank) => {
    if (allocatingNodeId) return;
    setAllocatingNodeId(nodeId);
    setTalentError(null);

    // Save previous state for rollback if server rejects
    const previousState = talentState;

    // Optimistic UI update: increment rank and decrement available points immediately
    setTalentState((prev) => {
      if (!prev) return prev;
      const updatedNodes = (prev.nodes || []).map((n) => {
        if (n.id === nodeId) {
          const newRank = rank !== undefined ? rank : (n.current_rank || 0) + 1;
          return { ...n, current_rank: newRank };
        }
        return n;
      });
      // Re-evaluate unlocked states optimistically
      const allocMap = {};
      for (const n of updatedNodes) {
        allocMap[n.id] = n.current_rank || 0;
      }
      const nodesWithUnlocks = updatedNodes.map((n) => {
        const prereqs = n.prerequisites || [];
        const isUnlocked = prereqs.every((p) => {
          const reqId = typeof p === "string" ? p : p?.node_id;
          const reqRank = typeof p === "object" && p?.min_rank ? p.min_rank : 1;
          return (allocMap[reqId] || 0) >= reqRank;
        });
        return { ...n, unlocked: isUnlocked };
      });

      return {
        ...prev,
        available_points: Math.max(0, (prev.available_points || 0) - 1),
        total_allocated_ranks: (prev.total_allocated_ranks || 0) + 1,
        nodes: nodesWithUnlocks,
      };
    });

    try {
      const res = await apiFetch("/api/v1/progression/talents/allocate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          entity_id: "keeper",
          node_id: nodeId,
          rank: rank,
        }),
      });

      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || "Failed to inscribe talent point");
      }

      // Re-fetch authoritative constellation state
      const freshRes = await apiFetch("/api/v1/progression/talents?entity_id=keeper");
      if (freshRes.ok) {
        const freshData = await freshRes.json();
        setTalentState(freshData);
      }
    } catch (err) {
      console.error("Talent allocation failed:", err);
      // Rollback to previous state on failure
      setTalentState(previousState);
      setTalentError(err.message || "Failed to inscribe talent node");
    } finally {
      setAllocatingNodeId(null);
    }
  };

  const invalidateLoad = useCallback(() => { ++loadId.current; }, []);

  useEffect(() => {
    fetchProgression();
    const refresh = () => fetchProgression();
    window.addEventListener("focus", refresh);
    window.addEventListener("navis:progression-changed", refresh);
    return () => {
      invalidateLoad();
      window.removeEventListener("focus", refresh);
      window.removeEventListener("navis:progression-changed", refresh);
    };
  }, [fetchProgression, invalidateLoad, status]);

  const handleLogXp = async (e) => {
    e.preventDefault();
    if (submitting.current) return;
    submitting.current = true;
    setSaving(true);
    setWriteError(null);
    try {
      const adjustment = {
        date: formDate,
        amount: Number(formAmount),
        reason: formDetails.trim(),
      };
      if (!formDate || formAmount === "" || !Number.isSafeInteger(adjustment.amount) || !adjustment.reason) throw new Error("Choose a date, whole XP amount, and a reason.");
      const signature = JSON.stringify(adjustment);
      if (!pendingAward.current || pendingAward.current.signature !== signature) {
        pendingAward.current = {
          signature,
          awardId: crypto.randomUUID(),
          sourceEventAt: new Date(`${formDate}T12:00:00`).toISOString(),
        };
      }
      const awardId = pendingAward.current.awardId;
      const payload = {
        award_id: awardId,
        entity_id: "keeper",
        amount: adjustment.amount,
        source_type: "manual_adjustment",
        source_ref: `manual/${awardId}`,
        source_event_at: pendingAward.current.sourceEventAt,
        local_date: formDate,
        rule_version: "xp-v1",
        provenance: { actor: "Keeper", interface: "ProgressionManifold" },
        reason: adjustment.reason,
        details: adjustment.reason,
      };
      const res = await apiFetch("/api/v1/progression/xp", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        pendingAward.current = null;
        await fetchProgression();
      } else {
        const payload = await res.json().catch(() => ({}));
        setWriteError(typeof payload.detail === "string" ? payload.detail : "Unable to record this adjustment. Check the date, amount, and reason.");
      }
    } catch (error) {
      setWriteError(error.message || "The adjustment could not be confirmed. Retry to safely reuse its award ID.");
      console.error("Failed to log XP", error);
    } finally {
      submitting.current = false;
      setSaving(false);
    }
  };

  const currentLevel = xpData?.level;
  const xpIntoLevel = xpData?.xp_into_level;
  const requiredForNext = xpData?.xp_for_next_level;
  const progressPercent = xpData?.progress_percent ?? 0;

  return (
    <div className="space-y-8 max-w-6xl mx-auto text-white">
      {error && <div className="p-4 rounded border border-red-500/30 bg-red-500/10 text-red-300 flex items-center justify-between"><span>{error}</span><button onClick={fetchProgression} className="px-3 py-1 border border-red-400/40 rounded hover:bg-red-400/10">Retry</button></div>}
      {xpData?.legacy_history_unresolved && <div className="p-3 rounded border border-amber-500/30 bg-amber-500/10 text-amber-200 text-xs">Earlier XP history is still unresolved. These totals show canonical ledger entries only.</div>}
      {/* Top Banner: Level and Total XP */}
      <div className="bg-zinc-900/60 border border-white/10 rounded-xl p-8 relative overflow-hidden shadow-2xl">
        <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-accent via-white to-accent opacity-50"></div>
        <div className="flex items-center justify-between z-10 relative">
          <div>
            <h2 className="text-[10px] font-mono text-accent uppercase tracking-[0.4em] mb-1">
              Keeper Uplink Status
            </h2>
            <div className="text-4xl font-black uppercase tracking-widest text-white drop-shadow-md">
              {xpData ? `Level ${currentLevel}` : "Awaiting ledger"}
            </div>
            <div className="text-xs text-white/50 mt-1 font-mono uppercase">
              Total Accrual: {xpData?.total_xp ?? "—"} XP
            </div>
          </div>
          <div className="w-1/2">
            <div className="flex justify-between text-xs font-mono mb-2 text-white/60">
              <span>{xpIntoLevel ?? "—"} XP</span>
              <span>{requiredForNext ?? "—"} XP</span>
            </div>
            <div className="h-3 w-full bg-black rounded-full overflow-hidden border border-white/5 relative shadow-inner">
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${progressPercent}%` }}
                transition={{ duration: 1, ease: "easeOut" }}
                className="h-full bg-accent shadow-[0_0_15px_rgba(0,212,255,0.6)]"
              />
            </div>
          </div>
        </div>
      </div>

      {/* Constellation Talent Tree Node-Graph */}
      {talentError && (
        <div className="p-4 rounded-xl border border-red-500/40 bg-red-500/10 text-red-300 text-xs font-mono flex items-center justify-between">
          <span>⚠️ {talentError}</span>
          <button
            onClick={() => setTalentError(null)}
            className="px-2 py-0.5 rounded border border-red-400/30 hover:bg-red-400/10 text-[10px] uppercase"
          >
            Dismiss
          </button>
        </div>
      )}
      <ConstellationTalentTree
        talentState={talentState}
        onAllocate={handleAllocateTalent}
        allocatingNodeId={allocatingNodeId}
        selectedBranch={selectedBranch}
        onSelectBranch={setSelectedBranch}
      />

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Left Column: XP Log & Heatmap */}
        <div className="md:col-span-2 space-y-6">
          <div className="bg-zinc-950 border border-white/5 rounded-xl p-6 shadow-inner">
            <div className="flex justify-between items-center mb-4 border-b border-white/5 pb-2">
              <h3 className="text-sm font-bold uppercase tracking-widest text-white flex items-center gap-2">
                <span className="text-accent animate-pulse">⚡</span> Accrual Timeline
              </h3>
            </div>
            <button onClick={fetchProgression} disabled={loading} className="text-accent text-xs mb-3">Refresh ledger</button>
            {/* Minimalist Log */}
            <div className="h-48 overflow-y-auto custom-scrollbar pr-2 space-y-2 font-mono text-[10px]">
              {loading && <div className="text-white/30 animate-pulse">Syncing timeline...</div>}
              {!loading && xpData?.history.length === 0 && <div>No canonical XP records yet.</div>}
              {xpData?.history.map((log) => (
                <div key={log.award_id} className="flex gap-4 p-2 bg-zinc-900/40 rounded hover:bg-zinc-900/80 transition-colors">
                  <span className="text-white/40">{log.date}</span>
                  <span className={`${log.amount < 0 ? "text-red-300" : "text-green-400"} font-bold w-12 text-right`}>{log.amount > 0 ? "+" : ""}{log.amount} XP</span>
                  <div className="text-white/60 flex-1 min-w-0 break-words">
                    <div>{log.reason || log.details}</div>
                    <div className="text-white/40">{log.entity_id} · {log.source_type} · {log.source_ref}</div>
                    {log.provenance?.actor && <div>Actor: {log.provenance.actor}</div>}
                    {log.correction_of && <div>Corrects: {log.correction_of}</div>}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-zinc-950 border border-white/5 rounded-xl p-6 shadow-inner">
            <h3 className="text-sm font-bold uppercase tracking-widest text-white mb-4">Manual Integration</h3>
            {writeError && <div role="alert" className="text-red-300 text-xs mb-3">{writeError} Retry Commit with the same inputs to safely reuse the award ID.</div>}
            <form onSubmit={handleLogXp} className="flex flex-wrap gap-4">
              <fieldset disabled={saving} className="contents">
              <input
                aria-label="Award date" required type="date"
                value={formDate}
                onChange={(e) => setFormDate(e.target.value)}
                className="bg-black text-white/80 border border-white/10 rounded px-3 py-2 font-mono text-xs focus:border-accent outline-none"
              />
              <input
                aria-label="XP amount" required step="1" type="number"
                value={formAmount}
                onChange={(e) => setFormAmount(e.target.value)}
                className="bg-black text-white/80 border border-white/10 rounded px-3 py-2 font-mono text-xs w-24 focus:border-accent outline-none"
              />
              <input
                aria-label="Adjustment reason" type="text"
                value={formDetails}
                onChange={(e) => setFormDetails(e.target.value)}
                placeholder="Reason for adjustment"
                required
                className="bg-black text-white/80 border border-white/10 rounded px-3 py-2 font-mono text-xs flex-1 focus:border-accent outline-none"
              />
              <button type="submit" className="px-4 py-2 bg-accent/10 border border-accent/40 text-accent font-bold uppercase text-[10px] tracking-widest rounded hover:bg-accent hover:text-black transition-all">
                {saving ? "Saving..." : "Commit"}
              </button>
              </fieldset>
            </form>
          </div>
        </div>

        {/* Right Column: Achievements */}
        <div className="bg-zinc-950 border border-white/5 rounded-xl p-6 shadow-inner flex flex-col h-[500px]">
          <h3 className="text-sm font-bold uppercase tracking-widest text-amber-400 mb-4 border-b border-white/5 pb-2">
            🏆 Milestones
          </h3>
          <div className="flex-1 overflow-y-auto custom-scrollbar space-y-4 pr-2">
            {achievements.length === 0 && !loading && (
              <div className="text-white/30 text-[10px] font-mono text-center mt-10">No milestones detected.</div>
            )}
            {achievements.map((ach) => (
              <motion.div
                key={ach.id}
                whileHover={{ scale: 1.02, x: 5 }}
                className={`p-3 rounded-lg border ${ach.date_achieved ? 'bg-amber-900/20 border-amber-500/30 shadow-[0_0_10px_rgba(245,158,11,0.1)]' : 'bg-black/50 border-white/5 opacity-50 grayscale'}`}
              >
                <div className="flex items-center gap-3 mb-1">
                  <div className={`w-8 h-8 rounded-full flex items-center justify-center border text-[10px] font-bold ${ach.date_achieved ? 'bg-amber-500/10 border-amber-500/50 text-amber-500' : 'bg-zinc-900 border-white/10 text-white/30'}`}>
                    {ach.code}
                  </div>
                  <div>
                    <h4 className={`text-xs font-bold uppercase tracking-wider ${ach.date_achieved ? 'text-amber-100' : 'text-white/60'}`}>{ach.name}</h4>
                    <div className="text-[9px] font-mono text-white/30">{ach.date_achieved || "LOCKED"}</div>
                  </div>
                </div>
                <div className="text-[10px] text-white/50 leading-relaxed ml-11">
                  {ach.description}
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
