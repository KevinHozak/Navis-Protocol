import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const source = await readFile(new URL('../src/components/SectorView.js', import.meta.url), 'utf8');
const backendSource = await readFile(new URL('../../backend/main.py', import.meta.url), 'utf8');

assert.match(source, /apiFetch\('\/api\/realm\/options', \{ signal \}\)/,
  'Moongate must load realm options through the shared API boundary with cancellation support.');
assert.match(source, /activeEntity\?\.id !== 'REALM_HOP_MODAL'/,
  'Moongate must refresh its destination options when the view becomes active.');
assert.match(source, /setRealmsLoading\(true\)/,
  'Moongate must expose a distinct loading state.');
assert.match(source, /setRealmsError\(err\?\.message \|\| 'Unable to load destination realms\.'\)/,
  'Moongate must preserve an actionable API error for the UI.');
assert.match(source, /Retry Resonance Scan/,
  'Moongate must offer an actionable retry control after a request failure.');
assert.match(source, /realmsLoaded && realms\.length === 0/,
  'Moongate must distinguish an empty successful response from loading and failure.');
assert.match(source, /onClick=\{\(\) => fetchDraft\(r\.name\)\}/,
  'A valid destination card must continue into squad drafting.');
assert.match(source, /onError=\{\(e\) => \{ e\.target\.style\.display = 'none'; \}\}/,
  'Destination cards must remain usable when their image asset fails.');

const hopHandler = source.match(/const handleRealmHop = async \(\) => \{([\s\S]*?)\n  \};/)?.[1];
assert.ok(hopHandler, 'Moongate must retain its realm hop handler.');
assert.match(hopHandler, /setHopLogs\(data\);[\s\S]*await onRefreshStatus\?\.\(\)/,
  'A successful realm hop must refresh parent status immediately.');
assert.match(hopHandler, /catch \(refreshError\)[\s\S]*console\.error/,
  'A status refresh failure must not replace successful hop telemetry.');
assert.match(hopHandler, /if \(!res\.ok\) throw new Error\(data\.detail \|\| "Realm hop failed"\)/,
  'A failed realm hop must retain its existing error behavior.');
assert.match(backendSource, /@app\.get\("\/api\/realm\/options"\)/,
  'The backend realm options endpoint must remain available.');

console.log('Moongate loading regression check passed.');
