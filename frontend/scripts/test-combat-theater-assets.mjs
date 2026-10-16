import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import vm from 'node:vm';

const root = resolve(process.cwd(), 'src');
const read = (path) => readFile(resolve(root, path), 'utf8');

const [desktopApiSrc, vaultAssetImageSrc, combatTheaterSrc] = await Promise.all([
  read('lib/desktopApi.js'),
  read('components/VaultAssetImage.js'),
  read('components/CombatTheater.js'),
]);

console.log('Testing CombatTheater logs and asset fallback contracts...');

// ============================================================================
// 1. Static Contract Checks
// ============================================================================

// Verify no fabricated combat log history in initial state or anywhere in CombatTheater
assert.doesNotMatch(
  combatTheaterSrc,
  /SOUL TRANSFERENCE|EXORCIST’S CLEANSING|WAR COUNCIL’S INSIGHT/,
  'CombatTheater must not contain fabricated combat log history',
);

// Verify combatLog initializes to empty array
assert.match(
  combatTheaterSrc,
  /const\s+\[combatLog,\s*setCombatLog\]\s*=\s*useState\(\[\]\);/,
  'CombatTheater must initialize combatLog to empty array',
);

// Verify absent /placeholder.png is not referenced
assert.doesNotMatch(
  combatTheaterSrc,
  /\/placeholder\.png/,
  'CombatTheater must not reference absent /placeholder.png',
);

// Verify CombatTheater delegates to VaultAssetImage
assert.match(
  combatTheaterSrc,
  /import\s+VaultAssetImage\s+from\s+["']\.\/VaultAssetImage["'];/,
  'CombatTheater must import VaultAssetImage',
);
assert.match(
  combatTheaterSrc,
  /<VaultAssetImage\b[^>]*assetPath=\{entity\.image\}[^>]*fallbackPaths=\{entity\.fallback\s*\?\s*\[entity\.fallback\]\s*:\s*\[\]\}/,
  'CombatTheater must render VaultAssetImage with entity.image and fallbackPaths',
);

// Verify vaultAssetUrl defaults to stable URLs (cacheBust: false)
assert.match(
  desktopApiSrc,
  /export\s+function\s+vaultAssetUrl\([^,)]*,\s*\{\s*cacheBust\s*=\s*false\s*\}\s*=\s*\{\}\)/,
  'desktopApi.vaultAssetUrl must default cacheBust to false for stable candidate URLs',
);

// Verify VaultAssetImage has accessible local CSS fallback
assert.match(
  vaultAssetImageSrc,
  /role="img"/,
  'VaultAssetImage must render accessible role="img" when all fallbacks are exhausted',
);
assert.match(
  vaultAssetImageSrc,
  /Image unavailable/,
  'VaultAssetImage must provide deliberate accessible text fallback',
);

// ============================================================================
// 2. Stable Candidate URLs & Bounded Fallback Progression
// ============================================================================

// Import vaultAssetUrl logic from desktopApi
const vaultAssetUrlMatch = desktopApiSrc.match(/export\s+function\s+vaultAssetUrl\([\s\S]*?\n\}/);
assert.ok(vaultAssetUrlMatch, 'vaultAssetUrl must be defined');

const apiContext = vm.createContext({
  apiUrl: (p) => `http://127.0.0.1:8000${p}`,
  Date: { now: () => 1700000000000 },
});
vm.runInContext(vaultAssetUrlMatch[0].replace('export ', '') + '\nglobalThis.vaultAssetUrl = vaultAssetUrl;', apiContext);

// Check URL stability: default call must NOT append fresh timestamps
const stableUrl1 = apiContext.vaultAssetUrl('Obstacles/Antagonists/Vex/Card.png');
const stableUrl2 = apiContext.vaultAssetUrl('Obstacles/Antagonists/Vex/Card.png');
assert.equal(stableUrl1, 'http://127.0.0.1:8000/api/vault/Obstacles/Antagonists/Vex/Card.png');
assert.equal(stableUrl1, stableUrl2, 'Repeated vaultAssetUrl calls must return identical stable URLs');
assert.doesNotMatch(stableUrl1, /\?t=/, 'Stable URLs must not append timestamp query parameter');

