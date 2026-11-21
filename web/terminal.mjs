import {action,reloadKey} from './keys.mjs';
import {installTestControls} from './test-controls.mjs';
import {renderDisplay,renderWinner,clearDisplay} from './display.mjs';
const $=id=>document.getElementById(id), id=()=>crypto.randomUUID();
let requestedTableId=location.pathname.match(/^\/table\/([0-9a-f]{32})$/)?.[1]||null;
const tokenKey=tid=>'premier-device-token:'+tid, pendingKey=()=> 'premier-pending-intent:'+(requestedTableId||'legacy');
let token=(requestedTableId&&localStorage.getItem(tokenKey(requestedTableId)))||localStorage.getItem('premier-device-token'), state=JSON.parse(sessionStorage.getItem('premier-last-view')||'null'), online=false, busy=false, selected=new Set(), stage=null, draft={}, lastStateAt=0, winners=[], seen=new Set(), offset=0, streamAbort=null;
if(requestedTableId&&state?.tables[0]?.id!==requestedTableId)state=null;
const operator=id(), mapping={claim:'NumpadMultiply',settings:'F2',mode:'F4',reload:null,...JSON.parse(localStorage.getItem('premier-key-mapping')||'null')};
mapping.reload=reloadKey(mapping);
const updateTestControls=installTestControls(()=>({state,claimCode:mapping.claim}));
// Only device credentials and key preferences persist. No local financial engine/balances.
const headers=(auth=token)=>({'Authorization':`Bearer ${auth}`,'Content-Type':'application/json',...(auth===token&&requestedTableId?{'X-Premier-Table':requestedTableId}:{})});
async function api(path,body,auth=token,method='POST'){
 const r=await fetch('/api/v1/'+path,{method,headers:headers(auth),body:body===undefined?undefined:JSON.stringify(body)});
 const data=await r.json(); if(!r.ok){const error=Error(data.detail||'Request failed');error.status=r.status;throw error;} return data;
}
const table=()=>state?.tables[0], round=()=>state?.rounds.find(r=>r.id===table()?.round_id);
function render(){updateTestControls();if(state&&table())renderDisplay(state,table(),round(),selected,online&&navigator.onLine,mapping.reload)}
function reloadScreen(){
 if(busy)return;
 // Keep credentials and any uncertain command ID. On reconnect the server is
 // authoritative; reloading never confirms/closes a round or changes balances.
 streamAbort?.abort();location.reload();
}
async function toggleMode(){
 if(busy||stage||!online||!navigator.onLine)return;
 busy=true;try{await command('mode',{table_id:table().id,mode:table().mode==='baccarat'?'progressive':'baccarat'});if(table().mode==='baccarat')$('baccarat').contentWindow?.focus();else window.focus()}catch(e){show('Смена режима','','notice');$('error').textContent=e.message}finally{busy=false}
}
window.addEventListener('message',e=>{if(e.origin===location.origin&&e.source===$('baccarat').contentWindow&&e.data?.type==='premier-mode'&&e.data.table_id===table()?.id)toggleMode()});
window.addEventListener('message',e=>{if(e.origin===location.origin&&e.source===$('baccarat').contentWindow&&e.data?.type==='premier-reload'&&e.data.table_id===table()?.id&&e.data.code===mapping.reload&&mapping.reload)reloadScreen()});
window.addEventListener('message',async e=>{
 if(e.origin!==location.origin||e.source!==$('baccarat').contentWindow||e.data?.type!=='premier-baccarat'||e.data.table_id!==table()?.id)return;
 const data=e.data,ops=['baccarat_result','baccarat_pair','baccarat_undo','baccarat_shoe','baccarat_settings'];
 const reply={type:'premier-baccarat-result',table_id:table().id,request_id:data.request_id};
 if(!ops.includes(data.op)||busy||stage){reply.error='Baccarat command unavailable';e.source.postMessage(reply,location.origin);return}
 busy=true;try{const response=await command(data.op,{...data.payload,table_id:table().id});reply.result=response.result}catch(error){reply.error=error.message}finally{busy=false;e.source.postMessage(reply,location.origin)}
});
function show(title,body,step){stage=step;$('service-title').textContent=title;$('service-body').innerHTML=body;$('error').textContent='';if(!$('service').open)$('service').showModal();$('service-body').querySelector('input')?.focus()}
function close(){stage=null;draft={};$('service-body').replaceChildren();$('service').close()}
function settings(){show('Настройки терминала','<label>Клавиша заявления <input id="claim-key"></label><p>F2 — настройки; F4 — смена режима.</p><label>Клавиша обновления экрана <select id="reload-key"><option value="">Не назначена</option value="NumpadDivide">NumPad /</option></select></label><p>Обновление сохраняет подтверждённый раунд, суммы и заявки на сервере. Неотправленный ввод будет отменён. После обновления дождитесь восстановления связи. Ввод может оставаться заблокированным ещё 15 секунд.</p><button type="button" id="reload-screen">Обновить экран</button><p>Baccarat MAX подключён. История результатов хранится на сервере отдельно для этого стола.</p>','settings');$('claim-key').value=mapping.claim;$('reload-key').value=mapping.reload||'';$('reload-screen').onclick=reloadScreen}
function claimStep(){draft.boxes=[];show('Выигрыш — участвующие боксы',`Выберите боксы 1–${table().boxes} на NumPad, затем Enter. Повторное нажатие снимает выбор. Укажите только старшую комбинацию каждого бокса.`,'box')}
async function command(op,payload,auth=token){
 if(!online||!navigator.onLine)throw Error('Нет подтверждённой связи с сервером');
 const intent={command_id:id(),op,payload,operator_id:operator,...(auth===token?{sequence:(table()?.device_sequence||0)+1}:{})};
 if(auth===token)sessionStorage.setItem(pendingKey(),JSON.stringify(intent));
 try{const result=await api('commands',intent,auth);if(auth===token){sessionStorage.removeItem(pendingKey());await refresh()}return result}catch(e){
  if(e.status){if(auth===token)sessionStorage.removeItem(pendingKey());throw e}
  // An uncertain response is recovered with the SAME ID. Never regenerate money intent.
  try {const result=await api('commands/'+intent.command_id,undefined,auth,'GET');if(auth===token){sessionStorage.removeItem(pendingKey());await refresh()}return result} catch {}
  if(!navigator.onLine)throw e;
  const result=await api('commands',intent,auth);if(auth===token){sessionStorage.removeItem(pendingKey());await refresh()}return result;
 }
}
async function submit(){
 if(busy)return;busy=true;
 try{
  if(stage==='pair'){
   const result=await api('pair',{code:$('pair-code').value,name:$('device-name').value,app_version:'1.0.0-test',...(requestedTableId?{table_id:requestedTableId}:{})});token=result.token;requestedTableId=result.table_id;localStorage.setItem(tokenKey(requestedTableId),token);history.replaceState(null,'','/table/'+requestedTableId);close();connect();return;
  }
  if(stage==='settings'){const next={...mapping,claim:$('claim-key').value,reload:$('reload-key').value||null};if(next.reload&&reloadKey(next)!==next.reload)throw Error('Клавиша обновления занята или не поддерживается');Object.assign(mapping,next);localStorage.setItem('premier-key-mapping',JSON.stringify(mapping));close();render();return}
  if(stage==='pending-choice'){if(draft.choice===1){draft.pendingClaims=state.claims.filter(x=>x.round_id===round().id&&x.status==='pending');draft.claim=draft.pendingClaims[0];show('Продолжить подтверждение','<label>Учётная запись <input id="manager-name" autocomplete="off"></label><label>Пароль/PIN <input id="manager-password" type="password" autocomplete="off"></label>','approval');return}if(draft.choice===2){draft={};claimStep();return}throw Error('Выберите 1 или 2')}
  if(stage==='box'){if(!draft.boxes?.length||draft.boxes.some(n=>!round()?.boxes.includes(n)))throw Error('Выберите участвующие боксы');show('Комбинация 1–5','1 Flush · 2 Full House · 3 Four of a Kind · 4 Straight Flush · 5 Royal Flush','tier');return}
  if(stage==='tier'){if(![1,2,3,4,5].includes(draft.tier))throw Error('Выберите комбинацию');show('Тип выплаты','1 — first five · 2 — seven cards','type');return}
  if(stage==='type'){if(!draft.type)throw Error('Выберите 1 или 2');show('Подтвердить заявление',`Боксы ${draft.boxes.join(", ")} · комбинация ${draft.tier} · ${draft.type}. Enter подтверждает.`,'claim-confirm');return}
  if(stage==='claim-confirm'){
   const result=await command('claims',{table_id:table().id,round_id:round().id,boxes:draft.boxes,tier:draft.tier,type:draft.type});draft.pendingClaims=result.result.claims.filter(c=>c.status==='pending');draft.claim=draft.pendingClaims[0]||result.result.claims[0];
   if(draft.claim.status==='pending'){show('Подтверждение уполномоченного сотрудника','<label>Учётная запись <input id="manager-name" autocomplete="off"></label><label>Пароль/PIN <input id="manager-password" type="password" autocomplete="off"></label>','approval');return}
   if(draft.claim.status==='disputed'){show('Спорная заявка сохранена','Автоматическая выплата заблокирована. Обратитесь к администратору.','notice');return}
   close();return;
  }
  if(stage==='approval'){
   let manager=await api('login',{name:$('manager-name').value,password:$('manager-password').value});$('manager-password').value='';
   try{
    draft.pendingClaims||=[draft.claim];
    while(draft.pendingClaims.length){
     draft.claim=draft.pendingClaims[0];
     const result=await command('approve',{claim_id:draft.claim.id},manager.token);
     if(result.result.status==='pending'){show('Первый этап принят','Введите отдельную учётную запись администратора.<label>Учётная запись <input id="manager-name"></label><label>Пароль/PIN <input id="manager-password" type="password"></label>','approval');return}
     draft.pendingClaims.shift();
    }
   }finally{await api('logout',{},manager.token)}
   close();return;
  }
  if(stage){close();return}
  if(!round()){await command('confirm',{table_id:table().id,round_id:table().next_round_id,boxes:[...selected]});selected.clear();await refresh()}
 }catch(e){if(!$('service').open)show('Операция не выполнена','','notice');$('error').textContent=e.message}finally{busy=false}
}
$('service-form').addEventListener('submit',e=>{e.preventDefault();submit()});$('cancel').onclick=close;
document.addEventListener('keydown',async e=>{
 const a=action(e,mapping);if(!a)return;e.preventDefault();if(busy)return;
 if(a.type==='reload'){reloadScreen();return}
 if(a.type==='cancel'){close();return}if(a.type==='settings'){settings();return}
 if(!online||!navigator.onLine){if(!$('service').open)show('Нет связи','Финансовые команды заблокированы.','notice');return}
 if(a.type==='mode'){await toggleMode();return}
 if(!stage&&(table()?.mode==='baccarat'||table()?.game==='baccarat')){return}
 if(a.type==='enter'){submit();return}
 if(stage){if(a.type==='digit'){if(stage==='pending-choice')draft.choice=a.value;if(stage==='box'&&a.value>=1&&a.value<=table().boxes){draft.boxes.includes(a.value)?draft.boxes=draft.boxes.filter(n=>n!==a.value):draft.boxes.push(a.value)}if(stage==='tier')draft.tier=a.value;if(stage==='type')draft.type=a.value===1?'progressive':a.value===2?'fixed':null;const old=$('service-body').querySelector('.choice');old?.remove();const choice=document.createElement('p');choice.className='choice';choice.textContent=stage==='box'?`Боксы: ${draft.boxes.join(', ')||'—'}`:`Выбор: ${a.value}`;$('service-body').append(choice)}return}
 if(a.type==='claim'&&round()){draft={};const pending=state.claims.find(x=>x.round_id===round().id&&x.status==='pending');if(pending){draft.pending=pending;show('Есть незавершённая заявка','1 — продолжить подтверждение · 2 — заявить выигрыш других боксов','pending-choice')}else claimStep();return}
 if(a.type==='digit'){
  if(!round()&&a.value>=1&&a.value<=table().boxes){selected.has(a.value)?selected.delete(a.value):selected.add(a.value);render()}
  if(a.value===0){busy=true;try{if(!round())await command('confirm',{table_id:table().id,round_id:table().next_round_id,boxes:[]});await refresh();await command('close',{table_id:table().id,round_id:round().id});selected.clear();await refresh()}catch(e){show('Не завершено', '','notice');$('error').textContent=e.message}finally{busy=false}}
 }
});
async function refresh(){state=await api('state',undefined,token,'GET');if(!requestedTableId&&table()){requestedTableId=table().id;localStorage.setItem(tokenKey(requestedTableId),token);history.replaceState(null,'','/table/'+requestedTableId)}offset=Date.parse(state.server_time)-Date.now();lastStateAt=Date.now();sessionStorage.setItem('premier-last-view',JSON.stringify(state));if(navigator.onLine&&table()?.operator?.id===operator&&Date.parse(table().operator.until)>Date.parse(state.server_time)){online=true;$('connection').hidden=true}render()}
async function heartbeat(){await refresh();await api('operator',{operator_id:operator});const legacy=sessionStorage.getItem('premier-pending-intent');if(legacy){const intent=JSON.parse(legacy);if(intent.payload?.table_id===requestedTableId&&!sessionStorage.getItem(pendingKey())){sessionStorage.setItem(pendingKey(),legacy);sessionStorage.removeItem('premier-pending-intent')}}const raw=sessionStorage.getItem(pendingKey());if(raw){const intent=JSON.parse(raw);try{await api('commands/'+intent.command_id,undefined,token,'GET')}catch{intent.operator_id=operator;try{await api('commands',intent)}catch(e){if(!/Stale|already|Claim already|Round is not/.test(e.message))throw e}}sessionStorage.removeItem(pendingKey())}await refresh();online=navigator.onLine;$('connection').hidden=online}
window.addEventListener('offline',()=>{online=false;$('connection').hidden=false;streamAbort?.abort();render()});
async function connect(){
 if(!navigator.onLine){online=false;$('connection').hidden=false;setTimeout(connect,2000);return}
 if(!token){show('Привязка устройства','<label>Одноразовый код <input id="pair-code" autocomplete="off"></label><label>Уникальное имя устройства <input id="device-name"></label>','pair');return}
 try{
  await heartbeat();streamAbort=new AbortController();const r=await fetch('/api/v1/stream',{headers:headers(),signal:streamAbort.signal});if(!r.ok)throw Error('Stream unavailable');const reader=r.body.getReader(),decoder=new TextDecoder();let buffer='';
  while(true){const chunk=await reader.read();if(chunk.done)break;buffer+=decoder.decode(chunk.value,{stream:true});let pos;
   while((pos=buffer.indexOf('\n\n'))>=0){const block=buffer.slice(0,pos);buffer=buffer.slice(pos+2);const type=block.match(/event: (\w+)/)?.[1],raw=block.match(/data: (.+)/)?.[1];if(!raw)continue;const data=JSON.parse(raw);
    if(type==='state'){state=data;offset=Date.parse(data.server_time)-Date.now();lastStateAt=Date.now();sessionStorage.setItem('premier-last-view',JSON.stringify(state));if(navigator.onLine&&table()?.operator?.id===operator&&Date.parse(table().operator.until)>Date.parse(state.server_time)){online=true;$('connection').hidden=true}render()}
    if(type==='winner'&&!seen.has(data.win_id)){seen.add(data.win_id);winners.push(data)}
   }
  }
 }catch(e){if(e.status===403||e.status===401){online=false;token=null;state=null;selected.clear();clearDisplay();show('Привязка этого стола','<label>Одноразовый код <input id="pair-code" autocomplete="off"></label><label>Уникальное имя устройства <input id="device-name"></label>','pair');$('error').textContent=e.message}else console.warn('Connection unavailable')}finally{online=false;$('connection').hidden=false;setTimeout(connect,2000)}
}
setInterval(async()=>{if(!token)return;try{await heartbeat()}catch{online=false;$('connection').hidden=false}},5000);
setInterval(()=>{
 if(Date.now()-lastStateAt>2500&&online){online=false;$('connection').hidden=false;render()}
 const clock=Date.now()+offset;winners=winners.filter(w=>Date.parse(w.show_until)>clock);const current=winners.find(w=>Date.parse(w.show_at)<=clock);renderWinner(current,state);
},100);
clearDisplay();render();$('connection').hidden=false;connect();
