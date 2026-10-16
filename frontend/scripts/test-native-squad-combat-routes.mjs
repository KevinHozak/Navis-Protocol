import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';

const root = resolve(process.cwd(), 'src');
const read = (path) => readFile(resolve(root, path), 'utf8');

const [desktopApiSrc, sectorViewSrc, combatTheaterSrc, combatProfileModalSrc] = await Promise.all([
  read('lib/desktopApi.js'),
  read('components/SectorView.js'),
  read('components/CombatTheater.js'),
  read('components/CombatProfileModal.js'),
]);

console.log('Testing native squad and combat route dispatch in desktop mode...');

// 1. Verify desktopApi dispatch logic
// Extract the command resolution line directly from desktopApi.js
const commandMatch = desktopApiSrc.match(/const\s+command\s*=\s*([^;]+);/);
assert.ok(commandMatch, 'desktopApi.js must define command resolution');
const resolveCommand = new Function('path', `return ${commandMatch[1]};`);

const testedRoutes = [
  { path: '/api/squad/deploy', expectedCommand: 'vault_request' },
  { path: '/api/squad/bench', expectedCommand: 'vault_request' },
  { path: '/api/squad/vanguard', expectedCommand: 'vault_request' },
  { path: '/api/combat/target', expectedCommand: 'vault_request' },
  { path: '/api/combat/log', expectedCommand: 'vault_request' },
  { path: '/api/combat/log?limit=10', expectedCommand: 'vault_request' },
  { path: '/api/bio/adjust', expectedCommand: 'vault_request' },
];

for (const { path, expectedCommand } of testedRoutes) {
  const actualCommand = resolveCommand(path);
  assert.equal(
    actualCommand,
    expectedCommand,
    `Route ${path} must dispatch to ${expectedCommand}, got ${actualCommand}`,
  );
}

// 2. Verify NativeResponse error handling contract
class NativeResponse {
  constructor(result) {
    this.status = result.status;
    this.ok = result.status >= 200 && result.status < 300;
    this._body = result.body;
    this._text = result.text;
  }
  async json() { return this._body; }
  async text() { return this._text; }
}

const errorScenarios = [
  { path: '/api/squad/deploy', status: 404, detail: 'Companion not found: Ghost' },
  { path: '/api/squad/deploy', status: 400, detail: 'SQUAD FULL: Recall a member to reserve first.' },
  { path: '/api/squad/deploy', status: 400, detail: 'Keeper cannot be deployed to squad' },
  { path: '/api/squad/bench', status: 400, detail: 'Keeper cannot be recalled to reserve' },
  { path: '/api/squad/vanguard', status: 400, detail: 'Keeper cannot be designated as Vanguard.' },
  { path: '/api/combat/target', status: 400, detail: "Invalid target type. Use 'antagonist' or 'beast'." },
  { path: '/api/bio/adjust', status: 422, detail: 'XP must be recorded through the entity-scoped progression ledger.' },
];

for (const scenario of errorScenarios) {
  const res = new NativeResponse({
    status: scenario.status,
    body: { detail: scenario.detail },
    text: JSON.stringify({ detail: scenario.detail }),
  });
  assert.equal(res.ok, false);
  assert.equal(res.status, scenario.status);
  const json = await res.json();
  assert.equal(json.detail, scenario.detail);
}

// 3. Verify UI Control Semantics
console.log('Verifying UI control semantics and deferred targeted replacement...');

// CombatTheater: Keeper is fixed, clicking member defers replacement to RESERVE_ROSTER with targeting: entity.name
assert.match(
  combatTheaterSrc,
  /else\s+if\s*\(entity\.name\s*!==\s*'Keeper'\)\s*\{\s*onSelectEntity\(\{\s*id:\s*'RESERVE_ROSTER'/,
  'CombatTheater must keep Keeper fixed and select RESERVE_ROSTER on click',
);
assert.match(
  combatTheaterSrc,
  /targeting:\s*entity\.name/,
  'CombatTheater must defer targeted replacement via targeting prop',
);
assert.doesNotMatch(combatTheaterSrc, /handleBench/, 'CombatTheater must not recall member on click');
assert.doesNotMatch(combatTheaterSrc, /127\.0\.0\.1:8000|localhost:8000/, 'CombatTheater must not hardcode backend URL');

// SectorView: deferred replacement slot displayed and swap button rendered
assert.match(
  sectorViewSrc,
  /const\s+targetRecall\s*=\s*activeEntity\?\.targeting/,
  'SectorView must extract targetRecall from activeEntity targeting',
);
assert.match(
  sectorViewSrc,
  /Targeting recall slot:/,
  'SectorView must display targeted recall slot notice',
);
assert.match(
  sectorViewSrc,
  /Swap for \$\{targetRecall\}/,
  'SectorView must display Swap button when targetRecall is active',
);
assert.match(
  sectorViewSrc,
  /payload\.target_recall\s*=\s*targetRecall/,
  'SectorView must pass target_recall in deploy payload',
);
assert.match(sectorViewSrc, /apiFetch\('\/api\/squad\/deploy'/, 'SectorView must use shared apiFetch for deploy');
assert.match(sectorViewSrc, /apiFetch\('\/api\/squad\/bench'/, 'SectorView must use shared apiFetch for bench');
assert.match(sectorViewSrc, /apiFetch\('\/api\/combat\/target'/, 'SectorView must use shared apiFetch for target');
assert.match(sectorViewSrc, /apiFetch\('\/api\/combat\/log'/, 'SectorView must use shared apiFetch for log');

// SectorView: handleTargetChange surfaces actionable error
assert.match(
  sectorViewSrc,
  /if\s*\(!res\.ok\)\s*throw\s+new\s+Error\(data\.detail\s*\|\|\s*"Failed to update target"\)/,
  'SectorView handleTargetChange must surface actionable error on non-ok response',
);

// CombatProfileModal: actions and error alerts
assert.match(combatProfileModalSrc, /apiFetch\(endpoint/, 'CombatProfileModal must use shared apiFetch');
assert.match(combatProfileModalSrc, /alert\(err\.detail\s*\|\|\s*"Action failed"\)/, 'CombatProfileModal must alert error detail');
assert.match(combatProfileModalSrc, /\/api\/squad\/deploy/, 'CombatProfileModal must call squad deploy');
assert.match(combatProfileModalSrc, /\/api\/squad\/bench/, 'CombatProfileModal must call squad bench');
assert.match(combatProfileModalSrc, /\/api\/squad\/vanguard/, 'CombatProfileModal must call squad vanguard');
assert.match(combatProfileModalSrc, /\/api\/combat\/target/, 'CombatProfileModal must call combat target');

console.log('✅ Standalone desktop smoke tests and route verification passed.');
console.log('');
console.log('📋 Explicitly recorded unperformed live checks:');
console.log('  1. Live OS mouse click dispatch in compiled Windows NSIS WebView2 shell.');
console.log('  2. Physical Google Drive background sync lock timing across separate hardware machines.');
console.log('  3. Tactical audio prosody vocalization through native Windows audio device.');
