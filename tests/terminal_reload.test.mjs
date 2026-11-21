// Exercise the real terminal module against an in-memory API and DOM boundary.
// No PostgreSQL, production URL, credentials, hardware, or financial engine runs.
// Run: node --experimental-vm-modules --test tests/terminal_reload.test.mjs
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';
import {randomUUID} from 'node:crypto';
import {test} from 'node:test';

const tableId='a'.repeat(32);
const origin='https://progressive.example.invalid';
const terminalSource=await readFile(new URL('../web/terminal.mjs',import.meta.url),'utf8');
const keysSource=await readFile(new URL('../web/keys.mjs',import.meta.url),'utf8');
const bridgeSource=await readFile(new URL('../web/baccarat/bridge.js',import.meta.url),'utf8');
const copy=value=>JSON.parse(JSON.stringify(value));
class Storage extends Map {
 getItem(key){return this.has(key)?this.get(key):null}
 setItem(key,value){this.set(key,String(value))}
 removeItem(key){this.delete(key)}
}
class Target {
 listeners=new Map();
 addEventListener(type,fn){const handlers=this.listeners.get(type)||[];handlers.push(fn);this.listeners.set(type,handlers)}
 async emit(type,event={}){for(const fn of this.listeners.get(type)||[]){await fn(event);if(event.stopped)break}}
 dispatchEvent(event){void this.emit(event.type,event);return true}
}
class Element extends Target {
 constructor(tagName='DIV'){super();this.tagName=tagName;this.open=false;this.hidden=false;this.value='';this.textContent='';this.innerHTML='';this.children=[];this.contentWindow={focus(){},postMessage(){}}}
 showModal(){this.open=true}
 close(){this.open=false}
 replaceChildren(...nodes){this.children=nodes}
 append(node){this.children.push(node)}
 querySelector(){return null}
 focus(){}
}
function event(code,extra={}){return {code,repeat:false,target:{tagName:'BODY'},preventDefault(){this.prevented=true},stopImmediatePropagation(){this.stopped=true},...extra}}
const response=(status,data)=>({status,ok:status>=200&&status<300,json:async()=>copy(data)});
function serverFixture({open=false}={}){
 const server={clock:Date.now(),calls:[],receipts:new Map(),barrier:null};
 server.state={environment:'test',config:{version:1,tiers:[]},pools:{1:400000,2:800000,3:2000000,4:10000000,5:25000000},claims:open?[]:[{id:'approved-fixture-claim',round_id:'confirmed-round',box:3,tier:1,status:'approved'}],
  tables:[{id:tableId,name:'Isolated fixture',number:'TEST',boxes:5,game:'poker',mode:'progressive',round_id:open?null:'confirmed-round',next_round_id:'next-round',device_sequence:7,operator:null}],
  rounds:open?[]:[{id:'confirmed-round',table_id:tableId,status:'confirmed',boxes:[1,3,5]}]};
 server.snapshot=()=>({...copy(server.state),server_time:new Date(server.clock).toISOString()});
 server.financial=()=>copy({pools:server.state.pools,rounds:server.state.rounds,claims:server.state.claims,round_id:server.state.tables[0].round_id,sequence:server.state.tables[0].device_sequence});
 server.fetch=async(url,options={},online=true)=>{
  if(!online)throw TypeError('Fixture network unavailable');
  const path=new URL(url,origin).pathname,method=options.method||'GET',body=options.body?JSON.parse(options.body):null;
  server.calls.push({path,method,body});
  const t=server.state.tables[0];
  if(path==='/api/v1/state')return response(200,server.snapshot());
  if(path==='/api/v1/operator'){
   if(t.operator&&t.operator.id!==body.operator_id&&Date.parse(t.operator.until)>server.clock)return response(409,{detail:'Another operator controls this table'});
   t.operator={id:body.operator_id,until:new Date(server.clock+15000).toISOString()};return response(200,{lease_seconds:15});
  }
  if(path==='/api/v1/stream')return {ok:true,body:{getReader:()=>({read:()=>new Promise(()=>{})})}};
  if(path.startsWith('/api/v1/commands/'))return server.receipts.has(path.split('/').at(-1))?response(200,server.receipts.get(path.split('/').at(-1))):response(404,{detail:'Command not committed'});
  if(path==='/api/v1/commands'&&method==='POST'){
   if(server.barrier)await server.barrier;
   if(server.receipts.has(body.command_id))return response(200,server.receipts.get(body.command_id));
   if(body.op==='confirm'){
    assert.equal(t.round_id,null);assert.equal(body.payload.round_id,t.next_round_id);
    t.round_id=body.payload.round_id;server.state.rounds.push({id:t.round_id,table_id:tableId,status:'confirmed',boxes:body.payload.boxes});
   }else if(body.op==='mode')t.mode=body.payload.mode;
   else if(body.op!=='baccarat_result')throw Error('Unexpected financial command in reload test: '+body.op);
   t.device_sequence=body.sequence;
   const result={command_id:body.command_id,acknowledgment:{sequence:body.sequence,committed:true},result:{}};server.receipts.set(body.command_id,result);return response(200,result);
  }
  throw Error('Unexpected fixture route '+method+' '+path);
 };
 return server;
}
async function eventually(predicate){for(let n=0;n<100;n++){if(predicate())return;await new Promise(resolve=>setImmediate(resolve))}assert.fail('Client did not reach expected state')}
async function terminal(server,storage={}){
 const local=storage.local||new Storage(),session=storage.session||new Storage();
 local.setItem('premier-device-token:'+tableId,'fixture-only-device-token');
 const elements=new Map(),document=new Target(),window=new Target(),timers=new Map();
 document.getElementById=id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id)};
 document.createElement=name=>new Element(name.toUpperCase());document.body=new Element('BODY');
 window.focus=()=>{};
 const navigator={onLine:true},location={pathname:'/table/'+tableId,search:'',origin,reloads:0,reload(){this.reloads++}};
 const clock=class extends Date {constructor(...args){super(...(args.length?args:[server.clock]))}static now(){return server.clock}};
 const context=vm.createContext({window,document,navigator,location,localStorage:local,sessionStorage:session,crypto:{randomUUID},Date:clock,
  history:{replaceState(){}},AbortController,TextDecoder,console:{warn(){}},
  setTimeout(){return 1},setInterval(fn,delay){timers.set(delay,fn);return delay},
  fetch:(url,opts)=>server.fetch(url,opts,navigator.onLine)});
 const display={last:null};
 const displayModule=new vm.SyntheticModule(['renderDisplay','renderWinner','clearDisplay'],function(){
  this.setExport('renderDisplay',(state,t,r,selected,enabled,reload)=>{display.last={state:copy(state),table:copy(t),round:r&&copy(r),selected:[...selected],enabled,reload}});
  this.setExport('renderWinner',()=>{});this.setExport('clearDisplay',()=>{});
 },{context});
 const controls=new vm.SyntheticModule(['installTestControls'],function(){this.setExport('installTestControls',()=>()=>{})},{context});
 const keys=new vm.SourceTextModule(keysSource,{context}),module=new vm.SourceTextModule(terminalSource,{context});
 await module.link(specifier=>({'./keys.mjs':keys,'./display.mjs':displayModule,'./test-controls.mjs':controls}[specifier]));
 await module.evaluate();
 const client={local,session,document,window,navigator,location,display,elements,element:document.getElementById,
  press:(code,extra)=>document.emit('keydown',event(code,extra)),pulse:()=>timers.get(5000)(),
  async settings(){await this.press('F2')},async reloadButton(){await this.settings();this.element('reload-screen').onclick()}};
 return client;
}
const posts=server=>server.calls.filter(x=>x.method==='POST'&&x.path==='/api/v1/commands');

