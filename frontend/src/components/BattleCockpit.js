"use client";
import { useState, useEffect } from "react";
import { apiFetch } from "../lib/desktopApi";
import { motion, AnimatePresence } from "framer-motion";

export default function BattleCockpit({ tasks, onTaskResolved }) {
  const [battleState, setBattleState] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [resolving, setResolving] = useState(false);

  // Modal State
  const [linkingTask, setLinkingTask] = useState(null);
  const [linkError, setLinkError] = useState(null);
  const [selectedTop, setSelectedTop] = useState(null);
  const [selectedBottom, setSelectedBottom] = useState(null);

  const renderCardAction = (actions) => {
    if (!Array.isArray(actions)) return String(actions);
    return actions.map((act, i) => (
      <div key={i} className="flex justify-between items-center py-0.5">
        <span className="font-bold uppercase tracking-wider">{act.action}</span>
        <div className="flex items-center gap-1">
          {act.value !== null && <span className="font-mono">{act.value}</span>}
          {act.modifier && <span className="text-[8px] px-1 bg-white/10 rounded">{act.modifier}</span>}
        </div>
      </div>
    ));
  };

  const fetchState = async () => {
    try {
      const res = await apiFetch("/api/battle/state");
      if (!res.ok) throw new Error("Failed to load battle state");
      const data = await res.json();
      setBattleState(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchState();
  }, []);

  const handleLink = async () => {
    if (!linkingTask || !selectedTop || !selectedBottom) return;
    setLinkError(null);
    try {
      const res = await apiFetch("/api/battle/link", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          task_id: linkingTask.id,
          resolution_id: crypto.randomUUID(),
          top_card_id: selectedTop.id,
          bottom_card_id: selectedBottom.id,
          source: {
            path: linkingTask.file_path || linkingTask.path,
            target_text: linkingTask.text,
            line_number: linkingTask.line_number,
          },
        }),
      });
      const result = await res.json();
      if (!res.ok) throw new Error(result.detail || "Failed to link task");
      
      setLinkingTask(null);
      setSelectedTop(null);
      setSelectedBottom(null);
      fetchState();
    } catch (err) {
      setLinkError(err.message);
      await fetchState();
    }
  };

  const handleResolve = async (taskId, operation = null, isCompleted = true) => {
    if (resolving) return;
    const link = battleState.active_links[taskId];
    const resolutionId = operation?.resolution_id || (isCompleted ? link?.resolution_id :
      `${link?.resolution_id || `legacy-${taskId}-${link?.timestamp}`}:cancel`);
    if (!resolutionId && isCompleted) {
      setNotice("This older link needs to be cancelled and linked again before completing its task.");
      return;
    }
    setResolving(true);
    try {
      const res = await apiFetch("/api/battle/resolve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ task_id: taskId, is_completed: operation?.is_completed ?? isCompleted,
          resolution_id: resolutionId || crypto.randomUUID(), source: operation?.source || link?.source }),
      });
      const result = await res.json();
      if (!res.ok) throw new Error(result.detail || "Failed to resolve task");
      setNotice(result.status === "pending_recovery" ? `Recovery pending: ${result.message}. Retry below.` :
        result.status === "already_completed" ? "This task is already complete. Cancel its link to release the cards." : null);
      if (result.status === "completed" && onTaskResolved) onTaskResolved(taskId);
      await fetchState();
    } catch (err) {
      setNotice(err.message);
    } finally {
      setResolving(false);
    }
  };

  const handleShortRest = async () => {
    try {
      const res = await apiFetch("/api/battle/rest", {
        method: "POST"
      });
      if (!res.ok) throw new Error("Failed to short rest");
      fetchState();
    } catch (err) {
      alert(err.message);
    }
  };

  if (loading) return <div className="p-8 text-center text-zinc-500 animate-pulse">Initializing Tactical Grid...</div>;
  if (error) return <div className="p-8 text-center text-red-500 bg-red-500/10 border border-red-500/20 rounded-xl">
      <p>Error: {error}</p>
      <button onClick={() => { setError(null); setLoading(true); fetchState(); }} className="mt-4 px-4 py-2 rounded border border-red-400/40 text-red-300 hover:bg-red-400/10">Retry</button>
    </div>;
  if (!battleState) return null;

  return (
    <div className="flex flex-col gap-8 w-full">
      {notice && <p role="status" className="p-4 rounded-xl bg-zinc-950/90 border border-red-400/30 text-red-300">{notice}</p>}
      {Object.entries(battleState.resolutions || {}).filter(([, op]) => op.phase !== "complete").map(([id, op]) => (
        <div key={id} className="p-4 rounded-xl bg-zinc-950/90 backdrop-blur-md border border-white/10 text-amber-300">
          Task completion pending
          <button disabled={resolving} onClick={() => handleResolve(op.task_id, { ...op, resolution_id: id })}
            className="ml-4 px-4 py-2 rounded border border-amber-400/30">Retry completion</button>
        </div>
      ))}
      
      {/* ----------------- ACTIVE LINKS ROW ----------------- */}
      <div className="flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-bold text-white tracking-widest uppercase">
            <span className="text-cyan-400 mr-2">⚡</span> Active Engagement
          </h2>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {Object.entries(battleState.active_links).length === 0 ? (
            <div className="col-span-full p-8 rounded-xl bg-zinc-900/50 border border-zinc-800 border-dashed text-center text-zinc-500 italic">
              No tactical maneuvers currently bound to field tasks. Select a task below to initiate a link.
            </div>
          ) : (
            Object.entries(battleState.active_links).map(([taskId, link]) => {
              const task = tasks?.find(t => t.id === taskId) || { text: `Task ${taskId}` };
              return (
                <motion.div 
                  initial={{ opacity: 0, scale: 0.95 }} 
                  animate={{ opacity: 1, scale: 1 }}
                  key={taskId} 
                  className="relative flex flex-col p-5 rounded-2xl bg-gradient-to-b from-zinc-900 to-black border border-cyan-500/20 hover:border-cyan-400/50 transition-colors group"
                >
                  {/* Glowing backdrop */}
                  <div className="absolute inset-0 bg-cyan-500/5 blur-xl opacity-0 group-hover:opacity-100 transition-opacity rounded-2xl -z-10" />
                  
                  {/* Task Header */}
                  <div className="flex items-start justify-between mb-4 pb-4 border-b border-white/5">
                    <p className="text-sm font-medium text-white line-clamp-2">{task.text}</p>
                    <div className="flex-shrink-0 w-8 h-8 rounded-full bg-cyan-500/10 flex items-center justify-center text-cyan-400 font-bold border border-cyan-500/20">
                      {link.top.initiative}
                    </div>
                  </div>

                  {/* Bound Cards */}
                  <div className="flex flex-col gap-2 mb-6">
                    <div className="flex items-center gap-3 p-3 rounded-xl bg-white/5 border border-white/5">
                      <div className="w-1 h-8 rounded-full bg-cyan-400" />
                      <div className="flex flex-col">
                        <span className="text-xs text-zinc-500 font-bold uppercase tracking-wider">Top Action</span>
                        <span className="text-sm font-medium text-zinc-300">{link.top.name}</span>
                      </div>
                    </div>
                    <div className="flex flex-col items-center justify-center -my-3 z-10">
                      <div className="w-6 h-6 rounded-full bg-zinc-950 border border-zinc-800 flex items-center justify-center text-[10px] text-zinc-500">🔗</div>
                    </div>
                    <div className="flex items-center gap-3 p-3 rounded-xl bg-white/5 border border-white/5">
                      <div className="w-1 h-8 rounded-full bg-amber-500" />
                      <div className="flex flex-col">
                        <span className="text-xs text-zinc-500 font-bold uppercase tracking-wider">Bottom Action</span>
                        <span className="text-sm font-medium text-zinc-300">{link.bottom.name}</span>
                      </div>
                    </div>
                  </div>

                  {/* Resolve Button */}
                  <button 
                    disabled={resolving}
                    onClick={() => handleResolve(taskId)}
                    className="mt-auto w-full py-3 rounded-xl bg-cyan-500/10 hover:bg-cyan-500 text-cyan-400 hover:text-black font-bold tracking-widest text-sm transition-all border border-cyan-500/30 hover:border-transparent uppercase"
                  >
                    Execute Sequence
                  </button>
                  <button disabled={resolving} onClick={() => handleResolve(taskId, null, false)}
                    className="mt-2 text-xs text-zinc-400 hover:text-white">Cancel link without completing task</button>
                </motion.div>
              );
            })
          )}
        </div>
      </div>

      {/* ----------------- TACTICAL HAND ----------------- */}
      <div className="flex flex-col gap-4 mt-8">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-bold text-white tracking-widest uppercase flex items-center gap-3">
            <span className="text-amber-400">🎴</span> Tactical Hand 
            <span className="text-xs font-normal text-zinc-500 bg-white/5 px-3 py-1 rounded-full border border-white/10">
              {battleState.hand.length} Available
            </span>
          </h2>
          
          <div className="flex gap-4 items-center">
            <div className="flex items-center gap-2 text-sm">
              <span className="text-zinc-500">Discard:</span>
              <span className="font-bold text-white bg-zinc-800 px-2 py-0.5 rounded">{battleState.discard.length}</span>
            </div>
            <div className="flex items-center gap-2 text-sm mr-4">
              <span className="text-zinc-500">Lost:</span>
              <span className="font-bold text-red-400 bg-red-400/10 border border-red-500/20 px-2 py-0.5 rounded">{battleState.lost.length}</span>
            </div>
            <button 
              onClick={handleShortRest}
              disabled={battleState.discard.length === 0}
              className="px-6 py-2 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-white font-medium text-sm transition-colors border border-white/5 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Short Rest
            </button>
          </div>
        </div>

        {/* Card Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-4">
          {battleState.hand.map(card => (
            <motion.div 
              layoutId={`card-${card.id}`}
              key={card.id} 
              className="flex flex-col h-48 rounded-xl bg-zinc-900 border border-white/10 overflow-hidden hover:border-white/30 transition-colors group relative"
            >
              <div className="p-3 border-b border-white/10 bg-black/50 flex justify-between items-center">
                <span className="text-xs font-bold text-zinc-400 truncate">{card.name}</span>
                <span className="text-xs font-mono text-cyan-400 font-bold ml-2">{card.initiative}</span>
              </div>
              
              <div className="flex-1 p-3 flex flex-col justify-between text-[11px] leading-relaxed">
                <div className="text-cyan-100/70 border-l-2 border-cyan-500/50 pl-2">
                  <span className="text-cyan-400 font-bold block mb-1">TOP</span>
                  {renderCardAction(card.top)}
                </div>
                <div className="my-2 border-t border-white/5 w-full"></div>
                <div className="text-amber-100/70 border-l-2 border-amber-500/50 pl-2">
                  <span className="text-amber-500 font-bold block mb-1">BOTTOM</span>
                  {renderCardAction(card.bottom)}
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      </div>

      {/* ----------------- UNLINKED TASKS (For Linking) ----------------- */}
      <div className="flex flex-col gap-4 mt-8">
        <h2 className="text-xl font-bold text-white tracking-widest uppercase">
          <span className="text-emerald-400 mr-2">🎯</span> Field Targets
        </h2>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {tasks?.filter(t => !battleState.active_links[t.id]).map(task => (
            <div key={task.id} className="flex items-center justify-between p-4 rounded-xl bg-zinc-900/50 border border-white/5 hover:border-white/10 transition-colors">
              <span className="text-sm text-zinc-300 truncate mr-4">{task.text}</span>
              <button 
                onClick={() => { setLinkError(null); setLinkingTask(task); }}
                className="flex-shrink-0 px-4 py-2 rounded-lg bg-white/5 hover:bg-emerald-500/20 text-zinc-400 hover:text-emerald-400 text-xs font-bold uppercase tracking-wider transition-colors border border-transparent hover:border-emerald-500/30"
              >
                Bind Maneuver
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* ----------------- LINKING MODAL ----------------- */}
      <AnimatePresence>
        {linkingTask && (
          <motion.div 
            initial={{ opacity: 0 }} 
            animate={{ opacity: 1 }} 
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md"
          >
            <motion.div 
              initial={{ scale: 0.95, y: 20 }}
              animate={{ scale: 1, y: 0 }}
              exit={{ scale: 0.95, y: 20 }}
              className="w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col bg-zinc-950 border border-zinc-800 rounded-3xl shadow-2xl shadow-cyan-900/20"
            >
              <div className="p-6 border-b border-white/5 flex items-start justify-between bg-zinc-900/50">
                <div>
                  <h3 className="text-lg font-bold text-white uppercase tracking-widest mb-2">Bind Tactical Maneuver</h3>
                  <p className="text-sm text-cyan-400 font-medium">{linkingTask.text}</p>
                </div>
                <button 
                  onClick={() => { setLinkingTask(null); setSelectedTop(null); setSelectedBottom(null); }}
                  className="w-8 h-8 flex items-center justify-center rounded-full bg-white/5 text-zinc-400 hover:bg-white/10 hover:text-white"
                >
                  ✕
                </button>
              </div>
              
              <div className="flex-1 overflow-y-auto p-6 bg-gradient-to-b from-zinc-950 to-black">
                
                {linkError && <p role="alert" className="mb-4 p-4 rounded-xl bg-zinc-950/90 backdrop-blur-md border border-red-400/30 text-red-300">{linkError}</p>}
                {/* Selection Indicators */}
                <div className="flex gap-4 mb-8">
                  <div className={`flex-1 p-4 rounded-xl border-2 transition-colors ${selectedTop ? 'border-cyan-500 bg-cyan-500/10' : 'border-dashed border-zinc-700 bg-zinc-900/50'}`}>
                    <div className="text-xs font-bold uppercase tracking-widest text-zinc-500 mb-1">Top Action</div>
                    {selectedTop ? (
                      <div className="text-sm font-bold text-white">{selectedTop.name} <span className="text-cyan-400 ml-2">Initiative {selectedTop.initiative}</span></div>
                    ) : (
                      <div className="text-sm text-zinc-500">Select a card for Top...</div>
                    )}
                  </div>
                  
                  <div className="flex items-center justify-center">
                    <span className="text-2xl text-zinc-700">⛓️</span>
                  </div>

                  <div className={`flex-1 p-4 rounded-xl border-2 transition-colors ${selectedBottom ? 'border-amber-500 bg-amber-500/10' : 'border-dashed border-zinc-700 bg-zinc-900/50'}`}>
                    <div className="text-xs font-bold uppercase tracking-widest text-zinc-500 mb-1">Bottom Action</div>
                    {selectedBottom ? (
                      <div className="text-sm font-bold text-white">{selectedBottom.name}</div>
                    ) : (
                      <div className="text-sm text-zinc-500">Select a card for Bottom...</div>
                    )}
                  </div>
                </div>

                {/* Card Selection Grid */}
                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
                  {battleState.hand.map(card => {
                    const isTop = selectedTop?.id === card.id;
                    const isBottom = selectedBottom?.id === card.id;
                    const isSelected = isTop || isBottom;
                    const disabled = (selectedTop && selectedBottom && !isSelected) || (isTop && !selectedBottom && selectedBottom?.id === card.id);

                    return (
                      <div 
                        key={`modal-${card.id}`}
                        onClick={() => {
                          if (isTop) setSelectedTop(null);
                          else if (isBottom) setSelectedBottom(null);
                          else if (!selectedTop) setSelectedTop(card);
                          else if (!selectedBottom) setSelectedBottom(card);
                        }}
                        className={`
                          flex flex-col h-48 rounded-xl border transition-all cursor-pointer overflow-hidden
                          ${isTop ? 'border-cyan-500 shadow-lg shadow-cyan-500/20 scale-105 z-10' : 
                            isBottom ? 'border-amber-500 shadow-lg shadow-amber-500/20 scale-105 z-10' : 
                            disabled ? 'border-white/5 opacity-30 cursor-not-allowed grayscale' : 
                            'border-white/10 hover:border-white/30 bg-zinc-900'}
                        `}
                      >
                         <div className={`p-2 flex justify-between items-center ${isTop ? 'bg-cyan-500/20' : isBottom ? 'bg-amber-500/20' : 'bg-black/50 border-b border-white/5'}`}>
                          <span className={`text-[10px] font-bold truncate ${isTop ? 'text-cyan-300' : isBottom ? 'text-amber-300' : 'text-zinc-400'}`}>{card.name}</span>
                          <span className="text-[10px] font-mono text-white font-bold ml-1">{card.initiative}</span>
                        </div>
                        
                        <div className="flex-1 p-2 flex flex-col justify-between text-[9px] leading-relaxed relative">
                          {/* Selection Overlays */}
                          {isTop && <div className="absolute inset-0 bg-gradient-to-b from-cyan-500/10 to-transparent pointer-events-none" />}
                          {isBottom && <div className="absolute inset-0 bg-gradient-to-t from-amber-500/10 to-transparent pointer-events-none" />}

                          <div className={`border-l-2 pl-2 ${isTop ? 'border-cyan-400 text-white' : 'border-cyan-500/30 text-cyan-100/50'}`}>
                            {renderCardAction(card.top)}
                          </div>
                          <div className={`border-l-2 pl-2 ${isBottom ? 'border-amber-400 text-white' : 'border-amber-500/30 text-amber-100/50'}`}>
                            {renderCardAction(card.bottom)}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>

              </div>

              {/* Modal Footer */}
              <div className="p-6 border-t border-white/5 bg-zinc-900/50 flex justify-end gap-4">
                <button 
                  onClick={() => { setLinkingTask(null); setSelectedTop(null); setSelectedBottom(null); }}
                  className="px-6 py-3 rounded-xl text-sm font-medium text-zinc-400 hover:text-white transition-colors"
                >
                  Cancel
                </button>
                <button 
                  onClick={handleLink}
                  disabled={!selectedTop || !selectedBottom}
                  className="px-8 py-3 rounded-xl bg-emerald-500 text-black font-bold tracking-widest uppercase text-sm disabled:opacity-50 disabled:bg-zinc-700 disabled:text-zinc-500 transition-colors"
                >
                  Confirm Binding
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

    </div>
  );
}
