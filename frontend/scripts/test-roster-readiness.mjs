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
const source = await readFile(new URL('../src/components/EntityRail.js', import.meta.url), 'utf8');
const code = swc.transformSync(source, {
  filename: 'EntityRail.js', jsc: { parser: { syntax: 'ecmascript', jsx: true }, transform: { react: { runtime: 'automatic' } } }, module: { type: 'es6' },
}).code;
// Use real Framer Motion with no DOM/animation driver: ready data must not wait
// for an exit callback, including in suspended/background rendering contexts.
const context = vm.createContext({ console, setTimeout, clearTimeout });
const mod = new vm.SourceTextModule(code, { context });
await mod.link(async name => {
  const values = name === 'react' ? { default: React, ...React }
    : name === 'react/jsx-runtime' ? require('react/jsx-runtime')
    : name === 'framer-motion' ? require('framer-motion')
    : name === './JournalCalendar' ? { default: () => null } : null;
  if (!values) throw new Error(`Unexpected import ${name}`);
  const dep = new vm.SyntheticModule(Object.keys(values), function () { for (const [k, v] of Object.entries(values)) this.setExport(k, v); }, { context });
  await dep.link(() => {}); await dep.evaluate(); return dep;
});
await mod.evaluate();
const Rail = mod.namespace.default;
let tree;
let selected;
let retries = 0;
const entity = { id: 'XP', name: 'XP Manifold', type: 'virtual' };
const props = { activeSector: 'PARTY', entities: [], onSelect: value => { selected = value; }, onRetry: () => { retries++; } };
const render = async patch => act(async () => { tree ? tree.update(React.createElement(Rail, { ...props, ...patch })) : tree = create(React.createElement(Rail, { ...props, ...patch })); });
await render({ loading: true });
assert.match(JSON.stringify(tree.toJSON()), /Uplink synchronizing/);
await render({ loading: false, entities: [entity] });
let button = tree.root.findAllByType('button').find(b => b.props.title === 'XP Manifold');
assert.ok(button, 'Ready roster must render without an exit-animation callback');
await act(async () => button.props.onClick());
assert.equal(selected.id, 'XP');
await render({ loading: true, activeSector: 'COMBAT' });
await render({ loading: false, activeSector: 'COMBAT', entities: [{ id: 'BATTLE_FIELD', name: 'Battle Field', type: 'virtual' }] });
assert.ok(tree.root.findAllByType('button').some(b => b.props.title === 'Battle Field'));
assert.doesNotMatch(JSON.stringify(tree.toJSON()), /Uplink synchronizing|XP Manifold/);
await render({ loading: true });
await render({ loading: false, entityLoadError: { message: 'Synthetic request failed' } });
assert.match(JSON.stringify(tree.toJSON()), /Synthetic request failed/);
await act(async () => tree.root.findAllByType('button').find(b => b.props.onClick === props.onRetry).props.onClick());
assert.equal(retries, 1);
await render({ loading: true });
await render({ loading: false, entities: [] });
assert.match(JSON.stringify(tree.toJSON()), /No items found/);
assert.doesNotMatch(JSON.stringify(tree.toJSON()), /Uplink synchronizing/);
await act(async () => tree.unmount());
console.log('Roster ready, interrupted navigation, error/retry and empty states render without animation completion.');
