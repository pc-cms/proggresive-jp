"""Isolated TEST server only: grouped wins and centrally retained Baccarat history."""
from pathlib import Path
import httpx,uuid,json,time
from playwright.sync_api import sync_playwright,expect
BASE='http://127.0.0.1:8321';c=httpx.Client(base_url=BASE)
r=c.post('/api/v1/login',json={'name':'admin','password':Path('/tmp/premier-test-admin-password').read_text()});r.raise_for_status();c.headers['Authorization']='Bearer '+r.json()['token']
def cmd(op,p):
 r=c.post('/api/v1/commands',json={'command_id':str(uuid.uuid4()),'op':op,'payload':p});r.raise_for_status();return r.json()['result']
t=cmd('table_register',{'number':'OWN-'+uuid.uuid4().hex[:5],'name':'Owner rules test','minimum':5000,'maximum':100000})
code=cmd('pair_create',{'table_id':t['id']})['pairing_code'];token=c.post('/api/v1/pair',json={'code':code,'name':'owner-'+uuid.uuid4().hex,'app_version':'test'}).json()['token']
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox']);ctx=browser.new_context();ctx.add_init_script('localStorage.setItem("premier-device-token",'+json.dumps(token)+')');page=ctx.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto(BASE+'/table/'+t['id']);page.wait_for_selector('#connection[hidden]',state='attached')
 for key in ['Numpad1','Numpad2','Numpad3','NumpadEnter']:page.keyboard.press(key)
 page.wait_for_selector('.box.on');page.keyboard.press('NumpadMultiply')
 for key in ['Numpad1','Numpad2','NumpadEnter','Numpad1','NumpadEnter','Numpad2','NumpadEnter','NumpadEnter']:page.keyboard.press(key)
 page.wait_for_selector('#service:not([open])',state='attached');current=c.get('/api/v1/state').json();claims=[x for x in current['claims'] if x['table_id']==t['id']]
 assert len(claims)==2 and {x['box'] for x in claims}=={1,2}
 assert all(x['status']=='approved' and x['amount']==25000 for x in claims)
 # Close a completed payout round before entering a separate Baccarat result.
 cmd('close',{'table_id':t['id'],'round_id':next(x['round_id'] for x in current['tables'] if x['id']==t['id'])})
 # Wait out the announcement queue; it intentionally blocks local Baccarat input.
 page.wait_for_selector('#winner:not([hidden])',timeout=5000);page.wait_for_selector('#winner[hidden]',state='attached',timeout=35000)
 page.keyboard.press('F4');page.wait_for_selector('#baccarat:not([hidden])');frame=page.frame_locator('#baccarat');expect(frame.locator('#localLabel')).to_have_text('SERVER DISPLAY')
 frame.locator('body').click(position={'x':10,'y':10});page.keyboard.press('Numpad1');expect(frame.locator('#playerCount')).to_have_text('1')
 cmd('table_update',{'table_id':t['id'],'minimum':10000});expect(frame.locator('#minimum')).to_have_text('10,000')
 page.keyboard.press('Numpad2');expect(frame.locator('#bankerCount')).to_have_text('1')
 state=c.get('/api/v1/state').json();history=next(x['baccarat'] for x in state['tables'] if x['id']==t['id']);assert [x['limits']['minimum'] for x in history['hands']]==[5000,10000]
 page.reload();page.wait_for_selector('#connection[hidden]',state='attached');expect(page.frame_locator('#baccarat').locator('#playerCount')).to_have_text('1');expect(page.frame_locator('#baccarat').locator('#bankerCount')).to_have_text('1')
 assert not errors,errors;browser.close()
print(json.dumps({'grouped_winning_boxes':[1,2],'one_award_per_box':True,'baccarat_server_history':True,'history_survives_reload':True,'historical_limits_preserved':True,'browser_errors':errors},indent=2))
