import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const scene = await readFile(new URL('../src/lib/MapScene.js', import.meta.url), 'utf8');
const wrapper = await readFile(new URL('../src/components/PhaserMapWrapper.js', import.meta.url), 'utf8');
const sector = await readFile(new URL('../src/components/SectorView.js', import.meta.url), 'utf8');

assert.match(scene, /onMapNodesLoaded\?\.\(nodes\)/,
  'Only validated map nodes should be exposed to the keyboard navigation list.');
assert.match(scene, /container\.on\('pointerup',[\s\S]*?selectNode\(node\.name/,
  'Pointer selection on a map node must use the shared node selection handler.');
assert.match(scene, /this\.onMapNodeSelected\?\.\(realmName\)/,
  'Selecting a map node must notify the wrapper and Moongate flow.');
assert.match(wrapper, /<button[\s\S]*?aria-pressed=\{selectedNode === node\.name\}/,
  'Every valid map node must be available as a keyboard-operable selected-state button.');
assert.match(wrapper, /onSelectRealm\?\.\(node\.name\)/,
  'Keyboard selection must invoke the same realm selection callback as the map.');
assert.match(sector, /const handleMapNodeSelect = async \(realmName\)/,
  'Map selection must route into the shared Moongate handler.');
assert.match(sector, /onSelectEntity\?\.\(\{ id: 'REALM_HOP_MODAL'/,
  'Map selection must open the existing Moongate experience.');
assert.match(sector, /const activeSquadNames = \[draftData\.vanguard\.name, \.\.\.selectedDraft\]/,
  'Realm hop must keep the existing vanguard plus two selected companions contract.');
assert.match(sector, /body: JSON\.stringify\(\{ realm_name: draftRealm, squad_names: activeSquadNames \}\)/,
  'The existing validated API request shape must be preserved.');
assert.match(sector, /disabled=\{selectedDraft\.length !== 2\}/,
  'A realm hop must remain blocked until the two required squad members are selected.');

console.log('Map realm navigation regression check passed.');
