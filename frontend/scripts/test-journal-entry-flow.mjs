import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';

const sourceRoot = resolve(process.cwd(), 'src');
const composer = await readFile(resolve(sourceRoot, 'components/JournalEntryComposer.js'), 'utf8');
const sectorView = await readFile(resolve(sourceRoot, 'components/SectorView.js'), 'utf8');
const page = await readFile(resolve(sourceRoot, 'app/page.js'), 'utf8');
const desktopApi = await readFile(resolve(sourceRoot, 'lib/desktopApi.js'), 'utf8');

assert.match(composer, /saveJournalEntry\(request\)/, 'composer must submit through the verified journal boundary');
assert.match(composer, /const request = \{ date, section, entry \}/, 'composer must retain the selected date, section, and entry');
assert.match(composer, /disabled=\{saving \|\| polishing \|\| !entry\.trim\(\)\}/, 'composer must prevent empty, duplicate, or concurrent polish submissions');
assert.match(composer, /apiFetch\('\/api\/journal\/entry\/polish'/, 'composer must request suggestions through the local journal endpoint');
assert.match(composer, /JSON\.stringify\(\{ entry, section \}\)/, 'composer must provide the selected section so the suggestion can use its context');
assert.match(composer, /Restore original draft/, 'composer must let the user recover the original draft');
assert.match(composer, /Suggestions use local Ollama and are not saved automatically/, 'composer must explain local-only, manual-save behavior');
assert.match(composer, /Local Ollama suggestions require the desktop app or a local Navis server/, 'composer must explain why local suggestions are unavailable on the hosted web app');
assert.match(desktopApi, /path === '\/api\/journal\/entry\/polish' && !supportsLocalOllama\(\)/, 'polish requests must not go to a remote backend');
assert.match(composer, /setError\(saveError\.message/, 'composer must retain a recoverable error state');
assert.match(composer, /onSaved\?\.\(result, request\)/, 'composer must report verified results with their exact submitted identity');
assert.match(sectorView, /sectorId === 'JOURNAL'[\s\S]*?<JournalEntryComposer/, 'Journal files must render the entry composer');
assert.match(page, /onJournalEntrySaved=\{handleJournalEntrySaved\}/, 'Journal view must receive the save callback');
assert.match(page, /handleJournalEntrySaved[\s\S]*?refreshActiveEntityContent\(result\.path\)/, 'saved Markdown must use guarded authoritative refresh in the matching journal view');

console.log('Journal entry UI flow checks passed.');
