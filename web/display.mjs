const $=id=>document.getElementById(id),fmt=n=>n.toLocaleString('en-US');
const names={5:'royal',4:'straight',3:'four',2:'full',1:'flush'};
const cards={royal:[['10','♠'],['J','♠'],['Q','♠'],['K','♠'],['A','♠']],straight:[['9','♠'],['8','♠'],['7','♠'],['6','♠'],['5','♠']],four:[['A','♠'],['A','♥'],['A','♦'],['A','♣'],['K','♠']],full:[['K','♠'],['K','♥'],['K','♦'],['Q','♣'],['Q','♠']],flush:[['A','♥'],['J','♥'],['8','♥'],['5','♥'],['2','♥']]};
const hand=id=>cards[id].map(([rank,suit])=>`<span class="card ${'♥♦'.includes(suit)?'red':''}"><span>${rank}</span><span class="suit">${suit}</span></span>`).join('');
let configVersion=null,activeTable=null,activeEnvironment=null,currentWinner=null,inputEnabled=false,activeReloadKey=null;
function fit(){if(!matchMedia('(max-width:800px) and (orientation:portrait)').matches)$('stage').style.transform=`translate(-50%,-50%) scale(${Math.min(innerWidth/1920,innerHeight/1080)})`;fitMoney()}
function fitMoney(){for(const el of document.querySelectorAll('.money')){el.style.fontSize='';let size=parseFloat(getComputedStyle(el).fontSize);while(el.scrollWidth>el.clientWidth+1&&size>22){size-=2;el.style.fontSize=size+'px'}}}
export function clearDisplay(){activeTable=null;configVersion=null;$('tierGrid').replaceChildren();$('fixedGrid').replaceChildren();$('boxes').replaceChildren();$('meter-royal').textContent='—';$('tableName').textContent='';$('baccarat').hidden=true;$('stage').hidden=false;$('winner').hidden=true;currentWinner=null}
function sendTable(){if(!activeTable)return;const t=activeTable;$('baccarat').contentWindow?.postMessage({type:'premier-table',table_id:t.id,name:t.name,number:t.number,minimum:t.minimum,maximum:t.maximum,baccarat:t.baccarat,reload_key:activeReloadKey,test_controls:activeEnvironment==='test'&&new URLSearchParams(location.search).get('test_controls')==='1',enabled:inputEnabled&&t.mode==='baccarat'&&!currentWinner},location.origin)}
window.addEventListener('message',e=>{if(e.origin===location.origin&&e.source===$('baccarat').contentWindow&&e.data?.type==='premier-ready'&&e.data.table_id===activeTable?.id)sendTable()});
export function renderDisplay(state,t,r,selected,enabled,reloadCode=null){
 inputEnabled=enabled;
 activeReloadKey=reloadCode;
 activeTable=t;activeEnvironment=state.environment;$('tableName').textContent=`${t.name} · ${t.number} · ${t.boxes} BOXES`;
 if(configVersion!==state.config.version){
  configVersion=state.config.version;$('tierGrid').replaceChildren();$('fixedGrid').replaceChildren();
  for(const tier of [...state.config.tiers].sort((a,b)=>b.code-a.code)){
   const name=names[tier.code];
   if(tier.code!==5){const plaque=document.createElement('article');plaque.className='plaque';plaque.dataset.tier=name;plaque.innerHTML=`<div class="plaque-name"></div><div class="meter-shell"><span class="currency">TZS</span><strong class="money" id="meter-${name}"></strong></div><div class="card-fan" aria-hidden="true">${hand(name)}</div><div class="qualifier">FIRST FIVE</div><div class="step" id="step-${name}"></div>`;plaque.querySelector('.plaque-name').textContent=tier.name;$('tierGrid').append(plaque)}
   const fixed=document.createElement('div');fixed.className='fixed-item';fixed.dataset.award=name;fixed.innerHTML=`<div class="fixed-name"></div><div class="fixed-amount"><small>TZS</small><span>${fmt(tier.fixed)}</span></div><div class="fixed-hand" aria-hidden="true">${hand(name)}</div>`;fixed.querySelector('.fixed-name').textContent=tier.name;$('fixedGrid').append(fixed);
  }
 }
 for(const tier of state.config.tiers)$('meter-'+names[tier.code]).textContent=fmt(state.pools[tier.code]);
 $('boxes').style.setProperty('--box-columns',String(Math.min(t.boxes,7)));
 $('boxes').replaceChildren(...Array.from({length:t.boxes},(_,i)=>{const n=i+1,on=r?.boxes.includes(n),chosen=selected.has(n),won=state.claims.some(c=>c.round_id===r?.id&&c.box===n&&c.status==='approved');const box=document.createElement('button');box.type='button';box.className='box'+(on?' on selected locked':chosen?' selected':'')+(won?' won':'');box.innerHTML=`<b>${n}</b><span>${won?'AWARDED':on?'ACTIVE':chosen?'SELECTED':'OFF'}</span>`;box.setAttribute('aria-pressed',String(!!(on||chosen)));return box}));
 const bacc=t.mode==='baccarat';$('stage').hidden=bacc;$('baccarat').hidden=!bacc;
 if(bacc&&!$('baccarat').getAttribute('src'))$('baccarat').src='/static/baccarat/index.html?table_id='+t.id;
 sendTable();fitMoney();
}
export function renderWinner(win,state){
 $('winner').hidden=!win;if(!win){if(currentWinner){currentWinner=null;sendTable()}return}
 const tier=state.config.tiers.find(t=>t.code===win.tier),name=names[win.tier];
 $('winner-text').textContent=`Table ${win.table_number} · Box ${win.box} · ${tier?.name} · TZS ${fmt(win.amount)}`;
 if(currentWinner===win.win_id)return;currentWinner=win.win_id;sendTable();
 $('winner').dataset.winningTier=name;$('winHand').textContent=tier?.name.toUpperCase()||'';$('winCards').innerHTML=hand(name);$('winAmount').textContent=fmt(win.amount);$('winBox').textContent=`TABLE ${win.table_number} · BOX ${win.box}`;
 $('winProgress').style.animation=`winTimer ${Date.parse(win.show_until)-Date.parse(win.show_at)}ms linear forwards`;
}
$('baccarat').addEventListener('load',()=>{sendTable();if(activeTable?.mode==='baccarat'&&!document.querySelector('dialog[open]'))$('baccarat').contentWindow.focus()});
window.addEventListener('resize',fit);fit();setInterval(()=>{$('clock').textContent=new Date().toLocaleTimeString('en-GB',{timeZone:'Africa/Dar_es_Salaam',hour12:false})+' EAT'},1000);
