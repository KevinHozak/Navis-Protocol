import assert from 'node:assert/strict';
import vm from 'node:vm';
import { readFile } from 'node:fs/promises';
import React from 'react';
import TestRenderer, { act } from 'react-test-renderer';
import swc from 'next/dist/build/swc/index.js';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

if (!vm.SourceTextModule) {
  const result = spawnSync(process.execPath, ['--experimental-vm-modules', fileURLToPath(import.meta.url)], { stdio: 'inherit' });
  if (result.error) throw result.error;
  process.exit(result.status ?? 1);
}

await swc.loadBindings();
const context = vm.createContext({ console, React });

async function loadComponent(filename, imports) {
  const source = await readFile(new URL(`../src/components/${filename}`, import.meta.url), 'utf8');
  const code = swc.transformSync(source, {
    filename,
    jsc: { parser: { syntax: 'ecmascript', jsx: true }, transform: { react: { runtime: 'classic' } } },
    module: { type: 'es6' },
  }).code;
  const component = new vm.SourceTextModule(code, { context });
  await component.link(async (specifier) => {
    const values = imports[specifier];
    assert.ok(values, `Unexpected import ${specifier} from ${filename}`);
    const module = new vm.SyntheticModule(Object.keys(values), function () {
      for (const [key, value] of Object.entries(values)) this.setExport(key, value);
    }, { context });
    await module.link(() => { throw new Error('Unexpected nested import'); });
    return module;
  });
  await component.evaluate();
  return component.namespace.default;
}

const EntityRail = await loadComponent('EntityRail.js', {
  react: { default: React, useEffect: React.useEffect, useState: React.useState },
  'framer-motion': { motion: { div: 'div' }, AnimatePresence: 'div' },
  './JournalCalendar': { default: () => null },
});
const SectorRail = await loadComponent('SectorRail.js', {
  react: { default: React },
});

const companions = [
  { id: 'Companions/2B', name: '2B', type: 'directory' },
  { id: 'Companions/A2', name: 'A2', type: 'directory' },
];
let selectedId = null;
let tree;

await act(async () => {
  tree = TestRenderer.create(React.createElement(EntityRail, {
    entities: companions,
    activeEntityId: companions[0].id,
    onSelect: (entity) => { selectedId = entity.id; },
    activeSector: 'COMPANIONS',
  }));
});

assert.equal(tree.root.findAllByType('button').length, 2, 'both synthetic companions remain selectable');
assert.equal(tree.root.findAllByProps({ 'aria-current': 'true' })[0].props.title, '2B', 'the active dossier is identified');
assert.match(tree.root.findByType('aside').props.className, /h-28/, 'Codex roster receives a bounded narrow layout');

await act(async () => tree.root.findAllByType('button')[1].props.onClick());
assert.equal(selectedId, 'Companions/A2', 'selecting another roster entry opens that dossier');

await act(async () => tree.root.findByType('input').props.onChange({ target: { value: '2B' } }));
assert.deepEqual(tree.root.findAllByType('button').map((button) => button.props.title), ['2B'], 'filter narrows the roster');

await act(async () => tree.update(React.createElement(EntityRail, {
  entities: [{ id: 'Residents/Tali', name: 'Tali', type: 'directory' }],
  activeEntityId: 'Residents/Tali',
  onSelect: (entity) => { selectedId = entity.id; },
  activeSector: 'RESIDENTS',
})));
assert.deepEqual(tree.root.findAllByType('button').map((button) => button.props.title), ['Tali'], 'area switching replaces stale entities and clears the prior filter');

await act(async () => tree.update(React.createElement(EntityRail, {
  entities: [], activeEntityId: null, onSelect() {}, activeSector: 'ANTAGONISTS', loading: true,
})));
assert.match(JSON.stringify(tree.toJSON()), /Uplink synchronizing/, 'loading state is visible');

await act(async () => tree.update(React.createElement(EntityRail, {
  entities: [], activeEntityId: null, onSelect() {}, activeSector: 'BEASTS',
})));
assert.match(JSON.stringify(tree.toJSON()), /No characters available/, 'empty roster state is visible');
await act(async () => tree.unmount());

let sectorTree;
await act(async () => {
  sectorTree = TestRenderer.create(React.createElement(SectorRail, { sectors: [], activeSector: 'COMPANIONS', onSelect() {}, compact: true }));
});
assert.match(sectorTree.root.findByType('aside').props.className, /h-12/, 'Codex area navigation uses the compact layout');
await act(async () => sectorTree.update(React.createElement(SectorRail, { sectors: [], activeSector: 'SYNTHESIS_LAB', onSelect() {} })));
assert.match(sectorTree.root.findByType('aside').props.className, /w-14/, 'non-Codex area navigation retains the desktop rail layout');
await act(async () => sectorTree.unmount());

const pageSource = await readFile(new URL('../src/app/page.js', import.meta.url), 'utf8');
assert.match(pageSource, /isCodexRosterSector \? 'flex-col md:flex-row' : 'flex-row'/, 'only Codex sectors stack their rails at narrow widths');
console.log('Codex synthetic roster selection, filtering, area switching, loading/empty states, and non-Codex layout checks passed.');
