import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { describeMapLoad } from '../src/lib/mapNodes.mjs';

const node = { name: 'Outpost', type: 'Town', x: 12, y: 34 };
assert.equal(describeMapLoad({ mapData: { nodes: [] } }).kind, 'empty');
assert.equal(describeMapLoad({ mapData: { destinations: [] } }).kind, 'invalid-schema');
assert.equal(describeMapLoad({ mapData: { nodes: [{ ...node, x: Infinity }] } }).kind, 'invalid-nodes');
assert.equal(describeMapLoad({ mapData: {}, dataLoadError: { status: 404 } }).kind, 'data-unavailable');
assert.equal(describeMapLoad({ mapData: {}, dataLoadError: { status: 200 } }).kind, 'invalid-json');

const imageFailure = describeMapLoad({
  mapData: { nodes: [node] },
  imageLoadError: { status: 404 },
});
assert.equal(imageFailure.kind, 'image-unavailable');
assert.deepEqual(imageFailure.nodes, [node], 'Image-only failures must preserve valid destinations.');
assert.equal(describeMapLoad({ mapData: { nodes: [node] } }).kind, 'ready',
  'A later successful retry must recover to the ready state.');

const scene = await readFile(new URL('../src/lib/MapScene.js', import.meta.url), 'utf8');
const wrapper = await readFile(new URL('../src/components/PhaserMapWrapper.js', import.meta.url), 'utf8');
const desktopApi = await readFile(new URL('../src/lib/desktopApi.js', import.meta.url), 'utf8');
const native = await readFile(new URL('../src-tauri/src/lib.rs', import.meta.url), 'utf8');
assert.match(scene, /file\.key === 'landscape' \|\| file\.key === 'overworld_data'/,
  'JSON and image transport failures must be tracked separately.');
assert.match(scene, /file\.xhrLoader\?\.status/,
  'HTTP failures should retain their response status for the diagnostic.');
assert.match(scene, /this\.cache\.json\.remove\('overworld_data'\)/,
  'A retry must discard cached JSON before requesting updated source data.');
assert.match(scene, /this\.textures\.remove\(key\)/,
  'A retry must discard cached image textures before reloading.');
assert.match(wrapper, /scene\.scene\.restart\(\)/,
  'Retry must reload the selected realm through the supported asset transport.');
assert.match(wrapper, /setNodes\(\[\]\)/,
  'Realm changes and retries must clear stale destinations before loading.');
assert.match(wrapper, /\}, \[currentRealm, handleSceneNodeSelected\]\)/,
  'Changing realms must destroy the previous scene and load only the selected realm.');
assert.match(scene, /apiUrl\(`\/api\/vault\/Realms/,
  'Web map assets must use the configured API transport.');
assert.match(desktopApi, /path\.startsWith\('\/api\/vault\/'\)[\s\S]*nativeVaultAssetUrl/,
  'Standalone desktop assets must use the native Vault protocol.');
assert.match(native, /register_uri_scheme_protocol\("vault"/,
  'The standalone desktop build must register the Vault asset protocol.');

console.log('Map loading diagnostics and recovery regression check passed.');