test('explicit reload preserves server round/pools/claims; lease is reacquired without bypass',async()=>{
 const server=serverFixture(),before=server.financial(),first=await terminal(server);
 await eventually(()=>first.element('connection').hidden);
 await first.reloadButton();assert.equal(first.location.reloads,1);assert.deepEqual(server.financial(),before);assert.equal(posts(server).length,0);
 const second=await terminal(server,first);
 await eventually(()=>server.calls.filter(x=>x.path==='/api/v1/operator').length>=2);
 assert.equal(second.element('connection').hidden,false);
 server.clock+=16000;await second.pulse();
 assert.equal(second.element('connection').hidden,true);assert.equal(second.display.last.round.id,'confirmed-round');
 assert.deepEqual(second.display.last.round.boxes,[1,3,5]);assert.equal(second.display.last.table.boxes,5);
 assert.deepEqual(server.financial(),before);assert.equal(posts(server).length,0);
});

test('reload is opt-in, leaves F4 unchanged, and ignores editable inputs and repeats',async()=>{
 const server=serverFixture(),client=await terminal(server);await eventually(()=>client.element('connection').hidden);
 await client.press('NumpadDivide');assert.equal(client.location.reloads,0);
 await client.settings();assert.equal(client.element('reload-key').value,'');
 client.element('reload-key').value='NumpadDivide';await client.element('service-form').emit('submit',{preventDefault(){}});
 await client.press('NumpadDivide',{target:{tagName:'INPUT'}});await client.press('NumpadDivide',{repeat:true});assert.equal(client.location.reloads,0);
 await client.press('F4');assert.equal(server.state.tables[0].mode,'baccarat');assert.equal(server.state.tables[0].round_id,'confirmed-round');assert.equal(client.location.reloads,0);
 await client.press('NumpadDivide');assert.equal(client.location.reloads,1);assert.deepEqual(posts(server).map(x=>x.body.op),['mode']);
});

