(() => {
'use strict';
const E=window.BaccaratEngine,$=id=>document.getElementById(id),KEY='premier-baccarat-max-v1:'+new URLSearchParams(location.search).get('table_id');
const DEFAULTS={brand:'PREMIER',table:'TABLE B01',board:33,min:'5',max:'10,000',currency:'TZS',announcement:'Welcome to Premier Casino. Good luck.',lang:'en',mode:'ultimate',quality:'max',sound:'off',logoData:''};
const MODES={ultimate:{label:'ALL SPECIALS',specials:['super6','dragon7','panda8','bigTiger','smallTiger']},classic:{label:'CLASSIC',specials:[]},ez:{label:'EZ BACCARAT',specials:['dragon7','panda8']},super6:{label:'SUPER 6',specials:['super6']},tiger:{label:'TIGER',specials:['bigTiger','smallTiger']}};
const SCENES={
 banker:{glyph:'B',title:'BANKER',zh:'庄家',sub:'WINNER',outcome:'B',color:'#b82342',light:'#ffd7b5',duration:2400},
 player:{glyph:'P',title:'PLAYER',zh:'闲家',sub:'WINNER',outcome:'P',color:'#326acf',light:'#d1e8ff',duration:2400},
 tie:{glyph:'T',title:'TIE',zh:'和局',sub:'EQUAL RESULT',outcome:'T',color:'#1b8964',light:'#c5ffe2',duration:2400},
 super6:{glyph:'6',title:'SUPER SIX',zh:'超级六',sub:'BANKER WIN · SIX',outcome:'B',color:'#b18433',light:'#ffe6a1',duration:3400},
 dragon7:{glyph:'7',title:'DRAGON SEVEN',zh:'龙七',sub:'BANKER WIN · THREE-CARD SEVEN',outcome:'B',art:'assets/dragon.png',color:'#c64b18',light:'#ffce80',duration:4400},
 panda8:{glyph:'8',title:'PANDA EIGHT',zh:'熊猫八',sub:'PLAYER WIN · THREE-CARD EIGHT',outcome:'P',art:'assets/panda.png',color:'#3b8767',light:'#d9f7c9',duration:4400},
 bigTiger:{glyph:'BIG',title:'TIGER',zh:'大老虎',sub:'BANKER WIN · THREE-CARD SIX',outcome:'B',art:'assets/tiger.png',color:'#c88122',light:'#ffda8e',duration:4400},
 smallTiger:{glyph:'SMALL',title:'TIGER',zh:'小老虎',sub:'BANKER WIN · TWO-CARD SIX',outcome:'B',art:'assets/tiger.png',color:'#917748',light:'#eed6a2',duration:3800},
 pair:{glyph:'2×',title:'DOUBLE PAIR',zh:'双对',sub:'PLAYER PAIR · BANKER PAIR',color:'#8c539e',light:'#f4d1ff',duration:2800}
};
const ZH={bead:'珠盘路',shoeStats:'本靴统计',banker:'庄家',player:'闲家',tie:'和局',bpair:'庄对',ppair:'闲对',tableLimits:'台面限额',minimum:'最低',maximum:'最高',shoe:'靴号',hand:'局号',board:'台号',big:'大路',current:'当前连胜',longest:'最长连胜',eye:'大眼仔',small:'小路',cock:'小强路',ready:'准备下一局',undo:'撤销',controls:'控制',showroom:'演示'};
const EN={};document.querySelectorAll('[data-t]').forEach(el=>{EN[el.dataset.t]=el.textContent});
let storageOK=true,storageReadError=false,lastSavedRaw=null;
function initial(){return {version:1,shoe:1,hands:[],history:[],pending:{P:false,B:false},settings:{...DEFAULTS}}}
function load(){const clean=initial();try{lastSavedRaw=localStorage.getItem(KEY);const raw=JSON.parse(lastSavedRaw||'null');if(!raw)return clean;if(typeof raw!=='object'||!Array.isArray(raw.hands)||raw.hands.some(h=>!h||!['P','B','T'].includes(h.outcome)))throw Error('Invalid saved shoe');clean.shoe=Math.max(1,Math.floor(Number(raw.shoe)||1));clean.hands=E.normalizeHands(Array.isArray(raw.hands)?raw.hands:[]);clean.history=Array.isArray(raw.history)?raw.history:[];clean.pending={P:!!raw.pending?.P,B:!!raw.pending?.B};clean.settings={...DEFAULTS,...raw.settings};if(!MODES[clean.settings.mode])clean.settings.mode='ultimate';if(!['max','balanced','quiet'].includes(clean.settings.quality))clean.settings.quality='max';return clean}catch{storageOK=false;storageReadError=true;return clean}}
let remoteBusy=false,live=window.premierRemote?initial():load(),demo=null,activePanel=null,returnFocus=null,sceneEpoch=0,sceneWait=null,particleRAF=0,autoTimer=0,toastTimer=0,audio=null,pendingLogo=null;
const current=()=>demo||live, settings=()=>({...live.settings,...(window.premierTable||{})});
window.addEventListener('premier-table',()=>{const remote=window.premierBaccarat;if(remote&&(remote.revision>=(live.revision??-1))){live={...remote,settings:{...DEFAULTS,...remote.settings}};storageOK=true}render()});
async function remoteMutation(op,payload){remoteBusy=true;try{const remote=await window.premierRemote.mutate(op,{...payload,revision:live.revision??0});if(remote.revision>=(live.revision??-1))live={...remote,settings:{...DEFAULTS,...remote.settings}};render();return true}catch(e){toast(e.message);return false}finally{remoteBusy=false}}
function save(){if(window.premierRemote)return true;try{if(storageReadError)throw Error('Saved shoe unreadable');const serialized=JSON.stringify(live);localStorage.setItem(KEY,serialized);lastSavedRaw=serialized;storageOK=true}catch{storageOK=false} $('storageWarning').hidden=storageOK;return storageOK}
function toast(message){clearTimeout(toastTimer);$('toast').textContent=message;$('toast').hidden=false;toastTimer=setTimeout(()=>$('toast').hidden=true,2500)}
function pad(n){return String(n).padStart(3,'0')}
function text(id,value){$(id).textContent=String(value)}
function fit(){const scale=Math.min(innerWidth/1920,innerHeight/1080);$('stage').style.transform=`translate(-50%,-50%) scale(${scale})`;document.documentElement.style.setProperty('--screen-scale',scale)}
function clock(){text('clock',new Date().toLocaleTimeString('en-GB',{hour12:false,timeZone:'Africa/Dar_es_Salaam'}))}
function render(){
 const state=current(),s=E.stats(state.hands),cfg=settings();
 document.documentElement.lang=cfg.lang==='zh'?'zh-CN':'en';document.querySelectorAll('[data-t]').forEach(el=>el.textContent=cfg.lang==='zh'?(ZH[el.dataset.t]||EN[el.dataset.t]):EN[el.dataset.t]);
 text('brandName',cfg.brand);$('brandLogo').hidden=false;$('brandText').hidden=true;$('brandLogo').src=cfg.logoData||'assets/premier-wordmark.svg';
 text('tableName',cfg.table);text('currency',cfg.currency);text('minimum',cfg.min);text('maximum',cfg.max);text('boardNumber',cfg.board);text('shoeNumber',pad(state.shoe));text('handNumber',pad(s.total));text('announcement',cfg.announcement);text('modeName',MODES[cfg.mode].label);text('modeBadge',demo?'DEMONSTRATION':'LIVE INPUT');text('localLabel',demo?'SHOWROOM':window.premierRemote?'SERVER DISPLAY':'LOCAL DISPLAY');
 [['banker',s.banker],['player',s.player],['tie',s.tie]].forEach(([key,n])=>{text(key+'Count',n);text(key+'Rate',((s.total?n/s.total:0)*100).toFixed(1)+'%')});text('bPairCount',s.bankerPair);text('pPairCount',s.playerPair);
 text('currentStreak',s.currentStreak.count?`${s.currentStreak.outcome} × ${s.currentStreak.count}`:'—');text('longestStreak',s.maxStreak.count?`${s.maxStreak.outcome} × ${s.maxStreak.count}`:'—');
 const last=state.hands.at(-1);text('lastLabel',last?`LAST · ${last.outcome==='B'?'BANKER':last.outcome==='P'?'PLAYER':'TIE'}`:'WAITING FOR FIRST RESULT');
 const flags=[];if(state.pending.P)flags.push('PLAYER PAIR');if(state.pending.B)flags.push('BANKER PAIR');text('ready',flags.length?'NEXT HAND · '+flags.join(' + '):(cfg.lang==='zh'?ZH.ready:EN.ready));
 ['bPairBtn','operatorBPair'].forEach(id=>{$(id).classList.toggle('armed',state.pending.B);$(id).setAttribute('aria-pressed',String(state.pending.B))});['pPairBtn','operatorPPair'].forEach(id=>{$(id).classList.toggle('armed',state.pending.P);$(id).setAttribute('aria-pressed',String(state.pending.P))});
 $('recent').replaceChildren();if(!state.hands.length){const n=document.createElement('small');n.textContent='RECENT HANDS · —';$('recent').append(n)}else state.hands.slice(-10).forEach(h=>{const el=document.createElement('span');el.className=h.outcome;el.textContent=h.outcome;$('recent').append(el)});
 $('demoBanner').hidden=!demo;document.querySelectorAll('[data-special]').forEach(el=>{el.disabled=!MODES[cfg.mode].specials.includes(el.dataset.special)});
 ['undoBtn','drawerUndo'].forEach(id=>{$(id).disabled=!state.hands.length});
 drawRoad('bead',E.beadCells(state.hands),'bead');const big=E.buildBigRoad(state.hands);drawRoad('big',big.cells,'big',big.initialTieCount);drawRoad('eye',E.buildDerivedRoad(state.hands,1).cells,'ring');drawRoad('small',E.buildDerivedRoad(state.hands,2).cells,'dot');drawRoad('cock',E.buildDerivedRoad(state.hands,3).cells,'slash');
 fitLabels();clock();
}
function fitLabels(){[['minimum',35,18],['maximum',35,18],['brandName',38,20],['tableName',21,14],['boardNumber',40,12]].forEach(([id,max,min])=>{const el=$(id);el.style.fontSize=max+'px';while(el.scrollWidth>el.clientWidth+1&&max>min){el.style.fontSize=(--max)+'px'}})}
const COLORS={B:'#c32d42',P:'#276bb6',T:'#258669',R:'#c32d42',U:'#276bb6'};
function drawRoad(id,cells,kind,initialTies=0){
 const canvas=$(id),w=canvas.clientWidth,h=canvas.clientHeight;if(!w||!h)return;
 const scale=Math.min(2,Math.max(1,(window.devicePixelRatio||1)*Math.min(innerWidth/1920,innerHeight/1080)));canvas.width=Math.round(w*scale);canvas.height=Math.round(h*scale);const ctx=canvas.getContext('2d');ctx.setTransform(scale,0,0,scale,0,0);
 const cell=Math.floor(h/6),cols=Math.floor(w/cell),gridWidth=cols*cell,left=(w-gridWidth)/2,top=(h-cell*6)/2;
 const paper=ctx.createLinearGradient(0,0,0,h);paper.addColorStop(0,'#e8efef');paper.addColorStop(.4,'#f8faf7');paper.addColorStop(1,'#e5e9e8');ctx.fillStyle=paper;ctx.fillRect(0,0,w,h);
 ctx.strokeStyle='#c8d2d2';ctx.lineWidth=.7;ctx.beginPath();for(let r=0;r<=6;r++){ctx.moveTo(left,top+r*cell+.5);ctx.lineTo(left+gridWidth,top+r*cell+.5)}for(let c=0;c<=cols;c++){ctx.moveTo(left+c*cell+.5,top);ctx.lineTo(left+c*cell+.5,top+6*cell)}ctx.stroke();
 const maxCol=cells.reduce((max,c)=>Math.max(max,c.col),0),start=Math.max(0,maxCol-cols+1);
 const point=(col,row)=>[left+(col-start+.5)*cell,top+(row+.5)*cell];
 function dot(x,y,r,color){ctx.beginPath();ctx.arc(x,y,r,0,Math.PI*2);const g=ctx.createRadialGradient(x-r*.35,y-r*.5,0,x,y,r);g.addColorStop(0,color==='B'||color==='R'?'#f57a80':color==='P'||color==='U'?'#70a9e2':'#6bc6a4');g.addColorStop(.5,COLORS[color]);g.addColorStop(1,color==='B'||color==='R'?'#7e1831':color==='P'||color==='U'?'#183d78':'#15513b');ctx.fillStyle=g;ctx.fill()}
 function pairs(c,x,y,r){[[c.bankerPair||c.tieBankerPair,'B',-.64,-.65],[c.playerPair||c.tiePlayerPair,'P',.64,.65]].forEach(([yes,color,dx,dy])=>{if(!yes)return;ctx.beginPath();ctx.arc(x+r*dx,y+r*dy,Math.max(2,r*.22),0,Math.PI*2);ctx.fillStyle=COLORS[color];ctx.fill();ctx.strokeStyle='#fff';ctx.lineWidth=1;ctx.stroke()})}
 if(!cells.length&&initialTies){const [x,y]=point(0,0);ctx.strokeStyle=COLORS.T;ctx.lineWidth=2.4;ctx.beginPath();ctx.moveTo(x-cell*.25,y+cell*.25);ctx.lineTo(x+cell*.25,y-cell*.25);ctx.stroke();if(initialTies>1){ctx.fillStyle=COLORS.T;ctx.font=`bold ${cell*.3}px Arial`;ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillText(initialTies,x,y)}}
 cells.forEach(c=>{if(c.col<start||c.col>=start+cols)return;const[x,y]=point(c.col,c.row),r=cell*(kind==='bead'?.37:.33),mark=c.outcome||c.mark;
  if(kind==='bead'){dot(x,y,r,mark);ctx.font=`bold ${cell*.39}px Arial`;ctx.fillStyle='#fff';ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillText(mark,x,y+1);pairs(c,x,y,r)}
  else if(kind==='dot'){dot(x,y,r*.69,mark)}
  else if(kind==='slash'){ctx.strokeStyle=COLORS[mark];ctx.lineWidth=Math.max(2,cell*.09);ctx.lineCap='round';ctx.beginPath();ctx.moveTo(x-r*.7,y+r*.7);ctx.lineTo(x+r*.7,y-r*.7);ctx.stroke();ctx.lineCap='butt'}
  else{ctx.beginPath();ctx.arc(x,y,r,0,Math.PI*2);ctx.strokeStyle=COLORS[mark];ctx.lineWidth=kind==='big'?Math.max(2,cell*.075):Math.max(2,cell*.065);ctx.stroke();if(kind==='big'){if(c.tieCount){ctx.strokeStyle=COLORS.T;ctx.lineWidth=2;ctx.beginPath();ctx.moveTo(x-r*.72,y+r*.72);ctx.lineTo(x+r*.72,y-r*.72);ctx.stroke();if(c.tieCount>1){ctx.font=`bold ${cell*.29}px Arial`;ctx.fillStyle=COLORS.T;ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillText(c.tieCount,x,y)}}pairs(c,x,y,r)}}
 });
}
// Avoid silently overwriting another tab's shoe or an unreadable saved record.
function canEdit(includeLiveSettings=false){
 if(window.premierRemote){if(remoteBusy){toast('Waiting for server confirmation');return false}return true}
 if(demo&&!includeLiveSettings)return true;
 if(storageReadError){toast('Saved shoe cannot be read. Recording is blocked.');return false}
 try{if(localStorage.getItem(KEY)!==lastSavedRaw){stopShow();live=load();render();$('storageWarning').hidden=storageOK;toast('Shoe changed in another tab. Review it, then repeat your action.');return false}}catch{storageOK=false;$('storageWarning').hidden=false}
 return true;
}
function persist(){if(!demo)save()}
async function addHand(outcome,special=null){
 if(!canEdit())return false;
 if(!['P','B','T'].includes(outcome))throw Error('Invalid outcome');
 if(special&&(!SCENES[special]||SCENES[special].outcome!==outcome))throw Error('Special result does not match winning hand');
 if(special&&!MODES[settings().mode].specials.includes(special)){toast('This special result is disabled in '+MODES[settings().mode].label);return false}
 if(window.premierRemote&&!demo){if(await remoteMutation('baccarat_result',{outcome,special})){closePanels();render();playHand(live.hands.at(-1));return true}return false}
 const state=current();const hand={id:Date.now(),outcome,special,playerPair:state.pending.P,bankerPair:state.pending.B,ts:new Date().toISOString()};state.hands.push(hand);state.pending={P:false,B:false};persist();closePanels();render();playHand(hand);return true;
}
function pair(side){if(!canEdit()||!['P','B'].includes(side))return;if(window.premierRemote&&!demo){remoteMutation('baccarat_pair',{side});return}current().pending[side]=!current().pending[side];persist();render()}
function undo(){if(!canEdit()||!current().hands.length)return;if(window.premierRemote&&!demo){stopShow();remoteMutation('baccarat_undo',{});return}stopShow();current().hands.pop();persist();render();toast('Last hand removed')}
function startNew(){if(!canEdit())return;if(window.premierRemote&&!demo){stopShow();remoteMutation('baccarat_shoe',{}).then(ok=>{if(ok)closePanels()});return}stopShow();const s=current();if(s.hands.length)s.history.unshift({shoe:s.shoe,hands:s.hands.slice(),endedAt:new Date().toISOString()});s.hands=[];s.pending={P:false,B:false};s.shoe++;persist();closePanels();render();toast('New shoe '+pad(s.shoe))}
function closePanels(){if(activePanel)$(activePanel).hidden=true;activePanel=null;$('scrim').hidden=true;if(returnFocus?.isConnected)returnFocus.focus({preventScroll:true})}
function openPanel(id){stopShow();closePanels();returnFocus=document.activeElement;activePanel=id;$(id).hidden=false;$('scrim').hidden=false;const first=$(id).querySelector('button,input,select');first?.focus({preventScroll:true});if(id==='settings'){pendingLogo=null;$('logoInput').value='';text('logoStatus',settings().logoData?'Custom logo saved':'Premier guideline wordmark');const f=$('settingsForm');if(window.premierRemote)for(const key of ['table','board','min','max','currency']){const input=f.elements.namedItem(key);if(input)input.disabled=true}Object.keys(DEFAULTS).forEach(k=>{if(f.elements.namedItem(k))f.elements.namedItem(k).value=settings()[k]})}}
function quiet(){return settings().quality==='quiet'||window.matchMedia('(prefers-reduced-motion: reduce)').matches}
function stopShow(){sceneEpoch++;clearTimeout(autoTimer);autoTimer=0;cancelAnimationFrame(particleRAF);particleRAF=0;if(sceneWait){clearTimeout(sceneWait.timer);sceneWait.resolve(false);sceneWait=null}$('cinema').hidden=true;$('sceneArt').hidden=true}
function sceneSound(name){if(settings().sound!=='on')return;try{audio ||= new (window.AudioContext||window.webkitAudioContext)();audio.resume();const base={banker:146.83,player:196,tie:220,super6:261.63,dragon7:110,panda8:174.61,bigTiger:98,smallTiger:130.81,pair:246.94}[name]||164.81;[1,1.5,2].forEach((ratio,i)=>{const osc=audio.createOscillator(),gain=audio.createGain(),now=audio.currentTime+i*.09;osc.type=i?'sine':'triangle';osc.frequency.setValueAtTime(base*ratio*.6,now);osc.frequency.exponentialRampToValueAtTime(base*ratio,now+.24);gain.gain.setValueAtTime(0,now);gain.gain.linearRampToValueAtTime(.045/(i+1),now+.1);gain.gain.exponentialRampToValueAtTime(.0001,now+1.3);osc.connect(gain).connect(audio.destination);osc.start(now);osc.stop(now+1.4)})}catch{}}
function animateParticles(name,color,duration,epoch){
 cancelAnimationFrame(particleRAF);if(quiet())return;const canvas=$('particles'),ctx=canvas.getContext('2d');canvas.width=1280;canvas.height=720;const start=performance.now(),count=settings().quality==='balanced'?32:100;
 const embers=Array.from({length:count},(_,i)=>({x:Math.random()*1280,y:Math.random()*720,r:.5+Math.random()*2.2,speed:16+Math.random()*45,phase:Math.random()*6.28,depth:.3+Math.random()*.7}));
 function frame(now){if(epoch!==sceneEpoch||$('cinema').hidden||document.hidden)return;const elapsed=(now-start)/1000;ctx.clearRect(0,0,1280,720);ctx.fillStyle=color;embers.forEach((p,i)=>{let x=p.x+Math.sin(elapsed*.5+p.phase)*25,y=p.y-elapsed*p.speed;if(name==='pair'){x=640+Math.cos(p.phase+elapsed*.18)*(120+i*4);y=360+Math.sin(p.phase+elapsed*.18)*(70+i*2)}else if(name==='super6'){x=640+Math.cos(p.phase+elapsed*.08)*(160+i*3.3);y=360+Math.sin(p.phase+elapsed*.08)*(100+i*2)}else if(name==='player'){x=p.x+elapsed*22;y=p.y-elapsed*18}ctx.globalAlpha=Math.max(0,Math.min(.75,(Math.sin(elapsed*1.2+p.phase)+1)*.35))*p.depth;ctx.beginPath();ctx.arc((x+1280)%1280,(y+1440)%720,p.r,0,Math.PI*2);ctx.fill()});ctx.globalAlpha=1;if(now-start<duration+400)particleRAF=requestAnimationFrame(frame)}particleRAF=requestAnimationFrame(frame);
}
function playScene(name,{preview=false,sub=null,duration=null,epoch=sceneEpoch}={}){
 if(!SCENES[name]||epoch!==sceneEpoch)return Promise.resolve(false);const s=SCENES[name],c=$('cinema');const ms=quiet()?Math.min(duration||s.duration,1800):(duration||s.duration);
 c.hidden=true;void c.offsetWidth;c.className='cinema '+name+(s.art?' has-art':'')+(quiet()?' quiet':'');c.style.setProperty('--scene',s.color);c.style.setProperty('--light',s.light);c.style.setProperty('--duration',ms+'ms');
 $('sceneArt').hidden=!s.art;if(s.art)$('sceneArt').src=s.art;
 const singlePair=name==='pair'&&(sub==='PLAYER PAIR'||sub==='BANKER PAIR');
 text('resultGlyph',singlePair?'PAIR':s.glyph);text('resultTitle',singlePair?(settings().lang==='zh'?(sub==='PLAYER PAIR'?'闲对':'庄对'):sub):(settings().lang==='zh'?s.zh:s.title));text('resultSub',singlePair?'PAIR RESULT':(sub||s.sub));
 c.hidden=false;void c.offsetWidth;animateParticles(name,s.light,ms,epoch);sceneSound(name);
 return new Promise(resolve=>{
  sceneWait={resolve,timer:setTimeout(()=>{
   if(epoch!==sceneEpoch){resolve(false);return}
   c.classList.add('is-leaving');
   sceneWait={resolve,timer:setTimeout(()=>{
    if(epoch===sceneEpoch){c.hidden=true;cancelAnimationFrame(particleRAF)}
    sceneWait=null;resolve(epoch===sceneEpoch);
   },quiet()?0:300)};
  },ms)};
 });
}
async function playHand(hand){stopShow();const epoch=sceneEpoch;const name=hand.special||(hand.outcome==='B'?'banker':hand.outcome==='P'?'player':'tie');const sub=hand.special==='dragon7'&&settings().mode==='ez'?'BANKER BET PUSHES':null;if(!await playScene(name,{epoch,sub}))return;if(hand.playerPair||hand.bankerPair){await playScene('pair',{epoch,sub:hand.playerPair&&hand.bankerPair?'PLAYER PAIR · BANKER PAIR':hand.playerPair?'PLAYER PAIR':'BANKER PAIR'});}}
function preview(name,sub=null){if(!SCENES[name])return;closePanels();stopShow();playScene(name,{preview:true,sub,epoch:sceneEpoch})}
function sampleState(){const s=initial();s.shoe=12;const outcomes='BBBPPTPBBBBBBBTBBPPPPBBPTPPPBPPBBBBTBBPPPBPPPPPTBPBBPPBBBPTPPBBPPBBB';s.hands=[...outcomes].map((o,i)=>({id:i+1,outcome:o,playerPair:i%13===4,bankerPair:i%17===6,special:null}));return s}
function showSamples(){stopShow();demo=sampleState();closePanels();render();toast('Demonstration shoe · live results are unchanged')}
function exitDemo(){stopShow();demo=null;closePanels();render();toast('Live shoe restored')}
function autoplay(){showSamples();let i=0;const order=[...Object.keys(SCENES).map(name=>({name})),{name:'pair',sub:'PLAYER PAIR'},{name:'pair',sub:'BANKER PAIR'}];const epoch=sceneEpoch;async function next(){if(epoch!==sceneEpoch||!demo)return;const item=order[i++%order.length];await playScene(item.name,{preview:true,epoch,sub:item.sub||null});if(epoch===sceneEpoch)autoTimer=setTimeout(next,1100)}next()}
document.querySelectorAll('[data-outcome]').forEach(el=>el.addEventListener('click',()=>addHand(el.dataset.outcome)));
document.querySelectorAll('[data-special]').forEach(el=>el.addEventListener('click',()=>addHand(SCENES[el.dataset.special].outcome,el.dataset.special)));
document.querySelectorAll('[data-preview]').forEach(el=>el.addEventListener('click',()=>preview(el.dataset.preview,el.dataset.pair||null)));
document.querySelectorAll('[data-close]').forEach(el=>el.addEventListener('click',closePanels));$('scrim').addEventListener('click',closePanels);
['bPairBtn','operatorBPair'].forEach(id=>$(id).onclick=()=>pair('B'));['pPairBtn','operatorPPair'].forEach(id=>$(id).onclick=()=>pair('P'));
$('settingsBtn').onclick=()=>openPanel('settings');$('operatorBtn').onclick=()=>openPanel('operator');$('demoBtn').onclick=()=>openPanel('showroom');$('undoBtn').onclick=undo;$('drawerUndo').onclick=undo;$('newShoeBtn').onclick=()=>openPanel('confirm');$('confirmNew').onclick=startNew;$('sampleBtn').onclick=showSamples;$('autoplayBtn').onclick=autoplay;$('exitDemoBtn').onclick=exitDemo;
async function fullscreen(){try{if(document.fullscreenElement)await document.exitFullscreen();else await document.documentElement.requestFullscreen()}catch{toast('Use your browser’s fullscreen or landscape mode')}}$('fullBtn').onclick=fullscreen;
$('settingsForm').onsubmit=e=>{e.preventDefault();if(!canEdit(true))return;const f=$('settingsForm'),cfg={...settings()};Object.keys(DEFAULTS).forEach(k=>{const el=f.elements.namedItem(k);if(el)cfg[k]=String(el.value).trim()});cfg.brand=cfg.brand||DEFAULTS.brand;cfg.table=cfg.table||DEFAULTS.table;cfg.board=Math.max(1,Math.min(9999,Math.floor(Number(cfg.board)||33)));if(pendingLogo!==null)cfg.logoData=pendingLogo;if(window.premierRemote){const allowed=['brand','announcement','lang','mode','quality','sound','logoData'];remoteMutation('baccarat_settings',{settings:Object.fromEntries(allowed.map(k=>[k,cfg[k]]))}).then(ok=>{if(ok)closePanels()});return}live.settings=cfg;save();closePanels();render();toast(storageOK?'Settings saved':'Settings applied, but local saving failed')};
$('logoInput').onchange=e=>{const file=e.target.files?.[0];if(!file)return;if(file.size>1500000||!['image/png','image/jpeg','image/webp'].includes(file.type)){toast('Choose a PNG, JPEG or WebP logo under 1.5 MB');e.target.value='';return}const reader=new FileReader();reader.onload=()=>{pendingLogo=String(reader.result);text('logoStatus','Logo ready · click Save settings')};reader.readAsDataURL(file)};
$('clearLogo').onclick=()=>{pendingLogo='';$('logoInput').value='';text('logoStatus','Premier guideline wordmark · click Save settings')};
document.addEventListener('keydown',e=>{
 if(e.key==='Escape'){stopShow();closePanels();return}if(e.key==='Tab'&&activePanel){const els=[...$(activePanel).querySelectorAll('button:not([disabled]),input,select')].filter(el=>!el.hidden);if(els.length){const first=els[0],last=els.at(-1);if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus()}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus()}}return}
 if(e.repeat||e.ctrlKey||e.metaKey||e.altKey||activePanel||/INPUT|SELECT|TEXTAREA/.test(e.target.tagName))return;
 const k=e.key.toLowerCase();const mapping={'1':'P','2':'B','3':'T'},sp={'6':'super6','7':'dragon7','8':'panda8','9':'bigTiger','+':'smallTiger'};const key=e.code?.startsWith('Numpad')?({NumpadAdd:'+',NumpadDecimal:'.'}[e.code]||e.code.replace('Numpad','')):k;
 if(mapping[key])addHand(mapping[key]);else if(key==='4')pair('P');else if(key==='5')pair('B');else if(sp[key])addHand(SCENES[sp[key]].outcome,sp[key]);else if(key==='0')openPanel('confirm');else if(['.','delete','backspace'].includes(key))undo();else if(k==='s')openPanel('settings');else if(k==='k')openPanel('operator');else if(k==='d')openPanel('showroom');else if(k==='f')fullscreen();else return;e.preventDefault();
});
window.addEventListener('resize',()=>{fit();render()});document.addEventListener('visibilitychange',()=>{if(document.hidden)stopShow()});
// Agent access is read-only. Recording outcomes still requires the operator's deliberate input.
if(document.modelContext?.registerTool){
 try{
  Promise.resolve(document.modelContext.registerTool({
   name:'read_baccarat_display',title:'Read Baccarat display',
   description:'Read the current locally displayed shoe statistics and whether demonstration mode is active. Does not record results.',
   inputSchema:{type:'object',properties:{},additionalProperties:false},annotations:{readOnlyHint:true},
   execute(input){
    if(!input||typeof input!=='object'||Array.isArray(input)||Object.keys(input).length)throw Error('Expected an empty object');
    return {demonstration:!!demo,table:settings().table,shoe:current().shoe,statistics:E.stats(current().hands),storageAvailable:storageOK};
   }
  })).catch(()=>{});
 }catch{}
}
fit();render();$('storageWarning').hidden=storageOK;if(storageReadError)$('storageWarning').textContent='Saved shoe cannot be read. Recording is blocked to protect existing data.';setInterval(clock,1000);
Object.values(SCENES).filter(s=>s.art).forEach(s=>{const image=new Image();image.src=s.art});
const q=new URLSearchParams(location.search);if(q.get('demo')==='1'){showSamples();}if(SCENES[q.get('scene')])setTimeout(()=>preview(q.get('scene')),400);
})();
