"use client";

import React from 'react';

export default function SectorRail({ sectors = [], activeSector, onSelect, compact = false }) {
  return (
    <aside aria-label="Areas" className={compact
      ? 'w-full h-12 border-b border-white/5 bg-black/30 flex flex-row items-center px-2 gap-2 z-40 shrink-0 overflow-x-auto md:w-14 md:h-auto md:border-b-0 md:border-r md:flex-col md:py-4 md:px-0 md:gap-3.5 md:overflow-x-hidden'
      : 'w-14 border-r border-white/5 bg-black/30 flex flex-col items-center py-4 gap-3.5 z-40 shrink-0'}>
      {sectors.map((sec) => (
        <button
          key={sec.id}
          onClick={() => onSelect(sec.id)}
          title={sec.label}
          className={`w-9 h-9 rounded flex items-center justify-center transition-all border ${
            activeSector === sec.id 
              ? 'bg-accent border-accent text-zinc-950 font-bold shadow-[0_0_10px_rgba(0,212,255,0.3)]' 
              : 'bg-zinc-900 border-white/10 text-white/60 hover:bg-zinc-800 hover:text-white hover:border-white/20'
          }`}
        >
          <span className="text-base">{sec.icon}</span>
        </button>
      ))}
    </aside>
  );
}
