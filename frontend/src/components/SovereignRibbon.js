"use client";

import React from 'react';
import { motion } from 'framer-motion';
import {
  BookOpen,
  Castle,
  CircleHelp,
  Coffee,
  Dumbbell,
  FlaskConical,
  Hammer,
  LibraryBig,
  Mountain,
  RefreshCw,
  Satellite,
  ScrollText,
  Settings2,
  Shield,
  WalletCards,
} from 'lucide-react';

const NAV_ICONS = {
  COMMAND: Satellite,
  SANCTUM: Castle,
  CODEX: BookOpen,
  DOMESTIC: Shield,
  FRONT: ScrollText,
  GAUNTLET: WalletCards,
  OUTLAND: Mountain,
  LAB: FlaskConical,
  PRISM: Coffee,
  REFLECTION: CircleHelp,
  IRON: Dumbbell,
  LIBRARY: LibraryBig,
  CHRONICLE: ScrollText,
  FORGE: Hammer,
};

// Keep the Tauri ribbon aligned with the original PWA's command flow. The
// backend settings object is user-editable, so its JSON insertion order is
// not a safe source of presentation order.
const NAV_ORDER = [
  'COMMAND',
  'SANCTUM',
  'DOMESTIC',
  'FRONT',
  'GAUNTLET',
  'OUTLAND',
  'LAB',
  'PRISM',
  'REFLECTION',
  'IRON',
  'LIBRARY',
  'CHRONICLE',
  'CODEX',
];

