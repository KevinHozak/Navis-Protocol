import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';

if (!vm.SourceTextModule) {
  const child = spawnSync(process.execPath, ['--experimental-vm-modules', fileURLToPath(import.meta.url)], { stdio: 'inherit' });
  process.exit(child.status ?? 1);
}
const require = createRequire(new URL('../package.json', import.meta.url));
const React = require('react'), Renderer = require('react-test-renderer');
const swc = require('next/dist/build/swc');
await swc.loadBindings();
const source = await readFile(new URL('../src/components/EncounterSetup.js', import.meta.url), 'utf8');
const code = swc.transformSync(source, { filename: 'EncounterSetup.js', jsc: { parser: { syntax: 'ecmascript', jsx: true }, transform: { react: { runtime: 'classic' } } }, module: { type: 'es6' } }).code;
const calls = [], responses = [];
const context = vm.createContext({ console });
async function synthetic(values) {
  const mod = new vm.SyntheticModule(Object.keys(values), function () { for (const [key, value] of Object.entries(values)) this.setExport(key, value); }, { context });
  await mod.link(() => {}); return mod;
}
const module = new vm.SourceTextModule(code, { context });
await module.link(name => {
  if (name === 'react') return synthetic({ default: React, useState: React.useState, useEffect: React.useEffect, useRef: React.useRef });
  if (name === 'framer-motion') return synthetic({ motion: { section: 'section' } });
  return synthetic({ apiFetch: async (path, options = {}) => {
    calls.push({ path, body: options.body && JSON.parse(options.body) });
    assert.ok(responses.length, `Unexpected call ${path}`);
    const response = responses.shift();
    return { ok: !response.detail, json: async () => response };
  } });
});
await module.evaluate();
const Component = module.namespace.default;
const catalog = { blocked: null, candidates: [{ enemy_id: 'Sentinel', name: 'Sentinel' }, { enemy_id: 'Missing', name: 'Missing', unavailable: 'Missing HP' }] };
const review = { preview_token: 'reviewed-state', encounter: { enemies: [{ id: 'Sentinel', hp: 20, attack: 4, affinity: 'Physical', intent_pattern: ['Charge', 'Strike'], vulnerabilities: { Digital: 2 } }] } };
let tree;
responses.push(catalog);
await Renderer.act(async () => { tree = Renderer.create(React.createElement(Component, { battle: null })); });
const button = text => tree.root.findAllByType('button').find(node => node.children.join('').includes(text));
assert.ok(button('Preview').props.disabled);
assert.equal(tree.root.findByProps({ value: 'Missing', disabled: true }).type, 'option');
await Renderer.act(async () => tree.root.findByType('select').props.onChange({ target: { value: 'Sentinel' } }));
responses.push(review);
await Renderer.act(async () => button('Preview').props.onClick());
assert.equal(calls.length, 2);
assert.equal(calls[1].path, '/api/battle/encounter/preview');
assert.ok(button('Confirm and start'));
await Renderer.act(async () => button('Dismiss').props.onClick());
assert.equal(calls.length, 2, 'Dismiss never creates an encounter');
responses.push(review);
await Renderer.act(async () => button('Preview').props.onClick());
responses.push({ detail: 'The preview changed. Review again.' });
await Renderer.act(async () => button('Confirm and start').props.onClick());
assert.match(tree.root.findByProps({ role: 'alert' }).children.join(''), /preview changed/);
assert.deepEqual(calls.at(-1).body, { enemy_id: 'Sentinel', preview_token: 'reviewed-state' });
responses.push({ encounter: review.encounter });
await Renderer.act(async () => { const confirm = button('Confirm and start'); confirm.props.onClick(); confirm.props.onClick(); });
assert.equal(calls.length, 5, 'Double confirmation dispatches only once');
assert.match(tree.root.findByProps({ role: 'status' }).children.join(''), /started/);
responses.push({ ...catalog, blocked: 'Finish pending combat recovery.' });
await Renderer.act(async () => tree.update(React.createElement(Component, { battle: {} })));
assert.ok(tree.root.findByType('select').props.disabled);
assert.ok(button('Preview').props.disabled);
await Renderer.act(async () => tree.unmount());
assert.equal(responses.length, 0);
console.log('Encounter selection, review, dismissal, stale errors, double-submit and recovery UI passed.');
