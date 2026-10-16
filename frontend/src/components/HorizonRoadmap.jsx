"use client";

import { useState } from 'react';
import { motion, useReducedMotion } from 'framer-motion';
import { horizonRoadmap } from '../lib/horizonRoadmap.mjs';

const horizons = ['year', 'quarter', 'month', 'week'];

export default function HorizonRoadmap() {
  const [horizon, setHorizon] = useState('year');
  const reduceMotion = useReducedMotion();
  const view = horizonRoadmap[horizon];

  function handleTabKey(event, index) {
    let next;
    if (event.key === 'ArrowRight') next = (index + 1) % horizons.length;
    if (event.key === 'ArrowLeft') next = (index + horizons.length - 1) % horizons.length;
    if (event.key === 'Home') next = 0;
    if (event.key === 'End') next = horizons.length - 1;
    if (next === undefined) return;
    event.preventDefault();
    setHorizon(horizons[next]);
    event.currentTarget.parentElement.children[next].focus();
  }

  return (
    <section className="min-w-0 flex-1 overflow-y-auto text-white" aria-labelledby="horizon-title">
      <div className="mx-auto max-w-[1480px] space-y-5 p-4 md:p-8">
        <header>
          <p className="text-xs font-bold uppercase tracking-widest text-cyan-300">Planning surface</p>
          <h1 id="horizon-title" className="mt-2 text-3xl font-bold md:text-4xl">Horizon Roadmap</h1>
          <p className="mt-3 max-w-3xl text-sm text-zinc-300">Zoom from annual direction into this week&apos;s small commitments across six life areas.</p>
          <p className="mt-3 rounded-xl border border-cyan-400/20 bg-cyan-400/5 p-3 text-sm text-cyan-100">Example planning content. These entries are illustrative, are not saved, and are not connected to your Vault.</p>
        </header>
        <div role="tablist" aria-label="Planning horizon" className="flex w-fit gap-1 rounded-xl border border-white/10 bg-zinc-950/90 p-1 backdrop-blur-md">
          {horizons.map((key, index) => (
            <button key={key} id={`horizon-tab-${key}`} role="tab" aria-selected={horizon === key} aria-controls="horizon-panel" tabIndex={horizon === key ? 0 : -1} onClick={() => setHorizon(key)} onKeyDown={(event) => handleTabKey(event, index)} className={`rounded-lg px-3 py-2 text-sm font-bold capitalize transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan-300 sm:px-5 ${horizon === key ? 'bg-cyan-400 text-zinc-950' : 'text-zinc-300 hover:bg-white/10'}`}>
              {key}
            </button>
          ))}
        </div>
        <div id="horizon-panel" role="tabpanel" aria-labelledby={`horizon-tab-${horizon}`}>
          <p className="mb-3 text-sm text-zinc-300">{view.note}</p>
          <p id="horizon-scroll-hint" className="mb-3 text-xs text-zinc-400">Scroll horizontally to explore every column.</p>
          <div role="region" aria-label="Horizon roadmap board" aria-describedby="horizon-scroll-hint" tabIndex={0} className="overflow-x-auto rounded-2xl border border-white/10 bg-zinc-950/90 shadow-xl backdrop-blur-md focus-visible:outline focus-visible:outline-2 focus-visible:outline-cyan-300">
            <motion.table key={horizon} initial={reduceMotion ? false : { opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.15 }} className="w-full min-w-[1040px] table-fixed border-collapse text-left">
              <caption className="sr-only">{horizon} planning examples by life area</caption>
              <thead className="bg-zinc-900">
                <tr><th scope="col" className="md:sticky md:left-0 z-20 w-40 bg-zinc-900 p-4 text-xs uppercase tracking-wider text-zinc-300">Life area</th>{view.columns.map(column => <th key={column} scope="col" className="p-4 text-xs uppercase tracking-wider text-zinc-200">{column}</th>)}</tr>
              </thead>
              <tbody>
                {view.lanes.map(lane => (
                  <tr key={lane.area} className="border-t border-white/10">
                    <th scope="row" className="md:sticky md:left-0 z-10 bg-zinc-950 p-4 align-top"><span className="block border-l-4 pl-3 text-sm font-bold" style={{ borderColor: lane.color }}>{lane.area}</span></th>
                    {lane.cells.map((text, index) => (
                      <td key={index} className="p-3 align-top">
                        <article className="min-h-28 rounded-xl border border-white/10 bg-zinc-900/90 p-4">
                          <div aria-hidden="true" className="mb-3 h-1 w-8 rounded" style={{ backgroundColor: lane.color }} />
                          <p className="text-sm leading-relaxed">{text}</p>
                          <p className="mt-3 text-xs text-zinc-400">{view.columns[index]}</p>
                        </article>
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </motion.table>
          </div>
        </div>
      </div>
    </section>
  );
}