export default function SovereignRibbon({ realm, navItems = [], activeId, onSelect, isSyncing }) {
  const tooltips = {
    'COMMAND': 'Command Hub - Central Protocol Control',
    'SANCTUM': 'The Sanctum: Personal Evolution & High-Fidelity Living',
    'DOMESTIC': 'The Domestic Breach: Household Logistics & Infrastructure',
    'FRONT': 'The High-Velocity Front: Professional Warfare & Career Engineering',
    'GAUNTLET': 'The Bureaucratic Gauntlet: Financial Defense & Resource Optimization',
    'OUTLAND': 'The Kinetic Outland: Physical Resilience & World Exploration',
    'LAB': 'Synthesis Lab - Alchemical Data Transmutation',
    'PRISM': 'Boba Lounge - Media & Knowledge Refraction',
    'REFLECTION': 'Friðr Hall - Reflection & Cognitive Reboot',
    'IRON': 'Iron Sanctum - Physical Training & Vitals',
    'LIBRARY': 'Library - The Grand Zettelkasten Archive',
    'CHRONICLE': 'Archives & Logs - Event Logs & History',
    'CODEX': 'Knowledge Base - The state of the Codex is the state of the self.',
    'FORGE': 'Asset Creation - Creation & System Development'
  };

  return (
    <motion.header 
      initial={{ y: -50, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      className="h-24 border-b border-white/5 bg-black/30 flex items-center justify-between px-4 z-50 shrink-0"
    >
      <div className="flex items-center gap-2 px-2 w-32 shrink-0 hidden sm:flex">
        <div className="w-10 h-10 rounded bg-accent/20 flex items-center justify-center border border-accent/40 text-accent font-bold text-xl">
          N
        </div>
      </div>

      <nav className="flex items-center gap-1.5 flex-1 min-w-0 overflow-x-auto justify-start">
        {navItems
          .filter(item => item.id !== 'SYSTEM' && item.id !== 'SYNC')
          .sort((a, b) => {
            const aIndex = NAV_ORDER.indexOf(a.id);
            const bIndex = NAV_ORDER.indexOf(b.id);
            const aRank = aIndex === -1 ? NAV_ORDER.length : aIndex;
            const bRank = bIndex === -1 ? NAV_ORDER.length : bIndex;
            return aRank - bRank;
          })
          .map((item) => {
          const Icon = NAV_ICONS[item.id] || CircleHelp;
          const isActive = activeId === item.id;
          return (
          <button
            key={item.id}
            onClick={() => onSelect(item.id)}
            title={tooltips[item.id] || item.label}
            aria-label={item.label || item.id}
            className={`w-16 sm:w-20 h-20 rounded border transition-all flex flex-col items-center justify-center gap-1 shrink-0 ${
              isActive
                ? 'bg-accent border-accent text-zinc-950 font-bold' 
                : 'bg-zinc-900 border-white/10 text-white/60 hover:bg-zinc-800 hover:border-white/20 group'
            }`}
          >
            <span
              className={`text-2xl transition-all ${isActive ? 'opacity-100' : 'opacity-70 group-hover:opacity-100'}`}
              style={{
                color: isActive ? '#050505' : 'var(--accent)',
                filter: isActive
                  ? 'drop-shadow(0 0 5px color-mix(in srgb, var(--accent) 85%, white))'
                  : 'drop-shadow(0 0 5px var(--accent)) drop-shadow(0 0 12px color-mix(in srgb, var(--accent) 55%, transparent))',
              }}
            >
              <Icon aria-hidden="true" size={24} strokeWidth={1.8} />
            </span>
            <span className="text-[9px] uppercase tracking-widest font-bold opacity-80">
              {item.id === 'PRISM' ? 'LOUNGE' : item.id}
            </span>
          </button>
          );
        })}
      </nav>
      
      <div className="flex items-center gap-1.5 pl-2 shrink-0 justify-end">
        <button 
          onClick={() => !isSyncing && onSelect('SYNC')}
          disabled={isSyncing}
          title={isSyncing ? "Syncing sequence in progress..." : "Sync - Push local protocol updates to the cloud vault"}
          className={`w-16 sm:w-20 h-20 rounded border flex flex-col items-center justify-center gap-1 transition-all group ${
            isSyncing 
              ? 'border-yellow-500/20 bg-yellow-500/5 text-yellow-500/60 cursor-not-allowed shadow-[0_0_10px_rgba(234,179,8,0.15)]'
              : 'border-emerald-500/20 bg-zinc-900 text-white/60 hover:bg-emerald-900/40 hover:border-emerald-400/40'
          }`}
        >
          <motion.span 
            animate={isSyncing ? { rotate: 360 } : {}}
            transition={isSyncing ? { repeat: Infinity, duration: 1.5, ease: "linear" } : {}}
            className="text-2xl opacity-70 group-hover:opacity-100 transition-all"
            style={{
              color: 'var(--accent)',
              filter: 'drop-shadow(0 0 5px var(--accent)) drop-shadow(0 0 12px color-mix(in srgb, var(--accent) 55%, transparent))',
            }}
          >
            <RefreshCw aria-hidden="true" size={24} strokeWidth={1.8} />
          </motion.span>
          <span className={`text-[9px] uppercase font-bold tracking-widest transition-colors ${
            isSyncing 
              ? 'text-yellow-500/60' 
              : 'text-white/60 group-hover:text-emerald-400'
          }`}>
            {isSyncing ? 'SYNCING' : 'SYNC'}
          </span>
        </button>
        <button 
          onClick={() => onSelect('SYSTEM')}
          title="System Config - Environment and diagnostic settings"
          className={`w-16 sm:w-20 h-20 rounded border flex flex-col items-center justify-center gap-1 hover:bg-zinc-800 transition-all group ${
            activeId === 'SYSTEM'
              ? 'bg-accent border-accent text-zinc-950 font-bold'
              : 'bg-zinc-900 border-white/10 text-white/60'
          }`}
        >
          <span
            className="text-2xl opacity-70 group-hover:opacity-100 transition-all"
            style={{
              color: 'var(--accent)',
              filter: 'drop-shadow(0 0 5px var(--accent)) drop-shadow(0 0 12px color-mix(in srgb, var(--accent) 55%, transparent))',
            }}
          >
            <Settings2 aria-hidden="true" size={24} strokeWidth={1.8} />
          </span>
          <span className={`text-[9px] uppercase font-bold tracking-widest ${activeId === 'SYSTEM' ? 'text-zinc-950' : 'text-white/60'}`}>SYSTEM</span>
        </button>
      </div>
    </motion.header>
  );
}