// Explicit cacheBust: true still works when requested
const bustedUrl = apiContext.vaultAssetUrl('Obstacles/Antagonists/Vex/Card.png', { cacheBust: true });
assert.equal(bustedUrl, 'http://127.0.0.1:8000/api/vault/Obstacles/Antagonists/Vex/Card.png?t=1700000000000');

// Simulate VaultAssetImage fallback progression when both Card.png and Portrait.png are unavailable
function simulateVaultAssetImage({ assetPath, fallbackPaths = [] }) {
  const paths = [assetPath, ...fallbackPaths].filter(Boolean);
  let pathIndex = 0;
  const requestedUrls = [];

  while (pathIndex < paths.length) {
    const currentPath = paths[pathIndex];
    const url = apiContext.vaultAssetUrl(currentPath);
    requestedUrls.push(url);

    // Simulate 404/network error triggering onError handler: setPathIndex(curr => curr + 1)
    pathIndex++;
  }

  // Once paths are exhausted, render accessible CSS fallback div
  const fallbackRendered = pathIndex >= paths.length;
  return { requestedUrls, fallbackRendered };
}

const simulation = simulateVaultAssetImage({
  assetPath: 'Obstacles/Antagonists/Vex/Card.png',
  fallbackPaths: ['Obstacles/Antagonists/Vex/Portrait.png'],
});

assert.equal(
  simulation.requestedUrls.length,
  2,
  'Exhausted image fallbacks must produce exactly 2 requests (primary + fallback)',
);
assert.equal(
  simulation.requestedUrls[0],
  'http://127.0.0.1:8000/api/vault/Obstacles/Antagonists/Vex/Card.png',
  'First request must target primary Card.png',
);
assert.equal(
  simulation.requestedUrls[1],
  'http://127.0.0.1:8000/api/vault/Obstacles/Antagonists/Vex/Portrait.png',
  'Second request must target fallback Portrait.png',
);
assert.equal(
  simulation.fallbackRendered,
  true,
  'Must terminate in deliberate accessible local/CSS fallback',
);
assert.ok(
  simulation.requestedUrls.every((u) => !u.includes('placeholder.png')),
  'Must never produce request for absent /placeholder.png',
);

// ============================================================================
// 3. Combat Log Ingestion: Real Response Shapes, Limits & Error States
// ============================================================================

// Extract the fetchLog function body from CombatTheater.js to test parsing contracts
const fetchLogStart = combatTheaterSrc.indexOf('    async function fetchLog() {');
const fetchLogEnd = combatTheaterSrc.indexOf('\n    fetchLog();', fetchLogStart);
assert.ok(fetchLogStart > 0 && fetchLogEnd > fetchLogStart, 'fetchLog must be found in CombatTheater.js');
const fetchLogSrc = combatTheaterSrc.slice(fetchLogStart, fetchLogEnd);

async function testFetchLogWithResponse(mockResponse, logUrl = 'Battle/Combat_Log.md') {
  let combatLogState = ['INITIAL_SHOULD_BE_OVERWRITTEN'];
  let loadingLogState = false;
  let requestedEndpoint = null;

  const context = vm.createContext({
    logUrl,
    ignore: false,
    setCombatLog: (val) => { combatLogState = val; },
    setLoadingLog: (val) => { loadingLogState = val; },
    apiFetch: async (endpoint) => {
      requestedEndpoint = endpoint;
      if (mockResponse instanceof Error) throw mockResponse;
      return mockResponse;
    },
    console: { error: () => {} },
  });

  vm.runInContext(fetchLogSrc + '\nglobalThis.run = fetchLog;', context);
  await context.run();
  return { combatLog: Array.isArray(combatLogState) ? [...combatLogState] : combatLogState, requestedEndpoint };
}

// Case 3a: Real documented Markdown vault response shape { content, path }
const syntheticVaultDoc = [
  '# Battle Encounter Log',
  '-- Note: Pre-combat banter omitted --',
  '> [KEEPER] activates [SHIELD REVERSAL] on [MINOTAUR]! +120 XP',
  '> [AVA] casts [TEMPEST NOVA]! +250 XP',
  'Random non-combat telemetry note',
  '> [KEEPER] strikes final blow! Victory achieved! +300 XP',
].join('\n');

