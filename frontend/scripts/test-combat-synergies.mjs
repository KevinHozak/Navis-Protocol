import assert from 'node:assert/strict';
import vm from 'node:vm';
import { createRequire } from 'node:module';
import { readFile } from 'node:fs/promises';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

if (!vm.SourceTextModule) {
  const result = spawnSync(process.execPath, ['--experimental-vm-modules', fileURLToPath(import.meta.url)], { stdio: 'inherit' });
  if (result.error) throw result.error;
  process.exit(result.status ?? 1);
}

const require = createRequire(import.meta.url);
const React = require('react');
const { act, create } = require('react-test-renderer');
const swc = require('next/dist/build/swc');
await swc.loadBindings();
const source = await readFile(new URL('../src/components/CombatTheater.js', import.meta.url), 'utf8');
const compiled = swc.transformSync(source, { filename: 'CombatTheater.js', jsc: { parser: { syntax: 'ecmascript', jsx: true }, transform: { react: { runtime: 'automatic' } } }, module: { type: 'es6' } }).code;
let battle = { encounter: { ap_per_turn: 2, ap_available: 3, synergies: [
  { name: 'Groza', passives: { shield_percent: 20 } },
  { name: 'Lyra', passives: { ap_bonus: 1 } },
  { name: 'Rita', passives: { kinetic_percent: 15 } },
], enemies: [] } };
const context = vm.createContext({ console, window: { addEventListener() {}, removeEventListener() {} } });
const mod = new vm.SourceTextModule(compiled, { context });
await mod.link(async name => {
  let values;
  if (name === 'react') values = { default: React, useState: React.useState, useEffect: React.useEffect };
  else if (name === 'react/jsx-runtime') values = require('react/jsx-runtime');
  else if (name === 'framer-motion') values = { motion: { div: 'div' } };
  else if (name === './VaultAssetImage') values = { default: props => React.createElement('img', { alt: props.alt }) };
  else if (name === '../lib/desktopApi') values = {
    apiFetch: async path => ({ ok: true, json: async () => path === '/api/battle/state' ? battle : { logs: [] } }),
    apiUrl: path => path, vaultAssetUrl: path => path,
  };
  else throw new Error(`Unexpected dependency ${name}`);
  const mock = new vm.SyntheticModule(Object.keys(values), function () {
    for (const [key, value] of Object.entries(values)) this.setExport(key, value);
  }, { context });
  await mock.link(() => {});
  return mock;
});
await mod.evaluate();
let renderer;
const status = { squad: ['Groza', 'Lyra', 'Rita', 'Reserve'].map(name => ({ name })) };
await act(async () => { renderer = create(React.createElement(mod.namespace.default, { status })); });
for (const name of ['Groza', 'Lyra', 'Rita']) {
  const aura = renderer.root.findByProps({ 'aria-label': `${name} active synergy` });
  assert.equal(aura.props.role, 'status');
}
assert.equal(renderer.root.findAllByProps({ 'aria-label': 'Reserve active synergy' }).length, 0);
assert.equal(renderer.root.findAllByProps({ 'aria-label': 'Keeper active synergy' }).length, 0);
const rendered = JSON.stringify(renderer.toJSON());
for (const label of ['+20% Shield', '+1 AP per turn', '+15% Kinetic damage']) assert.ok(rendered.includes(label));
assert.ok(renderer.root.findAllByType('p').some(p => p.children.join('').includes('AP 3')));
assert.equal(renderer.root.findAll(node => node.props.animate?.boxShadow === '0 0 24px rgba(255,77,77,0.5)').length, 3);
battle = { encounter: { ap_available: 2, synergies: [], enemies: [] } };
await act(async () => { renderer.update(React.createElement(mod.namespace.default, { status: { squad: [] } })); });
assert.equal(renderer.root.findAll(node => node.props['aria-label']?.endsWith('active synergy')).length, 0);
assert.ok(renderer.root.findAllByType('p').some(p => p.children.join('').includes('AP 2')));
await act(async () => renderer.unmount());
console.log('Combat synergy portraits, passive labels, AP budget and recall refresh passed.');
