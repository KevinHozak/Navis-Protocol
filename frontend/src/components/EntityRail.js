"use client";

import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import JournalCalendar from './JournalCalendar';

export default function EntityRail({ entities = [], activeEntityId, onSelect, activeSector, loading = false, entityLoadError, onRetry, selectedJournalDate, onJournalDateSelect, onRolloverComplete }) {
  const [filter, setFilter] = useState('');

  useEffect(() => {
    setFilter('');
  }, [activeSector]);

  const filteredEntities = entities.filter(e => 
    e.name.toLowerCase().includes(filter.toLowerCase())
  );

  const skeletonItems = Array.from({ length: 8 });

  const isJournal = activeSector === 'JOURNAL';
  const isCodexRoster = ['COMPANIONS', 'RESIDENTS', 'ANTAGONISTS', 'BEASTS', 'REALMS'].includes(activeSector);

  return (
    <aside aria-label={`${activeSector || 'Entity'} roster`} className={`flex flex-col z-30 shrink-0 ${isCodexRoster ? 'w-full h-28 border-b border-white/5 bg-zinc-950/90 md:w-56 md:h-auto md:border-b-0 md:border-r md:bg-black/30' : 'w-56 border-r border-white/5 bg-black/30'}`}>
      {/* Journal Calendar — shown above entity list when JOURNAL sector is active */}
      {isJournal && onJournalDateSelect && (
        <JournalCalendar
          selectedDate={selectedJournalDate}
          onDateSelect={onJournalDateSelect}
          onRolloverComplete={onRolloverComplete}
        />
      )}

      {!isJournal && (
        <div className={`border-b border-white/5 ${isCodexRoster ? 'p-2 md:p-3' : 'p-3'}`}>
          <input 
            type="text" 
            aria-label={`Filter ${activeSector?.split(':')[0] || 'entities'}`}
            placeholder={`Filter ${activeSector?.split(':')[0] || 'entities'}...`}
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="w-full bg-zinc-950 border border-white/10 rounded px-2.5 py-1.5 text-xs focus:outline-none focus:border-accent/50 text-white placeholder:text-white/20 font-medium"
            disabled={loading}
          />
        </div>
      )}

      {!isJournal && (
        <div className={`flex-1 p-2 custom-scrollbar ${isCodexRoster ? 'min-h-0 overflow-x-auto overflow-y-hidden md:overflow-x-hidden md:overflow-y-auto' : 'overflow-y-auto space-y-1'}`}>
          <AnimatePresence mode="wait">
          {loading ? (
            <motion.div
              key="skeleton"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.12 }}
              className="space-y-1.5 pt-1"
            >
              {skeletonItems.map((_, i) => (
                <div
                  key={i}
                  className="h-8 rounded border border-white/5 bg-white/[0.03] overflow-hidden relative"
                  style={{ animationDelay: `${i * 40}ms` }}
                >
                  <div
                    className="absolute inset-0 -translate-x-full animate-[shimmer_1.2s_infinite]"
                    style={{
                      background: 'linear-gradient(90deg, transparent, rgba(255,255,255,0.04), transparent)',
                      animationDelay: `${i * 80}ms`
                    }}
                  />
                </div>
              ))}
              <div className="text-[9px] text-accent/30 text-center pt-3 uppercase tracking-[0.3em] font-bold font-mono animate-pulse">
                Uplink synchronizing...
              </div>
            </motion.div>
          ) : (
            <motion.div
              key="entities"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.15 }}
              className={isCodexRoster ? 'flex min-w-max gap-1 md:min-w-0 md:flex-col' : 'space-y-1'}
            >
              {entityLoadError ? (
                <div role="alert" className="space-y-2 px-2 py-4 text-center">
                  <div className="text-[10px] text-red-200/80">{entityLoadError.message}</div>
                  <button type="button" onClick={onRetry} className="rounded border border-red-300/30 px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider text-red-100 hover:bg-red-950/50">
                    Retry Keeper load
                  </button>
                </div>
              ) : filteredEntities.length === 0 ? (
                <div className="w-full text-[10px] text-white/30 text-center py-2 uppercase tracking-wider font-semibold md:py-4">
                  {filter ? 'No matching items' : activeSector === 'KEEPER' ? 'No Keeper records found' : isCodexRoster ? 'No characters available' : 'No items found'}
                </div>
              ) : (
                filteredEntities.map((entity) => {
                  const isActive = activeEntityId === entity.id;
                  return (
                    <button 
                      key={entity.id}
                      onClick={() => onSelect(entity)}
                      title={entity.name}
                      aria-current={isActive ? 'true' : undefined}
                      className={`${isCodexRoster ? 'w-36 shrink-0 md:w-full md:shrink' : 'w-full'} text-left px-3 py-2 rounded border transition-all text-xs font-bold uppercase tracking-wider ${
                        isActive 
                          ? 'bg-accent border-accent text-zinc-950 shadow-[0_0_15px_rgba(0,212,255,0.05)]' 
                          : 'bg-zinc-900 border-white/10 text-white/60 hover:bg-zinc-800 hover:text-white hover:border-white/20'
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="truncate">{entity.name}</span>
                        {entity.type === 'directory' && <span className="text-[12px] opacity-60">📁</span>}
                        {entity.type === 'image' && <span className="text-[12px] opacity-60">🖼️</span>}
                      </div>
                    </button>
                  );
                })
              )}
            </motion.div>
          )}
          </AnimatePresence>
        </div>
      )}
    </aside>
  );
}