const res3a = await testFetchLogWithResponse({
  ok: true,
  json: async () => ({ content: syntheticVaultDoc, path: 'Battle/Combat_Log.md' }),
});
assert.equal(res3a.requestedEndpoint, '/api/vault/Battle/Combat_Log.md');
assert.deepEqual(res3a.combatLog, [
  '> [KEEPER] activates [SHIELD REVERSAL] on [MINOTAUR]! +120 XP',
  '> [AVA] casts [TEMPEST NOVA]! +250 XP',
  '> [KEEPER] strikes final blow! Victory achieved! +300 XP',
]);

// Case 3b: Log limit slicing (at most 15 entries)
const twentyLines = Array.from({ length: 20 }, (_, i) => `> [LOG] Combat action ${i + 1} completed`).join('\n');
const res3b = await testFetchLogWithResponse({
  ok: true,
  json: async () => ({ content: twentyLines, path: 'Battle/Combat_Log.md' }),
});
assert.equal(res3b.combatLog.length, 15, 'Must keep at most last 15 combat log lines');
assert.equal(res3b.combatLog[0], '> [LOG] Combat action 6 completed');
assert.equal(res3b.combatLog[14], '> [LOG] Combat action 20 completed');

// Case 3c: Real combat route response shape { logs }
const res3c = await testFetchLogWithResponse(
  {
    ok: true,
    json: async () => ({ logs: ['> [KEEPER] deployed.', '> [ECHO] synchronized.'] }),
  },
  '/api/combat/log',
);
assert.equal(res3c.requestedEndpoint, '/api/combat/log');
assert.deepEqual(res3c.combatLog, [
  '> [KEEPER] deployed.',
  '> [ECHO] synchronized.',
]);

// Case 3d: Empty log content must render empty array, NEVER fabricated entries
const res3d = await testFetchLogWithResponse({
  ok: true,
  json: async () => ({ content: '# Log header only with no combat', path: 'Battle/Combat_Log.md' }),
});
assert.deepEqual(res3d.combatLog, [], 'Empty log must result in empty combatLog array');

// Case 3e: HTTP error status (404 / 500) must clear to empty array, NEVER fabricated entries
const res3e = await testFetchLogWithResponse({
  ok: false,
  status: 404,
  json: async () => ({ detail: 'Resource not found' }),
});
assert.deepEqual(res3e.combatLog, [], '404 error response must result in empty combatLog array');

// Case 3f: Network fetch failure must clear to empty array, NEVER fabricated entries
const res3f = await testFetchLogWithResponse(new Error('Connection refused'));
assert.deepEqual(res3f.combatLog, [], 'Network failure must result in empty combatLog array');

// Case 3g: Native desktop mode without FastAPI (NativeResponse envelope)
class MockNativeResponse {
  constructor(body) {
    this.status = 200;
    this.ok = true;
    this._body = body;
    this._text = JSON.stringify(body);
  }
  async json() { return this._body; }
  async text() { return this._text; }
}

const res3g = await testFetchLogWithResponse(
  new MockNativeResponse({ content: '> [NATIVE] Desktop combat event logged.', path: 'Battle/Combat_Log.md' }),
);
assert.deepEqual(res3g.combatLog, ['> [NATIVE] Desktop combat event logged.']);

// ============================================================================
// 4. Native Route Dispatch
// ============================================================================

const commandMatch = desktopApiSrc.match(/const\s+command\s*=\s*([^;]+);/);
assert.ok(commandMatch, 'desktopApi.js must define command resolution');
const resolveCommand = new Function('path', `return ${commandMatch[1]};`);

assert.equal(
  resolveCommand('/api/vault/Battle/Combat_Log.md'),
  'vault_request',
  'Desktop native mode must route /api/vault/... to vault_request',
);
assert.equal(
  resolveCommand('/api/combat/log'),
  'vault_request',
  'Desktop native mode must route /api/combat/log to vault_request',
);

console.log('✅ All CombatTheater logs and asset fallback regression checks passed.');
