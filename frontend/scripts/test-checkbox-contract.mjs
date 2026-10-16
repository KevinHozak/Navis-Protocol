import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const source = fs.readFileSync(new URL('../src/app/page.js', import.meta.url), 'utf8');
const start = source.indexOf('  const handleToggleCheckbox');
const handler = source.slice(start, source.indexOf('  // Journal Calendar', start));
const context = {
  activeEntity: {id: 'tasks.md', type: 'file'}, activeSector: 'COMMAND', loadingContent: false,
  loadedContentEntityId: 'tasks.md', selectedEntityRef: {current: 'tasks.md'},
  sourceContentRef: {current: '- [ ] First'}, checkboxPending: {current: false},
  contentRevision: {current: 0}, refreshSequence: {current: 0}, appliedReadSequence: {current: 0},
  refreshActiveEntityContent: async () => {},
  AbortSignal, console, alert() {}, setPendingCheckboxXP(value) { context.pending = value; },
  setEntityContent(value) { context.content = value; },
  refreshStatus: async () => { throw Error('refresh failed'); },
};
vm.createContext(context);
vm.runInContext(handler + '\nglobalThis.toggle = handleToggleCheckbox;', context);
let resolve;
context.apiFetch = () => new Promise(r => {resolve = r;});
const first = context.toggle('First', true, 1);
assert.equal((await context.toggle('First', false, 1)).busy, true);
assert.equal(context.checkboxPending.current, true);
resolve({ok: true, json: async () => ({saved: true, content: '- [x] First', xp_status: 'pending'})});
await first;
assert.equal(context.content, '- [x] First');
assert.equal(context.pending.isChecked, true);
assert.equal(context.checkboxPending.current, false);
context.apiFetch = async () => ({ok: false, json: async () => ({detail: {content: '- [ ] Changed', message: 'stale'}})});
await context.toggle('First', true, 1);
assert.equal(context.content, '- [ ] Changed');
assert.match(source, /Retry XP/);
const native = fs.readFileSync(new URL('../src-tauri/src/lib.rs', import.meta.url), 'utf8');
assert.match(native, /p3::task_toggle_request/);

// Verify optimistic UI rendering contract in MarkdownRenderer
const rendererSource = fs.readFileSync(new URL('../src/components/MarkdownRenderer.js', import.meta.url), 'utf8');
assert.match(rendererSource, /optimisticOverrides/);
assert.match(rendererSource, /effectiveChecked/);
assert.match(rendererSource, /handleCheckboxChange/);

// Verify viewport scroll preservation contract in SectorView
const sectorViewSource = fs.readFileSync(new URL('../src/components/SectorView.js', import.meta.url), 'utf8');
assert.match(sectorViewSource, /scrollContainerRef/);
assert.match(sectorViewSource, /scrollPosRef/);
assert.match(sectorViewSource, /scrollContainerRef\.current\.scrollTop = targetScroll/);

console.log('Checkbox authority, rapid-click guard, XP recovery, optimistic UI and scroll preservation passed.');

// Execute real refresh logic with controlled completion order.
const refreshStart = source.indexOf('  const refreshActiveEntityContent');
vm.runInContext(source.slice(refreshStart, source.indexOf('  const refreshEntitiesForSector', refreshStart)) + '\nglobalThis.refresh = refreshActiveEntityContent;', context);
context.setLoadedContentEntityId = () => {};
context.setContentLoadError = () => {};
context.setLoadingContent = () => {};
let releaseRead;
context.apiFetch = () => new Promise(resolve => { releaseRead = resolve; });
const staleRead = context.refresh('tasks.md');
context.contentRevision.current += 1;
context.content = '- [x] First';
releaseRead({ok: true, json: async () => ({content: '- [ ] First'})});
await staleRead;
assert.equal(context.content, '- [x] First', 'read started before save cannot revert it');
let reads = [];
context.apiFetch = () => new Promise(resolve => reads.push(resolve));
const older = context.refresh('tasks.md');
const newer = context.refresh('tasks.md');
reads[1]({ok: true, json: async () => ({content: 'new'})});
await newer;
reads[0]({ok: true, json: async () => ({content: 'old'})});
await older;
assert.equal(context.content, 'new', 'out-of-order refresh cannot overwrite newest response');
context.checkboxPending.current = true;
await context.refresh('tasks.md');
assert.equal(reads.length, 2, 'watcher skips pending writes');
context.checkboxPending.current = false;
context.apiFetch = () => new Promise(resolve => { releaseRead = resolve; });
const navigated = context.refresh('tasks.md');
context.contentRevision.current += 1;
releaseRead({ok: true, json: async () => ({content: 'before navigation'})});
await navigated;
assert.equal(context.content, 'new');
console.log('Delayed watcher reads, out-of-order refresh and navigation revisions passed.');

