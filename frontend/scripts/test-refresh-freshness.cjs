const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const React = require('react');
const renderer = require('react-test-renderer');
const swc = require('next/dist/build/swc');
const deferred = () => { let resolve, reject; const promise = new Promise((a,b) => {resolve=a;reject=b;}); return {promise,resolve,reject}; };
const response = (body, ok=true) => ({ok,status:ok?200:503,json:async()=>body});
const payload = week => ({week_id:week,summary:{},tactical_debrief:`Debrief ${week}`,generated_at:'2026-10-26T12:00:00Z'});
function load(file, api, modules={}) {
  const module = {exports:{}};
  const code=swc.transformSync(fs.readFileSync(file,'utf8'),{filename:file,jsc:{parser:{syntax:'ecmascript',jsx:true},transform:{react:{runtime:'classic'}},target:'es2020'},module:{type:'commonjs'}}).code;
  vm.runInNewContext(code,{React,module,exports:module.exports,console,Date,AbortController,AbortSignal,process:{env:{}},window:{},
    setTimeout:()=>0,clearTimeout:()=>{},setInterval:()=>0,clearInterval:()=>{},
    require:id=>id==='react'?React:id==='framer-motion'?{motion:new Proxy({},{get:(_,k)=>k}),AnimatePresence:p=>p.children}
      :id.includes('desktopApi')?api:id.includes('journalDay')?{journalDay:()=> '2026-10-27'}
      :{__esModule:true,default:modules[id.split('/').at(-1)]||(()=>null)}});
  return module.exports;
}
(async()=>{
for(const transport of ['web','native']) {
  const calls=[];
  const api={apiFetch:(url,options)=>{if(url.endsWith('/manifest'))return Promise.resolve(response([]));const d=deferred();calls.push({...d,url,options,transport});return d.promise;},subscribeVaultStream:()=>()=>{},vaultAssetUrl:x=>x};
  const Fresh=load('src/components/ReadFreshness.js',api);
  assert.equal(Fresh.timestamp('2026-10-26T12:00:00'),'Unknown');
  assert.match(Fresh.timestamp('2026-10-26'),/timezone unknown/);
  const View=load('src/components/WeeklyHolocronView.js',api,{ReadFreshness:Fresh.default}).default;
  let root;
  const update=week=>renderer.act(async()=>root.update(React.createElement(View,{activeWeekId:week})));
  const settle=(index,body,ok=true)=>renderer.act(async()=>calls[index].resolve(response(body,ok)));
  const text=()=>JSON.stringify(root.toJSON());
  const click=label=>renderer.act(async()=>{root.root.findAllByType('button').find(b=>b.props.children===label).props.onClick();});
  await renderer.act(async()=>{root=renderer.create(React.createElement(View,{activeWeekId:'2026-W40'}));});
  await update('2026-W41'); await settle(1,payload('2026-W41')); await settle(0,payload('2026-W40'));
  assert.match(text(),/Debrief 2026-W41/);assert.doesNotMatch(text(),/Debrief 2026-W40/);
  assert.match(text(),/Last successful read/);assert.match(text(),/2026-10-26 12:00/);
  await click('Refresh');await settle(2,{},false);assert.match(text(),/Refresh failed/);assert.match(text(),/retained data/);assert.match(text(),/Debrief 2026-W41/);
  await click('Retry refresh');await settle(3,payload('2026-W40'));assert.match(text(),/Refresh failed/);assert.match(text(),/Debrief 2026-W41/);
  await click('Retry refresh');await settle(4,payload('2026-W41'));assert.doesNotMatch(text(),/Refresh failed/);
  await click('🔄 Regenerate'); await update('2026-W42');await settle(6,payload('2026-W42'));await settle(5,payload('2026-W41'));assert.match(text(),/Debrief 2026-W42/);
  await click('✨ AI Tactical Debrief');await update('2026-W43');await settle(8,payload('2026-W43'));await settle(7,{tactical_debrief:'obsolete AI'});assert.doesNotMatch(text(),/obsolete AI/);
  await update('2026-W44');await update('2026-W45');await settle(10,payload('2026-W45'));await renderer.act(async()=>calls[9].reject(new Error('old failure')));assert.doesNotMatch(text(),/old failure/);assert.match(text(),/Debrief 2026-W45/);
  await renderer.act(async()=>root.unmount());
  const statusCalls=[];
  const homeApi={...api,apiFetch:url=>{if(url==='/api/status'){const d=deferred();statusCalls.push(d);return d.promise;}return Promise.resolve(response([]));}};
  const Home=load('src/app/page.js',homeApi,{ReadFreshness:Fresh.default,SecurityGuard:p=>p.children}).default;
  await renderer.act(async()=>{root=renderer.create(React.createElement(Home));});
  await renderer.act(async()=>statusCalls[0].resolve(response({last_updated:'2026-10-25',squad:[]})));
  assert.match(text(),/Operational marker/);assert.match(text(),/2026-10-25/);
  const readBefore=root.root.findByType(Fresh.default).props.lastRead;
  await click('Refresh');await renderer.act(async()=>statusCalls[1].resolve(response({},false)));
  assert.match(text(),/Refresh failed/);assert.equal(root.root.findByType(Fresh.default).props.lastRead,readBefore);assert.match(text(),/2026-10-25/);
  await click('Retry refresh');await renderer.act(async()=>statusCalls[2].reject(new Error('lost transport')));assert.match(text(),/retained data/);
  await click('Retry refresh');await renderer.act(async()=>statusCalls[3].resolve(response({last_updated:'2026-10-26',squad:[]})));assert.doesNotMatch(text(),/Refresh failed/);
  await renderer.act(async()=>root.unmount());
}
console.log('Passed mounted dashboard/Holocron refresh and read/regenerate/debrief race checks (web/native doubles).');
})().catch(e=>{console.error(e);process.exitCode=1;});
