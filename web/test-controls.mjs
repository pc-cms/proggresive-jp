// Explicit browser TEST controls; commands still use the normal authenticated path.
export function installTestControls(getView){
 if(new URLSearchParams(location.search).get('test_controls')!=='1')return ()=>{};
 const root=document.createElement('aside');root.className='web-test-controls';root.hidden=true;
 const toggle=document.createElement('button');toggle.type='button';toggle.textContent='ТЕСТ · кнопки';toggle.setAttribute('aria-expanded','false');
 const panel=document.createElement('div');panel.className='web-test-keys';panel.hidden=true;
 const note=document.createElement('p');note.textContent='Тестовые операции · без реальных денег';panel.append(note);
 const keys=[...Array.from({length:10},(_,n)=>[String(n),'Numpad'+n,String(n)]),['Enter','NumpadEnter','Enter'],['* Выигрыш','claim','*'],['F4 Режим','F4','F4'],['Esc Назад','Escape','Escape'],['+ Small Tiger','NumpadAdd','+'],['. Отмена Baccarat','NumpadDecimal','.']];
 for(const [label,code,key] of keys){
  const button=document.createElement('button');button.type='button';button.textContent=label;button.dataset.testKey=code;
  button.onclick=()=>{
   const view=getView();if(view.state?.environment!=='test')return;
   const physical=code==='claim'?view.claimCode:code;
   if(view.state.tables[0]?.mode==='baccarat'&&!document.getElementById('service').open){
    document.getElementById('baccarat').contentWindow?.postMessage({type:'premier-test-key',table_id:view.state.tables[0].id,code:physical,key},location.origin);
   }else document.body.dispatchEvent(new KeyboardEvent('keydown',{code:physical,key,bubbles:true,cancelable:true}));
  };panel.append(button);
 }
 toggle.onclick=()=>{panel.hidden=!panel.hidden;toggle.setAttribute('aria-expanded',String(!panel.hidden))};root.append(toggle,panel);
 const dialog=document.getElementById('service');
 function position(){const parent=dialog.open?dialog:document.body;if(root.parentNode!==parent)parent.append(root)}
 new MutationObserver(position).observe(dialog,{attributes:true,attributeFilter:['open']});position();
 return ()=>{root.hidden=getView().state?.environment!=='test'};
}
