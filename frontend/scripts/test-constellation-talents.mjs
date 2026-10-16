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

// Test fixture for talent constellation state
const mockTalentState = {
  entity_id: 'keeper',
  level: 3,
  current_level: 3,
  total_xp: 3500,
  total_allocated_ranks: 1,
  available_points: 2,
  nodes: [
    {
      id: 'focus_deep_work',
      branch: 'Focus',
      tier: 1,
      prerequisites: [],
      max_rank: 3,
      perk_key: 'focus_deep_work_multiplier',
      name: 'Deep Work Flow',
      description: 'Enhances focus depth and execution endurance.',
      current_rank: 1,
      unlocked: true,
    },
    {
      id: 'focus_clarity',
      branch: 'Focus',
      tier: 2,
      prerequisites: ['focus_deep_work'],
      max_rank: 2,
      perk_key: 'focus_stamina_boost',
      name: 'Mindful Clarity',
      description: 'Reduces cognitive fatigue and extends stamina.',
      current_rank: 0,
      unlocked: true,
    },
    {
      id: 'martial_momentum',
      branch: 'Martial',
      tier: 1,
      prerequisites: [],
      max_rank: 3,
      perk_key: 'high_velocity_xp_bonus',
      name: 'High-Velocity Striker',
      description: '+10% XP yield on High-Velocity Front combat operations.',
      current_rank: 0,
      unlocked: true,
    },
    {
      id: 'martial_tenacity',
      branch: 'Martial',
      tier: 2,
      prerequisites: ['martial_momentum'],
      max_rank: 2,
      perk_key: 'reduced_rollover_penalty',
      name: 'Unyielding Tenacity',
      description: 'Mitigates friction and rollover penalties.',
      current_rank: 0,
      unlocked: false,
    },
  ],
};

const source = await readFile(new URL('../src/components/ConstellationTalentTree.jsx', import.meta.url), 'utf8');
const compiled = swc.transformSync(source, {
  filename: 'ConstellationTalentTree.jsx',
  jsc: { parser: { syntax: 'ecmascript', jsx: true }, transform: { react: { runtime: 'automatic' } } },
  module: { type: 'es6' },
}).code;

const context = vm.createContext({
  console,
  setTimeout,
  clearTimeout,
  document: {
    getElementById: (id) => ({
      focus: () => {},
      id,
    }),
  },
});

const sfxCalls = [];
const mod = new vm.SourceTextModule(compiled, { context });
await mod.link(async (name) => {
  let values;
  if (name === 'react') values = { default: React, useState: React.useState, useMemo: React.useMemo, useId: () => 'constellation-test' };
  else if (name === 'react/jsx-runtime') values = require('react/jsx-runtime');
  else if (name === 'framer-motion') values = {
    motion: { div: 'div', span: 'span', button: 'button', svg: 'svg' },
    AnimatePresence: ({ children }) => children,
  };
  else if (name === '../lib/AudioEngine') values = {
    default: {
      playSynthesizedSfx: (type) => sfxCalls.push(type),
      playSFX: () => {},
      say: () => {},
    },
  };
  else throw new Error(`Unexpected dependency ${name}`);

  const mock = new vm.SyntheticModule(Object.keys(values), function () {
    for (const [key, value] of Object.entries(values)) this.setExport(key, value);
  }, { context });
  await mock.link(() => {});
  return mock;
});

await mod.evaluate();
const ConstellationTalentTree = mod.namespace.default;
const { getNodeState, BRANCH_CONFIG } = mod.namespace;

// 1. Verify Node State Logic
assert.equal(getNodeState(mockTalentState.nodes[0], 2), 'AVAILABLE'); // rank 1 of 3, available
assert.equal(getNodeState({ ...mockTalentState.nodes[0], current_rank: 3 }, 2), 'MAXED');
assert.equal(getNodeState(mockTalentState.nodes[3], 2), 'LOCKED'); // unlocked: false
assert.equal(getNodeState(mockTalentState.nodes[1], 0), 'INSUFFICIENT_POINTS'); // unlocked, 0 points available
assert.equal(getNodeState(mockTalentState.nodes[1], 1), 'AVAILABLE'); // unlocked, 1 point available

// 2. Render Component with TestRenderer
let allocatedCalls = [];
let tree;
await act(async () => {
  tree = create(
    React.createElement(ConstellationTalentTree, {
      talentState: mockTalentState,
      onAllocate: (nodeId, rank) => allocatedCalls.push({ nodeId, rank }),
    })
  );
});

const renderedJson = JSON.stringify(tree.toJSON());

// Verify Header & Points Badge
assert.ok(renderedJson.includes('Astral Constellation Matrix'));
assert.ok(renderedJson.includes('Keeper Specialization Talents'));
assert.ok(renderedJson.includes('Available Talent Points'));

// Verify All Seed Node Names Render in SVG
for (const node of mockTalentState.nodes) {
  assert.ok(renderedJson.includes(node.name), `Should render node name: ${node.name}`);
}

// 3. Test Click Allocation for Available Node (focus_clarity: unlocked, 0 -> 1)
const focusClarityNode = tree.root.findByProps({ id: 'talent-node-focus_clarity' });
assert.ok(focusClarityNode, 'focus_clarity node element must exist');

await act(async () => {
  focusClarityNode.props.onClick();
});

// Should trigger onAllocate callback and synthesized sfx
assert.equal(allocatedCalls.length, 1);
assert.equal(allocatedCalls[0].nodeId, 'focus_clarity');
assert.equal(allocatedCalls[0].rank, 1);
assert.ok(sfxCalls.includes('allocate'), 'Should trigger allocate SFX');

// 4. Test Click on Locked Node (martial_tenacity)
const lockedNode = tree.root.findByProps({ id: 'talent-node-martial_tenacity' });
assert.ok(lockedNode, 'martial_tenacity node element must exist');
sfxCalls.length = 0;
await act(async () => {
  lockedNode.props.onClick();
});
// Should NOT invoke allocate and should trigger error SFX
assert.equal(allocatedCalls.length, 1, 'Allocation must not trigger for locked node');
assert.ok(sfxCalls.includes('error'), 'Should trigger error SFX on locked node click');

// 5. Test Keyboard Navigation & Enter Key Allocation
const deepWorkNode = tree.root.findByProps({ id: 'talent-node-focus_deep_work' });
sfxCalls.length = 0;
await act(async () => {
  deepWorkNode.props.onKeyDown({ key: 'Enter', preventDefault: () => {} });
});
assert.equal(allocatedCalls.length, 2);
assert.equal(allocatedCalls[1].nodeId, 'focus_deep_work');
assert.equal(allocatedCalls[1].rank, 2);

await act(async () => {
  tree.unmount();
});

console.log('✅ ConstellationTalentTree rendering, node states, tooltips, sound feedback, and keyboard allocation tests passed.');
