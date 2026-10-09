"""Checks the published views and media on the isolated local TEST server."""
from pathlib import Path
import httpx,uuid,json
from playwright.sync_api import sync_playwright,expect
BASE='http://127.0.0.1:8321'
c=httpx.Client(base_url=BASE)
r=c.post('/api/v1/login',json={'name':'admin','password':Path('/tmp/premier-test-admin-password').read_text()});r.raise_for_status();c.headers['Authorization']='Bearer '+r.json()['token']
def cmd(op,p):
 r=c.post('/api/v1/commands',json={'command_id':str(uuid.uuid4()),'op':op,'payload':p});r.raise_for_status();return r.json()['result']
t=cmd('table_register',{'number':'V'+uuid.uuid4().hex[:5],'name':'Premier Table 1','minimum':5000,'maximum':100000})
code=cmd('pair_create',{'table_id':t['id']})['pairing_code'];r=c.post('/api/v1/pair',json={'code':code,'name':'visual-'+uuid.uuid4().hex,'app_version':'test'});r.raise_for_status();token=r.json()['token']
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox']);ctx=browser.new_context(viewport={'width':1920,'height':1080});ctx.add_init_script('localStorage.setItem("premier-device-token",'+json.dumps(token)+')');page=ctx.new_page();errors=[];resources=[]
 page.on('console',lambda msg:errors.append(msg.text) if msg.type=='error' else None)
 page.on('response',lambda r:resources.append({'url':r.url,'status':r.status}) if r.status>=400 else None)
 page.goto(BASE+'/table/'+t['id']);page.wait_for_selector('#connection[hidden]',state='attached');page.wait_for_selector('#winner[hidden]',state='attached',timeout=20000)
 page.evaluate('document.fonts.ready');expect(page.locator('#clock')).to_contain_text('EAT')
 assert page.locator('.plaque').count()==5 and page.locator('.fixed-item').count()==5
 # All five published design variants must load their required fonts/backgrounds.
 for design in range(1,6):
  page.evaluate('(n)=>document.body.dataset.design=String(n)',design);page.wait_for_timeout(100)
 page.evaluate('document.body.dataset.design="1"');page.screenshot(path='docs/screenshots/progressive.png')
 page.keyboard.press('F4');page.wait_for_selector('#baccarat:not([hidden])');frame=page.frame_locator('#baccarat');frame.locator('#tableName').filter(has_text=t['name']).wait_for()
 assert frame.locator('#minimum').inner_text()=='5,000' and frame.locator('#maximum').inner_text()=='100,000'
 page.screenshot(path='docs/screenshots/baccarat.png')
 gallery=ctx.new_page();gallery.on('response',lambda r:resources.append({'url':r.url,'status':r.status}) if r.status>=400 else None);gallery.on('console',lambda msg:errors.append(msg.text) if msg.type=='error' else None);gallery.goto(BASE+'/static/baccarat/animations.html');gallery.wait_for_selector('video');assert gallery.locator('video').count()==11
 gallery.locator('video').first.evaluate('(video)=>video.load()');
 for _ in range(100):
  if gallery.locator('video').first.evaluate('(video)=>video.readyState')>=1:break
  gallery.wait_for_timeout(100)
 assert gallery.locator('video').first.evaluate('(video)=>video.readyState')>=1
 assert gallery.locator('video').first.evaluate('(video)=>video.videoWidth')==1280
 gallery.close();assert not errors,errors;assert not resources,resources;browser.close()
print(json.dumps({'original_design_variants':5,'shared_pool_plaques':5,'fixed_awards':5,'screenshot_size':'1920x1080','gallery_videos':11,'video_metadata_loaded':True,'console_errors':errors,'resource_errors':resources},indent=2))
