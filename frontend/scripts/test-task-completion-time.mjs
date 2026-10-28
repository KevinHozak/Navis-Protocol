import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';
import React from 'react';
import TestRenderer, {act} from 'react-test-renderer';
import swc from 'next/dist/build/swc/index.js';
import * as time from '../src/lib/taskCompletionTime.mjs';

const first = '2026-11-01T06:30:00Z', second = '2026-11-01T07:30:00Z';
assert.match(time.formatCompletionTime(first, 'America/Chicago'), /Nov 1, 2026.*1:30:00 AM CDT/);
assert.match(time.formatCompletionTime(second, 'America/Chicago'), /Nov 1, 2026.*1:30:00 AM CST/);
assert.match(time.formatCompletionTime('2026-03-08T07:59:59Z', 'America/Chicago'), /1:59:59 AM CST/);
assert.match(time.formatCompletionTime('2026-03-08T08:00:00Z', 'America/Chicago'), /3:00:00 AM CDT/);
assert.match(time.formatCompletionTime('2026-10-28T04:59:59Z'), /Oct 27, 2026.*11:59:59 PM CDT/);
assert.match(time.formatCompletionTime('2026-10-28T05:00:00Z'), /Oct 28, 2026.*12:00:00 AM CDT/);
assert.match(time.formatCompletionTime(first, 'Asia/Tokyo'), /3:30:00 PM GMT\+9/);
assert.equal(time.navisTimezone('invalid'), 'America/Chicago');
for (const value of [null, '', '2026-11-01', '2026-11-01T01:30:00', 'nonsense']) {
  assert.equal(time.formatCompletionTime(value), 'Completion time unknown');
}
assert.equal(time.completionMetadata(`Task <!-- navis-completion:{"completed_at":"${first}","history":[]} -->`), first);
assert.equal(time.completionMetadata('Task'), null);

await swc.loadBindings();
const module = {exports: {}};
const code = swc.transformSync(await readFile(new URL('../src/components/TaskStatusPicker.js', import.meta.url), 'utf8'), {filename:'TaskStatusPicker.js', jsc:{parser:{syntax:'ecmascript',jsx:true},transform:{react:{runtime:'classic'}}},module:{type:'commonjs'}}).code;
vm.runInNewContext(code, {module, exports:module.exports, require:name => name === 'react' ? React : time});
const {default: Picker, TaskTimezone} = module.exports;
let tree;
await act(async () => {tree = TestRenderer.create(React.createElement(TaskTimezone.Provider, {value:'Asia/Tokyo'}, React.createElement(Picker, {value:'done', completedAt:first, label:'Synthetic task'})));});
assert.match(tree.root.findByType('time').children.join(''), /3:30:00 PM GMT\+9/);
assert.equal(tree.root.findByType('time').props.dateTime, first);
await act(async () => {tree.update(React.createElement(Picker, {value:'done', completedAt:'2026-11-01', label:'Legacy task'}));});
assert.equal(tree.root.findByType('time').children.join(''), 'Completion time unknown');
await act(async () => {tree.update(React.createElement(Picker, {value:'pending', completedAt:first, label:'Reopened task'}));});
assert.equal(tree.root.findAllByType('time').length, 0);
await act(async () => tree.unmount());
console.log('Completion time: configured zone, midnight, DST folds/gaps, unknown legacy and reopened display passed.');
