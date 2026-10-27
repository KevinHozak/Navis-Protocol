const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const React = require('react');
const renderer = require('react-test-renderer');
const swc = require('next/dist/build/swc');

const source = fs.readFileSync('src/components/JournalCalendar.js', 'utf8');
const code = swc.transformSync(source, { filename: 'JournalCalendar.js',
  jsc: { parser: { syntax: 'ecmascript', jsx: true }, transform: { react: { runtime: 'classic' } }, target: 'es2020' },
  module: { type: 'commonjs' },
}).code;
const deferred = () => { let resolve, reject; const promise = new Promise((a, b) => { resolve = a; reject = b; }); return { promise, resolve, reject }; };
const success = dates => ({ ok: true, json: async () => ({ dates, availability: 'available' }) });

(async () => {
  for (const transport of ['web', 'native']) {
    const calls = [], opened = [], callbacks = [], module = { exports: {} };
    class FixtureDate extends Date { constructor(...args) { super(...(args.length ? args : ['2026-10-27T12:00:00-05:00'])); } }
    vm.runInNewContext(code, { module, exports: module.exports, console, Date: FixtureDate, AbortController, setTimeout, clearTimeout,
      require: name => name === 'react' ? { ...React, useCallback: (fn, deps) => { const callback = React.useCallback(fn, deps); callbacks.push(callback); return callback; } } : name.includes('journalDay') ? { journalDay: () => '2026-10-27' }
        : name.includes('AsyncJobModal') ? { default: () => null }
          : { apiFetch: (path, options) => { const response = deferred(); calls.push({ path, options, response, transport }); return response.promise; } },
    });
    let root;
    await renderer.act(async () => { root = renderer.create(React.createElement(module.exports.default,
      { selectedDate: '2026-10-02', onDateSelect: day => opened.push(day) })); });
    const text = () => JSON.stringify(root.toJSON());
    const latest = () => calls.at(-1);
    const settle = async value => renderer.act(async () => latest().response.resolve(value));
    const retry = async () => renderer.act(async () => { root.root.findAllByType('button').find(b => b.props.children === 'Retry dates').props.onClick(); });
    assert.match(text(), /Loading journal dates/);
    assert(!text().includes('No journal entries'));
    await settle({ ok: false, status: 503, json: async () => ({ detail: 'private path' }) });
    assert.match(text(), /Journal dates unavailable/);
    assert(!text().includes('private path') && !text().includes('No journal entries'));
    await retry(); await settle(success([]));
    assert.match(text(), /No journal entries this month/);
    assert(!text().includes('Retry dates'));
    // Reload via month navigation; old month requests must not replace new data.
    await renderer.act(async () => root.root.findByProps({ title: 'Next month' }).props.onClick());
    const november = latest();
    await renderer.act(async () => root.root.findByProps({ title: 'Previous month' }).props.onClick());
    assert(november.options.signal.aborted);
    await settle(success(['2026-10-02']));
    await renderer.act(async () => november.response.resolve(success(['2026-11-01'])));
    assert(!text().includes('Load 2026-11-01'));
    const day = root.root.findByProps({ title: 'Load 2026-10-02' });
    assert.equal(day.props.disabled, false);
    await renderer.act(async () => day.props.onClick());
    assert.equal(opened.at(-1), '2026-10-02');
    // Exercise the actual memoized callback also used by rollover completion.
    let refresh;
    await renderer.act(async () => { refresh = callbacks[0](2026, 10); });
    assert(root.root.findAllByType('button').filter(b => b.props.title?.includes('2026-10-02')).every(b => b.props.disabled));
    await settle({ ok: false, status: 503 }); await refresh;
    assert.match(text(), /Previously loaded dates shown/);
    assert(!text().includes('No journal entries'));
    await retry(); await settle(success(['2026-10-02']));
    await renderer.act(async () => root.root.findByProps({ title: 'Next month' }).props.onClick());
    await settle({ ok: false, status: 501 });
    assert.match(text(), /Calendar unavailable in this desktop version/);
    await retry();
    await renderer.act(async () => latest().response.reject(new Error('Native Python unavailable C:/Private')));
    assert.match(text(), /Journal dates unavailable/);
    assert(!text().includes('C:/Private'));
    await retry(); await settle(success(['2026-10-32']));
    assert.match(text(), /Journal date response unavailable/);
    await retry();
    await renderer.act(async () => latest().response.reject(Object.assign(new Error('timeout'), { name: 'AbortError' })));
    assert.match(text(), /Journal dates timed out/);
    await retry(); await settle({ ok: true, json: async () => { throw new SyntaxError('private malformed body'); } });
    assert.match(text(), /Journal dates unavailable/);
    assert(!text().includes('private malformed body'));
    assert(calls.every(call => !call.options.method || call.options.method === 'GET'));
    const pending = latest();
    await renderer.act(async () => root.unmount());
    assert(pending.options.signal.aborted);
    // Settle abandoned requests without state updates or lingering test promises.
    for (const call of calls) call.response.resolve(success([]));
  }
  console.log('Passed mounted calendar loading, unavailable/unsupported, retry, empty, valid entry and month-race scenarios across web/native doubles.');
})().catch(error => { console.error(error); process.exitCode = 1; });
