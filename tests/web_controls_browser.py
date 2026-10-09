"""Isolated TEST server: mouse-only controls use the normal authenticated commands."""
from pathlib import Path
import httpx,uuid,json
from playwright.sync_api import sync_playwright,expect
BASE='http://127.0.0.1:8321';c=httpx.Client(base_url=BASE)
r=c.post('/api/v1/login',json={'name':'admin','password':Path('/tmp/premier-test-admin-password').read_text()});r.raise_for_status();c.headers['Authorization']='Bearer '+r.json()['token']
def cmd(op,p):
 r=c.post('/api/v1/commands',json={'command_id':str(uuid.uuid4()),'op':op,'payload':p});r.raise_for_status();return r.json()['result']
def register(game):
 t=cmd('table_register',{'number':'WEB-'+uuid.uuid4().hex[:5],'name':'Browser test '+game,'game':game});code=cmd('pair_create',{'table_id':t['id']})['pairing_code']
 r=c.post('/api/v1/pair',json={'code':code,'name':'web-'+uuid.uuid4().hex,'app_version':'test'});r.raise_for_status();return t,r.json()['token']
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox']);errors=[]
 def open_table(game):
  t,token=register(game);ctx=browser.new_context();ctx.add_init_script('localStorage.setItem("premier-device-token",'+json.dumps(token)+')');page=ctx.new_page();page.on('pageerror',lambda e:errors.append(str(e)));page.goto(BASE+'/table/'+t['id']+'?test_controls=1');page.wait_for_selector('#connection[hidden]',state='attached',timeout=20000);page.locator('.web-test-controls>button').click();return ctx,page,t
 def press(page,code):page.locator('[data-test-key="'+code+'"]').click()
 bc,bp,bt=open_table('baccarat');frame=bp.frame_locator('#baccarat');frame.locator('#playerCount').wait_for();before=c.get('/api/v1/state').json()['pools'];press(bp,'Numpad1');expect(frame.locator('#playerCount')).to_have_text('1');assert c.get('/api/v1/state').json()['pools']==before
 press(bp,'F4');bp.wait_for_selector('#baccarat[hidden]',state='attached');press(bp,'F4');bp.wait_for_selector('#baccarat:not([hidden])');expect(frame.locator('#playerCount')).to_have_text('1');bc.close()
 ctx,page,t=open_table('poker')
 for key in ['Numpad1','Numpad3','NumpadEnter']:press(page,key)
 expect(page.locator('.box.on')).to_have_count(2)
 press(page,'Numpad0');expect(page.locator('.box.on')).to_have_count(0)
 for key in ['Numpad1','Numpad3','NumpadEnter']:press(page,key)
 expect(page.locator('.box.on')).to_have_count(2);press(page,'claim');expect(page.locator('#service')).to_be_visible()
 assert page.locator('#service .web-test-controls').count()==1
 for key in ['Numpad1','Numpad3','NumpadEnter','Numpad1','NumpadEnter','Numpad2','NumpadEnter','NumpadEnter']:press(page,key)
 page.wait_for_selector('#service:not([open])',state='attached');state=c.get('/api/v1/state').json();claims=[x for x in state['claims'] if x['table_id']==t['id']];assert {x['box'] for x in claims}=={1,3};assert all(x['amount']==25000 for x in claims)
 normal=browser.new_context();np=normal.new_page();np.goto(BASE+'/table/'+t['id']);np.wait_for_selector('#service[open]');assert np.locator('.web-test-controls').count()==0;normal.close()
 ctx.set_offline(True);page.wait_for_selector('#connection:not([hidden])');press(page,'Numpad0');expect(page.locator('#service')).to_be_visible();assert next(x['round_id'] for x in c.get('/api/v1/state').json()['tables'] if x['id']==t['id']) is not None
 assert not errors,errors;browser.close()
print(json.dumps({'mouse_only_progressive':True,'multiple_winning_boxes':[1,3],'controls_inside_dialog':True,'mouse_only_baccarat':True,'mode_switch_preserves_history':True,'no_controls_on_normal_kiosk':True,'offline_blocks_commands':True,'browser_errors':errors},indent=2))
