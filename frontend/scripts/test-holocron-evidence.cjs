const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const React = require('react');
const renderer = require('react-test-renderer');
const swc = require('next/dist/build/swc');

const source = fs.readFileSync('src/components/HolocronEvidence.js', 'utf8');
const code = swc.transformSync(source, {
  filename: 'HolocronEvidence.js',
  jsc: { parser: { syntax: 'ecmascript', jsx: true }, transform: { react: { runtime: 'classic' } }, target: 'es2020' },
  module: { type: 'commonjs' },
}).code;

(async () => {
  const page = fs.readFileSync('src/app/page.js', 'utf8');
  const navigation = page.match(/onOpenJournal=\{\(path, day\) => \{([\s\S]*?)\n\s*\}\}/)[1];
  const selected = {};
  let remembered = { JOURNAL: { id: 'Journal/2026/09/2026-09-29.md' } };
  vm.runInNewContext(`(path, day) => {${navigation}}`, {
    pillars: [{ id: 'CHRONICLE', sectors: [{ id: 'JOURNAL' }] }],
    setActivePillar: value => { selected.pillar = value; },
    setSelectedJournalDate: value => { selected.day = value; },
    setActiveSector: value => { selected.sector = value; },
    setActiveEntity: value => { selected.entity = value; },
    setSectorActiveEntities: updater => { remembered = updater(remembered); },
  })('Journal/2026/09/2026-09-28.md', '2026-09-28');
  assert.equal(remembered.JOURNAL.id, selected.entity.id);
  assert.equal(selected.day, '2026-09-28');
  assert.equal(selected.sector, 'JOURNAL');
  assert.equal(selected.pillar, 'CHRONICLE');
  for (const transport of ['web', 'native']) {
    const calls = [], opened = [], module = { exports: {} };
    let current = { id: 'journal-2026-09-28', date: '2026-09-28', status: 'available', fingerprint: 'original',
      path: 'Journal/2026/09/2026-09-28.md', counts: { completed: 1, total: 2 } };
    vm.runInNewContext(code, { module, exports: module.exports, console,
      require: id => id === 'react' ? React : { apiFetch: async (path, options) => {
        calls.push({ path, options, transport }); return { ok: true, json: async () => current };
      } },
    });
    const evidence = { start_date: '2026-09-28', end_date: '2026-10-04', logged_days: 1,
      sources: [{ id: current.id, date: current.date, fingerprint: 'original', status: 'available' }],
      metrics: { precision_rate: { status: 'partial', rule: 'Checked / total', source_ids: [current.id] } } };
    let root;
    await renderer.act(async () => { root = renderer.create(React.createElement(module.exports.default,
      { weekId: '2026-W40', evidence, onOpenJournal: (...args) => opened.push(args) })); });
    const text = () => JSON.stringify(root.toJSON());
    const inspect = () => renderer.act(async () => root.root.findAllByType('button').find(b => b.props.children[0] === 'Inspect ').props.onClick());
    await inspect();
    assert.match(text(), /available/);
    await renderer.act(async () => root.root.findAllByType('button').find(b => b.props.children === 'Open source journal').props.onClick());
    assert.deepEqual(opened[0], [current.path, current.date]);
    current = { ...current, fingerprint: 'changed' };
    await inspect();
    assert.match(text(), /changed; regenerate/);
    assert(!root.root.findAllByType('button').some(b => b.props.children === 'Open source journal'));
    current = { id: current.id, status: 'missing' };
    await inspect();
    assert.match(text(), /missing/);
    assert(calls.every(call => !call.options?.method || call.options.method === 'GET'));
    assert(calls.every(call => call.path === '/api/holocron/weekly/2026-W40/evidence/journal-2026-09-28'));
    await renderer.act(async () => root.unmount());
  }
  console.log('Passed mounted evidence inspection: available, changed, deleted, source navigation and GET-only transport.');
})().catch(error => { console.error(error); process.exitCode = 1; });
