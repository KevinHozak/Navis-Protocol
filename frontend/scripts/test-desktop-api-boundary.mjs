import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';

const root = resolve(process.cwd(), 'src');
const targets = [
  'components/WarRoom.js',
  'components/AsyncJobModal.js',
  'app/facilities/iron-sanctum/page.js',
  'components/SectorView.js',
  'components/CombatTheater.js',
  'components/CombatProfileModal.js',
];

for (const relativePath of targets) {
  const source = await readFile(resolve(root, relativePath), 'utf8');
  assert.match(source, /apiFetch|vaultAssetUrl/, `${relativePath} must use the shared desktop API boundary`);
  assert.doesNotMatch(source, /fetch\s*\(/, `${relativePath} contains a direct fetch call`);
  assert.doesNotMatch(source, /127\.0\.0\.1:8000|localhost:8000/, `${relativePath} contains a hard-coded local backend URL`);
}

const desktopApi = await readFile(resolve(root, 'lib/desktopApi.js'), 'utf8');
assert.match(desktopApi, /p5_request/, 'desktopApi must route neural and biometrics calls to the native P5 adapter');
assert.match(desktopApi, /vaultAssetUrl/, 'desktopApi must expose the shared Vault asset URL helper');
assert.doesNotMatch(desktopApi, /invokeNative\('polish_journal_entry'/, 'polishing must not bypass the shared configured provider');
const nativeDispatch = await readFile(resolve(root, '../src-tauri/src/lib.rs'), 'utf8');
assert.match(nativeDispatch, /journal\/entry\/polish[\s\S]*?p3::brief_request/, 'native polishing must use the packaged shared Python provider route');

const apiUrlDefinition = desktopApi.match(/export function apiUrl\(path\) \{[\s\S]*?\n\}/);
assert.ok(apiUrlDefinition, 'desktopApi must define apiUrl');
const nativeVaultAssetUrlDefinition = desktopApi.match(/function nativeVaultAssetUrl\(path\) \{[\s\S]*?\n\}/);
assert.ok(nativeVaultAssetUrlDefinition, 'desktopApi must define the native Vault URL mapper');
const createApiUrl = (userAgent, tauri = true) => new Function(
  'isTauriRuntime',
  'API_BASE',
  'navigator',
  `${nativeVaultAssetUrlDefinition[0]}; ${apiUrlDefinition[0].replace(/^export /, '')}; return apiUrl;`,
)(() => tauri, 'http://127.0.0.1:8000', { userAgent });
const windowsApiUrl = createApiUrl('Mozilla/5.0 (Windows NT 10.0; Win64; x64)');
const macApiUrl = createApiUrl('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)');
const webApiUrl = createApiUrl('Mozilla/5.0 (Windows NT 10.0; Win64; x64)', false);
assert.equal(
  windowsApiUrl('vault://localhost/Companions/Sabine%20Wren/Portrait.png'),
  'http://vault.localhost/Companions/Sabine%20Wren/Portrait.png',
  'apiUrl must map existing custom protocol URLs to the Windows WebView host',
);
assert.equal(
  windowsApiUrl('data:image/png;base64,AA=='),
  'data:image/png;base64,AA==',
  'apiUrl must preserve other absolute URL schemes',
);
assert.equal(
  windowsApiUrl('/api/vault/Companions/Sabine%20Wren/Portrait.png'),
  'http://vault.localhost/Companions/Sabine%20Wren/Portrait.png',
  'apiUrl must map Vault paths to the Windows WebView host',
);
assert.equal(
  macApiUrl('/api/vault/Companions/Sabine%20Wren/Portrait.png'),
  'vault://localhost/Companions/Sabine%20Wren/Portrait.png',
  'apiUrl must retain the native custom protocol on macOS',
);
assert.equal(
  webApiUrl('/api/vault/Companions/Sabine%20Wren/Portrait.png'),
  'http://127.0.0.1:8000/api/vault/Companions/Sabine%20Wren/Portrait.png',
  'apiUrl must retain the HTTP API path in a normal browser',
);

console.log('Desktop API boundary checks passed.');
