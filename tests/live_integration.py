"""Run against an isolated TEST instance, never a live casino.
Requires local file /tmp/premier-test-admin-password; no secrets in output.
"""
import json,uuid,time,threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import httpx
from playwright.sync_api import sync_playwright,expect
BASE='http://127.0.0.1:8321'
admin=httpx.Client(base_url=BASE,timeout=20)
login=admin.post('/api/v1/login',json={'name':'admin','password':Path('/tmp/premier-test-admin-password').read_text()});login.raise_for_status()
admin.headers['Authorization']='Bearer '+login.json()['token']
def cmd(op,p):
 r=admin.post('/api/v1/commands',json={'command_id':str(uuid.uuid4()),'op':op,'payload':p});r.raise_for_status();return r.json()['result']
def register(n):
 t=cmd('table_register',{'number':n,'name':'Integration '+n});code=cmd('pair_create',{'table_id':t['id']})['pairing_code']
 r=admin.post('/api/v1/pair',json={'code':code,'name':'integration-'+n,'app_version':'test'});r.raise_for_status();return t,r.json()['token']
run=uuid.uuid4().hex[:6]
t1,token1=register(run+'A');t2,token2=register(run+'B')
ready=[threading.Event() for _ in range(20)];arrivals=[];failure=[]
def subscriber(i):
 try:
  with httpx.Client(base_url=BASE,headers=admin.headers,timeout=30) as c:
   with c.stream('GET','/api/v1/stream') as r:
    r.raise_for_status();kind=''
    for line in r.iter_lines():
     if line.startswith('event: '):kind=line[7:]
     if line.startswith('data: ') and kind=='state':ready[i].set()
     if line.startswith('data: ') and kind=='winner':
      arrivals.append((i,time.time(),json.loads(line[6:])));return
 except Exception as e:failure.append(str(e));ready[i].set()