test('configured reload cannot interrupt a financial request in flight',async()=>{
 const server=serverFixture({open:true}),local=new Storage();local.setItem('premier-key-mapping',JSON.stringify({reload:'NumpadDivide'}));
 const client=await terminal(server,{local});await eventually(()=>client.element('connection').hidden);
 let release;server.barrier=new Promise(resolve=>{release=resolve});
 await client.press('Numpad1');await client.press('NumpadEnter');await eventually(()=>posts(server).length===1);
 await client.press('NumpadDivide');assert.equal(client.location.reloads,0);assert.ok(client.session.getItem('premier-pending-intent:'+tableId));
 release();await eventually(()=>server.state.tables[0].round_id==='next-round');
 assert.equal(posts(server).length,1);assert.deepEqual(server.state.rounds[0].boxes,[1]);
});

test('reload retains unknown outcome and recovers already committed ID without another command',async()=>{
 const server=serverFixture(),first=await terminal(server);await eventually(()=>first.element('connection').hidden);
 const intent={command_id:'fixture-committed',op:'confirm',payload:{table_id:tableId,round_id:'confirmed-round',boxes:[1,3,5]},sequence:7,operator_id:'previous-operator'};
 const key='premier-pending-intent:'+tableId;first.session.setItem(key,JSON.stringify(intent));server.receipts.set(intent.command_id,{result:{},acknowledgment:{sequence:7,committed:true}});
 await first.reloadButton();assert.deepEqual(JSON.parse(first.session.getItem(key)),intent);
 server.clock+=16000;const second=await terminal(server,first);await eventually(()=>second.element('connection').hidden);
 assert.equal(second.session.getItem(key),null);assert.equal(posts(server).length,0);assert.equal(second.display.last.round.id,'confirmed-round');
});

