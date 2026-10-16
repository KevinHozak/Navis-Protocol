"use client";

import React, { useState, useId } from "react";
import { motion, AnimatePresence } from "framer-motion";
import AudioEngine from "../lib/AudioEngine";

// Canonically defined branches and styling configurations
export const BRANCH_CONFIG = {
  Focus: {
    color: "#00d4ff", // cyan
    glow: "rgba(0, 212, 255, 0.5)",
    border: "border-cyan-400/50",
    bg: "bg-cyan-950/40",
    icon: "🎯",
    name: "Focus",
    description: "Deep work capacity, cognitive flow stamina, and uninterrupted execution.",
  },
  Martial: {
    color: "#ff4d4d", // red
    glow: "rgba(255, 77, 77, 0.5)",
    border: "border-red-400/50",
    bg: "bg-red-950/40",
    icon: "⚔️",
    name: "Martial",
    description: "High-Velocity Front momentum, crisis resolve, and friction resistance.",
  },
  Kinetic: {
    color: "#f59e0b", // amber
    glow: "rgba(245, 158, 11, 0.5)",
    border: "border-amber-400/50",
    bg: "bg-amber-950/40",
    icon: "⚡",
    name: "Kinetic",
    description: "Physical vitality, biomechanical discipline, and Outland expedition endurance.",
  },
  Lore: {
    color: "#a855f7", // purple
    glow: "rgba(168, 85, 247, 0.5)",
    border: "border-purple-400/50",
    bg: "bg-purple-950/40",
    icon: "📜",
    name: "Lore",
    description: "Holocron synthesis, library transmutation, and neural arbiter synergy.",
  },
};

// Spatial placement layout coordinates for node graphs (SVG canvas 1000 x 500)
export const DEFAULT_NODE_COORDINATES = {
  focus_deep_work: { x: 180, y: 340 },
  focus_clarity: { x: 180, y: 150 },
  martial_momentum: { x: 390, y: 340 },
  martial_tenacity: { x: 390, y: 150 },
  kinetic_vitality: { x: 610, y: 340 },
  kinetic_surge: { x: 610, y: 150 },
  lore_archivist: { x: 820, y: 340 },
  lore_synthesis: { x: 820, y: 150 },
};

export function getNodeState(node, availablePoints) {
  const currentRank = node?.current_rank ?? 0;
  const maxRank = node?.max_rank ?? 1;
  const unlocked = Boolean(node?.unlocked);

  if (currentRank >= maxRank) {
    return "MAXED";
  }
  if (!unlocked) {
    return "LOCKED";
  }
  if (availablePoints > 0) {
    return "AVAILABLE";
  }
  return "INSUFFICIENT_POINTS";
}