with ThreadPoolExecutor(20) as pool:
 tasks=[pool.submit(subscriber,i) for i in range(20)]
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
  contexts=[browser.new_context() for _ in range(2)]
  for ctx,token in zip(contexts,[token1,token2]):ctx.add_init_script('localStorage.setItem("premier-device-token",'+json.dumps(token)+');')
  pages=[ctx.new_page() for ctx in contexts];errors=[];resource_errors=[]
  for page,t in zip(pages,[t1,t2]):
   page.on('response',lambda r:resource_errors.append({'url':r.url,'status':r.status}) if '/static/' in r.url and r.status>=400 else None)
   page.on('pageerror',lambda e:errors.append(str(e)));page.goto(BASE+'/table/'+t['id']);page.wait_for_selector('.box');page.wait_for_selector('#connection[hidden]',state='attached')
   page.keyboard.press('Numpad1');page.keyboard.press('NumpadEnter');page.wait_for_selector('.box.on')
  for event in ready: assert event.wait(20),'Stream failed to become ready'
  assert not failure,failure
  before=admin.get('/api/v1/state').json();r2=next(t['round_id'] for t in before['tables'] if t['id']==t2['id'])
  pages[1].keyboard.press('F4');pages[1].wait_for_selector('#baccarat:not([hidden])')
  baccarat=pages[1].frame_locator('#baccarat');baccarat.locator('#playerCount').wait_for()
  assert baccarat.locator('#tableName').inner_text()==t2['name']
  baccarat.locator('body').click(position={'x':10,'y':10});pages[1].keyboard.press('Numpad1')
  expect(baccarat.locator('#playerCount')).to_have_text('1')
  modes=admin.get('/api/v1/state').json();assert modes['pools']==before['pools']
  assert next(t['round_id'] for t in modes['tables'] if t['id']==t2['id'])==r2
  assert next(t['mode'] for t in modes['tables'] if t['id']==t2['id'])=='baccarat'

  for page in pages: page.evaluate('() => { window.winShownAt = null; new MutationObserver(() => {if(!document.getElementById("winner").hidden && window.winShownAt===null)window.winShownAt=Date.now()}).observe(document.getElementById("winner"),{attributes:true,attributeFilter:["hidden"]}) }')
  # Physical code path also works with Num Lock off (event.key = End).
  pages[0].evaluate('document.dispatchEvent(new KeyboardEvent("keydown",{code:"NumpadMultiply",key:"*",bubbles:true}))')
  for key in ['Numpad1','NumpadEnter','Numpad1','NumpadEnter','Numpad2','NumpadEnter','NumpadEnter']:
   pages[0].keyboard.press(key);time.sleep(.1)
  for page in pages:page.wait_for_selector('#winner:not([hidden])',timeout=15000)
  display_skew=abs(pages[0].evaluate('() => window.winShownAt')-pages[1].evaluate('() => window.winShownAt'));assert display_skew<500,display_skew
  displayed=[page.locator('#winner-text').inner_text() for page in pages];assert displayed[0]==displayed[1]
  assert pages[1].locator('#baccarat').is_visible(), 'Winner overlay must preserve Baccarat mode'
  pages[1].wait_for_selector('#winner[hidden]',state='attached',timeout=20000)
  expect(baccarat.locator('#playerCount')).to_have_text('1')
  pages[1].keyboard.press('F4');pages[1].wait_for_selector('#baccarat[hidden]',state='attached')
  assert pages[1].locator('.box.on').count()==1
  pages[1].keyboard.press('F4');pages[1].wait_for_selector('#baccarat:not([hidden])')
  expect(baccarat.locator('#playerCount')).to_have_text('1')
  pages[1].keyboard.press('F4');pages[1].wait_for_selector('#baccarat[hidden]',state='attached')
  after=admin.get('/api/v1/state').json();assert next(t['round_id'] for t in after['tables'] if t['id']==t2['id'])==r2
  # A stored credential for another table never starts this kiosk.
  wrong=browser.new_context();wrong.add_init_script('localStorage.setItem("premier-device-token",'+json.dumps(token1)+');');wrongpage=wrong.new_page();wrongpage.goto(BASE+'/table/'+t2['id']);wrongpage.wait_for_selector('#service[open]');assert 'another table' in wrongpage.locator('#error').inner_text();assert wrongpage.locator('.box').count()==0;wrong.close()
  # Local Baccarat input also stops when its kiosk loses the operator connection.
  pages[1].keyboard.press('F4');pages[1].wait_for_selector('#baccarat:not([hidden])')
  contexts[1].set_offline(True);pages[1].wait_for_selector('#connection:not([hidden])');time.sleep(.2)
  pages[1].keyboard.press('Numpad2');assert baccarat.locator('#bankerCount').inner_text()=='0'
  contexts[1].set_offline(False);pages[1].wait_for_selector('#connection[hidden]',state='attached',timeout=15000)
  pages[1].keyboard.press('F4');pages[1].wait_for_selector('#baccarat[hidden]',state='attached')
  # Offline indicator and blocked command, then authoritative reconnect.
  contexts[1].set_offline(True);pages[1].wait_for_selector('#connection:not([hidden])',timeout=10000);pages[1].keyboard.press('Numpad0');time.sleep(.5)
  assert next(t['round_id'] for t in admin.get('/api/v1/state').json()['tables'] if t['id']==t2['id'])==r2
  contexts[1].set_offline(False);pages[1].keyboard.press('Escape');pages[1].wait_for_selector('#connection[hidden]',state='attached',timeout=15000)
  assert pages[0].url==BASE+'/table/'+t1['id'] and pages[1].url==BASE+'/table/'+t2['id']
  adminctx=browser.new_context();adminpage=adminctx.new_page();adminpage.goto(BASE+'/admin');adminpage.locator('#name').fill('admin');adminpage.locator('#password').fill(Path('/tmp/premier-test-admin-password').read_text());adminpage.locator('#login-form button').click();adminpage.wait_for_selector('a[href="/table/'+t1['id']+'"]');assert adminpage.locator('a[href="/table/'+t1['id']+'"]').inner_text()==BASE+'/table/'+t1['id'];adminctx.close()
  assert not errors,errors
  assert not resource_errors,resource_errors
  browser.close()
 for f in tasks:f.result(timeout=30)
assert len(arrivals)==20,(len(arrivals),failure)
assert len({x[2]['win_id'] for x in arrivals})==1
skew=max(x[1] for x in arrivals)-min(x[1] for x in arrivals)
print(json.dumps({'browser_clients':2,'sse_clients':20,'single_win_id':True,'delivery_spread_ms':round(skew*1000,1),'two_browser_display_spread_ms':display_skew,'same_winner_display':True,'other_round_preserved':True,'actual_baccarat_f4_preserves_round_and_pools':True,'baccarat_input_isolated':True,'winner_over_baccarat_and_return':True,'baccarat_history_preserved':True,'baccarat_offline_input_blocked':True,'offline_block_and_reconnect':True,'admin_kiosk_links':True,'permanent_table_urls':True,'wrong_table_credential_blocked':True,'browser_errors':errors,'static_resource_errors':resource_errors},indent=2))
