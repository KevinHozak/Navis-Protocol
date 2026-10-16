"use client";

import { useCallback, useEffect, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import { resolveMapTelemetry } from '@/lib/mapTelemetry.mjs';

export default function PhaserMapWrapper({ currentRealm, onSelectRealm, status }) {
  const [clock, setClock] = useState(() => Date.now());
  const telemetry = resolveMapTelemetry(status, currentRealm, clock);
  const telemetryRef = useRef(telemetry);
  telemetryRef.current = telemetry;
  useEffect(() => {
    const timer = setInterval(() => setClock(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);
  useEffect(() => {
    const scene = gameRef.current?.scene.getScene('MapScene');
    if (scene?.sys.isActive()) scene.renderTelemetry(telemetryRef.current);
  }, [status, currentRealm, clock]);
  const gameRef = useRef(null);
  const containerRef = useRef(null);
  const [nodes, setNodes] = useState([]);
  const [selectedNode, setSelectedNode] = useState('');
  const [mapStatus, setMapStatus] = useState({ kind: 'loading', message: 'Loading Overworld data and image…' });
  const handleSceneNodeSelected = useCallback((name) => {
    setSelectedNode(name);
    onSelectRealm?.(name);
  }, [onSelectRealm]);

  useEffect(() => {
    setNodes([]);
    setSelectedNode('');
    setMapStatus({ kind: 'loading', message: `Loading ${currentRealm} Overworld data and image…` });
    let isMounted = true;
    let game;
    let MapScene;

    const initPhaser = async () => {
      const Phaser = (await import('phaser')).default;
      MapScene = (await import('@/lib/MapScene')).default;

      if (!isMounted || !containerRef.current) return;

      const config = {
        type: Phaser.WEBGL,
        parent: containerRef.current,
        width: 1024,
        height: 576,
        backgroundColor: '#09090b',
        scene: [MapScene],
        scale: {
          mode: Phaser.Scale.FIT,
          autoCenter: Phaser.Scale.CENTER_BOTH
        }
      };

      config.callbacks = { preBoot: (instance) => {
        instance.registry.set('currentRealm', currentRealm);
        instance.registry.set('getMapTelemetry', () => telemetryRef.current);
        instance.registry.set('onMapNodesLoaded', (loaded) => { if (isMounted) setNodes(loaded); });
        instance.registry.set('onMapStatusChanged', (status) => { if (isMounted) setMapStatus(status); });
        instance.registry.set('onMapNodeSelected', (name) => { if (isMounted) handleSceneNodeSelected(name); });
      } };
      game = new Phaser.Game(config);
      game.registry.set('currentRealm', currentRealm);
      game.registry.set('onSelectRealm', handleSceneNodeSelected);


      gameRef.current = game;
    };

    initPhaser();

    return () => {
      isMounted = false;
      if (gameRef.current) {
        gameRef.current.destroy(true);
        gameRef.current = null;
      }
    };
  }, [currentRealm, handleSceneNodeSelected]);

  const retryMapLoad = () => {
    const scene = gameRef.current?.scene.getScene('MapScene');
    if (!scene) return;
    setMapStatus({ kind: 'loading', message: `Retrying ${currentRealm} Overworld assets…` });
    setNodes([]);
    setSelectedNode('');
    scene.scene.restart();
  };

  return (
    <div className="w-full h-full flex flex-col">
      <div
        ref={containerRef}
        className="flex-1 min-h-0 overflow-hidden rounded-lg border border-white/10 shadow-2xl relative"
      >
      {mapStatus.kind !== 'ready' && (
        <motion.div
          key={`${currentRealm}:${mapStatus.kind}:${mapStatus.message}`}
          initial={{ opacity: 0, y: 5 }}
          animate={{ opacity: 1, y: 0 }}
          className="absolute top-14 left-4 right-4 z-10 max-w-xl rounded border border-white/10 bg-zinc-950/90 p-3 text-xs font-mono text-white/80 backdrop-blur-md"
          role="status"
          aria-live="polite"
        >
          <p>{mapStatus.message}</p>
          {mapStatus.kind !== 'loading' && (
            <button
              type="button"
              onClick={retryMapLoad}
              className="mt-2 rounded border border-accent/50 px-3 py-1.5 text-accent transition-colors hover:bg-accent/10 focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
            >
              Retry map loading
            </button>
          )}
        </motion.div>
      )}
      <div className="absolute top-4 left-4 z-10 bg-black/60 backdrop-blur-md px-3 py-1.5 rounded border border-accent/30 text-accent font-mono text-[10px] uppercase tracking-widest flex items-center gap-2 pointer-events-none">
        <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
        Tactical View Active
      </div>
      <div className="absolute bottom-4 left-4 z-10 text-white/30 font-mono text-[9px] uppercase tracking-widest pointer-events-none">
        Select a node to open Moongate
      </div>
      </div>
      <div className="border border-white/10 bg-zinc-950/90 backdrop-blur-md p-3" aria-label="Map marker legend and position details">
        <p className="text-xs text-white/60 mb-2">Live positions · expire after 5 minutes</p>
        <ul className="flex flex-wrap gap-x-5 gap-y-2 text-xs font-mono">
          {telemetry.details.map((detail) => <li key={detail.kind}>
            <span style={{ color: detail.color }}>{detail.label}</span>
            <span className="text-white/60"> — {detail.text}</span>
          </li>)}
        </ul>
      </div>
      <div className="shrink-0 border-x border-b border-white/10 bg-zinc-950/90 p-3" aria-label="Overworld realm destinations">
        <p className="mb-2 text-[10px] font-mono uppercase tracking-widest text-white/50">Select a realm destination</p>
        {nodes.length ? (
          <ul className="flex flex-wrap gap-2">
            {nodes.map((node) => (
              <li key={`${node.name}:${node.x}:${node.y}`}>
                <button
                  type="button"
                  aria-pressed={selectedNode === node.name}
                  onClick={() => {
                    setSelectedNode(node.name);
                    onSelectRealm?.(node.name);
                  }}
                  className={`rounded border px-3 py-2 text-xs font-mono transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent ${selectedNode === node.name ? 'border-accent bg-accent/10 text-accent' : 'border-white/15 text-white/80 hover:border-accent hover:text-accent'}`}
                >
                  {node.name}
                </button>
              </li>
            ))}
          </ul>
        ) : <p className="text-xs text-white/40" role="status">Destinations appear here when valid map nodes are available.</p>}
      </div>
    </div>
  );
}
