import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { apiFetch } from '../lib/desktopApi';
import VaultAssetImage from './VaultAssetImage';

export default function CombatProfileModal({ isOpen, onClose, entityName, entityType, cardUrl }) {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (isOpen) {
      fetchStatus();
    }
  }, [isOpen]);

  const fetchStatus = async () => {
    try {
      const res = await apiFetch('/api/status');
      const data = await res.json();
      setStatus(data);
    } catch (e) {
      console.error("Failed to fetch status:", e);
    }
  };

  const handleAction = async (endpoint, payload) => {
    setLoading(true);
    try {
      const res = await apiFetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (res.ok) {
        await fetchStatus();
      } else {
        const err = await res.json();
        alert(err.detail || "Action failed");
      }
    } catch (e) {
      alert("Network error: " + e.message);
    }
    setLoading(false);
  };

  if (!isOpen) return null;

  // Determine state for Companions
  const squad = status?.squad || [];
  const isInSquad = squad.some(m => m.name === entityName);
  const isVanguard = squad.some(m => m.name === entityName && m.is_vanguard);
  
  // Determine state for Threats
  const isCurrentAntagonist = status?.current_antagonist === entityName;
  const isCurrentBeast = status?.current_beast === entityName;
  const isCurrentThreat = isCurrentAntagonist || isCurrentBeast;

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-8 bg-black/80 backdrop-blur-sm">
        <motion.div 
          initial={{ opacity: 0, scale: 0.95, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 20 }}
          className="relative w-full max-w-4xl bg-zinc-950/90 border border-white/10 rounded-2xl shadow-2xl flex overflow-hidden backdrop-blur-md"
        >
          {/* Left Column: Trading Card */}
          <div className="w-1/2 p-6 bg-black/40 border-r border-white/5 flex flex-col items-center justify-center relative">
            <div className="absolute inset-0 bg-gradient-to-br from-accent/5 to-transparent pointer-events-none" />
            <VaultAssetImage
              sourceUrls={cardUrl ? [cardUrl, cardUrl.replace('Card.png', 'Portrait.png')] : undefined}
              assetPath={cardUrl ? undefined : `${entityType}/${entityName}/Card.png`}
              fallbackPaths={cardUrl ? [] : [`${entityType}/${entityName}/Portrait.png`]}
              alt={`${entityName} Card`}
              className="w-full max-w-sm rounded-xl shadow-2xl object-cover ring-1 ring-white/10"
            />
          </div>

          {/* Right Column: Controls & Stats */}
          <div className="w-1/2 p-8 flex flex-col">
            <div className="flex justify-between items-start mb-8">
              <div>
                <h2 className="text-2xl font-bold text-white tracking-widest uppercase font-display">{entityName}</h2>
                <p className="text-xs text-accent uppercase tracking-[0.2em]">{entityType}</p>
              </div>
              <button 
                onClick={onClose}
                className="w-8 h-8 rounded-full bg-white/5 hover:bg-white/10 text-white/60 hover:text-white flex items-center justify-center transition-colors"
              >
                ✕
              </button>
            </div>

            <div className="flex-1 space-y-6">
              <div className="p-4 bg-zinc-900/50 rounded-lg border border-white/5">
                <h3 className="text-xs uppercase tracking-widest text-white/40 mb-4 font-bold">Tactical Deployment</h3>
                
                {loading ? (
                  <div className="py-4 text-center text-accent/60 animate-pulse text-sm font-mono tracking-widest uppercase">
                    Syncing Manifold...
                  </div>
                ) : (
                  <div className="space-y-3">
                    {entityType === 'Companions' && (
                      <>
                        {!isInSquad ? (
                          <button 
                            onClick={() => handleAction('/api/squad/deploy', { name: entityName })}
                            className="w-full py-3 bg-accent text-black font-bold uppercase tracking-widest rounded hover:bg-white transition-all shadow-[0_0_15px_rgba(0,212,255,0.3)]"
                          >
                            Deploy to Squad
                          </button>
                        ) : (
                          <>
                            <button 
                              onClick={() => handleAction('/api/squad/bench', { name: entityName })}
                              className="w-full py-3 bg-zinc-800 text-white font-bold uppercase tracking-widest rounded hover:bg-red-500/20 hover:text-red-400 transition-all border border-transparent hover:border-red-500/30"
                            >
                              Recall to Reserve
                            </button>
                            
                            {!isVanguard && (
                              <button 
                                onClick={() => handleAction('/api/squad/vanguard', { name: entityName })}
                                className="w-full py-3 bg-zinc-900 text-accent font-bold uppercase tracking-widest rounded border border-accent/20 hover:bg-accent/10 transition-all"
                              >
                                Designate Vanguard
                              </button>
                            )}
                          </>
                        )}
                      </>
                    )}

                    {(entityType === 'Antagonists' || entityType === 'Beasts') && (
                      <>
                        {!isCurrentThreat ? (
                          <button 
                            onClick={() => handleAction('/api/combat/target', { 
                              type: entityType === 'Antagonists' ? 'antagonist' : 'beast', 
                              name: entityName 
                            })}
                            className="w-full py-3 bg-red-500 text-white font-bold uppercase tracking-widest rounded hover:bg-red-400 transition-all shadow-[0_0_15px_rgba(239,68,68,0.3)]"
                          >
                            Designate Active Threat
                          </button>
                        ) : (
                          <button 
                            onClick={() => handleAction('/api/combat/target', { 
                              type: entityType === 'Antagonists' ? 'antagonist' : 'beast', 
                              name: '' 
                            })}
                            className="w-full py-3 bg-zinc-800 text-white font-bold uppercase tracking-widest rounded hover:bg-zinc-700 transition-all border border-transparent"
                          >
                            Clear Active Threat
                          </button>
                        )}
                      </>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}
