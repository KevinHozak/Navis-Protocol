import assert from 'node:assert/strict';
import vm from 'node:vm';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { readFile } from 'node:fs/promises';
import React from 'react';
import TestRenderer, { act } from 'react-test-renderer';
import swc from 'next/dist/build/swc/index.js';
import { horizonRoadmap } from '../src/lib/horizonRoadmap.mjs';
if (!vm.SourceTextModule) {
  const result = spawnSync(process.execPath, ['--experimental-vm-modules', fileURLToPath(import.meta.url)], { stdio: 'inherit' });
  if (result.error) throw result.error;
  process.exit(result.status ?? 1);
}
await swc.loadBindings();
const source = await readFile(new URL('../src/components/HorizonRoadmap.jsx', import.meta.url), 'utf8');
const compiled = swc.transformSync(source, { filename: 'HorizonRoadmap.jsx', jsc: { parser: { syntax: 'ecmascript', jsx: true }, transform: { react: { runtime: 'automatic' } } }, module: { type: 'es6' } }).code;
const context = vm.createContext({ console });
const mod = new vm.SourceTextModule(compiled, { context });
await mod.link(async name => {
  let values;
  if (name === 'react') values = { useState: React.useState };
  else if (name === 'react/jsx-runtime') values = await import('react/jsx-runtime');
  else if (name === 'framer-motion') values = { motion: { table: 'table' }, useReducedMotion: () => true };
  else if (name === '../lib/horizonRoadmap.mjs') values = { horizonRoadmap };
  else throw new Error(`Unexpected dependency: ${name}`);
  const mock = new vm.SyntheticModule(Object.keys(values), function () { for (const [key, value] of Object.entries(values)) this.setExport(key, value); }, { context });
  await mock.link(() => {});
  return mock;
});
await mod.evaluate();
let renderer;
act(() => { renderer = TestRenderer.create(React.createElement(mod.namespace.default)); });
const tabs = () => renderer.root.findAllByProps({ role: 'tab' });
for (const [index, [key, view]] of Object.entries(horizonRoadmap).entries()) {
  act(() => tabs()[index].props.onClick());
  assert.equal(tabs()[index].props['aria-selected'], true);
  assert.equal(renderer.root.findByProps({ role: 'tabpanel' }).props['aria-labelledby'], `horizon-tab-${key}`);
  const rows = renderer.root.findByType('tbody').findAllByType('tr');
  assert.equal(rows.length, 6);
  assert.deepEqual(rows.map(row => row.findByType('th').children[0].children[0]), ['Personal', 'Work', 'Home', 'Health', 'Relationships', 'Learning']);
  rows.forEach((row, i) => {
    assert.equal(row.findAllByType('td').length, 4);
    view.lanes[i].cells.forEach(text => assert.ok(JSON.stringify(row.findAllByType('p').map(p => p.children)).includes(text)));
  });
}
let focused = -1;
act(() => tabs()[3].props.onKeyDown({ key: 'ArrowRight', preventDefault() {}, currentTarget: { parentElement: { children: Array.from({ length: 4 }, (_, i) => ({ focus() { focused = i; } })) } } }));
assert.equal(focused, 0);
assert.equal(tabs()[0].props['aria-selected'], true);
assert.match(JSON.stringify(renderer.toJSON()), /not saved/);
assert.equal(renderer.root.findByProps({ 'aria-label': 'Horizon roadmap board' }).props.tabIndex, 0);
act(() => renderer.unmount());
console.log('Horizon tabs, six complete lanes, examples, and keyboard navigation passed.');

const page = await readFile(new URL('../src/app/page.js', import.meta.url), 'utf8');
const ribbon = await readFile(new URL('../src/components/SovereignRibbon.js', import.meta.url), 'utf8');
assert.match(page, /currentSectors = activePillar === 'COMMAND'/);
assert.match(page, /id: 'HORIZON_ROADMAP', label: 'Horizon Roadmap'/);
assert.match(page, /activeSector === 'HORIZON_ROADMAP'\s*\? <HorizonRoadmap/);
assert.match(page, /if \(activeSector === 'HORIZON_ROADMAP'( \|\| activeSector === 'HOLOCRON')?\) \{\s*setLoadingEntities\(false\);\s*return;/);
assert.match(page, /navItems=\{pillars\}/);
assert.ok(!ribbon.includes('HORIZON'));
console.log('Roadmap is a local Command sector with no top-level navigation entry.');