export default function ConstellationTalentTree({
  talentState,
  onAllocate,
  allocatingNodeId,
  selectedBranch,
  onSelectBranch,
}) {
  const [hoveredNodeId, setHoveredNodeId] = useState(null);
  const [selectedNodeId, setSelectedNodeId] = useState(null);
  const [feedbackNodeId, setFeedbackNodeId] = useState(null);
  const filterId = useId();

  const nodes = talentState?.nodes || [];
  const availablePoints = talentState?.available_points ?? 0;
  const currentLevel = talentState?.level ?? talentState?.current_level ?? 1;

  // Map nodes by id for quick lookup
  const nodeMap = React.useMemo(() => {
    const map = new Map();
    for (const n of nodes) {
      map.set(n.id, n);
    }
    return map;
  }, [nodes]);

  // Compute connections (prerequisite lines)
  const connections = React.useMemo(() => {
    const lines = [];
    for (const node of nodes) {
      const targetCoords = DEFAULT_NODE_COORDINATES[node.id] || { x: 500, y: 250 };
      const prereqs = node.prerequisites || [];
      for (const prereq of prereqs) {
        const prereqId = typeof prereq === "string" ? prereq : prereq?.node_id;
        if (!prereqId || !DEFAULT_NODE_COORDINATES[prereqId]) continue;
        const sourceCoords = DEFAULT_NODE_COORDINATES[prereqId];
        const sourceNode = nodeMap.get(prereqId);
        const isSatisfied = (sourceNode?.current_rank ?? 0) >= 1;
        lines.push({
          id: `${prereqId}->${node.id}`,
          sourceId: prereqId,
          targetId: node.id,
          source: sourceCoords,
          target: targetCoords,
          branch: node.branch,
          isSatisfied,
        });
      }
    }
    return lines;
  }, [nodes, nodeMap]);

  const activeNode = nodeMap.get(hoveredNodeId) || nodeMap.get(selectedNodeId);

  const handleNodeClick = (node) => {
    setSelectedNodeId(node.id);
    const state = getNodeState(node, availablePoints);

    if (state === "AVAILABLE" || (state === "INSUFFICIENT_POINTS" && node.unlocked)) {
      if (availablePoints > 0 && onAllocate) {
        AudioEngine.playSynthesizedSfx("allocate");
        setFeedbackNodeId(node.id);
        setTimeout(() => setFeedbackNodeId(null), 700);
        onAllocate(node.id, (node.current_rank ?? 0) + 1);
      } else {
        AudioEngine.playSynthesizedSfx("error");
      }
    } else if (state === "LOCKED") {
      AudioEngine.playSynthesizedSfx("error");
    } else {
      AudioEngine.playSynthesizedSfx("click");
    }
  };

  const handleKeyDown = (e, node) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      handleNodeClick(node);
    } else if (e.key === "ArrowRight" || e.key === "ArrowLeft" || e.key === "ArrowUp" || e.key === "ArrowDown") {
      // Find nearby nodes in direction
      const currentCoords = DEFAULT_NODE_COORDINATES[node.id] || { x: 500, y: 250 };
      let bestMatch = null;
      let minDistance = Infinity;

      for (const candidate of nodes) {
        if (candidate.id === node.id) continue;
        const coords = DEFAULT_NODE_COORDINATES[candidate.id] || { x: 500, y: 250 };
        const dx = coords.x - currentCoords.x;
        const dy = coords.y - currentCoords.y;

        let isMatch = false;
        if (e.key === "ArrowRight" && dx > 20 && Math.abs(dy) < 150) isMatch = true;
        if (e.key === "ArrowLeft" && dx < -20 && Math.abs(dy) < 150) isMatch = true;
        if (e.key === "ArrowUp" && dy < -20 && Math.abs(dx) < 150) isMatch = true;
        if (e.key === "ArrowDown" && dy > 20 && Math.abs(dx) < 150) isMatch = true;

        if (isMatch) {
          const dist = Math.hypot(dx, dy);
          if (dist < minDistance) {
            minDistance = dist;
            bestMatch = candidate;
          }
        }
      }

      if (bestMatch) {
        e.preventDefault();
        const nextEl = document.getElementById(`talent-node-${bestMatch.id}`);
        if (nextEl) {
          nextEl.focus();
          setSelectedNodeId(bestMatch.id);
          AudioEngine.playSynthesizedSfx("click");
        }
      }
    }
  };

  return (
    <div
      className="relative rounded-2xl bg-zinc-950/80 border border-white/10 p-6 overflow-hidden backdrop-blur-md shadow-2xl"
      data-testid="constellation-talent-tree"
    >
      {/* Background Starfield & Nebula Glow */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden opacity-40">
        <div className="absolute -top-32 -left-32 w-96 h-96 rounded-full bg-cyan-500/15 blur-3xl" />
        <div className="absolute -bottom-32 -right-32 w-96 h-96 rounded-full bg-purple-500/15 blur-3xl" />
        <div className="absolute top-1/2 left-1/3 w-80 h-80 rounded-full bg-amber-500/10 blur-3xl" />
      </div>

      {/* Header telemetry and branch filter selector */}
      <div className="flex flex-wrap items-center justify-between gap-4 mb-6 z-10 relative border-b border-white/10 pb-4">
        <div>
          <div className="text-[10px] font-mono uppercase tracking-[0.3em] text-cyan-400 flex items-center gap-2">
            <span>✨</span> Astral Constellation Matrix
          </div>
          <h3 className="text-xl font-black uppercase tracking-wider text-white mt-1">
            Keeper Specialization Talents
          </h3>
          <p className="text-xs text-white/50 font-mono mt-0.5">
            Level {currentLevel} · {talentState?.total_allocated_ranks ?? 0} Ranks Inscribed
          </p>
        </div>

        {/* Skill Points Reservoir Badge */}
        <div className="flex items-center gap-3">
          <div
            className={`px-4 py-2 rounded-xl font-mono border flex items-center gap-3 shadow-lg transition-all ${
              availablePoints > 0
                ? "bg-cyan-500/15 border-cyan-400/50 text-cyan-200 shadow-[0_0_20px_rgba(0,212,255,0.25)] animate-pulse"
                : "bg-zinc-900/60 border-white/10 text-white/50"
            }`}
            data-testid="available-talent-points"
          >
            <span className="text-sm">💠</span>
            <div>
              <div className="text-[9px] uppercase tracking-widest opacity-75">
                Available Talent Points
              </div>
              <div className="text-lg font-black leading-none">{availablePoints}</div>
            </div>
          </div>
        </div>
      </div>

      {/* Branch Quick Focus Tabs */}
      <div className="flex flex-wrap gap-2 mb-4 z-10 relative">
        <button
          type="button"
          onClick={() => onSelectBranch && onSelectBranch(null)}
          className={`px-3 py-1 rounded-lg text-xs font-mono uppercase tracking-wider border transition-all ${
            !selectedBranch
              ? "bg-white/15 border-white/40 text-white shadow-sm"
              : "bg-black/30 border-white/5 text-white/40 hover:text-white/80"
          }`}
        >
          All Constellations
        </button>
        {Object.entries(BRANCH_CONFIG).map(([bKey, bCfg]) => {
          const isSelected = selectedBranch === bKey;
          return (
            <button
              key={bKey}
              type="button"
              onClick={() => onSelectBranch && onSelectBranch(isSelected ? null : bKey)}
              className={`px-3 py-1 rounded-lg text-xs font-mono uppercase tracking-wider border flex items-center gap-1.5 transition-all ${
                isSelected
                  ? `${bCfg.bg} ${bCfg.border} text-white shadow-[0_0_12px_${bCfg.glow}]`
                  : "bg-black/30 border-white/5 text-white/40 hover:text-white/80"
              }`}
            >
              <span>{bCfg.icon}</span>
              <span>{bCfg.name}</span>
            </button>
          );
        })}
      </div>

      {/* Interactive Constellation SVG Node-Graph Canvas */}
      <div className="relative w-full aspect-[2/1] min-h-[360px] bg-black/60 rounded-xl border border-white/10 overflow-hidden shadow-inner">
        <svg
          viewBox="0 0 1000 500"
          className="w-full h-full select-none"
          role="region"
          aria-label="Interactive talent constellation map"
        >
          <defs>
            <filter id={`glow-${filterId}`} x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur in="SourceGraphic" stdDeviation="6" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
            <radialGradient id={`nebula-center-${filterId}`} cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="#00d4ff" stopOpacity="0.12" />
              <stop offset="100%" stopColor="#000000" stopOpacity="0" />
            </radialGradient>
          </defs>

          {/* Central subtle ambient nebula */}
          <rect width="1000" height="500" fill={`url(#nebula-center-${filterId})`} />

          {/* Background constellation stars (decorative) */}
          {[
            { cx: 80, cy: 90, r: 1.5, o: 0.4 },
            { cx: 280, cy: 70, r: 1.2, o: 0.3 },
            { cx: 500, cy: 40, r: 2, o: 0.5 },
            { cx: 720, cy: 80, r: 1.3, o: 0.3 },
            { cx: 920, cy: 110, r: 1.8, o: 0.4 },
            { cx: 100, cy: 440, r: 1.5, o: 0.3 },
            { cx: 900, cy: 420, r: 1.2, o: 0.4 },
            { cx: 500, cy: 460, r: 1.6, o: 0.3 },
          ].map((star, i) => (
            <circle
              key={i}
              cx={star.cx}
              cy={star.cy}
              r={star.r}
              fill="#ffffff"
              opacity={star.o}
              className="animate-pulse"
            />
          ))}

          {/* Inter-node constellation connecting lines */}
          {connections.map((conn) => {
            const branchCfg = BRANCH_CONFIG[conn.branch] || BRANCH_CONFIG.Focus;
            const isBranchDimmed = selectedBranch && selectedBranch !== conn.branch;
            return (
              <g key={conn.id} opacity={isBranchDimmed ? 0.15 : 1} className="transition-opacity duration-300">
                {/* Outer Glow Line */}
                <line
                  x1={conn.source.x}
                  y1={conn.source.y}
                  x2={conn.target.x}
                  y2={conn.target.y}
                  stroke={branchCfg.color}
                  strokeWidth={conn.isSatisfied ? 3.5 : 1.5}
                  strokeOpacity={conn.isSatisfied ? 0.6 : 0.2}
                  strokeDasharray={conn.isSatisfied ? "none" : "6 4"}
                  filter={conn.isSatisfied ? `url(#glow-${filterId})` : undefined}
                />
                {/* Core Star Beam Line */}
                <line
                  x1={conn.source.x}
                  y1={conn.source.y}
                  x2={conn.target.x}
                  y2={conn.target.y}
                  stroke={conn.isSatisfied ? "#ffffff" : branchCfg.color}
                  strokeWidth={conn.isSatisfied ? 1.5 : 1}
                  strokeOpacity={conn.isSatisfied ? 0.9 : 0.4}
                />
              </g>
            );
          })}

          {/* Node Render Loop */}
          {nodes.map((node) => {
            const coords = DEFAULT_NODE_COORDINATES[node.id] || { x: 500, y: 250 };
            const branchCfg = BRANCH_CONFIG[node.branch] || BRANCH_CONFIG.Focus;
            const state = getNodeState(node, availablePoints);
            const isHovered = hoveredNodeId === node.id;
            const isSelected = selectedNodeId === node.id;
            const isAllocating = allocatingNodeId === node.id;
            const isPulsing = feedbackNodeId === node.id;
            const isBranchDimmed = selectedBranch && selectedBranch !== node.branch;

            // Visual properties based on node state
            let strokeColor = branchCfg.color;
            let fillColor = "#09090b";
            let strokeWidth = 2;
            let nodeRadius = 24;
            let pulseEffect = false;

            if (state === "MAXED") {
              fillColor = branchCfg.color;
              strokeColor = "#ffffff";
              strokeWidth = 3;
              nodeRadius = 26;
            } else if (state === "AVAILABLE") {
              fillColor = "#18181b";
              strokeColor = branchCfg.color;
              strokeWidth = 2.5;
              pulseEffect = true;
            } else if (state === "INSUFFICIENT_POINTS") {
              fillColor = "#18181b";
              strokeColor = branchCfg.color;
              strokeWidth = 1.5;
            } else if (state === "LOCKED") {
              fillColor = "#09090b";
              strokeColor = "#52525b";
              strokeWidth = 1.5;
            }

            return (
              <g
                key={node.id}
                id={`talent-node-${node.id}`}
                tabIndex={0}
                role="button"
                aria-label={`${node.name}, Branch ${node.branch}, Rank ${node.current_rank} of ${node.max_rank}, Status ${state}`}
                aria-disabled={state === "LOCKED"}
                className="cursor-pointer focus:outline-none transition-opacity duration-300"
                opacity={isBranchDimmed ? 0.2 : 1}
                onClick={() => handleNodeClick(node)}
                onKeyDown={(e) => handleKeyDown(e, node)}
                onMouseEnter={() => setHoveredNodeId(node.id)}
                onMouseLeave={() => setHoveredNodeId(null)}
                onFocus={() => {
                  setHoveredNodeId(node.id);
                  setSelectedNodeId(node.id);
                }}
                onBlur={() => setHoveredNodeId(null)}
              >
                {/* Outer Ring Glow for Maxed or Available */}
                {(state === "MAXED" || state === "AVAILABLE" || isHovered || isSelected || isPulsing) && (
                  <circle
                    cx={coords.x}
                    cy={coords.y}
                    r={nodeRadius + (isPulsing ? 14 : isHovered ? 10 : 6)}
                    fill="none"
                    stroke={branchCfg.color}
                    strokeWidth={isPulsing ? 3 : 1.5}
                    strokeOpacity={isPulsing ? 0.9 : 0.4}
                    filter={`url(#glow-${filterId})`}
                    className={pulseEffect || isPulsing ? "animate-ping" : ""}
                  />
                )}

                {/* Main Node Circle */}
                <circle
                  cx={coords.x}
                  cy={coords.y}
                  r={nodeRadius}
                  fill={fillColor}
                  stroke={isHovered ? "#ffffff" : strokeColor}
                  strokeWidth={isHovered ? strokeWidth + 1.5 : strokeWidth}
                  className="transition-all duration-200"
                />

                {/* Node Center Icon / Glyph */}
                <text
                  x={coords.x}
                  y={coords.y + 5}
                  textAnchor="middle"
                  fontSize={state === "LOCKED" ? 14 : 16}
                  fill={state === "MAXED" ? "#000000" : state === "LOCKED" ? "#71717a" : "#ffffff"}
                  fontWeight="bold"
                  pointerEvents="none"
                  className="font-mono"
                >
                  {state === "LOCKED" ? "🔒" : branchCfg.icon}
                </text>

                {/* Rank Badge Indicator */}
                <g transform={`translate(${coords.x + 14}, ${coords.y - 14})`}>
                  <rect
                    x="-10"
                    y="-8"
                    width="20"
                    height="16"
                    rx="4"
                    fill={state === "MAXED" ? "#10b981" : state === "LOCKED" ? "#27272a" : branchCfg.color}
                    stroke="#ffffff"
                    strokeWidth="0.75"
                  />
                  <text
                    x="0"
                    y="4"
                    textAnchor="middle"
                    fontSize="9"
                    fill={state === "MAXED" || state === "LOCKED" ? "#ffffff" : "#000000"}
                    fontWeight="900"
                    fontFamily="monospace"
                    pointerEvents="none"
                  >
                    {node.current_rank}/{node.max_rank}
                  </text>
                </g>

                {/* Node Label Text */}
                <text
                  x={coords.x}
                  y={coords.y + nodeRadius + 18}
                  textAnchor="middle"
                  fontSize="12"
                  fill={isHovered || isSelected ? "#ffffff" : state === "LOCKED" ? "#71717a" : "#e4e4e7"}
                  fontWeight={isHovered || isSelected ? "bold" : "600"}
                  letterSpacing="0.05em"
                  pointerEvents="none"
                  className="uppercase font-mono"
                >
                  {node.name}
                </text>

                {/* Loading / Allocating Spinner Indicator */}
                {isAllocating && (
                  <circle
                    cx={coords.x}
                    cy={coords.y}
                    r={nodeRadius + 4}
                    fill="none"
                    stroke="#ffffff"
                    strokeWidth="2"
                    strokeDasharray="16 8"
                    className="animate-spin"
                  />
                )}
              </g>
            );
          })}
        </svg>

        {/* Hover / Selected Interactive Perk Tooltip HUD */}
        <AnimatePresence>
          {activeNode && (
            <motion.div
              initial={{ opacity: 0, y: 10, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 10, scale: 0.95 }}
              transition={{ duration: 0.15 }}
              className="absolute bottom-4 left-4 right-4 md:right-auto md:max-w-md bg-zinc-950/95 border border-white/20 p-4 rounded-xl shadow-2xl backdrop-blur-xl z-30"
              data-testid="talent-node-tooltip"
            >
              {(() => {
                const branchCfg = BRANCH_CONFIG[activeNode.branch] || BRANCH_CONFIG.Focus;
                const state = getNodeState(activeNode, availablePoints);
                const isAllocating = allocatingNodeId === activeNode.id;

                return (
                  <div>
                    <div className="flex items-start justify-between gap-4 border-b border-white/10 pb-2 mb-2">
                      <div className="flex items-center gap-2">
                        <span className="text-xl">{branchCfg.icon}</span>
                        <div>
                          <div
                            className="text-[10px] font-mono uppercase tracking-widest"
                            style={{ color: branchCfg.color }}
                          >
                            {activeNode.branch} · Tier {activeNode.tier}
                          </div>
                          <h4 className="text-sm font-bold uppercase tracking-wider text-white">
                            {activeNode.name}
                          </h4>
                        </div>
                      </div>
                      <div className="text-right">
                        <span
                          className={`inline-block px-2 py-0.5 rounded text-[10px] font-mono uppercase font-bold tracking-wider ${
                            state === "MAXED"
                              ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40"
                              : state === "AVAILABLE"
                              ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 animate-pulse"
                              : state === "LOCKED"
                              ? "bg-zinc-800 text-zinc-400 border border-zinc-700"
                              : "bg-amber-500/20 text-amber-300 border border-amber-500/40"
                          }`}
                        >
                          {state === "MAXED"
                            ? "Mastered"
                            : state === "AVAILABLE"
                            ? "Ready To Inscribe"
                            : state === "LOCKED"
                            ? "Locked"
                            : "Points Needed"}
                        </span>
                        <div className="text-[10px] font-mono text-white/50 mt-1">
                          Rank {activeNode.current_rank} of {activeNode.max_rank}
                        </div>
                      </div>
                    </div>

                    <p className="text-xs text-white/80 leading-relaxed mb-3">
                      {activeNode.description}
                    </p>

                    {/* Prerequisites section */}
                    {activeNode.prerequisites && activeNode.prerequisites.length > 0 && (
                      <div className="text-[10px] font-mono text-white/60 mb-3 bg-black/40 p-2 rounded border border-white/5">
                        <div className="uppercase tracking-wider text-white/40 mb-1">
                          Prerequisites:
                        </div>
                        <div className="flex flex-wrap gap-2">
                          {activeNode.prerequisites.map((p, idx) => {
                            const pId = typeof p === "string" ? p : p?.node_id;
                            const reqNode = nodeMap.get(pId);
                            const isMet = (reqNode?.current_rank ?? 0) >= 1;
                            return (
                              <span
                                key={idx}
                                className={`flex items-center gap-1 ${
                                  isMet ? "text-emerald-400" : "text-red-400"
                                }`}
                              >
                                <span>{isMet ? "✓" : "✗"}</span>
                                <span>{reqNode?.name || pId}</span>
                              </span>
                            );
                          })}
                        </div>
                      </div>
                    )}

                    {/* Allocation CTA Button */}
                    <div className="flex items-center justify-between gap-3 pt-1 border-t border-white/5">
                      <div className="text-[10px] font-mono text-white/40">
                        {state === "MAXED"
                          ? "Maximum rank reached."
                          : state === "LOCKED"
                          ? "Unlock prerequisite node to inscribe."
                          : availablePoints === 0
                          ? "Level up to gain talent points."
                          : "Costs 1 Talent Point"}
                      </div>
                      <button
                        type="button"
                        disabled={state !== "AVAILABLE" || isAllocating}
                        onClick={() => handleNodeClick(activeNode)}
                        data-testid="allocate-node-button"
                        className={`px-3 py-1.5 rounded-lg text-xs font-mono uppercase font-bold tracking-wider border transition-all ${
                          state === "AVAILABLE" && !isAllocating
                            ? "bg-cyan-500/20 border-cyan-400/60 text-cyan-200 hover:bg-cyan-400 hover:text-black shadow-[0_0_15px_rgba(0,212,255,0.4)]"
                            : "bg-zinc-900 border-white/5 text-white/30 cursor-not-allowed"
                        }`}
                      >
                        {isAllocating ? "Inscribing..." : state === "MAXED" ? "Max Rank" : "Inscribe (+1 Rank)"}
                      </button>
                    </div>
                  </div>
                );
              })()}
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Legend & Accessibility Instruction Footnote */}
      <div className="mt-4 flex flex-wrap items-center justify-between text-[11px] font-mono text-white/40 gap-2">
        <div className="flex items-center gap-4">
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 inline-block" /> Mastered
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 inline-block animate-pulse" /> Available
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-zinc-700 inline-block" /> Locked
          </span>
        </div>
        <div className="text-right">
          Use arrow keys to navigate nodes · Press Enter/Space to allocate
        </div>
      </div>
    </div>
  );
}
