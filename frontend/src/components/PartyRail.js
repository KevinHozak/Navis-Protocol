"use client";

import React from 'react';
import { motion } from 'framer-motion';
import VaultAssetImage from './VaultAssetImage';

export default function PartyRail({ entities = [] }) {

  return (
    <aside className="w-64 glass-dark border-l border-white/5 flex flex-col z-30 bg-black/40">
      <div className="p-4 border-b border-white/5 bg-accent/5">
        <h3 className="text-xs font-bold uppercase tracking-[0.2em] text-accent flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-accent animate-pulse"></span>
          Active Squad
        </h3>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-6">
        {entities.map((entity) => (
          <motion.div 
            key={entity.name}
            initial={{ x: 20, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            className="group cursor-pointer"
          >
            <div className="relative mb-3">
              <div className="aspect-[3/4] rounded-sm overflow-hidden border border-white/10 group-hover:border-accent/50 transition-all">
                <VaultAssetImage
                  assetPath={`Companions/${entity.name}/Portrait.png`}
                  fallbackPaths={[`Companions/${entity.name}/Card.png`]}
                  alt={entity.name}
                  className="w-full h-full object-cover grayscale group-hover:grayscale-0 transition-all duration-500 scale-105 group-hover:scale-100"
                />
              </div>
              <div className="absolute top-2 right-2 px-1.5 py-0.5 bg-black/60 backdrop-blur-md border border-white/10 rounded text-[10px] text-white/60 font-mono">
                {entity.level || 'LVL 1'}
              </div>
            </div>
            
            <div className="space-y-1">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-white/80 uppercase tracking-widest group-hover:text-accent transition-colors">
                  {entity.name}
                </span>
                <span className="text-[10px] text-white/20 font-mono italic">
                  {entity.role || 'Companion'}
                </span>
              </div>
              <div className="h-1 w-full bg-white/5 rounded-full overflow-hidden">
                <div className="h-full bg-accent/40 w-full shadow-[0_0_8px_rgba(0,212,255,0.2)]" />
              </div>
            </div>
          </motion.div>
        ))}
      </div>
    </aside>
  );
}
