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
const context = vm.createContext({ console, React, AbortController });
let requests = 0;
const payload = { history_note: 'Synthetic history', beasts: [{ name: 'Wyrm', affinity: 'Void', vulnerabilities: { Digital: 2 }, encounters: 2, wins: 1, defeats: 1, win_rate: 50, defeat_rate: 50, active: 0, slayings: 1, highest_turn_damage: 7, trophies: ['First Slaying'] }] };
const source = await readFile(new URL('../src/components/CodexBestiaryView.js', import.meta.url), 'utf8');
const code = swc.transformSync(source, { filename: 'CodexBestiaryView.js', jsc: { parser: { syntax: 'ecmascript', jsx: true }, transform: { react: { runtime: 'classic' } } }, module: { type: 'es6' } }).code;
const component = new vm.SourceTextModule(code, { context });
const linker = async name => {
  if (name === './HolocronEvidence') {
    const evidenceSource = await readFile(new URL('../src/components/HolocronEvidence.js', import.meta.url), 'utf8');
    const evidenceCode = swc.transformSync(evidenceSource, { filename: 'HolocronEvidence.js', jsc: { parser: { syntax: 'ecmascript', jsx: true }, transform: { react: { runtime: 'classic' } } }, module: { type: 'es6' } }).code;
    const evidence = new vm.SourceTextModule(evidenceCode, { context });
    await evidence.link(linker); return evidence;
  }
  const values = name === 'react' ? { default: React, useState: React.useState, useRef: React.useRef, useEffect: React.useEffect }
    : name === 'framer-motion' ? { motion: { article: 'article', div: 'div' } }
      : { apiFetch: async path => {
        if (path.includes('/holocron/')) return { ok: true, json: async () => path.endsWith('/manifest') ? [] : { summary: {}, combat: { beasts_neutralized: [{ name: 'Wyrm' }] } } };
        assert.equal(path, '/api/battle/bestiary'); requests++; return requests === 1 ? { ok: false, status: 503 } : { ok: true, json: async () => payload };
      } };
  const mod = new vm.SyntheticModule(Object.keys(values), function () { for (const [key, value] of Object.entries(values)) this.setExport(key, value); }, { context });
  await mod.link(() => {}); return mod;
};
await component.link(linker);
await component.evaluate();
let tree;
const scrolled = [];
await act(async () => { tree = TestRenderer.create(React.createElement(component.namespace.default, { selectedBeast: 'Wyrm' }), { createNodeMock: () => ({ scrollIntoView: options => scrolled.push(options) }) }); });
assert.equal(tree.root.findByProps({ role: 'alert' }).children[0], 'Bestiary unavailable (503)');
await act(async () => tree.root.findByType('button').props.onClick());
const rendered = JSON.stringify(tree.toJSON());
for (const text of ['Wyrm', 'Void', 'Digital ×2', '50% / 50%', 'First Slaying', 'Best turn damage']) assert.ok(rendered.includes(text), text);
assert.ok(scrolled.length);
await act(async () => tree.update(React.createElement(component.namespace.default, { selectedBeast: 'Missing' })));
assert.ok(JSON.stringify(tree.toJSON()).includes('No catalog or recorded history for '));
await act(async () => tree.unmount());
console.log('Bestiary rendering, failure/retry, selection and missing entry passed');

const holocronSource = await readFile(new URL('../src/components/WeeklyHolocronView.js', import.meta.url), 'utf8');
const holocronCode = swc.transformSync(holocronSource, { filename: 'WeeklyHolocronView.js', jsc: { parser: { syntax: 'ecmascript', jsx: true }, transform: { react: { runtime: 'classic' } } }, module: { type: 'es6' } }).code;
const holocron = new vm.SourceTextModule(holocronCode, { context });
await holocron.link(linker); await holocron.evaluate();
let opened;
await act(async () => { tree = TestRenderer.create(React.createElement(holocron.namespace.default, { onOpenBestiary: name => { opened = name; } })); });
await act(async () => tree.root.findByProps({ 'aria-label': 'Open Wyrm in Bestiary' }).props.onClick());
assert.equal(opened, 'Wyrm');
await act(async () => tree.unmount());
console.log('Cached Holocron threat deep-link callback passed');
