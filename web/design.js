
(function(){
 const key='premier.progressive.display.design',valid=v=>/^[1-5]$/.test(v||'');
 const names=['Regal','Quantum','Monument','Velocity','Constellation'];
 let saved='1';try{saved=localStorage.getItem(key)||'1';}catch{}
 const requested=new URLSearchParams(location.search).get('style');
 let current=valid(requested)?requested:valid(saved)?saved:'1';
 function apply(value,updateURL=false){
  current=value;document.body.dataset.design=value;
  document.title='Premier Progressive · '+names[Number(value)-1];
  try{localStorage.setItem(key,value);}catch{}
  if(updateURL){const url=new URL(location.href);url.searchParams.set('style',value);history.replaceState(null,'',url);}
 }
 function next(){apply(String(Number(current)%5+1),true);}
 apply(current);
 const brand=document.querySelector('.brand');brand.addEventListener('click',next);
 brand.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();e.stopPropagation();next();}});
 document.addEventListener('keydown',e=>{
  if(e.repeat||e.ctrlKey||e.metaKey||e.altKey||e.isComposing||document.querySelector('dialog[open]'))return;
  if(e.target.closest?.('input,select,textarea,[contenteditable="true"]'))return;
  if(e.code==='KeyD'){e.preventDefault();next();}
 });
})();
