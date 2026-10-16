import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';

const src = resolve(process.cwd(), 'src');
const read = (path) => readFile(resolve(src, path), 'utf8');
const [notice, reid, neural, banter, forge, warRoom, desktopApi, p5] = await Promise.all([
  read('components/NativeCapabilityNotice.js'),
  read('components/ReidInterface.jsx'),
  read('components/NeuralPanel.js'),
  read('components/SectorView.js'),
  read('components/ForgePanel.js'),
  read('components/WarRoom.js'),
  read('lib/desktopApi.js'),
  readFile(resolve(process.cwd(), 'src-tauri/src/p5.rs'), 'utf8'),
]);

assert.match(notice, /role="status"[\s\S]*unavailable in the desktop app[\s\S]*web mode/);

// Reid native conversation capabilities
assert.doesNotMatch(reid, /nativeUnavailable/, 'Reid must not disable conversation natively');
assert.match(reid, /providerError/, 'Reid must handle actionable provider error state');
assert.match(reid, /Retry/, 'Reid must provide retry action');
assert.match(reid, /Cancel/, 'Reid must provide cancel action');

// Neural native conversation capabilities
assert.doesNotMatch(neural, /nativeUnavailable/, 'Neural must not disable conversation natively');
assert.match(neural, /providerError/, 'Neural must handle actionable provider error state');
assert.match(neural, /Retry/, 'Neural must provide retry action');
assert.match(neural, /Cancel/, 'Neural must provide cancel action');

// Banter capabilities
assert.match(banter, /activeEntity\?\.id === 'BANTER'/, 'Banter history must load in web and native runtimes');
assert.match(banter, /disabled=\{generatingBanter\}/, 'Banter generation must remain available natively');
assert.doesNotMatch(banter, /NATIVE_UNAVAILABLE/, 'Banter must not show the native unavailable state');

// Forge capabilities
assert.doesNotMatch(forge, /nativeUnavailable/, 'Forge must use the shared service');
assert.match(forge, /proposal_id: proposal.id, approved: true/, 'Approval must bind the preview');
assert.match(forge, /\/api\/forge\/discard/, 'Discard must revoke the proposal');
assert.match(p5, /services.forge_service/, 'Native Forge must use the shared implementation');

// War Room native conversation capabilities
assert.doesNotMatch(warRoom, /nativeUnavailable/, 'War Room must not disable conversation natively');
assert.match(warRoom, /providerError/, 'War Room must handle actionable provider error state');
assert.match(warRoom, /Retry/, 'War Room must provide retry action');
assert.match(warRoom, /Cancel/, 'War Room must provide cancel action');
assert.match(warRoom, /Clear Signal/, 'War Room must provide clear action');

// Desktop API and P5 route contracts
assert.match(desktopApi, /p5_request/, 'Routes must continue using the native P5 boundary');
for (const route of ['/api/reid/chat', '/api/neural/chat', '/api/neural/banter/history', '/api/neural/warroom/chat', '/api/forge/submit', '/api/forge/approve']) {
  assert.ok(p5.includes(route), `Native route contract missing ${route}`);
}
assert.match(p5, /services.conversation_service/, 'Native P5 must use shared conversation service');
assert.match(p5, /generate_banter\(&root\(\), count\)/, 'Native P5 must route banter generation to the local provider');
assert.match(p5, /banter_history\(&root\(\)\)/, 'Native P5 must provide persisted banter history');
assert.match(p5, /conversation_routes_redact_secrets_when_provider_unavailable/, 'Native P5 must verify secret redaction when provider is unavailable');
assert.match(p5, /warroom_history_and_clear_work_with_synthetic_vault/, 'Native P5 must verify warroom history and clear');

console.log('Native capability UI and route contract checks passed.');
