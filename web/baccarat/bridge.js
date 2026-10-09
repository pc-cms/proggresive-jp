// Same-origin kiosk bridge. This module never accepts or emits financial commands.
(()=>{
 const tableId=new URLSearchParams(location.search).get('table_id');
 if(!/^[0-9a-f]{32}$/.test(tableId||'')||parent===window)return;
 let enabled=false,testControls=false,pending=new Map();
 window.premierRemote={mutate(op,payload){
  if(!enabled)return Promise.reject(Error('Нет связи или активного оператора'));
  const request_id=crypto.randomUUID();
  return new Promise((resolve,reject)=>{const timer=setTimeout(()=>{pending.delete(request_id);reject(Error('Нет подтверждения сервера. Проверьте историю перед повтором.'))},20000);pending.set(request_id,{resolve,reject,timer});parent.postMessage({type:'premier-baccarat',table_id:tableId,request_id,op,payload},location.origin)});
 }};
 for(const type of ['keydown','click'])document.addEventListener(type,e=>{if(!enabled&&e.code!=='F4'){e.preventDefault();e.stopImmediatePropagation()}},true);
 window.addEventListener('message',e=>{
  if(e.origin!==location.origin||e.source!==parent||e.data?.table_id!==tableId)return;
  if(e.data.type==='premier-test-key'){
   const valid=/^Numpad[0-9]$/.test(e.data.code)||['F4','Escape','NumpadEnter','NumpadAdd','NumpadDecimal'].includes(e.data.code);
   if(testControls&&valid)document.body.dispatchEvent(new KeyboardEvent('keydown',{code:e.data.code,key:e.data.key,bubbles:true,cancelable:true}));return;
  }
  if(e.data.type==='premier-baccarat-result'){
   const item=pending.get(e.data.request_id);if(!item)return;clearTimeout(item.timer);pending.delete(e.data.request_id);e.data.error?item.reject(Error(e.data.error)):item.resolve(e.data.result);return;
  }
  if(e.data.type!=='premier-table')return;
  window.premierBaccarat=e.data.baccarat;
  enabled=e.data.enabled===true;testControls=e.data.test_controls===true;
  window.premierTable={table:e.data.name,board:e.data.number,min:Number(e.data.minimum).toLocaleString('en-US'),max:Number(e.data.maximum).toLocaleString('en-US'),currency:'TZS'};
  window.dispatchEvent(new Event('premier-table'));
 });
 document.addEventListener('keydown',e=>{
  if(e.code!=='F4'||e.repeat||e.ctrlKey||e.altKey||e.metaKey)return;
  e.preventDefault();e.stopImmediatePropagation();parent.postMessage({type:'premier-mode',table_id:tableId},location.origin);
 },true);
 parent.postMessage({type:'premier-ready',table_id:tableId},location.origin);
})();
