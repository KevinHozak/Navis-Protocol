import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolveMapTelemetry } from '../src/lib/mapTelemetry.mjs';
const fixtures = JSON.parse(readFileSync(new URL('./fixtures/map-telemetry.json', import.meta.url)));
const now = Date.parse('2026-09-30T12:00:00Z');
for (const fixture of fixtures) {
  const result = resolveMapTelemetry(fixture.status, fixture.realm, now);
  assert.deepEqual(result.markers.map(m => m.kind), fixture.expected, fixture.name);
}
const current = structuredClone(fixtures[0].status);
for (const [field, value] of [['x', '12'], ['x', -1], ['y', 577], ['observed_at', 'bad'], ['observed_at', '2026-09-30T12:01:00Z'], ['realm', 'Elsewhere']]) {
  const changed = structuredClone(current);
  changed.map_telemetry.player[field] = value;
  assert.ok(!resolveMapTelemetry(changed, 'Earth', now).markers.some(m => m.kind === 'player'), field);
}
assert.equal(resolveMapTelemetry(current, 'Earth', now + 300001).markers.length, 0, 'All markers expire without another status refresh');
current.current_antagonist = 'New target';
assert.ok(!resolveMapTelemetry(current, 'Earth', now).markers.some(m => m.kind === 'antagonist'));
current.squad = ['Different'];
assert.ok(!resolveMapTelemetry(current, 'Earth', now).markers.some(m => m.kind === 'squad'));
console.log('Map telemetry fixture and expiry checks passed.');

// Execute the real scene method against a lightweight rendering fixture.
const sceneSource = readFileSync(new URL('../src/lib/MapScene.js', import.meta.url), 'utf8')
  .replace(/^import .*;$/gm, '').replace('export default class MapScene', 'return class MapScene');
const destroyed = [];
const layers = [];
const fakePhaser = { Scene: class {}, Display: { Color: { HexStringToColor: () => ({ color: 0 }) } } };
const Scene = new Function('Phaser', sceneSource)(fakePhaser);
const scene = new Scene();
scene.add = {
  container: () => {
    const layer = { items: [], setDepth() { return this; }, add(items) { this.items.push(...items); }, destroy(children) { destroyed.push(children); } };
    layers.push(layer);
    return layer;
  },
  graphics: () => ({ fillStyle() {}, fillCircle() {}, lineStyle() {}, strokeCircle() {} }),
  text: (_x, _y, label) => ({ label, setOrigin() { return this; } })
};
scene.renderTelemetry(resolveMapTelemetry(fixtures[0].status, 'Earth', now));
assert.equal(layers[0].items.length, 8);
scene.renderTelemetry(resolveMapTelemetry(fixtures[4].status, 'Earth', now));
assert.equal(layers[1].items.length, 4, 'Threat clearing replaces the layer');
scene.renderTelemetry(resolveMapTelemetry(fixtures[3].status, 'Mars', now));
assert.equal(layers[2].items.length, 0, 'Realm hop leaves no old markers');
assert.deepEqual(destroyed, [true, true], 'Previous marker children are destroyed');
console.log('Scene marker replacement and realm clearing checks passed.');