test('uncommitted intent after reload retries the same ID/sequence and expected round once',async()=>{
 const server=serverFixture({open:true}),session=new Storage();
 const intent={command_id:'fixture-uncommitted',op:'confirm',payload:{table_id:tableId,round_id:'next-round',boxes:[1,5]},sequence:8,operator_id:'previous-operator'};
 session.setItem('premier-pending-intent:'+tableId,JSON.stringify(intent));
 const client=await terminal(server,{session});await eventually(()=>client.element('connection').hidden);
 assert.equal(posts(server).length,1);const sent=posts(server)[0].body;
 assert.equal(sent.command_id,intent.command_id);assert.equal(sent.sequence,intent.sequence);assert.deepEqual(sent.payload,intent.payload);
 assert.equal(client.session.getItem('premier-pending-intent:'+tableId),null);assert.deepEqual(client.display.last.round.boxes,[1,5]);
});

test('Baccarat reload messages require the current iframe, origin, table and configured key',async()=>{
 const server=serverFixture(),local=new Storage();local.setItem('premier-key-mapping',JSON.stringify({reload:'NumpadDivide'}));
 const client=await terminal(server,{local});await eventually(()=>client.element('connection').hidden);
 const message={origin,source:client.element('baccarat').contentWindow,data:{type:'premier-reload',table_id:tableId,code:'NumpadDivide'}};
 await client.window.emit('message',{...message,origin:'https://other.invalid'});
 await client.window.emit('message',{...message,source:{}});
 await client.window.emit('message',{...message,data:{...message.data,table_id:'b'.repeat(32)}});
 await client.window.emit('message',{...message,data:{...message.data,code:'F4'}});
 assert.equal(client.location.reloads,0);await client.window.emit('message',message);assert.equal(client.location.reloads,1);assert.equal(posts(server).length,0);
});

test('rejected second iframe command cannot release the in-flight command guard',async()=>{
 const server=serverFixture(),local=new Storage();local.setItem('premier-key-mapping',JSON.stringify({reload:'NumpadDivide'}));
 const client=await terminal(server,{local});await eventually(()=>client.element('connection').hidden);
 let release;server.barrier=new Promise(resolve=>{release=resolve});
 const source=client.element('baccarat').contentWindow,messages=[];source.postMessage=data=>messages.push(data);
 const message={origin,source,data:{type:'premier-baccarat',table_id:tableId,request_id:'first',op:'baccarat_result',payload:{result:'player'}}};
 const first=client.window.emit('message',message);await eventually(()=>posts(server).length===1);
 await client.window.emit('message',{...message,data:{...message.data,request_id:'second'}});
 assert.equal(messages[0].request_id,'second');assert.equal(messages[0].error,'Baccarat command unavailable');
 await client.press('NumpadDivide');assert.equal(client.location.reloads,0);assert.equal(posts(server).length,1);
 release();await first;assert.equal(posts(server).length,1);assert.equal(messages[1].request_id,'first');assert.equal(messages[1].error,undefined);
 await client.press('NumpadDivide');assert.equal(client.location.reloads,1);
});

test('Baccarat bridge keeps F4 mode and forwards only explicitly configured reload',async()=>{
 const window=new Target(),document=new Target(),messages=[],parent={postMessage:data=>messages.push(data)};
 const context=vm.createContext({window,document,parent,location:{origin,search:'?table_id='+tableId},URLSearchParams,crypto:{randomUUID},Event,Promise,Map,setTimeout,clearTimeout});
 new vm.Script(bridgeSource).runInContext(context);messages.length=0;
 const update=reload_key=>window.emit('message',{origin,source:parent,data:{type:'premier-table',table_id:tableId,enabled:true,reload_key}});
 await update(null);await document.emit('keydown',event('NumpadDivide'));assert.equal(messages.length,0);
 await document.emit('keydown',event('F4'));assert.equal(messages[0].type,'premier-mode');messages.length=0;
 await update('NumpadDivide');await document.emit('keydown',event('NumpadDivide',{target:{tagName:'INPUT'}}));assert.equal(messages.length,0);
 await document.emit('keydown',event('NumpadDivide'));assert.deepEqual(copy(messages),[{type:'premier-reload',table_id:tableId,code:'NumpadDivide'}]);
});
