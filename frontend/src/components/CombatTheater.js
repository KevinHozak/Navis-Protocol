"use client";
import React, { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { apiFetch, apiUrl, vaultAssetUrl } from "../lib/desktopApi";
import VaultAssetImage from "./VaultAssetImage";

export default function CombatTheater({
  status,
  onSelectEntity,
  logUrl = "Battle/Combat_Log.md"
}) {
  const realm = status?.current_realm || "Unknown Realm";
  const realmImage = `Realms/${realm}/Landscape.png`;

  const enemies = [];
  if (status?.current_antagonist) {
    enemies.push({ 
      name: status.current_antagonist, 
      type: 'ANTAGONIST',
      image: `Obstacles/Antagonists/${status.current_antagonist}/Card.png`,
      fallback: `Obstacles/Antagonists/${status.current_antagonist}/Portrait.png`,
      health: 100 
    });
  }
  if (status?.current_beast) {
    enemies.push({ 
      name: status.current_beast, 
      type: 'BEAST',
      image: `Obstacles/Beasts/${status.current_beast}/Card.png`,
      fallback: `Obstacles/Beasts/${status.current_beast}/Portrait.png`,
      health: 100 
    });
  }

  const allies = [
    { name: "Keeper", image: "Keeper/Card.png", fallback: "Keeper/Portrait.png", health: 100 }
  ];
  if (status?.squad) {
    status.squad.forEach(entity => {
      allies.push({ 
        name: entity.name, 
        image: `Companions/${entity.name}/Card.png`,
        fallback: `Companions/${entity.name}/Portrait.png`,
        health: 100 
      });
    });
  }
  const [combatLog, setCombatLog] = useState([]);
  const [loadingLog, setLoadingLog] = useState(false);
  const [battle, setBattle] = useState(null);
  useEffect(() => {
    let ignore = false;
    const refresh = async () => {
      try {
        const response = await apiFetch('/api/battle/state');
        const data = response.ok ? await response.json() : null;
        if (!ignore) setBattle(data);
      } catch { if (!ignore) setBattle(null); }
    };
    refresh();
    window.addEventListener('navis:progression-changed', refresh);
    return () => { ignore = true; window.removeEventListener('navis:progression-changed', refresh); };
  }, [status]);

  // Fetch the actual log from the vault or combat route
  useEffect(() => {
    let ignore = false;

    async function fetchLog() {
      if (!logUrl) {
        setCombatLog([]);
        return;
      }
      setLoadingLog(true);
      try {
        const endpoint = logUrl.startsWith('/') ? logUrl : `/api/vault/${logUrl}`;
        const res = await apiFetch(endpoint);
        if (!res.ok) {
          if (!ignore) setCombatLog([]);
          return;
        }

        let data = null;
        if (typeof res.json === 'function') {
          try {
            data = await res.json();
          } catch {
            data = null;
          }
        }
        if (data === null && typeof res.text === 'function') {
          try {
            const raw = await res.text();
            try {
              data = JSON.parse(raw);
            } catch {
              data = raw;
            }
          } catch {
            data = null;
          }
        }

        let lines = [];
        if (Array.isArray(data?.logs)) {
          lines = data.logs
            .map((line) => (typeof line === 'string' ? line.trim() : ''))
            .filter((line) => line.startsWith('>'));
        } else if (typeof data?.content === 'string') {
          lines = data.content
            .split('\n')
            .map((line) => line.trim())
            .filter((line) => line.startsWith('>'));
        } else if (typeof data === 'string') {
          lines = data
            .split('\n')
            .map((line) => line.trim())
            .filter((line) => line.startsWith('>'));
        }

        if (!ignore) {
          setCombatLog(lines.slice(-15));
        }
      } catch (e) {
        console.error("Failed to fetch combat log", e);
        if (!ignore) {
          setCombatLog([]);
        }
      } finally {
        if (!ignore) {
          setLoadingLog(false);
        }
      }
    }

    fetchLog();
    return () => {
      ignore = true;
    };
  }, [logUrl]);

  // Helper to format log lines containing bracketed terms
  const formatLogLine = (line) => {
    // Basic regex to highlight [TEXT] in cyan
    const parts = line.split(/(\[.*?\])/g);
    return parts.map((part, i) => {
      if (part.startsWith('[') && part.endsWith(']')) {
        return <span key={i} className="text-cyan-400 font-bold tracking-wider">{part}</span>;
      }
      return <span key={i} className="text-zinc-300">{part}</span>;
    });
  };

  const renderCard = (entity, isEnemy) => {
    const synergy = !isEnemy && battle?.encounter?.synergies?.find(member => member.name === entity.name);
    const passiveLabels = synergy ? Object.entries(synergy.passives).filter(([, value]) => value > 0).map(([key, value]) => ({
      shield_percent: `+${value}% Shield`, ap_bonus: `+${value} AP per turn`, kinetic_percent: `+${value}% Kinetic damage`
    }[key])).filter(Boolean) : [];
    const borderColor = isEnemy ? "border-red-500/40 hover:border-red-400" : "border-cyan-500/40 hover:border-cyan-400";
    const shadowColor = isEnemy ? "shadow-red-500/20" : "shadow-cyan-500/20";
    const barColor = isEnemy ? "bg-red-500" : "bg-cyan-400";

    return (
      <motion.div
        key={entity.name}
        whileHover={{ scale: 1.05, y: -5 }}
        animate={{ boxShadow: synergy ? '0 0 24px rgba(255,77,77,0.5)' : isEnemy ? '0 0 15px rgba(255,77,77,0.2)' : '0 0 15px rgba(0,212,255,0.2)' }}
        onClick={async () => {
          if (onSelectEntity) {
            if (isEnemy) {
              if (entity.type === 'ANTAGONIST') {
                onSelectEntity({ id: 'ANTAGONIST_COMBAT', name: 'Antagonist Matrix', type: 'virtual' });
              } else if (entity.type === 'BEAST') {
                onSelectEntity({ id: 'BEAST_COMBAT', name: 'Regional Beast Matrix', type: 'virtual' });
              }
            } else if (entity.name !== 'Keeper') {
              onSelectEntity({ id: 'RESERVE_ROSTER', name: 'Reserve Roster', type: 'virtual', targeting: entity.name });
            }
          }
        }}
        className={`w-40 bg-black/80 ${borderColor} border rounded-xl overflow-hidden shadow-[0_0_15px_var(--tw-shadow-color)] ${shadowColor} backdrop-blur-md transition-colors ${(isEnemy || (!isEnemy && entity.name !== 'Keeper')) ? 'cursor-pointer' : ''}`}
      >
        <VaultAssetImage 
          assetPath={entity.image}
          fallbackPaths={entity.fallback ? [entity.fallback] : []}
          alt={entity.name} 
          className="w-full h-60 object-cover border-b border-white/10"
          fallbackClassName="w-full h-60 border-b border-white/10"
        />
        <div className="p-3 text-center">
          <div className="text-white font-bold text-xs uppercase tracking-widest mb-2 truncate">
            {entity.name}
          </div>
          {passiveLabels.length > 0 && <div role="status" aria-label={`${entity.name} active synergy`} className="mb-2 text-xs text-red-400">
            <span className="font-bold">✦ Active Synergy</span>
            {passiveLabels.map(label => <p key={label}>{label}</p>)}
          </div>}
          {/* Health Bar */}
          <div className="bg-zinc-900 h-1.5 rounded-full w-full overflow-hidden">
            <motion.div 
              initial={{ width: 0 }}
              animate={{ width: `${entity.health}%` }}
              className={`h-full ${barColor} rounded-full`}
            />
          </div>
        </div>
      </motion.div>
    );
  };

  return (
    <div className="flex flex-col max-w-6xl mx-auto w-full mb-8">
      <div className="text-center mb-6">
        <h2 className="text-2xl font-black text-red-500 tracking-[0.2em] uppercase font-mono drop-shadow-[0_0_10px_rgba(239,68,68,0.5)]">
          ⚔️ COMBAT THEATER: {realm}
        </h2>
      </div>

      <div 
        className="relative border border-zinc-800 rounded-3xl p-10 overflow-hidden shadow-2xl"
        style={{
          backgroundImage: `linear-gradient(rgba(10, 10, 10, 0.8), rgba(10, 10, 10, 0.9)), url('${vaultAssetUrl(realmImage, { cacheBust: false })}')`,
          backgroundSize: 'cover',
          backgroundPosition: 'center',
          boxShadow: 'inset 0 0 100px #000'
        }}
      >
        {/* Enemies Row */}
        <div className="flex justify-center flex-wrap gap-8 mb-16 relative z-10">
          {enemies.map(e => renderCard(e, true))}
        </div>

        {/* VS Divider */}
        <div className="absolute top-1/2 left-0 right-0 flex justify-center items-center -translate-y-1/2 opacity-20 pointer-events-none">
          <div className="h-px bg-red-500 w-1/3"></div>
          <span className="mx-4 text-4xl font-black text-red-500 tracking-widest">VS</span>
          <div className="h-px bg-red-500 w-1/3"></div>
        </div>

        {/* Allies Row */}
        <div className="flex justify-center flex-wrap gap-8 relative z-10">
          {allies.map(a => renderCard(a, false))}
        </div>
      </div>

      {/* Combat Log */}
      {battle?.encounter && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mt-6 p-5 bg-zinc-950/90 backdrop-blur-md border border-white/10 rounded-xl text-sm">
          <p className="text-red-400">Turn {battle.encounter.turn || 1} · HP {battle.encounter.player_hp ?? 100} · AP {battle.encounter.ap_available ?? battle.encounter.ap_per_turn ?? 2}</p>
          {battle.encounter.enemies?.filter(enemy => enemy.hp > 0).map((enemy, index) => <div key={enemy.id || index} className="mt-2 text-zinc-300">
            <p>{enemy.id || 'Enemy'}: {enemy.intent} · {enemy.affinity || 'Physical'}</p>
            {Object.entries(enemy.vulnerabilities || {}).map(([element, multiplier]) => <span key={element} className="inline-block mr-2 text-amber-400">Weakness: {element} · XP ×{multiplier}</span>)}
          </div>)}
          {battle.hand?.map(card => {
            const advantages = battle.encounter.enemies?.filter(enemy => enemy.hp > 0 && (enemy.vulnerabilities?.[card.element] || 1) > 1) || [];
            return <p key={card.id} className={card.attack > 0 && advantages.length ? 'text-amber-400' : 'text-zinc-300'}>{card.name || card.id}: {card.element || 'Physical'} · AP {card.ap_cost} · Attack {card.attack} · Shield {card.shield}{card.attack > 0 && advantages.length > 0 && ` · Elemental advantage: ${advantages.map(enemy => enemy.id || 'Enemy').join(', ')}`}</p>;
          })}
          {battle.last_round?.critical_hits?.length > 0 && <p role="status" className="mt-3 text-red-400">⚡ Critical Strike · Task XP ×{battle.last_round.xp_multiplier}</p>}
        </motion.div>
      )}
      <div className="mt-10">
        <h3 className="text-cyan-500/80 font-bold tracking-widest uppercase mb-4 text-sm flex items-center gap-2">
          <span>📜</span> Combat Log
          {loadingLog && <span className="text-xs text-zinc-500 animate-pulse ml-2">Syncing with Vault...</span>}
        </h3>
        <div className="bg-black border border-white/10 rounded-xl p-5 h-64 overflow-y-auto flex flex-col gap-3 font-mono text-xs shadow-inner">
          {combatLog.length === 0 && !loadingLog && (
            <div className="text-zinc-600 italic">No combat events recorded.</div>
          )}
          {combatLog.map((line, i) => (
            <motion.div 
              key={i} 
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.05 }}
              className="leading-relaxed border-l-2 border-cyan-500/30 pl-3 py-1"
            >
              {formatLogLine(line)}
            </motion.div>
          ))}
          {/* Dummy element to scroll into view could go here */}
        </div>
      </div>
    </div>
  );
}