context.apiFetch = async (path, options = {}) => {
  if (options.method === 'POST') throw new Error('response lost after save');
  return {ok: true, json: async () => ({content: '- [x] First'})};
};
assert.equal((await context.toggle('First', true, 1)).ok, false);
assert.equal(context.content, '- [x] First', 'uncertain save reads back without blind rollback');
assert.equal(context.checkboxPending.current, false);
context.loadingContent = true;
assert.equal((await context.toggle('First', false, 1)).ok, false);
context.loadingContent = false;
let finishSave;
context.apiFetch = async (path, options = {}) => {
  if (options.method === 'POST') return new Promise(resolve => {finishSave = resolve;});
  return {ok: true, json: async () => ({content: 'new document'})};
};
const navigatingSave = context.toggle('First', true, 1);
context.selectedEntityRef.current = 'other.md';
context.contentRevision.current += 1;
context.content = 'new document';
finishSave({ok: true, json: async () => ({content: '- [x] First'})});
await navigatingSave;
assert.equal(context.content, 'new document', 'late save cannot replace another document');
console.log('Lost response recovery, explicit rejected input and late save after navigation passed.');

// Initial-load fallback must survive a newer failed watcher request.
const effectStart = source.indexOf('  // 4. Entity Change');
const effectBody = source.slice(source.indexOf('    contentRevision.current += 1;', effectStart), source.indexOf('  }, [activeEntity]);', effectStart));
context.AbortController = AbortController;
context.activeEntity = {id: 'tasks.md', type: 'file'};
context.selectedEntityRef.current = 'tasks.md';
context.setLoadingContent = value => { context.loadingContent = value; };
context.setLoadedContentEntityId = value => { context.loadedContentEntityId = value; };
vm.runInContext('globalThis.load = () => {\n' + effectBody + '\n};', context);
for (const failure of ['rejected', 'non-ok']) {
  const pendingReads = [];
  context.apiFetch = () => new Promise((resolve, reject) => pendingReads.push({resolve, reject}));
  context.load();
  const watcher = context.refresh('tasks.md');
  if (failure === 'rejected') pendingReads[1].reject(Error('watcher timed out'));
  else pendingReads[1].resolve({ok: false});
  await watcher;
  pendingReads[0].resolve({ok: true, json: async () => ({content: '- [x] Fallback'})});
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(context.loadingContent, false);
  assert.equal(context.loadedContentEntityId, 'tasks.md');
  assert.equal(context.content, '- [x] Fallback');
}
// A successful newer watcher still supersedes the initial load.
const pendingReads = [];
context.apiFetch = () => new Promise(resolve => pendingReads.push(resolve));
context.load();
const watcher = context.refresh('tasks.md');
pendingReads[1]({ok: true, json: async () => ({content: 'newest'})});
await watcher;
pendingReads[0]({ok: true, json: async () => ({content: 'older'})});
await new Promise(resolve => setImmediate(resolve));
assert.equal(context.content, 'newest');

// Late native completion emits the original task path, even after JS aborts.
const nativeToggle = native.slice(native.indexOf('if method.as_deref() == Some("POST") && path == "/api/tasks/toggle"'), native.indexOf('if method.as_deref() == Some("POST")\n        &&'));
assert.match(nativeToggle, /value.get\("file_path"\)/);
assert.match(nativeToggle, /path: task_path/);
const eventStart = source.indexOf('      onEvent:');
const eventHandler = source.slice(eventStart + '      onEvent:'.length, source.indexOf('      onConnectionChange:', eventStart)).trim().replace(/,\s*$/, '');
vm.runInContext('globalThis.event = ' + eventHandler, context);
const journalId = 'Journal/2026/10/2026-10-06.md';
context.activeEntity = {id: journalId, name: '2026-10-06', type: 'file'};
context.activeEntityRef = {current: context.activeEntity};
context.activeSector = 'JOURNAL';
context.activeSectorRef = {current: 'JOURNAL'};
context.selectedJournalDate = '2026-10-06';
context.selectedJournalDateRef = {current: '2026-10-06'};
context.selectedEntityRef.current = journalId;
context.loadedContentEntityId = journalId;
context.refreshEntitiesForSector = async () => {};
context.refreshStatus = async () => {};
let persisted = '- [ ] First';
context.sourceContentRef.current = persisted;
context.apiFetch = async (path, options = {}) => {
  if (options.method === 'POST') throw Error('native wait timed out before persistence');
  return {ok: true, json: async () => ({content: persisted})};
};
await context.toggle('First', true, 1);
assert.equal(context.content, persisted);
persisted = '- [x] First';
await context.event({type: 'journal', path: journalId, action: 'modified'});
assert.equal(context.content, persisted, 'late native save reconciles after timeout readback');
console.log('Failed watcher initial-load fallback and late native save reconciliation passed.');
