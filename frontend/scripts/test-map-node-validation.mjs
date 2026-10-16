import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { validateMapNodes } from '../src/lib/mapNodes.mjs';

const validNode = (overrides = {}) => ({ x: 10, y: 20, type: 'Town', name: 'Outpost', ...overrides });

assert.deepEqual(validateMapNodes({ nodes: [] }), { nodes: [], skipped: 0, hasNodeList: true },
  'Zero nodes must produce an intentional empty result.');
assert.equal(validateMapNodes({ nodes: [validNode()] }).nodes.length, 1,
  'One valid node must remain available for icon rendering without requiring a spline.');
assert.equal(validateMapNodes({ nodes: [validNode(), validNode({ x: 30, type: 'Camp' })] }).nodes.length, 2,
  'Short maps with fewer than seven valid nodes must be retained.');

const malformed = [null, [], validNode({ x: NaN }), validNode({ y: Infinity }), validNode({ name: '' }), validNode({ name: 4 }), validNode({ type: 'Unknown' })];
const cleaned = validateMapNodes({ nodes: [...malformed, validNode({ name: '  Keep me  ' })] });
assert.equal(cleaned.skipped, malformed.length, 'Malformed nodes must be counted for a recoverable diagnostic.');
assert.deepEqual(cleaned.nodes, [validNode({ name: 'Keep me' })],
  'Only nodes with finite coordinates, supported types, and non-empty names may render.');
assert.equal(validateMapNodes(null).hasNodeList, false, 'Missing source data must be distinguishable from an empty map.');

const scene = await readFile(new URL('../src/lib/MapScene.js', import.meta.url), 'utf8');
assert.match(scene, /if \(nodes\.length >= 2\)/, 'Spline drawing must be skipped for zero or one point.');
assert.match(scene, /nodes\.forEach\(/, 'Every validated node must retain normal icon rendering.');
assert.doesNotMatch(scene, /nodes\[\s*[046]\s*\]/, 'Rendering must not assume fixed node indexes for entity markers.');
assert.match(scene, /showMapDataDiagnostic\(result\)/,
  'Skipped or unavailable map data must produce a visible diagnostic.');

console.log('Map node validation regression check passed.');
